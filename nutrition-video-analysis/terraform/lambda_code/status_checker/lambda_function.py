import json
import os
from decimal import Decimal
import boto3

dynamodb = boto3.resource('dynamodb')
DYNAMODB_JOBS_TABLE = os.environ.get('DYNAMODB_JOBS_TABLE')


class DecimalEncoder(json.JSONEncoder):
    """Handle DynamoDB Decimal types in JSON serialization."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def lambda_handler(event, context):
    """Check job status from DynamoDB."""

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

        # Return job status
        result = {
            'job_id': job['job_id'],
            'status': job['status'],
            'created_at': job.get('created_at'),
            'updated_at': job.get('updated_at'),
            'filename': job.get('filename')
        }

        # Add progress info if available
        if 'progress' in job:
            result['progress'] = job['progress']

        # Add error message if failed
        if job['status'] == 'failed' and 'error' in job:
            result['error'] = job['error']

        # Add completion time if done
        if job['status'] == 'completed' and 'completed_at' in job:
            result['completed_at'] = job['completed_at']

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
