from fastapi import FastAPI, UploadFile, File, Form, HTTPException
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
        "docs": "/docs"
    }

@app.post("/ocr")
async def run_ocr(
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None)
):
    temp_file = None
    temp_file_path = None
    
    try:
        if file_url:
            try:
                response = requests.get(file_url, timeout=10)
                response.raise_for_status()
                image_bytes = response.content
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to download image: {str(e)}")
        
        elif file:
            image_bytes = await file.read()
        
        else:
            raise HTTPException(status_code=400, detail="Please provide either a file or file_url")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name
        
        try:
            result = ocr.ocr(temp_file_path, cls=True)
            
            return {
                "success": True,
                "results": result
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
