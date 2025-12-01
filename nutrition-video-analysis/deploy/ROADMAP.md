# 🗺️ Deployment Roadmap

Your path from research code to production deployment.

## ✅ Phase 1: Code Refactoring (COMPLETED)

**Duration:** Completed
**Status:** ✅ Done

- [x] Extract pipeline into clean modules
- [x] Create configuration management
- [x] Implement model caching
- [x] Add error handling
- [x] Create database layer
- [x] Build REST API
- [x] Docker containerization
- [x] Write documentation

**Deliverables:**
- Production-ready code in `deploy/app/`
- Docker setup in `deploy/`
- Complete documentation

---

## 🔄 Phase 2: Local Testing (NEXT - 1-2 days)

**Status:** 🎯 **START HERE**

### Day 1: Setup & Basic Testing

**Morning (2-3 hours):**
1. ✅ Setup environment
   ```bash
   cd deploy
   cp env.example .env
   # Add GEMINI_API_KEY
   ```

2. ✅ Copy dependencies
   ```bash
   # Copy SAM2 checkpoints
   # Copy nutrition database files (PDF, Excel)
   ```

3. ✅ Build Docker image
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

**Afternoon (2-3 hours):**
4. ✅ Test API endpoints
   ```bash
   python test_api.py path/to/test_video.mp4
   ```

5. ✅ Verify results
   - Check nutrition estimates
   - Review logs for errors
   - Test with multiple videos

6. ✅ Performance tuning
   - Adjust `FRAME_SKIP` for speed
   - Test `RESIZE_WIDTH` settings
   - Enable `USE_FP16` if supported

### Day 2: Edge Cases & Optimization

7. ✅ Test edge cases
   - Large videos (>100MB)
   - Short videos (<5 seconds)
   - Low quality videos
   - Multiple concurrent uploads

8. ✅ Monitor resources
   - GPU utilization (`nvidia-smi`)
   - Memory usage
   - Processing time

9. ✅ Optimize configuration
   - Find optimal frame skip
   - Balance speed vs accuracy
   - Test different video resolutions

**Success Criteria:**
- [ ] API responds to all endpoints
- [ ] Video processing completes successfully
- [ ] Nutrition results are reasonable (±20% accuracy)
- [ ] Processing time < 5 min for 30-second video
- [ ] No memory leaks after 10 videos

---

## ☁️ Phase 3: Cloud Deployment (Week 1)

**Duration:** 3-5 days
**Status:** ⏳ Pending Phase 2 completion

### Day 1-2: Infrastructure Setup

**AWS EC2 Deployment:**
1. ⏳ Create AWS account / Access existing account
2. ⏳ Launch GPU instance (g4dn.xlarge)
   - Region: us-east-1 (cheapest)
   - AMI: Ubuntu 22.04 LTS with Deep Learning
   - Storage: 100GB SSD
   - Security group: Allow ports 22, 80, 443, 8000

3. ⏳ SSH into instance
   ```bash
   ssh -i key.pem ubuntu@<instance-ip>
   ```

4. ⏳ Install dependencies
   ```bash
   # Docker
   curl -fsSL https://get.docker.com | sh
   
   # nvidia-docker
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
     sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   sudo apt-get update && sudo apt-get install -y nvidia-docker2
   sudo systemctl restart docker
   ```

5. ⏳ Test GPU
   ```bash
   docker run --rm --gpus all nvidia/cuda:11.8.0-base nvidia-smi
   ```

**Alternative: Google Cloud Platform**
```bash
gcloud compute instances create nutrition-api \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --image-family=pytorch-latest-gpu \
  --boot-disk-size=100GB
```

### Day 3: Application Deployment

6. ⏳ Clone repository
   ```bash
   git clone <your-repo>
   cd Nutrition5k/Grounded-SAM-2/deploy
   ```

7. ⏳ Configure environment
   ```bash
   cp env.example .env
   nano .env  # Add production settings
   ```

8. ⏳ Deploy application
   ```bash
   ./start.sh
   ```

9. ⏳ Test from external network
   ```bash
   # From your local machine
   curl http://<instance-ip>:8000/health
   ```

### Day 4-5: Production Hardening

10. ⏳ Setup domain & SSL
    ```bash
    # Install NGINX
    sudo apt-get install nginx certbot python3-certbot-nginx
    
    # Get SSL certificate
    sudo certbot --nginx -d api.yourdomain.com
    ```

