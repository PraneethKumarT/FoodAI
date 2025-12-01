
# Nutrition Video Analysis API - Deployment Guide

**🔗 GitHub Repository**: https://github.com/leolorence12345/-nutrition-video-analysis

Production-ready REST API for automated food recognition and calorie estimation from videos.

## 🚀 Live Production Deployment

**🌐 API**: http://18.214.98.110:8000  
**📚 Interactive Docs**: http://18.214.98.110:8000/docs  
**❤️ Health Check**: http://18.214.98.110:8000/health

**Current Instance**: AWS EC2 t3.xlarge (CPU-only, for testing)  
**Status**: ✅ Running  
**Deployed From**: GitHub (leolorence12345/-nutrition-video-analysis)

> **⚠️ Note**: Current t3 instance is for API testing only. Full AI pipeline (Florence-2, SAM2, Metric3D) requires GPU instance (g4dn.xlarge recommended).

## 🏗️ Architecture

```
User → FastAPI → [Florence-2] → [SAM2] → [Metric3D] → [RAG] → Results
                     ↓              ↓          ↓           ↓
                 Detection    Tracking    Depth    Nutrition DB
```

## 📋 Prerequisites

- **GPU**: NVIDIA GPU with CUDA 11.8+ (8GB+ VRAM recommended)
- **Docker**: Docker 20.10+ with nvidia-docker2
- **RAM**: 16GB+ recommended
- **Storage**: 50GB+ for models and data

## 🚀 Quick Start

### 1. Prepare Environment

```bash
# Navigate to deploy directory
cd deploy

# Copy environment template
cp env.example .env

# Edit .env with your configuration
nano .env  # Add your GEMINI_API_KEY
```

### 2. Build and Run

```bash
# Build Docker image
docker-compose build

# Start API service
docker-compose up -d

# Check logs
docker-compose logs -f nutrition-api
```

### 3. Test API

```bash
# Health check
curl http://localhost:8000/health

# Upload video
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@/path/to/video.mp4"

# Get status (use job_id from upload response)
curl http://localhost:8000/api/status/{job_id}

# Get results
curl http://localhost:8000/api/results/{job_id}
```

## 📁 Project Structure

```
deploy/
├── app/
│   ├── config.py          # Configuration management
│   ├── models.py          # Model loading & caching
│   ├── pipeline.py        # Main processing pipeline
│   ├── api.py             # FastAPI endpoints
│   └── database.py        # Job tracking database
├── data/
│   ├── uploads/           # Uploaded videos
│   ├── outputs/           # Processing results
│   └── rag/              # Nutrition databases
├── Dockerfile            # Container definition
├── docker-compose.yml    # Service orchestration
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🔧 Configuration

All settings are controlled via environment variables in `.env`:

### Essential Settings

```env
# Required: Gemini API key for calorie fallback
GEMINI_API_KEY=your-key-here

# GPU device (cuda or cpu)
DEVICE=cuda

# Video processing
MAX_VIDEO_SIZE_MB=500
FRAME_SKIP=10
MAX_FRAMES=60
```

### Advanced Settings

See `env.example` for all available options including:
- Database configuration (SQLite/PostgreSQL)
- Model paths and variants
- Tracking parameters
- Security settings

## 🎯 API Endpoints

### POST `/api/upload`
Upload a video for analysis
```bash
curl -X POST -F "file=@video.mp4" http://localhost:8000/api/upload
```

Response:
```json
{
  "job_id": "abc-123",
  "status": "processing",
  "message": "Video uploaded successfully"
}
```

### GET `/api/status/{job_id}`
Check processing status
```bash
curl http://localhost:8000/api/status/abc-123
```

### GET `/api/results/{job_id}`
Get nutrition analysis results
```bash
curl http://localhost:8000/api/results/abc-123?detailed=true
```

Response:
```json
{
  "job_id": "abc-123",
  "status": "completed",
  "nutrition_summary": {
    "total_calories_kcal": 650,
    "total_mass_g": 425,
    "num_food_items": 3
  },
  "detailed_results": {...}
}
```

### GET `/api/download/{job_id}`
Download full results as JSON

### DELETE `/api/jobs/{job_id}`
Delete job and associated files

## 🐳 Docker Commands

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart
docker-compose restart

# Access container shell
docker-compose exec nutrition-api bash

# Clean up everything
docker-compose down -v
```

## ☁️ Cloud Deployment

### AWS EC2 with GPU

1. **Launch Instance**
   ```bash
   # Instance type: g4dn.xlarge (T4 GPU, $0.52/hr)
   # AMI: Deep Learning AMI (Ubuntu 22.04)
   # Storage: 100GB+ EBS
   ```

