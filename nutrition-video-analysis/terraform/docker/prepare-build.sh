#!/bin/bash
# Prepare Docker build context with AI processing code

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.."

echo "Preparing Docker build context..."

# Copy AI processing modules from deploy/app
echo "Copying app modules..."
rm -rf "$SCRIPT_DIR/app"
cp -r "$PROJECT_ROOT/deploy/app" "$SCRIPT_DIR/"

# Copy SAM2 package
echo "Copying SAM2..."
rm -rf "$SCRIPT_DIR/sam2_package"
mkdir -p "$SCRIPT_DIR/sam2_package"
if [ -d "$PROJECT_ROOT/sam2" ]; then
    cp -r "$PROJECT_ROOT/sam2" "$SCRIPT_DIR/sam2_package/"
    cp -r "$PROJECT_ROOT/checkpoints" "$SCRIPT_DIR/sam2_package/" 2>/dev/null || echo "Checkpoints not found, will download at runtime"
fi

# Copy nutrition RAG system
echo "Copying nutrition RAG system..."
if [ -f "$PROJECT_ROOT/nutrition_rag_system.py" ]; then
    cp "$PROJECT_ROOT/nutrition_rag_system.py" "$SCRIPT_DIR/"
fi

# Copy nutrition databases
echo "Copying nutrition databases..."
if [ -d "$PROJECT_ROOT/nutrition_databases" ]; then
    cp -r "$PROJECT_ROOT/nutrition_databases" "$SCRIPT_DIR/app/" 2>/dev/null || echo "Nutrition databases not found"
fi

# Copy Grounding DINO if needed
if [ -d "$PROJECT_ROOT/grounding_dino" ]; then
    echo "Copying Grounding DINO..."
    cp -r "$PROJECT_ROOT/grounding_dino" "$SCRIPT_DIR/app/"
fi

echo "Build context prepared successfully!"
echo "Ready to build Docker image."
