from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from paddleocr import PaddleOCR
import requests
from typing import Optional
import tempfile
import os
from pdf2image import convert_from_path, convert_from_bytes
from PIL import Image
import io

app = FastAPI(
    title="PaddleOCR API",
    description="OCR service powered by PaddleOCR - supports images and PDFs",
    version="2.0.0"
)

ocr = PaddleOCR(use_angle_cls=True, lang='en')

@app.get("/")
async def root():
    return {
        "message": "PaddleOCR API is running",
        "version": "2.0.0",
        "features": ["images", "pdfs", "multi-page"],
        "docs": "/docs",
        "test": "/test"
    }

@app.get("/test")
async def test_page():
    """
    Serve the test HTML page
    """
    return FileResponse("test.html")

def is_pdf(file_bytes: bytes) -> bool:
    """Check if file is a PDF by looking at magic bytes"""
    return file_bytes[:4] == b'%PDF'

def process_image_bytes(image_bytes: bytes, temp_dir: str) -> dict:
    """Process a single image and return OCR results"""
    temp_file_path = None
    try:
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg', dir=temp_dir) as temp_file:
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name
        
        # Run OCR
        result = ocr.ocr(temp_file_path, cls=True)
        return {"success": True, "data": result}
    
    except Exception as e:
        return {"success": False, "error": str(e)}
    
    finally:
        # Clean up
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass

def process_pdf_bytes(pdf_bytes: bytes, temp_dir: str, max_pages: int = 50) -> dict:
    """Convert PDF to images and process each page"""
    try:
        # Convert PDF to images (one per page)
        images = convert_from_bytes(
            pdf_bytes,
            dpi=200,  # Good balance between quality and speed
            fmt='jpeg'
        )
        
        total_pages = len(images)
        
        # Check page limit
        if total_pages > max_pages:
            return {
                "success": False,
                "error": f"PDF has {total_pages} pages. Maximum allowed is {max_pages} pages."
            }
        
        # Process each page
        results = {}
        for page_num, image in enumerate(images, start=1):
            # Convert PIL Image to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_bytes = img_byte_arr.getvalue()
            
            # Process the page
            page_result = process_image_bytes(img_bytes, temp_dir)
            
            if page_result["success"]:
                results[f"page_{page_num}"] = page_result["data"]
            else:
                results[f"page_{page_num}"] = {"error": page_result["error"]}
        
        return {
            "success": True,
            "document_type": "pdf",
            "total_pages": total_pages,
            "results": results
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"PDF processing failed: {str(e)}"
        }

@app.post("/ocr")
async def run_ocr(
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None),
    max_pages: Optional[int] = Form(50)
):
    """
    OCR endpoint - accepts images or PDFs via upload or URL
    
    Parameters:
    - file: Upload an image or PDF file directly
    - file_url: Or provide a URL to an image or PDF
    - max_pages: Maximum number of pages to process for PDFs (default: 50)
    
    Returns JSON with OCR results
    """
    
    temp_dir = None
    
    try:
        # Create temporary directory for this request
        temp_dir = tempfile.mkdtemp()
        
        # Validate input
        if not file_url and (not file or not file.filename):
            raise HTTPException(
                status_code=400, 
                detail="Please provide either a file upload or a file_url"
            )
        
        # Get file bytes from URL
        if file_url and file_url.strip():
            try:
                response = requests.get(file_url, timeout=30)
                response.raise_for_status()
                file_bytes = response.content
                filename = file_url.split('/')[-1].lower()
            except Exception as e:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to download file: {str(e)}"
                )
        
        # Get file bytes from upload
        elif file and file.filename:
            file_bytes = await file.read()
            filename = file.filename.lower()
        
        else:
            raise HTTPException(
                status_code=400, 
                detail="Please provide either a file upload or a file_url"
            )
        
        # Check if it's a PDF
        if is_pdf(file_bytes):
            # Process as PDF
            result = process_pdf_bytes(file_bytes, temp_dir, max_pages)
            
            if not result["success"]:
                raise HTTPException(
                    status_code=400,
                    detail=result["error"]
                )
            
            return result
        
        else:
            # Process as single image
            result = process_image_bytes(file_bytes, temp_dir)
            
            if not result["success"]:
                raise HTTPException(
                    status_code=500,
                    detail=f"OCR processing failed: {result['error']}"
                )
            
            return {
                "success": True,
                "document_type": "image",
                "results": result["data"]
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error: {str(e)}"
        )
    
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass
