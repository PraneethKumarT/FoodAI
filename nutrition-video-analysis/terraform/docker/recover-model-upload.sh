#!/bin/bash
# Recovery script to upload existing files and retry failed downloads
set -x  # Debug output but don't exit on error

echo "=== Model Upload Recovery Script Started at $(date) ==="

# Configuration
REGION="us-east-1"
S3_BUCKET="nutrition-video-analysis-dev-models-60ppnqfp"
MARKER_BUCKET="nutrition-video-analysis-dev-videos-60ppnqfp"

# Ensure directories exist
mkdir -p /tmp/checkpoints
mkdir -p /tmp/gdino_checkpoints

# Upload any existing SAM2 files first
echo "=== Uploading existing SAM2 checkpoints to S3 ==="
if [ "$(ls -A /tmp/checkpoints 2>/dev/null)" ]; then
    aws s3 cp /tmp/checkpoints/ s3://${S3_BUCKET}/checkpoints/ --recursive --region ${REGION}
    echo "Uploaded existing SAM2 files"
else
    echo "No existing SAM2 files to upload"
fi

# Upload any existing Grounding DINO files
echo "=== Uploading existing Grounding DINO checkpoints to S3 ==="
if [ "$(ls -A /tmp/gdino_checkpoints 2>/dev/null)" ]; then
    aws s3 cp /tmp/gdino_checkpoints/ s3://${S3_BUCKET}/gdino_checkpoints/ --recursive --region ${REGION}
    echo "Uploaded existing Grounding DINO files"
else
    echo "No existing Grounding DINO files to upload"
fi

cd /tmp

# Download missing SAM2.1 checkpoints with retry
echo "=== Downloading missing SAM2.1 checkpoints ===\"
SAM2p1_BASE_URL="https://dl.fbaipublicfiles.com/segment_anything_2/092824"

for model in sam2.1_hiera_tiny.pt sam2.1_hiera_small.pt sam2.1_hiera_base_plus.pt sam2.1_hiera_large.pt; do
    if [ ! -f "checkpoints/${model}" ]; then
        echo "Downloading ${model}..."
        curl -L -o "checkpoints/${model}" "${SAM2p1_BASE_URL}/${model}" || echo "Failed to download ${model}, continuing..."
    else
        echo "${model} already exists, skipping download"
    fi
done

# Download missing Grounding DINO checkpoints with retry
echo "=== Downloading missing Grounding DINO checkpoints ==="
GDINO_BASE_URL="https://github.com/IDEA-Research/GroundingDINO/releases/download"

if [ ! -f "gdino_checkpoints/groundingdino_swint_ogc.pth" ]; then
    echo "Downloading groundingdino_swint_ogc.pth..."
    curl -L -o gdino_checkpoints/groundingdino_swint_ogc.pth "${GDINO_BASE_URL}/v0.1.0-alpha/groundingdino_swint_ogc.pth" || echo "Failed, continuing..."
else
    echo "groundingdino_swint_ogc.pth already exists, skipping"
fi

if [ ! -f "gdino_checkpoints/groundingdino_swinb_cogcoor.pth" ]; then
    echo "Downloading groundingdino_swinb_cogcoor.pth..."
    curl -L -o gdino_checkpoints/groundingdino_swinb_cogcoor.pth "${GDINO_BASE_URL}/v0.1.0-alpha2/groundingdino_swinb_cogcoor.pth" || echo "Failed, continuing..."
else
    echo "groundingdino_swinb_cogcoor.pth already exists, skipping"
fi

# Final upload of all files
echo "=== Final upload of all checkpoints to S3 ===\"
aws s3 cp checkpoints/ s3://${S3_BUCKET}/checkpoints/ --recursive --region ${REGION}
aws s3 cp gdino_checkpoints/ s3://${S3_BUCKET}/gdino_checkpoints/ --recursive --region ${REGION}

# Verify uploads
echo "=== Verifying uploads ==="
echo "SAM2 checkpoints:"
aws s3 ls s3://${S3_BUCKET}/checkpoints/ --region ${REGION} --recursive --human-readable

echo "Grounding DINO checkpoints:"
aws s3 ls s3://${S3_BUCKET}/gdino_checkpoints/ --region ${REGION} --recursive --human-readable

# Write completion marker
echo "Model upload completed at $(date)" > /tmp/upload-complete.txt
aws s3 cp /tmp/upload-complete.txt s3://${MARKER_BUCKET}/models-upload-complete.txt --region ${REGION}

echo "=== DONE ==="
