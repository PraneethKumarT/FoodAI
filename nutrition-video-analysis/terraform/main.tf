 # =============================================================================
  # NUTRITION VIDEO ANALYSIS - FULL SERVERLESS ARCHITECTURE
  # =============================================================================

  terraform {
    required_version = ">= 1.0"
    required_providers {
      aws = {
        source  = "hashicorp/aws"
        version = "~> 5.0"
      }
      random = {
        source  = "hashicorp/random"
        version = "~> 3.1"
      }
    }
  }

  provider "aws" {
    region = var.aws_region
    default_tags {
      tags = {
        Project     = var.project_name
        Environment = var.environment
        ManagedBy   = "terraform"
      }
    }
  }

  # =============================================================================
  # VARIABLES
  # =============================================================================

  variable "aws_region" {
    description = "AWS region"
    type        = string
    default     = "us-east-1"
  }

  variable "project_name" {
    description = "Project name"
    type        = string
    default     = "nutrition-video-analysis"
  }

  variable "environment" {
    description = "Environment"
    type        = string
    default     = "dev"
  }

  variable "gemini_api_key" {
    description = "Gemini API key"
    type        = string
    default     = ""
    sensitive   = true
  }

  variable "notification_email" {
    description = "Email for notifications"
    type        = string
    default     = "admin@example.com"
  }

  # =============================================================================
  # LOCALS AND RANDOM
  # =============================================================================

  locals {
    name_prefix = "${var.project_name}-${var.environment}"
  }

  resource "random_string" "suffix" {
    length  = 8
    upper   = false
    special = false
  }

  data "aws_caller_identity" "current" {}
  data "aws_region" "current" {}

  # =============================================================================
  # KMS KEY
  # =============================================================================

  resource "aws_kms_key" "main" {
    description             = "KMS key for ${local.name_prefix}"
    deletion_window_in_days = 7
    enable_key_rotation     = true

    tags = {
      Name = "${local.name_prefix}-kms-key"
    }
  }

  resource "aws_kms_alias" "main" {
    name          = "alias/${local.name_prefix}-encryption"
    target_key_id = aws_kms_key.main.key_id
  }

  # =============================================================================
  # S3 BUCKETS
  # =============================================================================

  resource "aws_s3_bucket" "videos" {
    bucket = "${local.name_prefix}-videos-${random_string.suffix.result}"

    tags = {
      Name = "${local.name_prefix}-videos"
      Type = "video-storage"
    }
  }

  resource "aws_s3_bucket" "results" {
    bucket = "${local.name_prefix}-results-${random_string.suffix.result}"

    tags = {
      Name = "${local.name_prefix}-results"
      Type = "results-storage"
    }
  }

  resource "aws_s3_bucket" "models" {
    bucket = "${local.name_prefix}-models-${random_string.suffix.result}"

    tags = {
      Name = "${local.name_prefix}-models"
      Type = "model-storage"
    }
  }

  # S3 Bucket Encryption
  resource "aws_s3_bucket_server_side_encryption_configuration" "videos" {
    bucket = aws_s3_bucket.videos.id

    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.main.arn
        sse_algorithm     = "aws:kms"
      }
    }
  }

  resource "aws_s3_bucket_server_side_encryption_configuration" "results" {
    bucket = aws_s3_bucket.results.id

    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.main.arn
        sse_algorithm     = "aws:kms"
      }
    }
  }

  resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
    bucket = aws_s3_bucket.models.id

    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.main.arn
        sse_algorithm     = "aws:kms"
      }
    }
  }

  # S3 Bucket Public Access Block
  resource "aws_s3_bucket_public_access_block" "videos" {
    bucket = aws_s3_bucket.videos.id

    block_public_acls       = true
    block_public_policy     = true
    ignore_public_acls      = true
    restrict_public_buckets = true
  }

  resource "aws_s3_bucket_public_access_block" "results" {
    bucket = aws_s3_bucket.results.id

    block_public_acls       = true
    block_public_policy     = true
    ignore_public_acls      = true
    restrict_public_buckets = true
  }

  resource "aws_s3_bucket_public_access_block" "models" {
    bucket = aws_s3_bucket.models.id

    block_public_acls       = true
    block_public_policy     = true
    ignore_public_acls      = true
    restrict_public_buckets = true
  }

  # =============================================================================
  # DYNAMODB TABLE
  # =============================================================================

  resource "aws_dynamodb_table" "jobs" {
    name           = "${local.name_prefix}-jobs"
    billing_mode   = "PAY_PER_REQUEST"
    hash_key       = "job_id"

    attribute {
      name = "job_id"
      type = "S"
    }

    attribute {
      name = "status"
      type = "S"
    }

    attribute {
      name = "created_at"
      type = "S"
    }

    global_secondary_index {
      name               = "status-created_at-index"
      hash_key           = "status"
      range_key          = "created_at"
      projection_type    = "ALL"
    }

    server_side_encryption {
      enabled     = true
      kms_key_arn = aws_kms_key.main.arn
    }

    point_in_time_recovery {
      enabled = true
    }

    tags = {
      Name = "${local.name_prefix}-jobs"
      Type = "job-tracking"
    }
  }

  # =============================================================================
  # SQS QUEUES
  # =============================================================================

  resource "aws_sqs_queue" "video_processing" {
    name                       = "${local.name_prefix}-video-processing"
    visibility_timeout_seconds = 900
    message_retention_seconds  = 1209600

    kms_master_key_id = aws_kms_key.main.arn

    tags = {
      Name = "${local.name_prefix}-video-processing"
    }
  }

  resource "aws_sqs_queue" "nutrition_analysis" {
    name                       = "${local.name_prefix}-nutrition-analysis"
    visibility_timeout_seconds = 300
    message_retention_seconds  = 1209600

    kms_master_key_id = aws_kms_key.main.arn

    tags = {
      Name = "${local.name_prefix}-nutrition-analysis"
    }
  }

  # =============================================================================
  # IAM ROLES
  # =============================================================================

  # Lambda Execution Role
  resource "aws_iam_role" "lambda_execution_role" {
    name_prefix = "nutri-analysis-dev-lambda-exec-"

    assume_role_policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Action = "sts:AssumeRole"
          Effect = "Allow"
          Principal = {
            Service = "lambda.amazonaws.com"
          }
        }
      ]
    })

    tags = {
      Name = "${local.name_prefix}-lambda-execution-role"
    }
  }

  resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
    role       = aws_iam_role.lambda_execution_role.name
    policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  }

  # Lambda Custom Policy
  resource "aws_iam_policy" "lambda_custom_policy" {
    name_prefix = "${local.name_prefix}-lambda-custom-"
    description = "Custom policy for Lambda functions"

    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "s3:GetObject",
            "s3:PutObject",
            "s3:DeleteObject"
          ]
          Resource = [
            "${aws_s3_bucket.videos.arn}/*",
            "${aws_s3_bucket.results.arn}/*",
            "${aws_s3_bucket.models.arn}/*"
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:UpdateItem",
            "dynamodb:Query"
          ]
          Resource = [
            aws_dynamodb_table.jobs.arn,
            "${aws_dynamodb_table.jobs.arn}/index/*"
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "sqs:SendMessage",
            "sqs:ReceiveMessage",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes"
          ]
          Resource = [
            aws_sqs_queue.video_processing.arn,
            aws_sqs_queue.nutrition_analysis.arn
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "kms:Encrypt",
            "kms:Decrypt",
            "kms:GenerateDataKey",
            "kms:DescribeKey"
          ]
          Resource = aws_kms_key.main.arn
        }
      ]
    })
  }

  resource "aws_iam_role_policy_attachment" "lambda_custom_policy" {
    role       = aws_iam_role.lambda_execution_role.name
    policy_arn = aws_iam_policy.lambda_custom_policy.arn
  }

  # =============================================================================
  # LAMBDA FUNCTIONS
  # =============================================================================

  # Archive Lambda code from directories
  data "archive_file" "upload_handler_zip" {
    type        = "zip"
    source_dir  = "${path.module}/lambda_code/upload_handler"
    output_path = "${path.module}/upload_handler.zip"
  }

  data "archive_file" "status_checker_zip" {
    type        = "zip"
    source_dir  = "${path.module}/lambda_code/status_checker"
    output_path = "${path.module}/status_checker.zip"
  }

  data "archive_file" "results_handler_zip" {
    type        = "zip"
    source_dir  = "${path.module}/lambda_code/results_handler"
    output_path = "${path.module}/results_handler.zip"
  }

  resource "aws_lambda_function" "upload_handler" {
    filename         = data.archive_file.upload_handler_zip.output_path
    function_name    = "${local.name_prefix}-upload-handler"
    role            = aws_iam_role.lambda_execution_role.arn
    handler         = "lambda_function.lambda_handler"
    runtime         = "python3.11"
    timeout         = 30
    memory_size     = 512

    source_code_hash = data.archive_file.upload_handler_zip.output_base64sha256

    environment {
      variables = {
        S3_VIDEOS_BUCKET      = aws_s3_bucket.videos.bucket
        DYNAMODB_JOBS_TABLE   = aws_dynamodb_table.jobs.name
        SQS_VIDEO_QUEUE_URL   = aws_sqs_queue.video_processing.url
        GEMINI_API_KEY        = var.gemini_api_key
      }
    }

    tags = {
      Name = "${local.name_prefix}-upload-handler"
    }
  }

  resource "aws_lambda_function" "status_checker" {
    filename         = data.archive_file.status_checker_zip.output_path
    function_name    = "${local.name_prefix}-status-checker"
    role            = aws_iam_role.lambda_execution_role.arn
    handler         = "lambda_function.lambda_handler"
    runtime         = "python3.11"
    timeout         = 10
    memory_size     = 256

    source_code_hash = data.archive_file.status_checker_zip.output_base64sha256

    environment {
      variables = {
        DYNAMODB_JOBS_TABLE = aws_dynamodb_table.jobs.name
      }
    }

    tags = {
      Name = "${local.name_prefix}-status-checker"
    }
  }

  resource "aws_lambda_function" "results_handler" {
    filename         = data.archive_file.results_handler_zip.output_path
    function_name    = "${local.name_prefix}-results-handler"
    role            = aws_iam_role.lambda_execution_role.arn
    handler         = "lambda_function.lambda_handler"
    runtime         = "python3.11"
    timeout         = 30
    memory_size     = 512

    source_code_hash = data.archive_file.results_handler_zip.output_base64sha256

    environment {
      variables = {
        S3_RESULTS_BUCKET   = aws_s3_bucket.results.bucket
        DYNAMODB_JOBS_TABLE = aws_dynamodb_table.jobs.name
        GEMINI_API_KEY      = var.gemini_api_key
      }
    }

    tags = {
      Name = "${local.name_prefix}-results-handler"
    }
  }

  # =============================================================================
  # API GATEWAY
  # =============================================================================

  resource "aws_api_gateway_rest_api" "main" {
    name        = "${local.name_prefix}-api"
    description = "Nutrition Video Analysis API"

    endpoint_configuration {
      types = ["REGIONAL"]
    }
  }

  # Health endpoint
  resource "aws_api_gateway_resource" "health" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    parent_id   = aws_api_gateway_rest_api.main.root_resource_id
    path_part   = "health"
  }

  resource "aws_api_gateway_method" "health_get" {
    rest_api_id   = aws_api_gateway_rest_api.main.id
    resource_id   = aws_api_gateway_resource.health.id
    http_method   = "GET"
    authorization = "NONE"
  }

  resource "aws_api_gateway_integration" "health_mock" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    resource_id = aws_api_gateway_resource.health.id
    http_method = aws_api_gateway_method.health_get.http_method
    type        = "MOCK"

    request_templates = {
      "application/json" = "{\"statusCode\": 200}"
    }
  }

  resource "aws_api_gateway_method_response" "health_200" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    resource_id = aws_api_gateway_resource.health.id
    http_method = aws_api_gateway_method.health_get.http_method
    status_code = "200"

    response_models = {
      "application/json" = "Empty"
    }
  }

  resource "aws_api_gateway_integration_response" "health_200" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    resource_id = aws_api_gateway_resource.health.id
    http_method = aws_api_gateway_method.health_get.http_method
    status_code = aws_api_gateway_method_response.health_200.status_code

    response_templates = {
      "application/json" = jsonencode({
        status = "healthy"
        service = "nutrition-video-analysis"
        timestamp = "$context.requestTime"
      })
    }
  }

  # =============================================================================
  # API ROUTES - /api resource
  # =============================================================================

  resource "aws_api_gateway_resource" "api" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    parent_id   = aws_api_gateway_rest_api.main.root_resource_id
    path_part   = "api"
  }

  # /api/upload endpoint
  resource "aws_api_gateway_resource" "upload" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    parent_id   = aws_api_gateway_resource.api.id
    path_part   = "upload"
  }

  resource "aws_api_gateway_method" "upload_post" {
    rest_api_id   = aws_api_gateway_rest_api.main.id
    resource_id   = aws_api_gateway_resource.upload.id
    http_method   = "POST"
    authorization = "NONE"
  }

  resource "aws_api_gateway_integration" "upload_lambda" {
    rest_api_id             = aws_api_gateway_rest_api.main.id
    resource_id             = aws_api_gateway_resource.upload.id
    http_method             = aws_api_gateway_method.upload_post.http_method
    integration_http_method = "POST"
    type                    = "AWS_PROXY"
    uri                     = aws_lambda_function.upload_handler.invoke_arn
  }

  # /api/status/{job_id} endpoint
  resource "aws_api_gateway_resource" "status" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    parent_id   = aws_api_gateway_resource.api.id
    path_part   = "status"
  }

  resource "aws_api_gateway_resource" "status_job_id" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    parent_id   = aws_api_gateway_resource.status.id
    path_part   = "{job_id}"
  }

  resource "aws_api_gateway_method" "status_get" {
    rest_api_id   = aws_api_gateway_rest_api.main.id
    resource_id   = aws_api_gateway_resource.status_job_id.id
    http_method   = "GET"
    authorization = "NONE"

    request_parameters = {
      "method.request.path.job_id" = true
    }
  }

  resource "aws_api_gateway_integration" "status_lambda" {
    rest_api_id             = aws_api_gateway_rest_api.main.id
    resource_id             = aws_api_gateway_resource.status_job_id.id
    http_method             = aws_api_gateway_method.status_get.http_method
    integration_http_method = "POST"
    type                    = "AWS_PROXY"
    uri                     = aws_lambda_function.status_checker.invoke_arn
  }

  # /api/results/{job_id} endpoint
  resource "aws_api_gateway_resource" "results" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    parent_id   = aws_api_gateway_resource.api.id
    path_part   = "results"
  }

  resource "aws_api_gateway_resource" "results_job_id" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    parent_id   = aws_api_gateway_resource.results.id
    path_part   = "{job_id}"
  }

  resource "aws_api_gateway_method" "results_get" {
    rest_api_id   = aws_api_gateway_rest_api.main.id
    resource_id   = aws_api_gateway_resource.results_job_id.id
    http_method   = "GET"
    authorization = "NONE"

    request_parameters = {
      "method.request.path.job_id" = true
    }
  }

  resource "aws_api_gateway_integration" "results_lambda" {
    rest_api_id             = aws_api_gateway_rest_api.main.id
    resource_id             = aws_api_gateway_resource.results_job_id.id
    http_method             = aws_api_gateway_method.results_get.http_method
    integration_http_method = "POST"
    type                    = "AWS_PROXY"
    uri                     = aws_lambda_function.results_handler.invoke_arn
  }

  # Lambda permissions for API Gateway
  resource "aws_lambda_permission" "upload_api_gateway" {
    statement_id  = "AllowAPIGatewayInvoke"
    action        = "lambda:InvokeFunction"
    function_name = aws_lambda_function.upload_handler.function_name
    principal     = "apigateway.amazonaws.com"
    source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
  }

  resource "aws_lambda_permission" "status_api_gateway" {
    statement_id  = "AllowAPIGatewayInvoke"
    action        = "lambda:InvokeFunction"
    function_name = aws_lambda_function.status_checker.function_name
    principal     = "apigateway.amazonaws.com"
    source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
  }

  resource "aws_lambda_permission" "results_api_gateway" {
    statement_id  = "AllowAPIGatewayInvoke"
    action        = "lambda:InvokeFunction"
    function_name = aws_lambda_function.results_handler.function_name
    principal     = "apigateway.amazonaws.com"
    source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
  }

  # CORS for upload endpoint
  resource "aws_api_gateway_method" "upload_options" {
    rest_api_id   = aws_api_gateway_rest_api.main.id
    resource_id   = aws_api_gateway_resource.upload.id
    http_method   = "OPTIONS"
    authorization = "NONE"
  }

  resource "aws_api_gateway_integration" "upload_options" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    resource_id = aws_api_gateway_resource.upload.id
    http_method = aws_api_gateway_method.upload_options.http_method
    type        = "MOCK"

    request_templates = {
      "application/json" = "{\"statusCode\": 200}"
    }
  }

  resource "aws_api_gateway_method_response" "upload_options_200" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    resource_id = aws_api_gateway_resource.upload.id
    http_method = aws_api_gateway_method.upload_options.http_method
    status_code = "200"

    response_parameters = {
      "method.response.header.Access-Control-Allow-Headers" = true
      "method.response.header.Access-Control-Allow-Methods" = true
      "method.response.header.Access-Control-Allow-Origin"  = true
    }

    response_models = {
      "application/json" = "Empty"
    }
  }

  resource "aws_api_gateway_integration_response" "upload_options_200" {
    rest_api_id = aws_api_gateway_rest_api.main.id
    resource_id = aws_api_gateway_resource.upload.id
    http_method = aws_api_gateway_method.upload_options.http_method
    status_code = aws_api_gateway_method_response.upload_options_200.status_code

    response_parameters = {
      "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
      "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST'"
      "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    }
  }

  # API Deployment
  resource "aws_api_gateway_deployment" "main" {
    rest_api_id = aws_api_gateway_rest_api.main.id

    depends_on = [
      aws_api_gateway_integration.health_mock,
      aws_api_gateway_integration.upload_lambda,
      aws_api_gateway_integration.status_lambda,
      aws_api_gateway_integration.results_lambda,
      aws_api_gateway_integration.upload_options
    ]

    triggers = {
      redeployment = sha1(jsonencode([
        aws_api_gateway_resource.api.id,
        aws_api_gateway_resource.upload.id,
        aws_api_gateway_resource.status.id,
        aws_api_gateway_resource.results.id,
        aws_api_gateway_method.upload_post.id,
        aws_api_gateway_method.status_get.id,
        aws_api_gateway_method.results_get.id,
        aws_api_gateway_integration.upload_lambda.id,
        aws_api_gateway_integration.status_lambda.id,
        aws_api_gateway_integration.results_lambda.id,
      ]))
    }

    lifecycle {
      create_before_destroy = true
    }
  }

  # API Gateway Stage
  resource "aws_api_gateway_stage" "main" {
    deployment_id = aws_api_gateway_deployment.main.id
    rest_api_id   = aws_api_gateway_rest_api.main.id
    stage_name    = "v1"
  }

  # =============================================================================
  # ECR REPOSITORY
  # =============================================================================

  resource "aws_ecr_repository" "video_processor" {
    name                 = "${local.name_prefix}-video-processor"
    image_tag_mutability = "MUTABLE"

    image_scanning_configuration {
      scan_on_push = true
    }

    encryption_configuration {
      encryption_type = "KMS"
      kms_key         = aws_kms_key.main.arn
    }

    tags = {
      Name = "${local.name_prefix}-video-processor"
    }
  }

  resource "aws_ecr_lifecycle_policy" "video_processor" {
    repository = aws_ecr_repository.video_processor.name

    policy = jsonencode({
      rules = [
        {
          rulePriority = 1
          description  = "Keep last 5 images"
          selection = {
            tagStatus   = "any"
            countType   = "imageCountMoreThan"
            countNumber = 5
          }
          action = {
            type = "expire"
          }
        }
      ]
    })
  }

  # =============================================================================
  # VPC FOR ECS (Required for Fargate)
  # =============================================================================

  resource "aws_vpc" "main" {
    cidr_block           = "10.0.0.0/16"
    enable_dns_hostnames = true
    enable_dns_support   = true

    tags = {
      Name = "${local.name_prefix}-vpc"
    }
  }

  resource "aws_internet_gateway" "main" {
    vpc_id = aws_vpc.main.id

    tags = {
      Name = "${local.name_prefix}-igw"
    }
  }

  resource "aws_subnet" "public_1" {
    vpc_id                  = aws_vpc.main.id
    cidr_block              = "10.0.1.0/24"
    availability_zone       = "${var.aws_region}a"
    map_public_ip_on_launch = true

    tags = {
      Name = "${local.name_prefix}-public-1"
    }
  }

  resource "aws_subnet" "public_2" {
    vpc_id                  = aws_vpc.main.id
    cidr_block              = "10.0.2.0/24"
    availability_zone       = "${var.aws_region}b"
    map_public_ip_on_launch = true

    tags = {
      Name = "${local.name_prefix}-public-2"
    }
  }

  resource "aws_route_table" "public" {
    vpc_id = aws_vpc.main.id

    route {
      cidr_block = "0.0.0.0/0"
      gateway_id = aws_internet_gateway.main.id
    }

    tags = {
      Name = "${local.name_prefix}-public-rt"
    }
  }

  resource "aws_route_table_association" "public_1" {
    subnet_id      = aws_subnet.public_1.id
    route_table_id = aws_route_table.public.id
  }

  resource "aws_route_table_association" "public_2" {
    subnet_id      = aws_subnet.public_2.id
    route_table_id = aws_route_table.public.id
  }

  resource "aws_security_group" "ecs_tasks" {
    name_prefix = "${local.name_prefix}-ecs-tasks-"
    vpc_id      = aws_vpc.main.id

    egress {
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = ["0.0.0.0/0"]
    }

    tags = {
      Name = "${local.name_prefix}-ecs-tasks-sg"
    }
  }

  # =============================================================================
  # ECS CLUSTER
  # =============================================================================

  resource "aws_ecs_cluster" "main" {
    name = "${local.name_prefix}-cluster"

    setting {
      name  = "containerInsights"
      value = "enabled"
    }

    tags = {
      Name = "${local.name_prefix}-cluster"
    }
  }

  resource "aws_ecs_cluster_capacity_providers" "main" {
    cluster_name = aws_ecs_cluster.main.name

    capacity_providers = ["FARGATE", "FARGATE_SPOT"]

    default_capacity_provider_strategy {
      base              = 1
      weight            = 100
      capacity_provider = "FARGATE_SPOT"
    }
  }

  # =============================================================================
  # ECS TASK EXECUTION ROLE
  # =============================================================================

  resource "aws_iam_role" "ecs_task_execution_role" {
    name_prefix = "${local.name_prefix}-ecs-exec-"

    assume_role_policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Action = "sts:AssumeRole"
          Effect = "Allow"
          Principal = {
            Service = "ecs-tasks.amazonaws.com"
          }
        }
      ]
    })

    tags = {
      Name = "${local.name_prefix}-ecs-task-execution-role"
    }
  }

  resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
    role       = aws_iam_role.ecs_task_execution_role.name
    policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  }

  # Allow pulling from ECR with KMS
  resource "aws_iam_role_policy" "ecs_task_execution_ecr_kms" {
    name = "ecr-kms-access"
    role = aws_iam_role.ecs_task_execution_role.id

    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "kms:Decrypt",
            "kms:DescribeKey"
          ]
          Resource = aws_kms_key.main.arn
        }
      ]
    })
  }

  # =============================================================================
  # ECS TASK ROLE (for the running container)
  # =============================================================================

  resource "aws_iam_role" "ecs_task_role" {
    name_prefix = "${local.name_prefix}-ecs-task-"

    assume_role_policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Action = "sts:AssumeRole"
          Effect = "Allow"
          Principal = {
            Service = "ecs-tasks.amazonaws.com"
          }
        }
      ]
    })

    tags = {
      Name = "${local.name_prefix}-ecs-task-role"
    }
  }

  resource "aws_iam_role_policy" "ecs_task_policy" {
    name = "ecs-task-policy"
    role = aws_iam_role.ecs_task_role.id

    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "s3:GetObject",
            "s3:PutObject",
            "s3:DeleteObject"
          ]
          Resource = [
            "${aws_s3_bucket.videos.arn}/*",
            "${aws_s3_bucket.results.arn}/*",
            "${aws_s3_bucket.models.arn}/*"
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "s3:ListBucket"
          ]
          Resource = [
            aws_s3_bucket.videos.arn,
            aws_s3_bucket.results.arn,
            aws_s3_bucket.models.arn
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:UpdateItem",
            "dynamodb:Query"
          ]
          Resource = [
            aws_dynamodb_table.jobs.arn,
            "${aws_dynamodb_table.jobs.arn}/index/*"
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "sqs:ReceiveMessage",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes",
            "sqs:ChangeMessageVisibility"
          ]
          Resource = [
            aws_sqs_queue.video_processing.arn,
            aws_sqs_queue.nutrition_analysis.arn
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "kms:Encrypt",
            "kms:Decrypt",
            "kms:GenerateDataKey",
            "kms:DescribeKey"
          ]
          Resource = aws_kms_key.main.arn
        },
        {
          Effect = "Allow"
          Action = [
            "logs:CreateLogStream",
            "logs:PutLogEvents"
          ]
          Resource = "*"
        }
      ]
    })
  }

  # =============================================================================
  # CLOUDWATCH LOG GROUP
  # =============================================================================

  resource "aws_cloudwatch_log_group" "ecs_video_processor" {
    name              = "/ecs/${local.name_prefix}-video-processor"
    retention_in_days = 14

    tags = {
      Name = "${local.name_prefix}-video-processor-logs"
    }
  }

  # =============================================================================
  # ECS TASK DEFINITION
  # =============================================================================

  resource "aws_ecs_task_definition" "video_processor" {
    family                   = "${local.name_prefix}-video-processor"
    network_mode             = "awsvpc"
    requires_compatibilities = ["FARGATE"]
    cpu                      = "4096"   # 4 vCPU
    memory                   = "16384"  # 16 GB RAM
    execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
    task_role_arn            = aws_iam_role.ecs_task_role.arn

    container_definitions = jsonencode([
      {
        name      = "video-processor"
        image     = "${aws_ecr_repository.video_processor.repository_url}:latest"
        essential = true

        environment = [
          { name = "S3_VIDEOS_BUCKET", value = aws_s3_bucket.videos.bucket },
          { name = "S3_RESULTS_BUCKET", value = aws_s3_bucket.results.bucket },
          { name = "S3_MODELS_BUCKET", value = aws_s3_bucket.models.bucket },
          { name = "DYNAMODB_JOBS_TABLE", value = aws_dynamodb_table.jobs.name },
          { name = "SQS_VIDEO_QUEUE_URL", value = aws_sqs_queue.video_processing.url },
          { name = "AWS_REGION", value = var.aws_region },
          { name = "DEVICE", value = "cpu" }  # Change to "cuda" for GPU instances
        ]

        secrets = [
          {
            name      = "GEMINI_API_KEY"
            valueFrom = aws_ssm_parameter.gemini_api_key.arn
          }
        ]

        logConfiguration = {
          logDriver = "awslogs"
          options = {
            "awslogs-group"         = aws_cloudwatch_log_group.ecs_video_processor.name
            "awslogs-region"        = var.aws_region
            "awslogs-stream-prefix" = "ecs"
          }
        }

        healthCheck = {
          command     = ["CMD-SHELL", "python -c 'print(1)' || exit 1"]
          interval    = 30
          timeout     = 5
          retries     = 3
          startPeriod = 60
        }
      }
    ])

    tags = {
      Name = "${local.name_prefix}-video-processor"
    }
  }

  # =============================================================================
  # SSM PARAMETER FOR SECRETS
  # =============================================================================

  resource "aws_ssm_parameter" "gemini_api_key" {
    name        = "/${local.name_prefix}/gemini-api-key"
    description = "Gemini API key for nutrition analysis"
    type        = "SecureString"
    value       = var.gemini_api_key
    key_id      = aws_kms_key.main.arn

    tags = {
      Name = "${local.name_prefix}-gemini-api-key"
    }
  }

  # Allow ECS execution role to read SSM parameter
  resource "aws_iam_role_policy" "ecs_task_execution_ssm" {
    name = "ssm-access"
    role = aws_iam_role.ecs_task_execution_role.id

    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "ssm:GetParameters",
            "ssm:GetParameter"
          ]
          Resource = aws_ssm_parameter.gemini_api_key.arn
        }
      ]
    })
  }

  # =============================================================================
  # ECS SERVICE (Auto-scaling based on SQS)
  # =============================================================================

  resource "aws_ecs_service" "video_processor" {
    name            = "${local.name_prefix}-video-processor"
    cluster         = aws_ecs_cluster.main.id
    task_definition = aws_ecs_task_definition.video_processor.arn
    desired_count   = 0  # Scale from 0 - starts when messages arrive

    capacity_provider_strategy {
      capacity_provider = "FARGATE_SPOT"
      weight            = 100
      base              = 0
    }

    network_configuration {
      subnets          = [aws_subnet.public_1.id, aws_subnet.public_2.id]
      security_groups  = [aws_security_group.ecs_tasks.id]
      assign_public_ip = true
    }

    deployment_maximum_percent         = 200
    deployment_minimum_healthy_percent = 0

    tags = {
      Name = "${local.name_prefix}-video-processor-service"
    }

    lifecycle {
      ignore_changes = [desired_count]
    }
  }

  # =============================================================================
  # AUTO SCALING FOR ECS (Based on SQS Queue Depth)
  # =============================================================================

  resource "aws_appautoscaling_target" "ecs_target" {
    max_capacity       = 5
    min_capacity       = 0
    resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.video_processor.name}"
    scalable_dimension = "ecs:service:DesiredCount"
    service_namespace  = "ecs"
  }

  resource "aws_appautoscaling_policy" "ecs_scale_up" {
    name               = "${local.name_prefix}-scale-up"
    policy_type        = "StepScaling"
    resource_id        = aws_appautoscaling_target.ecs_target.resource_id
    scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
    service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

    step_scaling_policy_configuration {
      adjustment_type         = "ChangeInCapacity"
      cooldown                = 60
      metric_aggregation_type = "Average"

      step_adjustment {
        metric_interval_lower_bound = 0
        scaling_adjustment          = 1
      }
    }
  }

  resource "aws_appautoscaling_policy" "ecs_scale_down" {
    name               = "${local.name_prefix}-scale-down"
    policy_type        = "StepScaling"
    resource_id        = aws_appautoscaling_target.ecs_target.resource_id
    scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
    service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

    step_scaling_policy_configuration {
      adjustment_type         = "ChangeInCapacity"
      cooldown                = 300
      metric_aggregation_type = "Average"

      step_adjustment {
        metric_interval_upper_bound = 0
        scaling_adjustment          = -1
      }
    }
  }

  # CloudWatch Alarm for SQS Queue Depth
  resource "aws_cloudwatch_metric_alarm" "sqs_messages_visible" {
    alarm_name          = "${local.name_prefix}-sqs-messages-visible"
    comparison_operator = "GreaterThanThreshold"
    evaluation_periods  = 1
    metric_name         = "ApproximateNumberOfMessagesVisible"
    namespace           = "AWS/SQS"
    period              = 60
    statistic           = "Average"
    threshold           = 0
    alarm_description   = "Scale up when messages are in the queue"

    dimensions = {
      QueueName = aws_sqs_queue.video_processing.name
    }

    alarm_actions = [aws_appautoscaling_policy.ecs_scale_up.arn]
  }

  resource "aws_cloudwatch_metric_alarm" "sqs_messages_empty" {
    alarm_name          = "${local.name_prefix}-sqs-messages-empty"
    comparison_operator = "LessThanOrEqualToThreshold"
    evaluation_periods  = 5
    metric_name         = "ApproximateNumberOfMessagesVisible"
    namespace           = "AWS/SQS"
    period              = 60
    statistic           = "Average"
    threshold           = 0
    alarm_description   = "Scale down when queue is empty"

    dimensions = {
      QueueName = aws_sqs_queue.video_processing.name
    }

    alarm_actions = [aws_appautoscaling_policy.ecs_scale_down.arn]
  }

  # =============================================================================
  # OUTPUTS
  # =============================================================================

  output "api_gateway_url" {
    description = "API Gateway URL"
    value       = "${aws_api_gateway_rest_api.main.execution_arn}/v1"
  }

  output "api_gateway_invoke_url" {
    description = "API Gateway Invoke URL"
    value       = "https://${aws_api_gateway_rest_api.main.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/v1"
  }

  output "s3_buckets" {
    description = "S3 bucket names"
    value = {
      videos  = aws_s3_bucket.videos.bucket
      results = aws_s3_bucket.results.bucket
      models  = aws_s3_bucket.models.bucket
    }
  }

  output "dynamodb_table" {
    description = "DynamoDB table name"
    value       = aws_dynamodb_table.jobs.name
  }

  output "lambda_functions" {
    description = "Lambda function names"
    value = {
      upload_handler  = aws_lambda_function.upload_handler.function_name
      status_checker  = aws_lambda_function.status_checker.function_name
      results_handler = aws_lambda_function.results_handler.function_name
    }
  }

  output "ecr_repository" {
    description = "ECR repository URL for video processor"
    value       = aws_ecr_repository.video_processor.repository_url
  }

  output "ecs_cluster" {
    description = "ECS cluster name"
    value       = aws_ecs_cluster.main.name
  }

  output "ecs_service" {
    description = "ECS service name"
    value       = aws_ecs_service.video_processor.name
  }

  output "next_steps" {
    description = "Next steps after deployment"
    value = {
      test_api      = "curl https://${aws_api_gateway_rest_api.main.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/v1/health"
      upload_models = "Upload AI model checkpoints to s3://${aws_s3_bucket.models.bucket}"
      push_docker   = "docker push ${aws_ecr_repository.video_processor.repository_url}:latest"
      monitor       = "Check AWS Console for deployed resources"
    }
  }