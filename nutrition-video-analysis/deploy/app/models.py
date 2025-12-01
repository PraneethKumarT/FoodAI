"""
Model Loading and Caching
Handles initialization of Florence-2, SAM2, Metric3D, and RAG system
"""
import torch
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any
from functools import lru_cache
import logging

from transformers import AutoProcessor, AutoModelForCausalLM
from sam2.build_sam import build_sam2_video_predictor

logger = logging.getLogger(__name__)


class ModelCache:
    """Singleton class to cache loaded models"""
    _instance = None
    _models = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get(self, key: str):
        return self._models.get(key)
    
    def set(self, key: str, model: Any):
        self._models[key] = model
    
    def clear(self):
        """Clear all cached models to free memory"""
        self._models.clear()
        torch.cuda.empty_cache()


# Global cache instance
model_cache = ModelCache()


def load_florence2(model_name: str = "microsoft/Florence-2-base-ft", device: str = "cuda") -> tuple:
    """
    Load Florence-2 model and processor
    
    Args:
        model_name: HuggingFace model name
        device: Device to load model on
        
    Returns:
        (processor, model) tuple
    """
    cache_key = f"florence2_{model_name}_{device}"
    cached = model_cache.get(cache_key)
    if cached:
        logger.info(f"Using cached Florence-2 model")
        return cached
    
    logger.info(f"Loading Florence-2 model: {model_name}...")
    
    processor = AutoProcessor.from_pretrained(
        model_name,
        trust_remote_code=True,
        cache_dir=None  # Use default HF cache
    )
    
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        cache_dir=None
    ).to(device)
    
    model.eval()
    
    result = (processor, model)
    model_cache.set(cache_key, result)
    
    logger.info(f"✓ Florence-2 loaded successfully")
    return result


def load_sam2(config_path: str, checkpoint_path: str, device: str = "cuda"):
    """
    Load SAM2 video predictor
    
    Args:
        config_path: Path to SAM2 config YAML
        checkpoint_path: Path to SAM2 checkpoint
        device: Device to load model on
        
    Returns:
        SAM2 video predictor
    """
    cache_key = f"sam2_{checkpoint_path}_{device}"
    cached = model_cache.get(cache_key)
    if cached:
        logger.info("Using cached SAM2 model")
        return cached
    
    logger.info(f"Loading SAM2 model: {checkpoint_path}...")
    
    predictor = build_sam2_video_predictor(
        config_file=config_path,
        ckpt_path=checkpoint_path,
        device=device
    )
    
    model_cache.set(cache_key, predictor)
    
    logger.info("✓ SAM2 loaded successfully")
    return predictor


def load_metric3d(model_name: str = "metric3d_vit_small", device: str = "cuda"):
    """
    Load Metric3D depth estimation model
    
    Args:
        model_name: Metric3D model variant
        device: Device to load model on
        
    Returns:
        Metric3D model
    """
    cache_key = f"metric3d_{model_name}_{device}"
    cached = model_cache.get(cache_key)
    if cached:
        logger.info("Using cached Metric3D model")
        return cached
    
    logger.info(f"Loading Metric3D model: {model_name}...")
    
    try:
        model = torch.hub.load(
            'yvanyin/metric3d',
            model_name,
            pretrain=True
        )
        model = model.to(device)
        model.eval()
        
        model_cache.set(cache_key, model)
        logger.info("✓ Metric3D loaded successfully")
        return model
        
    except Exception as e:
        logger.error(f"Failed to load Metric3D: {e}")
        raise


def load_nutrition_rag(
    pdf_path: Path,
    fndds_path: Path,
    cofid_path: Path,
    gemini_api_key: Optional[str] = None
):
    """
    Load and initialize Nutrition RAG system
    
    Args:
        pdf_path: Path to density PDF
        fndds_path: Path to FNDDS Excel
        cofid_path: Path to CoFID Excel
        gemini_api_key: Optional Gemini API key for fallback
        
    Returns:
        Initialized NutritionRAG instance
    """
    cache_key = "nutrition_rag"
    cached = model_cache.get(cache_key)
    if cached:
        logger.info("Using cached NutritionRAG system")
        return cached
    
    logger.info("Loading Nutrition RAG system...")
    
    # Import here to avoid circular dependency
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from nutrition_rag_system import NutritionRAG
    
    # Set Gemini API key if provided
    if gemini_api_key:
        import os
        os.environ['GEMINI_API_KEY'] = gemini_api_key
    
    rag = NutritionRAG(
        pdf_path=pdf_path,
        fndds_path=fndds_path,
        cofid_path=cofid_path
    )
    
    # Pre-load databases
    rag.extract_density_from_pdf()
    rag.load_calorie_databases()
    rag.build_faiss_index()
    
    model_cache.set(cache_key, rag)
    logger.info("✓ NutritionRAG loaded successfully")
    
    return rag


class ModelManager:
    """High-level model management interface"""
    
    def __init__(self, config):
        self.config = config
        self.device = config.DEVICE
        
        # Models will be loaded on demand
        self._florence2 = None
        self._sam2 = None
        self._metric3d = None
        self._rag = None
    
    @property
    def florence2(self):
        """Lazy load Florence-2"""
        if self._florence2 is None:
            self._florence2 = load_florence2(
                model_name=self.config.FLORENCE2_MODEL,
                device=self.device
            )
        return self._florence2
    
    @property
    def sam2(self):
        """Lazy load SAM2"""
        if self._sam2 is None:
            self._sam2 = load_sam2(
                config_path=self.config.SAM2_CONFIG,
                checkpoint_path=self.config.SAM2_CHECKPOINT,
                device=self.device
            )
        return self._sam2
    
    @property
    def metric3d(self):
        """Lazy load Metric3D"""
        if self._metric3d is None:
            self._metric3d = load_metric3d(
                model_name=self.config.METRIC3D_MODEL,
                device=self.device
            )
        return self._metric3d
    
    @property
    def rag(self):
        """Lazy load NutritionRAG"""
        if self._rag is None:
            self._rag = load_nutrition_rag(
                pdf_path=self.config.DENSITY_PDF_PATH,
                fndds_path=self.config.FNDDS_EXCEL_PATH,
                cofid_path=self.config.COFID_EXCEL_PATH,
                gemini_api_key=self.config.GEMINI_API_KEY
            )
        return self._rag
    
    def preload_all(self):
        """Preload all models (useful for container warmup)"""
        logger.info("Preloading all models...")
        _ = self.florence2
        _ = self.sam2
        _ = self.metric3d
        _ = self.rag
        logger.info("✓ All models preloaded")
    
    def clear_cache(self):
        """Clear all cached models"""
        self._florence2 = None
        self._sam2 = None
        self._metric3d = None
        self._rag = None
        model_cache.clear()
        logger.info("Model cache cleared")


# Test function
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from config import settings
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing model loading...")
    
    manager = ModelManager(settings)
    
    # Test lazy loading
    print("\n1. Testing Florence-2 lazy load...")
    proc, model = manager.florence2
    print(f"   ✓ Florence-2: {type(model).__name__}")
    
    print("\n2. Testing SAM2 lazy load...")
    sam2 = manager.sam2
    print(f"   ✓ SAM2: {type(sam2).__name__}")
    
    print("\nDone!")

