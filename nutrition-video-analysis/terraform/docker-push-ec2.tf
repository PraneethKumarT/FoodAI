# Temporary EC2 instance to push Docker image to ECR
# This creates a small instance with enough disk space to load the 3.12GB image

data "aws_ami" "amazon_linux_2023" {
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

# Security group for temporary EC2 instance
resource "aws_security_group" "docker_push_temp" {
  name_prefix = "docker-push-temp-"
  description = "Temporary SG for Docker push EC2 instance"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-docker-push-temp"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# IAM role for EC2 instance
resource "aws_iam_role" "docker_push_temp" {
  name_prefix = "docker-push-temp-"

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
    Name        = "${var.project_name}-${var.environment}-docker-push-temp"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Attach necessary policies
resource "aws_iam_role_policy" "docker_push_temp" {
  name_prefix = "docker-push-temp-"
  role        = aws_iam_role.docker_push_temp.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.videos.arn}",
          "${aws_s3_bucket.videos.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = "${aws_kms_key.main.arn}"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "docker_push_temp" {
  name_prefix = "docker-push-temp-"
  role        = aws_iam_role.docker_push_temp.name
}

# EC2 instance
resource "aws_instance" "docker_push_temp" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t3.medium"
  subnet_id              = aws_subnet.public_1.id
  vpc_security_group_ids = [aws_security_group.docker_push_temp.id]
  iam_instance_profile   = aws_iam_instance_profile.docker_push_temp.name

  root_block_device {
    volume_size = 40
    volume_type = "gp3"
  }

  user_data = base64encode(<<-EOF
    #!/bin/bash
    exec > >(tee /var/log/user-data.log)
    exec 2>&1
    set -x

    echo "Starting Docker build process..."

    # Install Docker and git
    yum update -y
    yum install -y docker git
    systemctl start docker
    systemctl enable docker
    usermod -a -G docker ec2-user

    # Run build as ec2-user
    su - ec2-user << 'EOSU'
      set -x
      cd /home/ec2-user

      # Clone repo
      echo "Cloning repository..."
      git clone https://github.com/PraneethKumarT/FoodAI.git
      cd FoodAI/nutrition-video-analysis

      # ECR login
      echo "Logging into ECR..."
      aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 185329004895.dkr.ecr.us-east-1.amazonaws.com

      # Build AMD64
      echo "Building AMD64 image..."
      docker build --platform linux/amd64 -f deploy/Dockerfile -t 185329004895.dkr.ecr.us-east-1.amazonaws.com/nutrition-video-analysis-dev-video-processor:latest .

      # Push to ECR
      echo "Pushing to ECR..."
      docker push 185329004895.dkr.ecr.us-east-1.amazonaws.com/nutrition-video-analysis-dev-video-processor:latest

      # Success marker
      echo "Build completed at $(date)" > /tmp/build-complete.txt
      aws s3 cp /tmp/build-complete.txt s3://nutrition-video-analysis-dev-videos-60ppnqfp/docker-images/build-complete.txt --region us-east-1

      echo "DONE!"
EOSU
  EOF
  )

  tags = {
    Name        = "${var.project_name}-${var.environment}-docker-push-temp"
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "Temporary instance for Docker push to ECR"
  }
}

output "docker_push_instance_id" {
  value       = aws_instance.docker_push_temp.id
  description = "EC2 instance ID for Docker push"
}

output "docker_push_log_command" {
  value       = "aws ec2 get-console-output --instance-id ${aws_instance.docker_push_temp.id} --region us-east-1 --output text"
  description = "Command to view the Docker push progress"
}
