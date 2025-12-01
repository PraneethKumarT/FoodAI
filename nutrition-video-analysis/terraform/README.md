# Nutrition Video Analysis - Terraform Infrastructure

This Terraform configuration deploys a serverless microservice architecture on AWS for automated nutrition analysis from food videos.

## 🏗️ Architecture Overview

```
API Gateway → Lambda Functions → ECS Fargate (GPU) → RAG System
     ↓              ↓                    ↓              ↓
S3 Storage ← DynamoDB Jobs ← SQS Queues ← EFS Models
```

## 🚀 Quick Start

### Prerequisites

1. **AWS CLI configured** with appropriate permissions
2. **Terraform >= 1.0** installed
3. **Docker** for building container images (optional)

### Deployment Steps

1. **Clone and navigate to terraform directory**
   ```bash
   cd terraform
   ```

2. **Copy and customize variables**
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values
   ```

3. **Initialize Terraform**
   ```bash
   terraform init
   ```

4. **Plan deployment**
   ```bash
   terraform plan
   ```

5. **Deploy infrastructure**
   ```bash
   terraform apply
   ```

6. **Note the outputs**
   ```bash
   terraform output
   ```

## 📋 Required Variables

### Essential Configuration

```hcl
# terraform.tfvars
aws_region     = "us-east-1"
project_name   = "nutrition-video-analysis" 
environment    = "dev"
gemini_api_key = "your-gemini-api-key"
notification_email = "your-email@example.com"
```

### Optional Configuration

```hcl
# Cost optimization
enable_spot_instances = true
max_vcpus = 256

# Storage
s3_video_retention_days = 30
dynamodb_billing_mode = "PAY_PER_REQUEST"

# Security
enable_encryption = true
enable_api_key = false
```

## 🔧 Key Features

### ✅ **Version Drift Protection**
Lambda functions include `lifecycle.ignore_changes` to prevent unwanted updates:

```hcl
lifecycle {
  ignore_changes = [
    filename,
    source_code_hash,
    last_modified,
    version
  ]
}
```

### ✅ **Cost Optimization**
- **Spot instances** for 60-70% savings on GPU compute
- **S3 Intelligent Tiering** for automatic cost optimization
- **Pay-per-request DynamoDB** for variable workloads
- **VPC endpoints** to avoid NAT Gateway costs

### ✅ **Auto-scaling**
- **Lambda** scales automatically from 0 to 1000+ concurrent executions
- **ECS Fargate** scales based on SQS queue depth
- **Batch** auto-scales GPU instances based on job queue

### ✅ **Security**
- **KMS encryption** for all storage services
- **VPC isolation** for compute resources
- **IAM least privilege** policies
- **Private subnets** for sensitive workloads

## 📊 Architecture Components

### API Layer
- **API Gateway**: RESTful API with CORS support
- **Lambda Functions**: Serverless request handlers
  - Upload Handler (512MB, 30s)
  - Status Checker (256MB, 10s)  
  - Results Handler (512MB, 30s)
  - Nutrition RAG (3GB, 5min)

### Compute Layer
- **ECS Fargate**: GPU-enabled containers for AI processing
- **AWS Batch**: Job queue management with spot instances
- **Auto Scaling**: Based on SQS queue depth

### Storage Layer
- **S3 Buckets**: Videos, results, and model storage
- **DynamoDB**: Job status and metadata tracking
- **EFS**: Shared nutrition model files for Lambda

### Messaging
- **SQS**: Asynchronous job processing queues
- **SNS**: Notification system for job completion

## 💰 Cost Estimates

### Monthly Costs (POC Usage)

| Component | Light (100 videos) | Medium (500 videos) | Heavy (1000 videos) |
|-----------|-------------------|-------------------|-------------------|
| Lambda | ~$2 | ~$8 | ~$15 |
| ECS Fargate (Spot) | ~$15 | ~$50 | ~$100 |
| Storage (S3/DynamoDB) | ~$5 | ~$15 | ~$25 |
| Data Transfer | ~$3 | ~$10 | ~$20 |
| **Total** | **~$25** | **~$83** | **~$160** |

### Cost Optimization Tips

1. **Use Spot Instances**: 60-70% savings on GPU compute
2. **Optimize Video Retention**: Reduce S3 storage costs
3. **Right-size Lambda Memory**: Balance performance vs cost
4. **Monitor with Cost Explorer**: Set up billing alerts

## 🔍 Monitoring

### CloudWatch Dashboards
- API Gateway metrics (latency, errors, requests)
- Lambda performance (duration, memory, errors)
- ECS cluster utilization
- SQS queue depth and processing time

### Alarms
- Lambda error rates > 5%
- API Gateway 5xx errors
- ECS task failures
- SQS message age > 15 minutes

## 🛠️ Customization

### Adding New Lambda Functions

1. Create function directory in `lambda_code/`
2. Add to `modules/lambda/main.tf`
3. Update API Gateway routes if needed

### Scaling Configuration

```hcl
# Increase GPU capacity
max_vcpus = 512

# Increase Lambda memory
memory_size = 1024

# Add provisioned concurrency
provisioned_concurrent_executions = 5
```

### Security Hardening

```hcl
# Enable API key authentication
enable_api_key = true

# Restrict CORS origins
cors_origins = ["https://yourdomain.com"]

# Enable WAF (add separately)
enable_waf = true
```

## 🔄 Updates and Maintenance

### Updating Lambda Code
```bash
# Update function code
cp new_code/* lambda_code/upload_handler/

# Lambda will ignore code changes due to lifecycle rules
# To force update, use AWS CLI or console
aws lambda update-function-code \
  --function-name nutrition-video-analysis-dev-upload-handler \
  --zip-file fileb://upload_handler.zip
```

### Infrastructure Updates
```bash
# Plan changes
terraform plan

# Apply only specific resources
terraform apply -target=module.compute

# Destroy specific components
terraform destroy -target=module.monitoring
```

## 🚨 Troubleshooting

### Common Issues

1. **Lambda timeout**: Increase timeout or memory
2. **ECS task failures**: Check CloudWatch logs
3. **API Gateway 5xx**: Verify Lambda permissions
4. **High costs**: Check Spot instance usage and S3 lifecycle

### Debug Commands
```bash
# Check Lambda logs
aws logs tail /aws/lambda/nutrition-video-analysis-dev-upload-handler

# Check ECS task logs
aws ecs describe-tasks --cluster nutrition-video-analysis-dev-cluster

# Monitor SQS queues
aws sqs get-queue-attributes --queue-url <queue-url>
```

## 📚 Additional Resources

- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [ECS Fargate Cost Optimization](https://aws.amazon.com/blogs/containers/theoretical-cost-optimization-by-amazon-ecs-launch-type-fargate-vs-ec2/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Test infrastructure changes in dev environment
4. Submit pull request with detailed description

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.