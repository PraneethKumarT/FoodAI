# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Installation & Setup
```bash
# Download model checkpoints (required)
cd checkpoints && bash download_ckpts.sh && cd ..
cd gdino_checkpoints && bash download_ckpts.sh && cd ..

# Install SAM2 package
pip install -e .

# Install API dependencies
pip install -r deploy/requirements.txt

# Set up environment for API
cd deploy && cp env.example .env
# Edit .env with GEMINI_API_KEY
```

### Development & Testing
```bash
# Run local API server
cd deploy && python run_local.py

# Build Docker image
cd deploy && docker-compose build

# Run with Docker
cd deploy && docker-compose up -d

# View Docker logs
cd deploy && docker-compose logs -f nutrition-api

# Test RAG system only
python test_rag_only.py

# Test full tracking pipeline
python test_tracking_metric3d.py
```

### Docker Operations
```bash
# Build with CUDA support (uses Makefile)
make build-image

# Run container with GPU access
make run

# Stop services
cd deploy && docker-compose down
```

## Architecture

This is an AI-powered nutrition analysis system that processes food videos to estimate caloric content. The system combines multiple state-of-the-art models:

### Core Pipeline Flow
1. **Video Processing**: Extract frames with configurable skip rates
2. **Object Detection**: Florence-2 detects food items in key frames
3. **Object Tracking**: SAM2 maintains consistent object IDs across video frames  
4. **Depth Estimation**: Metric3D provides absolute depth measurements in meters
5. **Volume Calculation**: Combine depth maps with segmentation masks for 3D volume
6. **Nutrition Lookup**: RAG system queries FAISS-indexed nutrition databases
7. **Results**: Return per-item nutrition estimates and meal summaries

### Key Components

**API Server** (`deploy/app/`):
- `api.py`: FastAPI REST endpoints for video upload and result retrieval
- `pipeline.py`: Main processing orchestrator that coordinates all models
- `models.py`: Model loading and management with memory optimization
- `config.py`: Environment-based configuration management
- `database.py`: SQLite job tracking and status management

**Core Models**:
- **Florence-2**: Microsoft's vision foundation model for food object detection
- **SAM2**: Meta's segmentation model for precise object tracking across frames
- **Metric3D**: Depth estimation model providing absolute depth in meters
- **RAG System**: FAISS + sentence transformers for nutrition database search

**Nutrition RAG** (`nutrition_rag_system.py`):
- Indexes FNDDS and CoFID nutrition databases using FAISS
- Semantic search for food density and calorie information
- Fallback to Gemini API for unknown foods

**Data Sources** (`rag/`):
- `FNDDS.xlsx`: USDA Food and Nutrient Database for Dietary Studies
- `CoFID.xlsx`: Comprehensive Food Item Database
- `ap815e.pdf`: Food density reference tables

### Object-Specific Constraints
The system applies geometric validation based on food type:
- **Plates**: 1-3cm height limit
- **Utensils**: 0.5-2cm height limit  
- **Glasses**: 5-15cm height range
- **Food items**: 1-10cm height range

### Volume to Nutrition Calculation
```
volume_ml = surface_area_cm² × average_height_cm
mass_g = volume_ml × food_density_g/ml
calories = (mass_g / 100) × calories_per_100g_from_database
```

## Configuration

Environment variables in `deploy/.env`:
- `GEMINI_API_KEY`: Required for nutrition fallback queries
- `DEVICE`: "cuda" or "cpu" for model inference
- `MAX_FRAMES`: Maximum frames to process per video (default: 60)
- `FRAME_SKIP`: Skip rate for frame extraction (default: 10)
- `DETECTION_INTERVAL`: Frames between detection runs (default: 30)

## Model Management

Models are automatically downloaded to `checkpoints/` and `gdino_checkpoints/` directories. The system supports multiple SAM2 variants:
- `sam2.1_hiera_small.pt`: Fastest, lower accuracy
- `sam2.1_hiera_base.pt`: Balanced (default)
- `sam2.1_hiera_large.pt`: Highest accuracy, slower

## Development Notes

- No formal test framework is configured; use the provided test scripts
- Development tools (black, pytest, flake8) are commented out in requirements.txt
- The system can run CPU-only but requires GPU for reasonable performance
- FAISS CPU version is used by default; switch to faiss-gpu for better performance
- API supports both local and Docker deployment modes