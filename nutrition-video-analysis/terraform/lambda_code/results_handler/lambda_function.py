import json
import os
import boto3
from decimal import Decimal

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

S3_RESULTS_BUCKET = os.environ.get('S3_RESULTS_BUCKET')
DYNAMODB_JOBS_TABLE = os.environ.get('DYNAMODB_JOBS_TABLE')


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal types from DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def lambda_handler(event, context):
    """Get job results from S3 and DynamoDB."""

    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,OPTIONS'
    }

    try:
        # Get job_id from path parameters
        job_id = event.get('pathParameters', {}).get('job_id')

        if not job_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'job_id is required'})
            }

        # Get job from DynamoDB
        table = dynamodb.Table(DYNAMODB_JOBS_TABLE)
        response = table.get_item(Key={'job_id': job_id})

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'Job not found'})
            }

        job = response['Item']

        # Check if job is completed
        if job['status'] != 'completed':
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Job not completed',
                    'status': job['status'],
                    'message': 'Please check /api/status/{job_id} for current status'
                })
            }

        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        detailed = query_params.get('detailed', 'false').lower() == 'true'

        # Build response with summary from DynamoDB
        result = {
            'job_id': job['job_id'],
            'status': 'completed',
            'created_at': job.get('created_at'),
            'completed_at': job.get('completed_at'),
            'filename': job.get('filename')
        }

        # Add nutrition summary if available in DynamoDB
        if 'nutrition_summary' in job:
            result['nutrition_summary'] = job['nutrition_summary']

        # Add detected foods if available in DynamoDB
        if 'detected_foods' in job:
            result['detected_foods'] = job['detected_foods']

        # If detailed results requested, fetch from S3
        if detailed:
            results_key = job.get('results_s3_key', f'results/{job_id}/results.json')

            try:
                s3_response = s3.get_object(
                    Bucket=S3_RESULTS_BUCKET,
                    Key=results_key
                )
                detailed_results = json.loads(s3_response['Body'].read().decode('utf-8'))
                result['detailed_results'] = detailed_results
            except s3.exceptions.NoSuchKey:
                result['detailed_results'] = None
                result['warning'] = 'Detailed results not found in S3'
            except Exception as e:
                result['detailed_results'] = None
                result['warning'] = f'Error fetching detailed results: {str(e)}'

        # Generate presigned URL for downloading full results
        results_key = job.get('results_s3_key', f'results/{job_id}/results.json')
        try:
            download_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': S3_RESULTS_BUCKET,
                    'Key': results_key
                },
                ExpiresIn=3600  # 1 hour
            )
            result['download_url'] = download_url
        except Exception:
            pass  # Skip if can't generate URL

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(result, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }
