from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from paddleocr import PaddleOCR
import requests
from typing import Optional
import tempfile
import os

app = FastAPI(
    title="PaddleOCR API",
    description="OCR service powered by PaddleOCR",
    version="1.0.0"
)

ocr = PaddleOCR(use_angle_cls=True, lang='en')

@app.get("/")
async def root():
    return {
        "message": "PaddleOCR API is running",
        "version": "1.0.0",
        "docs": "/docs",
        "test": "/test"
    }

@app.get("/test")
async def test_page():
    """
    Serve the test HTML page
    """
    return FileResponse("test.html")

@app.post("/ocr")
async def run_ocr(
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None)
):
    temp_file_path = None
    
    try:
        # Validate that we have at least one input
        if not file_url and (not file or not file.filename):
            raise HTTPException(
                status_code=400, 
                detail="Please provide either a file upload or a file_url"
            )
        
        # Get image bytes from URL
        if file_url and file_url.strip():
            try:
                response = requests.get(file_url, timeout=10)
                response.raise_for_status()
                image_bytes = response.content
            except Exception as e:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to download image: {str(e)}"
                )
        # Get image bytes from uploaded file
        elif file and file.filename:
            image_bytes = await file.read()
        else:
            raise HTTPException(
                status_code=400, 
                detail="Please provide either a file upload or a file_url"
            )
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name
        
        # Run OCR
        try:
            result = ocr.ocr(temp_file_path, cls=True)
            
            return {
                "success": True,
                "results": result
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"OCR processing failed: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error: {str(e)}"
        )
    
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
