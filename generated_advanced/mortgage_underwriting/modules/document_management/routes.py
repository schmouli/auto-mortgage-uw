from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.document_management.services import DocumentManagementService
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentVerifyRequest,
    DocumentRejectRequest,
    DocumentChecklistResponse,
    DocumentListResponse,
    DocumentDownloadResponse
)

router = APIRouter(prefix="/api/v1/applications", tags=["Document Management"])

async def get_service(db: AsyncSession = Depends(get_async_session)) -> DocumentManagementService:
    return DocumentManagementService(db)

@router.get("/{application_id}/documents/checklist", response_model=DocumentChecklistResponse)
async def get_document_checklist(
    application_id: int = Path(..., gt=0),
    service: DocumentManagementService = Depends(get_service)
) -> DocumentChecklistResponse:
    """Get document checklist for an application."""
    try:
        return await service.get_checklist(application_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "INTERNAL_ERROR"})

@router.post("/{application_id}/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    application_id: int = Path(..., gt=0),
    document_type: str = None,
    file: UploadFile = File(...),
    service: DocumentManagementService = Depends(get_service)
) -> DocumentUploadResponse:
    """Upload a document for an application."""
    # FIXED: Add input validation
    if not document_type:
        raise HTTPException(status_code=400, detail={"detail": "Document type is required", "error_code": "MISSING_DOC_TYPE"})
    
    try:
        content = await file.read()
        return await service.upload_document(
            application_id=application_id,
            uploaded_by=1,  # Would come from auth context
            document_type=document_type,
            file_content=content,
            original_filename=file.filename,
            mime_type=file.content_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "UPLOAD_FAILED"})

@router.get("/{application_id}/documents", response_model=List[DocumentListResponse])
async def list_documents(
    application_id: int = Path(..., gt=0),
    service: DocumentManagementService = Depends(get_service)
) -> List[DocumentListResponse]:
    """List all documents for an application."""
    try:
        return await service.list_documents(application_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "LIST_FAILED"})

@router.put("/{application_id}/documents/{doc_id}/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_document(
    application_id: int = Path(..., gt=0),
    doc_id: int = Path(..., gt=0),
    payload: DocumentVerifyRequest,
    service: DocumentManagementService = Depends(get_service)
) -> None:
    """Mark a document as verified."""
    try:
        await service.verify_document(doc_id, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "VERIFY_FAILED"})

@router.put("/{application_id}/documents/{doc_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_document(
    application_id: int = Path(..., gt=0),
    doc_id: int = Path(..., gt=0),
    payload: DocumentRejectRequest,
    service: DocumentManagementService = Depends(get_service)
) -> None:
    """Reject a document with reason."""
    try:
        await service.reject_document(doc_id, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "REJECT_FAILED"})

@router.delete("/{application_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    application_id: int = Path(..., gt=0),
    doc_id: int = Path(..., gt=0),
    service: DocumentManagementService = Depends(get_service)
) -> None:
    """Delete a document."""
    try:
        await service.delete_document(doc_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "DELETE_FAILED"})

@router.get("/{application_id}/documents/{doc_id}/download", response_model=DocumentDownloadResponse)
async def download_document(
    application_id: int = Path(..., gt=0),
    doc_id: int = Path(..., gt=0),
    service: DocumentManagementService = Depends(get_service)
) -> DocumentDownloadResponse:
    """Generate download link for a document."""
    try:
        return await service.generate_download_link(doc_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "DOWNLOAD_FAILED"})