11. ⏳ Configure NGINX reverse proxy
    ```nginx
    server {
        listen 443 ssl;
        server_name api.yourdomain.com;
        
        location / {
            proxy_pass http://localhost:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
    ```

12. ⏳ Enable security
    - Set `REQUIRE_API_KEY=True`
    - Configure firewall (only 80, 443, 22)
    - Setup automatic backups

13. ⏳ Setup monitoring
    - CloudWatch/Stackdriver logging
    - Uptime monitoring (UptimeRobot)
    - Cost alerts

**Success Criteria:**
- [ ] API accessible via public IP
- [ ] SSL certificate installed (HTTPS)
- [ ] Processing works on cloud instance
- [ ] Monitoring configured
- [ ] Backups automated

---

## 🚀 Phase 4: Optimization & Scaling (Week 2)

**Status:** ⏳ Pending Phase 3

### Performance Optimization

14. ⏳ Enable FP16 precision
    ```env
    USE_FP16=True
    ```

15. ⏳ Optimize batch processing
    - Test different batch sizes
    - Implement request batching

16. ⏳ Benchmark performance
    - Measure throughput (videos/hour)
    - Identify bottlenecks
    - Profile GPU utilization

### Scaling

17. ⏳ Setup auto-scaling
    - Create AMI/image from instance
    - Configure auto-scaling group
    - Setup load balancer

18. ⏳ Add Redis for caching
    ```yaml
    # In docker-compose.yml
    redis:
      image: redis:7-alpine
    ```

19. ⏳ Implement job queue (SQS/Pub-Sub)
    - Move to async queue
    - Add retry logic
    - Dead letter queue for failures

**Success Criteria:**
- [ ] Processing time < 3 min per video
- [ ] Auto-scales from 1-5 instances
- [ ] Cost per video < $0.15
- [ ] 99.5% uptime

---

## 📱 Phase 5: Client Integration (Week 3-4)

**Status:** ⏳ Pending Phase 4

### Web Dashboard

20. ⏳ Create frontend (React/Next.js)
    - Video upload interface
    - Real-time progress tracking
    - Results visualization
    - Nutrition breakdown charts

21. ⏳ API client library
    - JavaScript/TypeScript SDK
    - Python SDK
    - Documentation

### Mobile Integration

22. ⏳ Mobile app (React Native/Flutter)
    - Camera integration
    - Upload from gallery
    - Offline support
    - Push notifications

**Success Criteria:**
- [ ] Web dashboard deployed
- [ ] Mobile app beta released
- [ ] API documentation complete
- [ ] User testing completed

---

## 🔬 Phase 6: Research & Improvement (Ongoing)

**Status:** ⏳ Continuous

### Accuracy Improvements

23. ⏳ Fine-tune models
    - Collect user feedback
    - Retrain on nutrition-specific data
    - A/B test model variants

24. ⏳ Enhanced RAG system
    - Expand nutrition database
    - Better food matching
    - Regional food databases

### New Features

25. ⏳ Meal planning
    - Dietary recommendations
    - Macro tracking
    - Recipe suggestions

26. ⏳ Multi-language support
    - Internationalize food names
    - Support regional cuisines

**Success Criteria:**
- [ ] Calorie accuracy > 90%
- [ ] User satisfaction > 4.5/5
- [ ] Processing cost < $0.10/video

---

## 📊 Timeline Overview

```
Week 1:  Local Testing + Cloud Setup
Week 2:  Production Deployment + Optimization
Week 3:  Scaling + Monitoring
Week 4:  Client Integration
Month 2: User Testing + Improvements
Month 3: Scale to 10K+ users
```

## 💰 Budget Projection

### Month 1 (Testing & Setup)
- Development instance: $50
- Testing costs: $20
- **Total: $70**

### Month 2 (MVP Launch)
- Production instance (g4dn.xlarge): $125
- Database (RDS): $25
- Storage: $10
- **Total: $160**

### Month 3 (Scaling)
- 3x instances (auto-scaled): $375
- Load balancer: $20
- Database: $50
- CDN: $30
- **Total: $475**

---

## 🎯 Current Status

**You are here:** ✅ Phase 1 Complete → 🎯 **Phase 2 Next**

**Next Action:** Run local tests
```bash
cd deploy
./start.sh
python test_api.py path/to/video.mp4
```

**ETA to Production:** 5-7 days (if testing goes smoothly)

---

**Questions?** Check [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md) for detailed next steps.

