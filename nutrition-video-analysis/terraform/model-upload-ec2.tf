# Temporary EC2 instance to download and upload model checkpoints to S3
# This creates a small instance to download ~3GB of model files and upload to S3

data "aws_ami" "amazon_linux_2023_models" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Security group for model upload EC2 instance
resource "aws_security_group" "model_upload_temp" {
  name_prefix = "model-upload-temp-"
  description = "Temporary SG for model upload EC2 instance"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-model-upload-temp"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# IAM role for model upload EC2 instance
resource "aws_iam_role" "model_upload_temp" {
  name_prefix = "model-upload-temp-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-model-upload-temp"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Attach necessary policies for S3 and KMS
resource "aws_iam_role_policy" "model_upload_temp" {
  name_prefix = "model-upload-temp-"
  role        = aws_iam_role.model_upload_temp.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.models.arn}",
          "${aws_s3_bucket.models.arn}/*",
          "${aws_s3_bucket.videos.arn}",
          "${aws_s3_bucket.videos.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "${aws_kms_key.main.arn}"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "model_upload_temp" {
  name_prefix = "model-upload-temp-"
  role        = aws_iam_role.model_upload_temp.name
}

# EC2 instance for model upload
resource "aws_instance" "model_upload_temp" {
  ami                    = data.aws_ami.amazon_linux_2023_models.id
  instance_type          = "t3.medium"
  subnet_id              = aws_subnet.public_1.id
  vpc_security_group_ids = [aws_security_group.model_upload_temp.id]
  iam_instance_profile   = aws_iam_instance_profile.model_upload_temp.name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  # Download models and upload to S3
  user_data = base64encode(<<-EOF
    #!/bin/bash
    set -x
    exec > >(tee /var/log/user-data.log)
    exec 2>&1

    echo "Starting model download and upload at $(date)"

    # Download and execute upload script from GitHub
    curl -fsSL https://raw.githubusercontent.com/PraneethKumarT/FoodAI/main/nutrition-video-analysis/terraform/docker/download-and-upload-models.sh | bash

    echo "Model upload completed at $(date)"
  EOF
  )

  tags = {
    Name        = "${var.project_name}-${var.environment}-model-upload-temp"
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "Temporary instance for model checkpoint upload to S3"
  }
}

output "model_upload_instance_id" {
  value       = aws_instance.model_upload_temp.id
  description = "EC2 instance ID for model upload"
}

output "model_upload_log_command" {
  value       = "aws ec2 get-console-output --instance-id ${aws_instance.model_upload_temp.id} --region us-east-1 --output text"
  description = "Command to view the model upload progress"
}
