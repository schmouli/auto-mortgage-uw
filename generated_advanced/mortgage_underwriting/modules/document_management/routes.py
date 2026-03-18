from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.document_management.schemas import (
from mortgage_underwriting.modules.document_management.services import DocumentManagementService

    DocumentUploadRequest,
    DocumentResponse,
    DocumentRequirementResponse,
    DocumentChecklistResponse,
    DocumentListResponse
)
from mortgage_underwriting.modules.document_management.models import DocumentStatus

router = APIRouter(prefix="/api/v1/applications", tags=["Document Management"])

ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/heic"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
UPLOAD_DIR = Path("/uploads")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing special characters."""
    return "".join(c for c in filename if c.isalnum() or c in (" ", ".", "_", "-")).strip()


def convert_heic_to_pdf(file_content: bytes) -> bytes:
    """Placeholder for HEIC to PDF conversion."""
    # In production, integrate with image processing library like Pillow or ImageMagick
    return file_content  # Placeholder


@router.get("/{application_id}/documents/checklist", response_model=DocumentChecklistResponse)


async def get_document_checklist(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get required documents status checklist for an application."""
    service = DocumentManagementService(db)
    try:
        return await service.get_checklist(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "CHECKLIST_FETCH_ERROR"}
        )


@router.post("/{application_id}/documents/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)


async def upload_document(
    application_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    notes: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_session),
):
    """Upload a document for an application."""
    # Validate file size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "File size exceeds 10MB limit", "error_code": "FILE_TOO_LARGE"}
        )
    
    # Reset file pointer after reading
    await file.seek(0)
    
    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Unsupported file type: {file.content_type}", "error_code": "UNSUPPORTED_FILE_TYPE"}
        )
    
    # Convert HEIC to PDF if needed
    if file.content_type == "image/heic":
        file_content = convert_heic_to_pdf(file_content)
        file.filename = file.filename.replace(".heic", ".pdf")
        file.content_type = "application/pdf"
    
    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)
    if not safe_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid filename", "error_code": "INVALID_FILENAME"}
        )
    
    # Generate path
    doc_type_dir = document_type.lower().replace(" ", "_")
    file_path = UPLOAD_DIR / str(application_id) / doc_type_dir / safe_filename
    
    # Ensure directories exist
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save file
    with open(file_path, "wb") as buffer:
        buffer.write(file_content)
    
    # Log file hash for virus scanning (placeholder)
    import hashlib
    file_hash = hashlib.sha256(file_content).hexdigest()
    
    # Create document record
    service = DocumentManagementService(db)
    try:
        from mortgage_underwriting.modules.document_management.schemas import DocumentCreate
        from mortgage_underwriting.modules.document_management.models import DocumentType
        
        # Map string to enum
        try:
            doc_type_enum = DocumentType(document_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": f"Invalid document type: {document_type}", "error_code": "INVALID_DOCUMENT_TYPE"}
            )
        
        doc_create = DocumentCreate(
            application_id=application_id,
            uploaded_by=1,  # Would come from auth context
            document_type=doc_type_enum,
            file_name=safe_filename,
            file_path=str(file_path),
            file_size=len(file_content),
            mime_type=file.content_type
        )
        
        return await service.upload_document(doc_create)
    except Exception as e:
        # Clean up uploaded file on failure
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "UPLOAD_FAILED"}
        )


@router.get("/{application_id}/documents", response_model=DocumentListResponse)


async def list_documents(
    application_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
):
    """List uploaded documents for an application."""
    service = DocumentManagementService(db)
    try:
        documents, total = await service.list_documents(application_id, page, size)
        return DocumentListResponse(
            items=documents,
            total=total,
            page=page,
            size=size
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOCUMENT_LIST_FAILED"}
        )


@router.get("/{application_id}/documents/{doc_id}/download")


async def download_document(
    application_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Download a document. Returns presigned URL in production."""
    service = DocumentManagementService(db)
    try:
        document = await service.get_document(doc_id)
        # In production, return presigned URL from cloud storage
        return {"url": f"/files/{document.file_path}"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOWNLOAD_FAILED"}
        )


@router.put("/{application_id}/documents/{doc_id}/verify", response_model=DocumentResponse)


async def verify_document(
    application_id: int,
    doc_id: int,
    verified: bool = True,
    db: AsyncSession = Depends(get_async_session),
):
    """Mark a document as verified."""
    service = DocumentManagementService(db)
    try:
        from mortgage_underwriting.modules.document_management.schemas import DocumentUpdate
        update_data = DocumentUpdate(is_verified=verified, verified_by=1)  # Would come from auth context
        return await service.update_document_status(doc_id, update_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "VERIFICATION_FAILED"}
        )


@router.put("/{application_id}/documents/{doc_id}/reject", response_model=DocumentResponse)


async def reject_document(
    application_id: int,
    doc_id: int,
    reason: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Reject a document with a reason."""
    service = DocumentManagementService(db)
    try:
        from mortgage_underwriting.modules.document_management.schemas import DocumentUpdate
        update_data = DocumentUpdate(status=DocumentStatus.REJECTED, rejection_reason=reason)
        return await service.update_document_status(doc_id, update_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "REJECTION_FAILED"}
        )


@router.delete("/{application_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)


async def delete_document(
    application_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a document."""
    service = DocumentManagementService(db)
    try:
        success = await service.delete_document(doc_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Document not found", "error_code": "DOCUMENT_NOT_FOUND"}
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DELETION_FAILED"}
        )