2. **Install Docker & nvidia-docker**
   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   
   # Install nvidia-docker
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
     sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   
   sudo apt-get update
   sudo apt-get install -y nvidia-docker2
   sudo systemctl restart docker
   ```

3. **Deploy Application**
   ```bash
   git clone <your-repo>
   cd deploy
   cp env.example .env
   # Edit .env with production values
   docker-compose up -d
   ```

4. **Setup NGINX (optional)**
   ```bash
   sudo apt-get install nginx
   # Configure reverse proxy
   ```

### Google Cloud Platform

```bash
# Create instance with GPU
gcloud compute instances create nutrition-api \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --boot-disk-size=100GB

# SSH and deploy
gcloud compute ssh nutrition-api
```

### Kubernetes

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nutrition-api
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: api
        image: your-registry/nutrition-api:latest
        resources:
          limits:
            nvidia.com/gpu: 1
        ports:
        - containerPort: 8000
```

## 📊 Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# GPU status
docker-compose exec nutrition-api nvidia-smi
```

### Logs

```bash
# Real-time logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Specific service
docker-compose logs nutrition-api
```

### Metrics (Optional)

Add Prometheus monitoring:
```yaml
# In docker-compose.yml
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

## 🔒 Security Checklist

- [ ] Set strong `API_KEY` in production
- [ ] Enable `REQUIRE_API_KEY=True`
- [ ] Restrict `CORS_ORIGINS` to your domain
- [ ] Use HTTPS (setup SSL certificate)
- [ ] Enable firewall rules (only port 443/80)
- [ ] Rotate Gemini API key regularly
- [ ] Setup automated backups for database
- [ ] Use secrets manager for sensitive data

## 🐛 Troubleshooting

### GPU Not Detected
```bash
# Test GPU in container
docker run --rm --gpus all nvidia/cuda:11.8.0-base nvidia-smi

# Check nvidia-docker
sudo systemctl status nvidia-docker
```

### Out of Memory
- Reduce `BATCH_SIZE` in .env
- Reduce `MAX_FRAMES` to process fewer frames
- Increase `FRAME_SKIP` to skip more frames
- Use smaller model: `SAM2_CHECKPOINT=sam2.1_hiera_small.pt`

### Slow Processing
- Check GPU utilization: `nvidia-smi`
- Enable FP16: `USE_FP16=True`
- Reduce video resolution: `RESIZE_WIDTH=640`

### Model Download Failures
```bash
# Manually download models
docker-compose exec nutrition-api python3 -c "
from transformers import AutoModel
AutoModel.from_pretrained('microsoft/Florence-2-base-ft')
"
```

## 📈 Performance Optimization

### For Speed
- Use FP16: `USE_FP16=True`
- Skip frames: `FRAME_SKIP=15`
- Reduce resolution: `RESIZE_WIDTH=640`
- Use smaller models: `metric3d_vit_small`

### For Accuracy
- Process more frames: `FRAME_SKIP=5`
- Higher resolution: `RESIZE_WIDTH=1024`
- Larger models: `SAM2_CHECKPOINT=sam2.1_hiera_large.pt`

## 💰 Cost Estimation

### AWS g4dn.xlarge (T4 GPU)
- **Instance**: $0.52/hour
- **Storage**: $0.10/GB/month
- **Transfer**: $0.09/GB

**Monthly estimate (1000 videos/day):**
- Compute (8hrs/day): ~$125
- Storage (100GB): $10
- **Total**: ~$135/month

### Auto-scaling
```bash
# Scale down when queue is empty
docker-compose scale nutrition-api=0

# Scale up during peak hours
docker-compose scale nutrition-api=3
```

## 📝 License & Attribution

This deployment uses:
- **SAM2**: Meta's Segment Anything Model 2
- **Florence-2**: Microsoft's vision foundation model
- **Metric3D**: Depth estimation model
- **FastAPI**: Modern web framework

## 🤝 Support

For issues and questions:
1. Check logs: `docker-compose logs`
2. Review troubleshooting section above
3. Open GitHub issue with logs and configuration

## 🎯 Next Steps

1. ✅ Deploy to cloud (AWS/GCP)
2. ✅ Setup monitoring (Prometheus/Grafana)
3. ✅ Implement caching (Redis)
4. ✅ Add authentication (JWT)
5. ✅ Create web dashboard
6. ✅ Mobile app integration
7. ✅ A/B testing framework
8. ✅ Export to PDF reports

