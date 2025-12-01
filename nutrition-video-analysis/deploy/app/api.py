"""
FastAPI REST API for Nutrition Video Analysis
Provides endpoints for upload, status checking, and result retrieval
"""
import os
import uuid
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends, Header
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from app.config import settings, init_directories, validate_config
from app.models import ModelManager
from app.pipeline import NutritionVideoPipeline
from app.database import Database, JobStatus

# Initialize logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Video-based nutrition analysis using Florence-2, SAM2, Metric3D, and RAG"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
db = None
model_manager = None
pipeline = None


# Pydantic models for API
class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    status: str
    progress: Optional[float] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class NutritionSummary(BaseModel):
    total_food_volume_ml: float
    total_mass_g: float
    total_calories_kcal: float
    num_food_items: int


class ResultsResponse(BaseModel):
    job_id: str
    status: str
    video_name: str
    timestamp: str
    nutrition_summary: Optional[NutritionSummary] = None
    detailed_results: Optional[dict] = None


# API Key validation (optional)
async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key if authentication is enabled"""
    if not settings.REQUIRE_API_KEY:
        return True
    
    if not x_api_key or x_api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global db, model_manager, pipeline
    
    logger.info("Starting Nutrition Video Analysis API...")
    
    # Validate configuration
    if not validate_config():
        logger.error("Configuration validation failed")
        raise RuntimeError("Invalid configuration")
    
    # Create directories
    init_directories()
    
    # Initialize database
    logger.info("Initializing database...")
    db = Database(settings.DATABASE_URL)
    db.init_db()
    
    # Initialize models (lazy loading)
    logger.info("Initializing model manager...")
    model_manager = ModelManager(settings)
    
    # Skip model preloading in local testing - models load on demand
    # This prevents startup failures and speeds up API start time
    logger.info("Models will load on demand (lazy loading enabled)")
    
    # Initialize pipeline
    pipeline = NutritionVideoPipeline(model_manager, settings)
    
    logger.info("✓ API ready to accept requests")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down...")
    if model_manager:
        model_manager.clear_cache()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
        "device": settings.DEVICE
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    import torch
    
    return {
        "status": "healthy",
        "gpu_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "models_loaded": bool(model_manager._florence2 or model_manager._sam2),
        "database": "connected" if db else "not initialized"
    }


@app.post("/api/upload", response_model=JobResponse, dependencies=[Depends(verify_api_key)])
async def upload_video(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Upload a video for nutrition analysis
    
    Args:
        file: Video file (mp4, avi, mov, mkv)
        
    Returns:
        Job ID and status
    """
    logger.info(f"Received upload request: {file.filename}")
    
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file format. Allowed: {settings.ALLOWED_FORMATS}"
        )
    
    # Validate file size
    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    
    if file_size_mb > settings.MAX_VIDEO_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file_size_mb:.1f}MB). Max: {settings.MAX_VIDEO_SIZE_MB}MB"
        )
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Save uploaded file
    upload_path = settings.UPLOAD_DIR / f"{job_id}{file_ext}"
    with open(upload_path, "wb") as f:
        f.write(contents)
    
    logger.info(f"Saved video: {upload_path} ({file_size_mb:.1f}MB)")
    
    # Create job in database
    db.create_job(
        job_id=job_id,
        video_name=file.filename,
        video_path=str(upload_path),
        status=JobStatus.PENDING
    )
    
    # Queue async processing
    background_tasks.add_task(process_video_background, job_id, upload_path)
    
    logger.info(f"Job {job_id} queued for processing")
    
    return JobResponse(
        job_id=job_id,
        status="processing",
        message="Video uploaded successfully and queued for processing"
    )


