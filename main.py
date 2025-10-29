from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from paddleocr import PaddleOCR
import io
import requests
from typing import Optional

# Create the FastAPI application
app = FastAPI(
    title="PaddleOCR API",
    description="OCR service powered by PaddleOCR",
    version="1.0.0"
)

# Initialize PaddleOCR (this happens once when the app starts)
# use_angle_cls=True means it can handle rotated text
# lang='en' means English (change to 'ch' for Chinese, etc.)
ocr = PaddleOCR(use_angle_cls=True, lang='en')

@app.get("/")
async def root():
    """
    Health check endpoint - just returns a message to confirm the API is running
    """
    return {
        "message": "PaddleOCR API is running",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.post("/ocr")
async def run_ocr(
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None)
):
    """
    OCR endpoint - accepts either a file upload OR a URL to an image
    
    Parameters:
    - file: Upload an image file directly
    - file_url: Or provide a URL to an image
    
    Returns JSON with OCR results
    """
    
    # Get the image bytes from either the file upload or URL
    if file_url:
        try:
            response = requests.get(file_url, timeout=10)
            response.raise_for_status()
            file_bytes = response.content
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to download image: {str(e)}")
    
    elif file:
        file_bytes = await file.read()
    
    else:
        raise HTTPException(status_code=400, detail="Please provide either a file or file_url")
    
    # Run OCR on the image
    try:
        # Convert bytes to a format PaddleOCR can read
        image_stream = io.BytesIO(file_bytes)
        result = ocr.ocr(image_stream, cls=True)
        
        return {
            "success": True,
            "results": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
