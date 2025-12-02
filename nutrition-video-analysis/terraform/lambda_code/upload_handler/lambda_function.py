import json
import os
import uuid
import boto3
from botocore.config import Config
from datetime import datetime
import base64

# Configure S3 client with signature version 4 for KMS-encrypted buckets
s3_config = Config(signature_version='s3v4')
s3 = boto3.client('s3', config=s3_config)
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

S3_VIDEOS_BUCKET = os.environ.get('S3_VIDEOS_BUCKET')
DYNAMODB_JOBS_TABLE = os.environ.get('DYNAMODB_JOBS_TABLE')
SQS_VIDEO_QUEUE_URL = os.environ.get('SQS_VIDEO_QUEUE_URL')


def lambda_handler(event, context):
    """Handle video upload - returns presigned URL or processes base64 upload."""

    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,OPTIONS,POST'
    }

    try:
        # Parse request body
        body = {}
        if event.get('body'):
            if event.get('isBase64Encoded'):
                body = json.loads(base64.b64decode(event['body']).decode('utf-8'))
            else:
                body = json.loads(event['body'])

        # Generate unique job ID
        job_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + 'Z'

        # Check if requesting presigned URL or direct upload
        request_type = body.get('type', 'presigned')
        filename = body.get('filename', f'{job_id}.mp4')
        content_type = body.get('content_type', 'video/mp4')

        # S3 key for video
        s3_key = f'uploads/{job_id}/{filename}'

        if request_type == 'presigned':
            # Generate presigned URL for direct S3 upload
            # Include SSE parameters for KMS-encrypted bucket
            presigned_url = s3.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': S3_VIDEOS_BUCKET,
                    'Key': s3_key,
                    'ContentType': content_type,
                    'ServerSideEncryption': 'aws:kms'
                },
                ExpiresIn=3600  # 1 hour
            )

            # Create job record in DynamoDB
            table = dynamodb.Table(DYNAMODB_JOBS_TABLE)
            table.put_item(Item={
                'job_id': job_id,
                'status': 'pending_upload',
                'created_at': timestamp,
                'updated_at': timestamp,
                's3_key': s3_key,
                'filename': filename
            })

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'job_id': job_id,
                    'upload_url': presigned_url,
                    'status': 'pending_upload',
                    'message': 'Upload video to the provided URL, then call /api/process/{job_id}'
                })
            }

        elif request_type == 'base64':
            # Handle base64 encoded video (for smaller files)
            video_data = body.get('video_data')
            if not video_data:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'video_data is required for base64 upload'})
                }

            # Decode and upload to S3
            video_bytes = base64.b64decode(video_data)
            s3.put_object(
                Bucket=S3_VIDEOS_BUCKET,
                Key=s3_key,
                Body=video_bytes,
                ContentType=content_type
            )

            # Create job record
            table = dynamodb.Table(DYNAMODB_JOBS_TABLE)
            table.put_item(Item={
                'job_id': job_id,
                'status': 'queued',
                'created_at': timestamp,
                'updated_at': timestamp,
                's3_key': s3_key,
                'filename': filename
            })

            # Queue for processing
            sqs.send_message(
                QueueUrl=SQS_VIDEO_QUEUE_URL,
                MessageBody=json.dumps({
                    'job_id': job_id,
                    's3_bucket': S3_VIDEOS_BUCKET,
                    's3_key': s3_key
                })
            )

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'job_id': job_id,
                    'status': 'queued',
                    'message': 'Video uploaded and queued for processing'
                })
            }

        elif request_type == 'confirm':
            # Confirm upload complete and start processing
            confirm_job_id = body.get('job_id')
            if not confirm_job_id:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'job_id is required to confirm upload'})
                }

            # Get job record
            table = dynamodb.Table(DYNAMODB_JOBS_TABLE)
            response = table.get_item(Key={'job_id': confirm_job_id})

            if 'Item' not in response:
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({'error': 'Job not found'})
                }

            job = response['Item']

            # Update status and queue for processing
            table.update_item(
                Key={'job_id': confirm_job_id},
                UpdateExpression='SET #status = :status, updated_at = :updated_at',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'queued',
                    ':updated_at': datetime.utcnow().isoformat() + 'Z'
                }
            )

            # Queue for processing
            sqs.send_message(
                QueueUrl=SQS_VIDEO_QUEUE_URL,
                MessageBody=json.dumps({
                    'job_id': confirm_job_id,
                    's3_bucket': S3_VIDEOS_BUCKET,
                    's3_key': job['s3_key']
                })
            )

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'job_id': confirm_job_id,
                    'status': 'queued',
                    'message': 'Video queued for processing'
                })
            }

        else:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': f'Unknown request type: {request_type}'})
            }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }
