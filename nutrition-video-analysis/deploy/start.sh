#!/bin/bash
# Startup script for Nutrition Video Analysis API

set -e

echo "=================================================="
echo "Nutrition Video Analysis API - Startup"
echo "=================================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "   Copy env.example to .env and configure:"
    echo "   cp env.example .env"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "   Please start Docker and try again"
    exit 1
fi

# Check for GPU
if command -v nvidia-smi &> /dev/null; then
    echo "✅ GPU detected:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
else
    echo "⚠️  No GPU detected - will run on CPU (slower)"
fi

# Build Docker image
echo ""
echo "Building Docker image..."
docker-compose build

# Start services
echo ""
echo "Starting services..."
docker-compose up -d

# Wait for API to be ready
echo ""
echo "Waiting for API to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API is ready!"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   Attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ API failed to start!"
    echo "   Check logs with: docker-compose logs"
    exit 1
fi

# Display status
echo ""
echo "=================================================="
echo "✅ Nutrition Video Analysis API is running!"
echo "=================================================="
echo ""
echo "API Endpoint:  http://localhost:8000"
echo "Documentation: http://localhost:8000/docs"
echo "Health Check:  http://localhost:8000/health"
echo ""
echo "Useful commands:"
echo "  • View logs:    docker-compose logs -f"
echo "  • Stop API:     docker-compose down"
echo "  • Restart:      docker-compose restart"
echo ""
echo "Test the API:"
echo '  curl -X POST "http://localhost:8000/api/upload" \'
echo '    -F "file=@your_video.mp4"'
echo ""
echo "=================================================="

