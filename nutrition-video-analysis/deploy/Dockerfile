# Production Dockerfile for Nutrition Video Analysis API
# Multi-stage build for optimized image size

FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip

# Install PyTorch with CUDA support
RUN pip3 install --no-cache-dir \
    torch==2.1.0 \
    torchvision==0.16.0 \
    --index-url https://download.pytorch.org/whl/cu118

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/data/uploads \
    /app/data/outputs \
    /app/data/rag \
    /app/models \
    /app/checkpoints \
    /app/configs

# Copy application code
COPY app/ /app/app/

# Copy parent directory files (SAM2, nutrition_rag_system.py, etc.)
# Note: During build, mount parent directory or copy required files
COPY ../sam2 /app/sam2
COPY ../nutrition_rag_system.py /app/
COPY ../checkpoints /app/checkpoints
COPY ../configs /app/configs

# Copy RAG data
COPY ../rag /app/data/rag

# Set Python path
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run API server
CMD ["python3", "-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]

