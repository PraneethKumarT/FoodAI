"""
Run API locally without Docker
For development and testing
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set environment variables (edit these!)
os.environ.setdefault("GEMINI_API_KEY", "AIzaSyBI52gm0JaJbMbM0xeqO9EuN86p88gIHj0")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/nutrition.db")
os.environ.setdefault("DEVICE", "cuda")  # or "cpu" if no GPU
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("SAM2_CHECKPOINT", "D:/Nutrition5k/Grounded-SAM-2/checkpoints/sam2.1_hiera_base_plus.pt")
os.environ.setdefault("SAM2_CONFIG", "D:/Nutrition5k/Grounded-SAM-2/configs/sam2.1/sam2.1_hiera_b+.yaml")
os.environ.setdefault("DENSITY_PDF_PATH", "D:/Nutrition5k/Grounded-SAM-2/rag/ap815e.pdf")
os.environ.setdefault("FNDDS_EXCEL_PATH", "D:/Nutrition5k/Grounded-SAM-2/rag/FNDDS.xlsx")
os.environ.setdefault("COFID_EXCEL_PATH", "D:/Nutrition5k/Grounded-SAM-2/rag/CoFID.xlsx")
os.environ.setdefault("UPLOAD_DIR", "D:/Nutrition5k/Grounded-SAM-2/deploy/data/uploads")
os.environ.setdefault("OUTPUT_DIR", "D:/Nutrition5k/Grounded-SAM-2/deploy/data/outputs")
os.environ.setdefault("MAX_FRAMES", "30")  # Quick test - fewer frames
os.environ.setdefault("FRAME_SKIP", "10")  # Process every 10th frame
os.environ.setdefault("RESIZE_WIDTH", "800")  # Smaller for faster processing

# Import and run API
if __name__ == "__main__":
    print("="*60)
    print("Running Nutrition API Locally (No Docker)")
    print("="*60)
    print(f"Device: {os.environ.get('DEVICE')}")
    print(f"Upload Dir: {os.environ.get('UPLOAD_DIR')}")
    print(f"Max Frames: {os.environ.get('MAX_FRAMES')}")
    print()
    print("API will be available at: http://localhost:8000")
    print("Docs at: http://localhost:8000/docs")
    print("="*60)
    print()
    
    import uvicorn
    from app.api import app
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

