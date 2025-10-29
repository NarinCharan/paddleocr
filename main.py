from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from paddleocr import PaddleOCR
import requests
from typing import Optional
import tempfile
import os

# Create the FastAPI application
app = FastAPI(
    title="PaddleOCR API",
    description="OCR service powered by PaddleOCR",
    version="1.0.0"
)

# Initialize PaddleOCR (this happens once when the app starts)
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
    
    # Create a temporary file to store the image
    temp_file = None
    
    try:
        # Get the image bytes from either the file upload or URL
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
        
        # Save to a temporary file (PaddleOCR works best with file paths)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name
        
        # Run OCR on the temporary file
        try:
            result = ocr.ocr(temp_file_path, cls=True)
            
            return {
                "success": True,
                "results": result
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    finally:
        # Clean up the temporary file
        if temp_file and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
```

---

## 🎓 **What This Version Does Differently**

1. **Uses temporary files** - PaddleOCR works most reliably with file paths
2. **Simpler dependencies** - No need for PIL or numpy conversions
3. **Automatic cleanup** - Deletes temp files after processing
4. **Better error messages** - Will show the actual error from PaddleOCR

---

## 🔄 **Deploy Steps**

1. **Update `main.py`** on GitHub with the simplified version above
2. **Update `requirements.txt`** (add numpy if you want, but it should already come with paddlepaddle)
3. **Commit changes**
4. **Let Coolify redeploy**
5. **Try the OCR again** with this URL:
```
   https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/release/2.6/doc/imgs_en/img_12.jpg
