# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the FoodAI project containing a nutrition video analysis system. The main codebase is in the `-nutrition-video-analysis/` subdirectory.

## Commands

### Installation & Setup
```bash
# Navigate to main project
cd -nutrition-video-analysis

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
cd -nutrition-video-analysis/deploy && python run_local.py

# Build and run with Docker
cd -nutrition-video-analysis/deploy && docker-compose build && docker-compose up -d

# View Docker logs
cd -nutrition-video-analysis/deploy && docker-compose logs -f nutrition-api

# Test RAG system only
python -nutrition-video-analysis/test_rag_only.py

# Test full tracking pipeline
python -nutrition-video-analysis/test_tracking_metric3d.py
```

### Terraform Infrastructure
```bash
cd -nutrition-video-analysis/terraform
terraform init
terraform plan
terraform apply

# Build and push Docker image for ECS
cd docker && ./build-and-push.sh
```

### AWS Infrastructure Commands
```bash
# Test API endpoints
curl https://qx3i66fa87.execute-api.us-east-1.amazonaws.com/v1/health
curl -X POST https://qx3i66fa87.execute-api.us-east-1.amazonaws.com/v1/api/upload \
  -H "Content-Type: application/json" \
  -d '{"type": "presigned", "filename": "test.mp4"}'

# Check ECS service status
aws ecs describe-services --cluster nutrition-video-analysis-dev-cluster \
  --services nutrition-video-analysis-dev-video-processor

# View ECS logs
aws logs tail /ecs/nutrition-video-analysis-dev-video-processor --follow

# Force ECS service update after Docker push
aws ecs update-service --cluster nutrition-video-analysis-dev-cluster \
  --service nutrition-video-analysis-dev-video-processor --force-new-deployment
```

## Architecture

AI-powered nutrition analysis system that processes food videos to estimate caloric content using multiple computer vision models.

### Pipeline Flow
1. **Video Processing**: Extract frames with configurable skip rates
2. **Object Detection**: Florence-2 detects food items in key frames
3. **Object Tracking**: SAM2 maintains consistent object IDs across video frames
4. **Depth Estimation**: Metric3D provides absolute depth measurements in meters
5. **Volume Calculation**: Combine depth maps with segmentation masks for 3D volume
6. **Nutrition Lookup**: RAG system queries FAISS-indexed nutrition databases (FNDDS, CoFID)
7. **Results**: Return per-item nutrition estimates and meal summaries

### Key Components

**API Server** (`-nutrition-video-analysis/deploy/app/`):
- `api.py`: FastAPI REST endpoints for video upload and result retrieval
- `pipeline.py`: Main processing orchestrator that coordinates all models
- `models.py`: Model loading and management with memory optimization
- `config.py`: Environment-based configuration management
- `database.py`: SQLite job tracking and status management

**Core Models**:
- **Florence-2**: Microsoft's vision foundation model for food object detection
- **SAM2**: Meta's segmentation model for precise object tracking (`sam2/` directory)
- **Grounding DINO**: Alternative detection model (`grounding_dino/` directory)
- **Metric3D**: Depth estimation model providing absolute depth in meters

**Nutrition RAG** (`-nutrition-video-analysis/nutrition_rag_system.py`):
- Indexes FNDDS and CoFID nutrition databases using FAISS
- Semantic search for food density and calorie information
- Fallback to Gemini API for unknown foods

**Terraform Infrastructure** (`-nutrition-video-analysis/terraform/`):
- Serverless AWS architecture: API Gateway → Lambda → ECS Fargate → S3/DynamoDB
- S3 buckets: `videos`, `results`, `models` (KMS encrypted)
- DynamoDB: `nutrition-video-analysis-dev-jobs` for job tracking
- SQS: `video-processing` queue triggers ECS auto-scaling (0→5 tasks)
- ECR: `nutrition-video-analysis-dev-video-processor` repository
- ECS: Fargate Spot cluster with 4 vCPU, 16GB RAM per task

**API Endpoints** (Base: `https://qx3i66fa87.execute-api.us-east-1.amazonaws.com/v1`):
- `GET /health` - Health check
- `POST /api/upload` - Get presigned URL or confirm upload
- `GET /api/status/{job_id}` - Check job status
- `GET /api/results/{job_id}` - Get nutrition results

### Volume to Nutrition Calculation
```
volume_ml = surface_area_cm² × average_height_cm
mass_g = volume_ml × food_density_g/ml
calories = (mass_g / 100) × calories_per_100g_from_database
```

## Configuration

Environment variables in `-nutrition-video-analysis/deploy/.env`:
- `GEMINI_API_KEY`: Required for nutrition fallback queries
- `DEVICE`: "cuda" or "cpu" for model inference
- `MAX_FRAMES`: Maximum frames to process per video (default: 60)
- `FRAME_SKIP`: Skip rate for frame extraction (default: 10)
- `DETECTION_INTERVAL`: Frames between detection runs (default: 30)

## Code Style

For SAM2 contributions, use `ufmt format` for linting (requires `black==24.2.0`, `usort==1.0.2`, `ufmt==2.0.0b2`).