async def process_video_background(job_id: str, video_path: Path):
    """
    Background task for video processing
    
    Args:
        job_id: Unique job identifier
        video_path: Path to uploaded video
    """
    try:
        logger.info(f"[{job_id}] Starting background processing...")
        
        # Update status to processing
        db.update_job_status(job_id, JobStatus.PROCESSING)
        
        # Run pipeline
        results = pipeline.process_video(video_path, job_id)
        
        # Save results
        output_path = settings.OUTPUT_DIR / f"{job_id}_results.json"
        import json
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Update database
        db.update_job_results(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            results_path=str(output_path),
            total_calories=results['nutrition']['summary']['total_calories_kcal'],
            num_food_items=results['nutrition']['summary']['num_food_items']
        )
        
        logger.info(f"[{job_id}] ✓ Processing completed")
        
    except Exception as e:
        logger.error(f"[{job_id}] Processing failed: {e}", exc_info=True)
        
        db.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=str(e)
        )


@app.get("/api/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """
    Get processing status for a job
    
    Args:
        job_id: Job identifier from upload
        
    Returns:
        Current job status and metadata
    """
    job = db.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return StatusResponse(
        job_id=job['job_id'],
        status=job['status'],
        progress=None,  # Could implement progress tracking
        error=job.get('error_message'),
        created_at=job['created_at'],
        completed_at=job.get('completed_at')
    )


@app.get("/api/results/{job_id}", response_model=ResultsResponse)
async def get_results(job_id: str, detailed: bool = False):
    """
    Get nutrition analysis results
    
    Args:
        job_id: Job identifier
        detailed: Include full object-level details (default: False)
        
    Returns:
        Nutrition analysis results
    """
    job = db.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job['status'] != JobStatus.COMPLETED:
        return ResultsResponse(
            job_id=job_id,
            status=job['status'],
            video_name=job['video_name'],
            timestamp=job['created_at'].isoformat()
        )
    
    # Load results from file
    import json
    results_path = Path(job['results_path'])
    
    if not results_path.exists():
        raise HTTPException(status_code=500, detail="Results file not found")
    
    with open(results_path, 'r') as f:
        full_results = json.load(f)
    
    response = ResultsResponse(
        job_id=job_id,
        status=job['status'],
        video_name=job['video_name'],
        timestamp=full_results['timestamp'],
        nutrition_summary=NutritionSummary(**full_results['nutrition']['summary'])
    )
    
    if detailed:
        response.detailed_results = full_results
    
    return response


@app.get("/api/download/{job_id}")
async def download_results(job_id: str):
    """
    Download full results as JSON file
    
    Args:
        job_id: Job identifier
        
    Returns:
        JSON file download
    """
    job = db.get_job(job_id)
    
    if not job or job['status'] != JobStatus.COMPLETED:
        raise HTTPException(status_code=404, detail="Results not available")
    
    results_path = Path(job['results_path'])
    
    if not results_path.exists():
        raise HTTPException(status_code=500, detail="Results file not found")
    
    return FileResponse(
        path=results_path,
        media_type='application/json',
        filename=f"nutrition_results_{job_id}.json"
    )


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str, dependencies=[Depends(verify_api_key)]):
    """
    Delete a job and its associated files
    
    Args:
        job_id: Job identifier
        
    Returns:
        Deletion confirmation
    """
    job = db.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete video file
    if job.get('video_path'):
        video_path = Path(job['video_path'])
        if video_path.exists():
            video_path.unlink()
    
    # Delete results file
    if job.get('results_path'):
        results_path = Path(job['results_path'])
        if results_path.exists():
            results_path.unlink()
    
    # Delete from database
    db.delete_job(job_id)
    
    return {"message": f"Job {job_id} deleted successfully"}


@app.get("/api/jobs")
async def list_jobs(status: Optional[str] = None, limit: int = 100):
    """
    List all jobs with optional filtering
    
    Args:
        status: Filter by status (pending, processing, completed, failed)
        limit: Maximum number of jobs to return
        
    Returns:
        List of jobs
    """
    jobs = db.list_jobs(status=status, limit=limit)
    return {"jobs": jobs, "count": len(jobs)}


if __name__ == "__main__":
    # Run with: python api.py
    uvicorn.run(
        "api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )


