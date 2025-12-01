# 🍽️ Nutrition Video Analysis API

AI-powered nutrition estimation from food videos using Florence-2, SAM2, Metric3D, and RAG.

## 🎯 Features

- **Object Detection**: Florence-2 for food item detection
- **Video Tracking**: SAM2 for continuous object tracking across frames
- **Depth Estimation**: Metric3D for absolute depth measurements
- **Volume Calculation**: 3D volume estimation with object-specific constraints
- **Nutrition Analysis**: RAG system using FAISS + LLM for calorie/density lookup
- **Production API**: FastAPI with async processing and Docker support

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- CUDA 11.8+ (for GPU)
- Docker (optional)

### Installation

```bash
# Clone repository
git clone <your-repo-url>
cd Grounded-SAM-2

# Download model checkpoints
cd checkpoints && bash download_ckpts.sh && cd ..
cd gdino_checkpoints && bash download_ckpts.sh && cd ..

# Install dependencies
pip install -r deploy/requirements.txt

# Install SAM2
pip install -e .

# Set up environment
cd deploy
cp env.example .env
# Edit .env with your GEMINI_API_KEY
```

### Run Locally

```bash
cd deploy
python run_local.py
```

API will be available at `http://localhost:8000`

### Run with Docker

```bash
cd deploy
docker-compose up --build
```

## 📚 API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Main Endpoints

- `POST /api/v1/analyze` - Upload video for analysis
- `GET /api/v1/status/{job_id}` - Check job status
- `GET /api/v1/results/{job_id}` - Get analysis results
- `GET /health` - Health check

## 🏗️ Project Structure

```
Grounded-SAM-2/
├── deploy/              # Production API
│   ├── app/
│   │   ├── api.py      # FastAPI app
│   │   ├── config.py   # Configuration
│   │   ├── models.py   # Model management
│   │   ├── pipeline.py # Processing pipeline
│   │   └── database.py # Job tracking
│   ├── Dockerfile
│   └── requirements.txt
├── sam2/                # SAM2 model
├── grounding_dino/      # Grounding DINO
├── nutrition_rag_system.py  # RAG system
├── rag/                 # Nutrition databases
│   ├── ap815e.pdf
│   ├── FNDDS.xlsx
│   └── CoFID.xlsx
└── checkpoints/         # Model weights (not in repo)
```

## ⚙️ Configuration

Edit `deploy/.env`:

```env
GEMINI_API_KEY=your_key_here
DEVICE=cuda  # or 'cpu'
MAX_FRAMES=60
FRAME_SKIP=10
DETECTION_INTERVAL=30
```

## 🧪 Testing

```bash
# Test RAG system
python test_rag_only.py

# Test full pipeline
python test_tracking_metric3d.py
```

## 📦 Deployment

See [deploy/ROADMAP.md](deploy/ROADMAP.md) for:
- AWS deployment
- GPU instance setup
- Production checklist

## 🔬 Technical Details

### Pipeline Flow

1. **Video Loading**: Extract frames with configurable skip rate
2. **Detection**: Florence-2 detects food items periodically
3. **Tracking**: SAM2 maintains object IDs across frames
4. **Depth**: Metric3D estimates absolute depth in meters
5. **Volume**: Calculate 3D volume using depth + masks
6. **Nutrition**: RAG retrieves density/calories from databases
7. **Results**: Return per-item nutrition + meal summary

### Object-Specific Constraints

The system applies geometric constraints based on food type:
- **Plates**: 1-3cm height
- **Utensils**: 0.5-2cm height
- **Glasses**: 5-15cm height
- **Food items**: 1-10cm height

### Volume Calculation

```
volume_ml = surface_area_cm² × height_cm
mass_g = volume_ml × density_g/ml
calories = (mass_g / 100) × calories_per_100g
```

## 🎓 Citation

If you use this work, please cite:

```bibtex
@misc{nutrition-video-analysis,
  title={AI-Powered Nutrition Estimation from Food Videos},
  author={Your Name},
  year={2025},
  howpublished={\url{https://github.com/yourusername/repo}}
}
```

## 📄 License

See LICENSE files for SAM2, Grounding DINO, and this project.

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md)

## 📞 Contact

- Email: your.email@example.com
- Issues: https://github.com/yourusername/repo/issues

---

**Note**: Model checkpoints are not included in the repository due to size.
Download them using the provided scripts in `checkpoints/` and `gdino_checkpoints/`.

