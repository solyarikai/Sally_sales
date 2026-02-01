"""Google Drive API endpoints.

Upload files to Google Drive and convert to Google Docs/Sheets format.
"""
import os
import tempfile
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel

from app.services.google_drive_service import google_drive_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drive", tags=["Google Drive"])


class DriveUploadResponse(BaseModel):
    """Response from file upload."""
    success: bool
    file_id: Optional[str] = None
    view_url: Optional[str] = None
    name: Optional[str] = None
    error: Optional[str] = None


class DriveStatusResponse(BaseModel):
    """Google Drive integration status."""
    configured: bool
    shared_drive_id: Optional[str] = None


@router.get("/status", response_model=DriveStatusResponse)
async def get_drive_status():
    """Check if Google Drive integration is configured."""
    configured = google_drive_service.is_configured()
    shared_drive_id = google_drive_service.get_shared_drive_id()
    
    return DriveStatusResponse(
        configured=configured,
        shared_drive_id=shared_drive_id
    )


@router.post("/upload", response_model=DriveUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    convert: bool = Query(True, description="Convert to Google format (Sheets/Docs)")
):
    """Upload a file to Google Drive.
    
    Supports: xlsx, xls, csv, docx, doc, pptx, ppt, pdf
    
    If convert=True (default), Office files are converted to Google format:
    - xlsx/xls/csv -> Google Sheets
    - docx/doc -> Google Docs
    - pptx/ppt -> Google Slides
    
    Returns a view URL that anyone can access.
    """
    if not google_drive_service.is_configured():
        raise HTTPException(
            status_code=503, 
            detail="Google Drive not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS."
        )
    
    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    file_ext = os.path.splitext(file.filename)[1].lower()
    allowed_extensions = ['.xlsx', '.xls', '.csv', '.docx', '.doc', '.pptx', '.ppt', '.pdf']
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Save uploaded file to temp directory
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Upload to Google Drive
        result = google_drive_service.upload_file(
            file_path=tmp_path,
            convert_to_google_format=convert
        )
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        if result:
            return DriveUploadResponse(
                success=True,
                file_id=result['file_id'],
                view_url=result['view_url'],
                name=file.filename
            )
        else:
            return DriveUploadResponse(
                success=False,
                error="Upload failed. Check server logs for details."
            )
            
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        # Clean up temp file if it exists
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-xlsx", response_model=DriveUploadResponse)
async def upload_xlsx_as_sheet(
    file: UploadFile = File(...)
):
    """Upload an XLSX file and convert to Google Sheets.
    
    Convenience endpoint for the most common use case.
    Returns a Google Sheets view URL.
    """
    if not file.filename or not file.filename.lower().endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Only .xlsx files are accepted")
    
    return await upload_file(file=file, convert=True)
