from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from paddleocr import PaddleOCR
from pdf2image import convert_from_bytes
import requests
from typing import Optional, List
import tempfile
import os
import time
import hashlib
from datetime import datetime
import io

app = FastAPI(
    title="OCR Microservice",
    description="Production OCR service powered by PaddleOCR",
    version="1.0.0"
)

# Initialize OCR (cached, one instance per language)
ocr_instances = {}

def get_ocr(language: str):
    """Get or create OCR instance for language"""
    if language not in ocr_instances:
        print(f"Initializing OCR for language: {language}")
        ocr_instances[language] = PaddleOCR(
            use_angle_cls=True, 
            lang=language,
            show_log=False
        )
    return ocr_instances[language]

@app.get("/")
async def root():
    return {
        "service": "OCR Microservice",
        "version": "1.0.0",
        "status": "running",
        "supported_languages": ["en", "ch", "fr", "german", "es", "pt", "ru", "ar", "ja", "ko"],
        "endpoints": {
            "ocr": "/ocr",
            "health": "/health",
            "languages": "/languages"
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "ocr_instances_loaded": len(ocr_instances)
    }

def is_pdf(file_bytes: bytes) -> bool:
    """Check if file is PDF"""
    return file_bytes[:4] == b'%PDF'

def parse_pages(pages_param: str, total_pages: int, max_pages: int) -> List[int]:
    """
    Parse page parameter into list of page numbers
    
    Examples:
    - "all" → [1, 2, 3, 4, 5]
    - "first" → [1]
    - "last" → [5]
    - "1-3" → [1, 2, 3]
    - "1,3,5" → [1, 3, 5]
    """
    if pages_param == "all":
        return list(range(1, min(total_pages + 1, max_pages + 1)))
    
    if pages_param == "first":
        return [1]
    
    if pages_param == "last":
        return [total_pages]
    
    # Range: "1-3"
    if "-" in pages_param:
        start, end = pages_param.split("-")
        start = int(start)
        end = min(int(end), total_pages, max_pages)
        return list(range(start, end + 1))
    
    # Specific pages: "1,3,5"
    if "," in pages_param:
        page_list = [int(p.strip()) for p in pages_param.split(",")]
        return [p for p in page_list if 1 <= p <= total_pages and p <= max_pages]
    
    # Single page: "3"
    try:
        page = int(pages_param)
        if 1 <= page <= total_pages:
            return [page]
    except ValueError:
        pass
    
    return [1]  # Default to first page

@app.post("/ocr")
async def extract_text(
    # INPUT SOURCE
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None),
    
    # OCR CONFIGURATION
    language: str = Form("en"),
    
    # PAGE HANDLING
    pages: str = Form("all"),
    max_pages: int = Form(50),
    
    # OUTPUT OPTIONS
    include_confidence: bool = Form(True),
    include_coordinates: bool = Form(False),
    include_metadata: bool = Form(False),
    
    # PREPROCESSING
    auto_rotate: bool = Form(True),
    enhance_quality: bool = Form(False),
    
    # TRACKING
    request_id: Optional[str] = Form(None)
):
    """
    Extract text from PDF or image using OCR
    """
    
    start_time = time.time()
    temp_dir = None
    
    try:
        # Generate request ID if not provided
        if not request_id:
            request_id = hashlib.md5(
                f"{time.time()}".encode()
            ).hexdigest()[:12]
        
        print(f"[{request_id}] Starting OCR request")
        
        # Validate input
        if not file and not file_url:
            raise HTTPException(
                status_code=400,
                detail="Either 'file' or 'file_url' must be provided"
            )
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        
        # Get file bytes
        if file_url:
            print(f"[{request_id}] Downloading from URL: {file_url}")
            try:
                response = requests.get(file_url, timeout=30)
                response.raise_for_status()
                file_bytes = response.content
                filename = file_url.split("/")[-1]
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to download file: {str(e)}"
                )
        else:
            print(f"[{request_id}] Processing uploaded file: {file.filename}")
            file_bytes = await file.read()
            filename = file.filename
        
        # Detect file type
        is_pdf_file = is_pdf(file_bytes)
        print(f"[{request_id}] File type: {'PDF' if is_pdf_file else 'Image'}")
        
        # Get OCR instance for language
        ocr = get_ocr(language)
        
        # Process based on file type
        if is_pdf_file:
            print(f"[{request_id}] Converting PDF to images...")
            # Convert PDF to images
            images = convert_from_bytes(
                file_bytes,
                dpi=200,
                fmt='jpeg'
            )
            
            total_pages = len(images)
            print(f"[{request_id}] PDF has {total_pages} pages")
            
            # Parse which pages to process
            pages_to_process = parse_pages(pages, total_pages, max_pages)
            print(f"[{request_id}] Processing pages: {pages_to_process}")
            
            # Process selected pages
            all_results = []
            all_text = []
            total_confidence = 0
            confidence_count = 0
            
            for page_num in pages_to_process:
                print(f"[{request_id}] OCR on page {page_num}...")
                
                # Convert PIL image to bytes
                img_byte_arr = io.BytesIO()
                images[page_num - 1].save(img_byte_arr, format='JPEG')
                img_bytes = img_byte_arr.getvalue()
                
                # Save temporarily
                temp_img_path = os.path.join(temp_dir, f"page_{page_num}.jpg")
                with open(temp_img_path, 'wb') as f:
                    f.write(img_bytes)
                
                # Run OCR
                result = ocr.ocr(temp_img_path, cls=auto_rotate)
                
                if result and result[0]:
                    page_text_lines = []
                    page_data = {
                        "page_number": page_num,
                        "lines": []
                    }
                    
                    for line in result[0]:
                        text = line[1][0]
                        confidence = line[1][1]
                        bbox = line[0] if include_coordinates else None
                        
                        page_text_lines.append(text)
                        total_confidence += confidence
                        confidence_count += 1
                        
                        if include_confidence or include_coordinates:
                            line_data = {"text": text}
                            if include_confidence:
                                line_data["confidence"] = round(confidence, 4)
                            if include_coordinates:
                                line_data["bbox"] = bbox
                            page_data["lines"].append(line_data)
                    
                    page_text = "\n".join(page_text_lines)
                    all_text.append(page_text)
                    
                    if include_confidence or include_coordinates:
                        page_data["text"] = page_text
                        all_results.append(page_data)
            
            combined_text = "\n\n".join(all_text)
            avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 0
            
        else:
            # Single image processing
            print(f"[{request_id}] Processing single image...")
            temp_img_path = os.path.join(temp_dir, filename)
            with open(temp_img_path, 'wb') as f:
                f.write(file_bytes)
            
            result = ocr.ocr(temp_img_path, cls=auto_rotate)
            
            if not result or not result[0]:
                combined_text = ""
                avg_confidence = 0
                all_results = []
                total_pages = 1
                pages_to_process = []
            else:
                text_lines = []
                total_confidence = 0
                page_data = {"page_number": 1, "lines": []}
                
                for line in result[0]:
                    text = line[1][0]
                    confidence = line[1][1]
                    bbox = line[0] if include_coordinates else None
                    
                    text_lines.append(text)
                    total_confidence += confidence
                    
                    if include_confidence or include_coordinates:
                        line_data = {"text": text}
                        if include_confidence:
                            line_data["confidence"] = round(confidence, 4)
                        if include_coordinates:
                            line_data["bbox"] = bbox
                        page_data["lines"].append(line_data)
                
                combined_text = "\n".join(text_lines)
                avg_confidence = total_confidence / len(result[0]) if len(result[0]) > 0 else 0
                all_results = [page_data] if (include_confidence or include_coordinates) else []
                total_pages = 1
                pages_to_process = [1]
        
        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        print(f"[{request_id}] Processing complete in {processing_time_ms}ms")
        
        # Build response
        response = {
            "success": True,
            "request_id": request_id,
            "text": combined_text,
            "pages_processed": len(pages_to_process),
            "processing_time_ms": processing_time_ms
        }
        
        if include_confidence:
            response["confidence"] = round(avg_confidence, 4)
        
        if (include_coordinates or include_confidence) and all_results:
            response["pages"] = all_results
        
        if include_metadata:
            response["metadata"] = {
                "file_type": "pdf" if is_pdf_file else "image",
                "total_pages": total_pages if is_pdf_file else 1,
                "language": language,
                "preprocessing": {
                    "auto_rotate": auto_rotate,
                    "enhance_quality": enhance_quality
                },
                "ocr_version": "PaddleOCR 2.8.1",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[{request_id}] Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing failed: {str(e)}"
        )
    
    finally:
        # Cleanup
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass

@app.get("/languages")
async def list_languages():
    """List supported OCR languages"""
    return {
        "supported_languages": [
            {"code": "en", "name": "English"},
            {"code": "ch", "name": "Chinese (Simplified)"},
            {"code": "chinese_cht", "name": "Chinese (Traditional)"},
            {"code": "fr", "name": "French"},
            {"code": "german", "name": "German"},
            {"code": "es", "name": "Spanish"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "ru", "name": "Russian (Cyrillic)"},
            {"code": "ar", "name": "Arabic"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"}
        ]
    }
