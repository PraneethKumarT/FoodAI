# Deployment Checklist 🚀

Use this checklist to ensure a successful deployment to production.

## Pre-Deployment


### Local Testing
- [ ] Test all API endpoints locally
- [ ] Verify GPU acceleration works
- [ ] Test with sample videos (small, medium, large)
- [ ] Check memory usage during processing
- [ ] Verify nutrition database integration
- [ ] Test error handling (invalid files, large files)
- [ ] Review logs for warnings/errors

### Configuration
- [ ] Create `.env` file from `env.example`
- [ ] Set `GEMINI_API_KEY`
- [ ] Configure `DEVICE=cuda` (or `cpu` for testing)
- [ ] Set `DEBUG=False` for production
- [ ] Configure `CORS_ORIGINS` to specific domains
- [ ] Set strong `API_KEY` if using authentication
- [ ] Review and adjust `MAX_VIDEO_SIZE_MB`
- [ ] Configure `DATABASE_URL` (PostgreSQL for production)

### Security
- [ ] Enable API key authentication (`REQUIRE_API_KEY=True`)
- [ ] Restrict CORS origins to your domain
- [ ] Setup SSL/TLS certificate (HTTPS)
- [ ] Configure firewall rules (only necessary ports)
- [ ] Store secrets in environment variables (not in code)
- [ ] Setup secrets manager (AWS Secrets Manager, GCP Secret Manager)
- [ ] Enable rate limiting
- [ ] Review and restrict file upload permissions

### Models & Data
- [ ] Download all required model checkpoints
- [ ] Verify SAM2 checkpoint exists
- [ ] Verify nutrition database files (PDF, Excel)
- [ ] Test model loading locally
- [ ] Ensure sufficient storage for model cache

## Cloud Deployment

### Infrastructure Setup
- [ ] Choose cloud provider (AWS/GCP/Azure)
- [ ] Select GPU instance type (g4dn.xlarge recommended)
- [ ] Configure storage (100GB+ EBS/Persistent Disk)
- [ ] Setup VPC and security groups
- [ ] Configure auto-scaling (optional)
- [ ] Setup load balancer (if multiple instances)

### Instance Configuration
- [ ] SSH key pair created
- [ ] Instance launched with GPU support
- [ ] Docker installed
- [ ] nvidia-docker2 installed
- [ ] GPU drivers verified (`nvidia-smi`)
- [ ] Git repository cloned
- [ ] `.env` file configured

### Database
- [ ] Database created (RDS/Cloud SQL or local SQLite)
- [ ] Database credentials configured
- [ ] Database migrations run
- [ ] Backup strategy configured

### Deployment
- [ ] Docker image built successfully
- [ ] Container started (`docker-compose up -d`)
- [ ] Health check passing
- [ ] API accessible on public IP
- [ ] Test file upload
- [ ] Test complete processing pipeline
- [ ] Verify results accuracy

### Monitoring & Logging
- [ ] Setup logging aggregation (CloudWatch/Stackdriver)
- [ ] Configure alerts for errors
- [ ] Setup performance monitoring
- [ ] Configure uptime monitoring
- [ ] Setup cost alerts
- [ ] Create dashboard for metrics

### Networking
- [ ] Domain name configured (optional)
- [ ] DNS records updated
- [ ] SSL certificate installed (Let's Encrypt)
- [ ] HTTPS redirect configured
- [ ] CDN configured (CloudFront/Cloud CDN) - optional

## Post-Deployment

### Validation
- [ ] Test API from external network
- [ ] Verify all endpoints work
- [ ] Test with production data
- [ ] Check response times
- [ ] Verify error handling
- [ ] Test concurrent requests

### Documentation
- [ ] Update API documentation
- [ ] Create user guide
- [ ] Document deployment process
- [ ] Create runbook for common issues
- [ ] Document backup/restore procedures

### Backup & Recovery
- [ ] Database backup automated
- [ ] Test database restore
- [ ] Model files backed up
- [ ] Configuration backed up
- [ ] Disaster recovery plan documented

### Optimization
- [ ] Enable FP16 if supported
- [ ] Configure optimal batch sizes
- [ ] Tune frame skip and resolution
- [ ] Setup model caching (Redis)
- [ ] Configure job queue (SQS/Pub-Sub)

### Maintenance
- [ ] Schedule regular updates
- [ ] Setup automated security patches
- [ ] Configure log rotation
- [ ] Plan for model updates
- [ ] Setup monitoring for disk space

## Ongoing Operations

### Daily
- [ ] Check error logs
- [ ] Monitor resource usage
- [ ] Review API metrics
- [ ] Check backup status

### Weekly
- [ ] Review performance metrics
- [ ] Analyze cost reports
- [ ] Review security logs
- [ ] Clean up old jobs/videos

### Monthly
- [ ] Update dependencies
- [ ] Review and optimize costs
- [ ] Security audit
- [ ] Performance optimization review
- [ ] User feedback review

## Emergency Procedures

### API Down
1. Check container status: `docker-compose ps`
2. Check logs: `docker-compose logs --tail=100`
3. Restart: `docker-compose restart`
4. If persists, rebuild: `docker-compose down && docker-compose up -d`

### Out of Memory
1. Check GPU memory: `nvidia-smi`
2. Reduce `MAX_FRAMES` in .env
3. Reduce `RESIZE_WIDTH`
4. Restart container

### Database Issues
1. Check connection: `docker-compose exec nutrition-api python3 -c "from app.database import Database; db = Database(...)"`
2. Check disk space
3. Restore from backup if corrupted

### High Costs
1. Check instance uptime (auto-shutdown when idle)
2. Review video processing volumes
3. Optimize frame skip/resolution
4. Consider reserved instances

## Rollback Plan

If deployment fails:
1. [ ] Keep previous version accessible
2. [ ] Document rollback procedure
3. [ ] Test rollback in staging
4. [ ] Have database backup ready
5. [ ] Communicate downtime to users

---

**Deployment Date:** _________________

**Deployed By:** _________________

**Version:** _________________

**Notes:**

