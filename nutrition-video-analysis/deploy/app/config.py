"""
Production Configuration Management
Supports environment variables and different deployment modes
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # API Settings
    API_TITLE: str = "Nutrition Video Analysis API"
    API_VERSION: str = "1.0.0"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    
    # File Storage
    UPLOAD_DIR: Path = Path("/app/data/uploads")
    OUTPUT_DIR: Path = Path("/app/data/outputs")
    MODEL_CACHE_DIR: Path = Path("/app/models")
    
    # Video Processing
    MAX_VIDEO_SIZE_MB: int = 500
    ALLOWED_FORMATS: list = [".mp4", ".avi", ".mov", ".mkv"]
    FRAME_SKIP: int = 10  # Process every Nth frame
    MAX_FRAMES: Optional[int] = 60  # None = process all
    RESIZE_WIDTH: int = 800
    
    # Model Settings
    SAM2_CHECKPOINT: str = "checkpoints/sam2.1_hiera_base_plus.pt"
    SAM2_CONFIG: str = "configs/sam2.1/sam2.1_hiera_b+.yaml"
    FLORENCE2_MODEL: str = "microsoft/Florence-2-base-ft"
    METRIC3D_MODEL: str = "metric3d_vit_small"
    
    # Tracking Settings
    DETECTION_INTERVAL: int = 30
    IOU_MATCH_THRESHOLD: float = 0.20
    CENTER_DISTANCE_THRESHOLD: float = 200.0
    LABEL_SIMILARITY_BOOST: float = 0.20
    
    # Object Filtering
    GENERIC_OBJECTS: list = ['table', 'tablecloth', 'menu card', 'background', 'setting', 'surface']
    MIN_BOX_AREA: int = 500
    
    # Nutrition Analysis
    REFERENCE_PLATE_DIAMETER_CM: float = 25.0
    DENSITY_PDF_PATH: Path = Path("/app/data/rag/ap815e.pdf")
    FNDDS_EXCEL_PATH: Path = Path("/app/data/rag/FNDDS.xlsx")
    COFID_EXCEL_PATH: Path = Path("/app/data/rag/CoFID.xlsx")
    CALORIE_SIMILARITY_THRESHOLD: float = 0.5
    
    # External APIs
    GEMINI_API_KEY: Optional[str] = None
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/nutrition.db"  # PostgreSQL: postgresql://user:pass@host/db
    
    # Cache
    REDIS_URL: Optional[str] = None  # e.g., "redis://localhost:6379"
    CACHE_MODELS: bool = True
    
    # GPU/Compute
    DEVICE: str = "cuda"  # "cuda" or "cpu"
    USE_FP16: bool = True  # Half precision for 2x speedup
    BATCH_SIZE: int = 1  # Increase for more GPU memory
    
    # Job Queue
    QUEUE_TYPE: str = "memory"  # "memory", "redis", or "sqs"
    SQS_QUEUE_URL: Optional[str] = None
    MAX_CONCURRENT_JOBS: int = 3
    JOB_TIMEOUT_SECONDS: int = 3600  # 1 hour
    
    # Security
    CORS_ORIGINS: list = ["*"]  # In production: ["https://yourdomain.com"]
    MAX_REQUESTS_PER_MINUTE: int = 10
    API_KEY_HEADER: str = "X-API-Key"
    REQUIRE_API_KEY: bool = False
    
    # Logging
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    LOG_FORMAT: str = "json"  # "json" or "text"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


def init_directories():
    """Create required directories if they don't exist"""
    dirs = [
        settings.UPLOAD_DIR,
        settings.OUTPUT_DIR,
        settings.MODEL_CACHE_DIR,
        settings.DENSITY_PDF_PATH.parent,
    ]
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)


def get_device():
    """Get compute device (cuda/cpu) with error handling"""
    import torch
    if settings.DEVICE == "cuda" and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def validate_config():
    """Validate configuration before starting"""
    errors = []
    
    # Check Gemini API key if required
    if not settings.GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY not set - calorie fallback will be limited")
    
    # Check model files exist (in production)
    if not settings.DEBUG:
        model_path = Path(settings.SAM2_CHECKPOINT)
        if not model_path.exists() and not model_path.is_absolute():
            errors.append(f"SAM2 checkpoint not found: {settings.SAM2_CHECKPOINT}")
    
    # Check GPU availability
    import torch
    if settings.DEVICE == "cuda" and not torch.cuda.is_available():
        errors.append("CUDA requested but not available - falling back to CPU")
        settings.DEVICE = "cpu"
    
    if errors:
        print("⚠️  Configuration warnings:")
        for error in errors:
            print(f"  - {error}")
    
    return len([e for e in errors if "not found" in e]) == 0  # Only fail on critical errors


if __name__ == "__main__":
    print("Current Configuration:")
    print(f"  Upload Dir: {settings.UPLOAD_DIR}")
    print(f"  Output Dir: {settings.OUTPUT_DIR}")
    print(f"  Device: {get_device()}")
    print(f"  Database: {settings.DATABASE_URL}")
    print(f"  Gemini API: {'✓ Configured' if settings.GEMINI_API_KEY else '✗ Not set'}")
    print(f"\nValidation: {'✓ Passed' if validate_config() else '✗ Failed'}")

