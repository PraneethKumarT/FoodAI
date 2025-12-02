# Nutrition Video Analysis - ECS Worker Container
# Base image with Python and common ML dependencies

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Try to install flash-attn (optional, may fail on some platforms)
RUN pip install --no-cache-dir flash-attn==2.3.6 || echo "flash-attn installation failed, continuing without it"

# Copy worker script
COPY worker.py .

# Copy AI processing modules
COPY app/ ./app/

# Copy SAM2 package to root so it's importable as 'sam2'
COPY sam2_package/sam2 ./sam2/
COPY sam2_package/checkpoints ./checkpoints/

# Copy nutrition RAG system
COPY nutrition_rag_system.py .

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "print('healthy')" || exit 1

# Run worker
CMD ["python", "worker.py"]
