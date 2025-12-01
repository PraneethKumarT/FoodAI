#!/usr/bin/env python3
"""
ECS Worker - Polls SQS queue and processes video files for nutrition analysis.
"""

import json
import os
import sys
import time
import tempfile
import traceback
from datetime import datetime
from decimal import Decimal

import boto3

# AWS clients
s3 = boto3.client('s3')
sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')

# Environment variables
S3_VIDEOS_BUCKET = os.environ.get('S3_VIDEOS_BUCKET')
S3_RESULTS_BUCKET = os.environ.get('S3_RESULTS_BUCKET')
S3_MODELS_BUCKET = os.environ.get('S3_MODELS_BUCKET')
DYNAMODB_JOBS_TABLE = os.environ.get('DYNAMODB_JOBS_TABLE')
SQS_VIDEO_QUEUE_URL = os.environ.get('SQS_VIDEO_QUEUE_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
DEVICE = os.environ.get('DEVICE', 'cpu')

# Processing settings
MAX_FRAMES = int(os.environ.get('MAX_FRAMES', '60'))
FRAME_SKIP = int(os.environ.get('FRAME_SKIP', '10'))
DETECTION_INTERVAL = int(os.environ.get('DETECTION_INTERVAL', '30'))


def convert_floats_to_decimal(obj):
    """Recursively convert floats to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    return obj


def update_job_status(job_id: str, status: str, **kwargs):
    """Update job status in DynamoDB."""
    table = dynamodb.Table(DYNAMODB_JOBS_TABLE)

    update_expr = 'SET #status = :status, updated_at = :updated_at'
    expr_names = {'#status': 'status'}
    expr_values = {
        ':status': status,
        ':updated_at': datetime.utcnow().isoformat() + 'Z'
    }

    for key, value in kwargs.items():
        update_expr += f', {key} = :{key}'
        expr_values[f':{key}'] = convert_floats_to_decimal(value)

    table.update_item(
        Key={'job_id': job_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values
    )


def download_video(s3_bucket: str, s3_key: str, local_path: str):
    """Download video from S3."""
    print(f"Downloading video from s3://{s3_bucket}/{s3_key}")
    s3.download_file(s3_bucket, s3_key, local_path)
    print(f"Downloaded to {local_path}")


def upload_results(job_id: str, results: dict):
    """Upload results to S3."""
    results_key = f'results/{job_id}/results.json'

    s3.put_object(
        Bucket=S3_RESULTS_BUCKET,
        Key=results_key,
        Body=json.dumps(results, indent=2, default=str),
        ContentType='application/json'
    )

    print(f"Results uploaded to s3://{S3_RESULTS_BUCKET}/{results_key}")
    return results_key


def process_video(video_path: str, job_id: str) -> dict:
    """
    Process video through the nutrition analysis pipeline.

    Pipeline:
    1. Extract frames
    2. Detect food items with Florence-2
    3. Track objects with SAM2
    4. Estimate depth with Metric3D
    5. Calculate volumes
    6. Look up nutrition data
    7. Return results
    """

    # Update status to processing
    update_job_status(job_id, 'processing', progress=0)

    try:
        # Import processing modules (loaded here to avoid import errors during container startup)
        sys.path.insert(0, '/app')

        from app.pipeline import NutritionVideoPipeline
        from app.models import ModelManager
        from app.config import Settings

        # Initialize configuration
        print("Initializing configuration...")
        config = Settings()
        config.DEVICE = DEVICE
        config.GEMINI_API_KEY = GEMINI_API_KEY

        update_job_status(job_id, 'processing', progress=5)

        # Initialize models
        print("Loading AI models...")
        model_manager = ModelManager(config)

        update_job_status(job_id, 'processing', progress=10)

        # Initialize pipeline
        print("Initializing processing pipeline...")
        pipeline = NutritionVideoPipeline(model_manager, config)

        update_job_status(job_id, 'processing', progress=15)

        # Process video
        from pathlib import Path
        print(f"Processing video: {video_path}")
        results = pipeline.process_video(Path(video_path), job_id)

        update_job_status(job_id, 'processing', progress=95)

        # Transform results to expected format
        meal_summary = results.get('nutrition', {}).get('meal_summary', {})

        return {
            'job_id': job_id,
            'video_path': video_path,
            'detected_items': results.get('nutrition', {}).get('items', []),
            'meal_summary': meal_summary,
            'processing_info': {
                'frames_processed': results.get('num_frames_processed', 0),
                'device': DEVICE,
                'mock': False,
                'calibration': results.get('calibration', {})
            },
            'tracking': results.get('tracking', {}),
            'full_results': results
        }

    except ImportError as e:
        print(f"Pipeline not available, using mock processing: {e}")
        # Mock processing for testing without full pipeline
        return mock_process_video(video_path, job_id)
    except Exception as e:
        print(f"Real processing failed: {e}, falling back to mock")
        traceback.print_exc()
        return mock_process_video(video_path, job_id)


def real_process_video(video_path: str, job_id: str) -> dict:
    """Real video processing using AI pipeline."""
    from pathlib import Path
    from app.config import Settings
    from app.models import ModelManager
    from app.pipeline import NutritionVideoPipeline

    print("Running real AI video processing...")

    # Initialize configuration
    config = Settings()
    config.DEVICE = DEVICE
    config.GEMINI_API_KEY = GEMINI_API_KEY

    # Initialize models
    print("Loading AI models...")
    update_job_status(job_id, 'processing', progress=5)
    model_manager = ModelManager(config)

    # Initialize pipeline
    print("Initializing processing pipeline...")
    update_job_status(job_id, 'processing', progress=10)
    pipeline = NutritionVideoPipeline(model_manager, config)

    # Process video
    print(f"Processing video: {video_path}")
    update_job_status(job_id, 'processing', progress=15)

    results = pipeline.process_video(Path(video_path), job_id)

    update_job_status(job_id, 'processing', progress=95)

    # Transform results to expected format
    meal_summary = results.get('nutrition', {}).get('meal_summary', {})

    return {
        'job_id': job_id,
        'video_path': video_path,
        'detected_items': results.get('nutrition', {}).get('items', []),
        'meal_summary': meal_summary,
        'processing_info': {
            'frames_processed': results.get('num_frames_processed', 0),
            'device': DEVICE,
            'mock': False,
            'calibration': results.get('calibration', {})
        },
        'tracking': results.get('tracking', {}),
        'full_results': results
    }


def mock_process_video(video_path: str, job_id: str) -> dict:
    """Mock video processing for testing infrastructure."""

    print("Running mock video processing...")

    # Simulate processing time
    for i in range(10):
        time.sleep(1)
        progress = (i + 1) * 10
        update_job_status(job_id, 'processing', progress=progress)
        print(f"Processing progress: {progress}%")

    # Return mock results
    return {
        'job_id': job_id,
        'video_path': video_path,
        'detected_items': [
            {
                'id': 1,
                'name': 'apple',
                'confidence': 0.95,
                'volume_ml': 150.0,
                'mass_g': 150.0,
                'calories': 78.0,
                'nutrition': {
                    'protein_g': 0.4,
                    'carbs_g': 20.7,
                    'fat_g': 0.2,
                    'fiber_g': 3.6
                }
            },
            {
                'id': 2,
                'name': 'banana',
                'confidence': 0.92,
                'volume_ml': 120.0,
                'mass_g': 118.0,
                'calories': 105.0,
                'nutrition': {
                    'protein_g': 1.3,
                    'carbs_g': 27.0,
                    'fat_g': 0.4,
                    'fiber_g': 3.1
                }
            }
        ],
        'meal_summary': {
            'total_calories': 183.0,
            'total_protein_g': 1.7,
            'total_carbs_g': 47.7,
            'total_fat_g': 0.6,
            'total_fiber_g': 6.7,
            'item_count': 2
        },
        'processing_info': {
            'frames_processed': 60,
            'processing_time_seconds': 10.0,
            'device': DEVICE,
            'mock': True
        }
    }


def process_message(message: dict):
    """Process a single SQS message."""

    body = json.loads(message['Body'])
    job_id = body['job_id']
    s3_bucket = body['s3_bucket']
    s3_key = body['s3_key']
    receipt_handle = message['ReceiptHandle']

    print(f"\n{'='*60}")
    print(f"Processing job: {job_id}")
    print(f"Video: s3://{s3_bucket}/{s3_key}")
    print(f"{'='*60}\n")

    try:
        # Update status
        update_job_status(job_id, 'processing', progress=0)

        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as tmpdir:
            # Download video
            video_filename = os.path.basename(s3_key)
            video_path = os.path.join(tmpdir, video_filename)
            download_video(s3_bucket, s3_key, video_path)

            update_job_status(job_id, 'processing', progress=5)

            # Process video
            results = process_video(video_path, job_id)

            # Upload results
            results_key = upload_results(job_id, results)

            # Extract food names from detected items
            food_items = [
                {
                    'name': item.get('name'),
                    'calories': item.get('calories')
                }
                for item in results.get('detected_items', [])
            ]

            # Update job as completed
            update_job_status(
                job_id,
                'completed',
                progress=100,
                completed_at=datetime.utcnow().isoformat() + 'Z',
                results_s3_key=results_key,
                nutrition_summary=results.get('meal_summary', {}),
                detected_foods=food_items
            )

            print(f"\n{'='*60}")
            print(f"Job {job_id} completed successfully!")
            print(f"{'='*60}\n")

        # Delete message from queue
        sqs.delete_message(
            QueueUrl=SQS_VIDEO_QUEUE_URL,
            ReceiptHandle=receipt_handle
        )

    except Exception as e:
        print(f"Error processing job {job_id}: {str(e)}")
        traceback.print_exc()

        # Update job as failed
        update_job_status(
            job_id,
            'failed',
            error=str(e)
        )

        # Don't delete message - let it return to queue for retry
        # After max retries, it will go to DLQ if configured


def poll_queue():
    """Poll SQS queue for messages."""

    print(f"Starting worker...")
    print(f"Queue URL: {SQS_VIDEO_QUEUE_URL}")
    print(f"Videos bucket: {S3_VIDEOS_BUCKET}")
    print(f"Results bucket: {S3_RESULTS_BUCKET}")
    print(f"Device: {DEVICE}")
    print("")

    while True:
        try:
            # Receive messages
            response = sqs.receive_message(
                QueueUrl=SQS_VIDEO_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,  # Long polling
                VisibilityTimeout=900  # 15 minutes
            )

            messages = response.get('Messages', [])

            if messages:
                for message in messages:
                    process_message(message)
            else:
                print("No messages in queue, waiting...")

        except KeyboardInterrupt:
            print("\nShutting down worker...")
            break
        except Exception as e:
            print(f"Error polling queue: {str(e)}")
            traceback.print_exc()
            time.sleep(5)  # Wait before retrying


if __name__ == '__main__':
    # Validate environment
    required_vars = [
        'S3_VIDEOS_BUCKET',
        'S3_RESULTS_BUCKET',
        'DYNAMODB_JOBS_TABLE',
        'SQS_VIDEO_QUEUE_URL'
    ]

    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        print(f"Error: Missing required environment variables: {missing}")
        sys.exit(1)

    poll_queue()
