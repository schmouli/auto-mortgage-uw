from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Path, Query
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.documents.schemas import (
    DocumentResponse,
    DocumentChecklistResponse,
    DocumentCreate
)
from mortgage_underwriting.modules.documents.services import DocumentService

router = APIRouter(prefix="/api/v1/applications/{application_id}/documents", tags=["Document Management"])


def get_document_service(db: AsyncSession = Depends(get_async_session)) -> DocumentService:
    return DocumentService(db)


@router.get("/checklist", response_model=DocumentChecklistResponse)
async def get_document_checklist(
    application_id: int = Path(..., gt=0),
    service: DocumentService = Depends(get_document_service)
) -> DocumentChecklistResponse:
    """Get required documents status for an application."""
    try:
        return await service.get_checklist(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "CHECKLIST_FETCH_FAILED"}
        )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    application_id: int = Path(..., gt=0),
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
    user_id: int = Query(..., gt=0)  # In real app, this would come from auth token
) -> DocumentResponse:
    """Upload a new document for an application."""
    try:
        # Read file content
        content = await file.read()
        
        # Prepare payload
        payload = DocumentCreate(
            document_type=file.content_type.split('/')[1],  # Simplified for example
            file_name=file.filename or "unnamed",
            file_size=len(content),
            mime_type=file.content_type
        )
        
        return await service.upload_document(application_id, user_id, payload, content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "UPLOAD_FAILED"}
        )


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    application_id: int = Path(..., gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: DocumentService = Depends(get_document_service)
) -> List[DocumentResponse]:
    """List uploaded documents for an application."""
    try:
        return await service.list_documents(application_id, page, page_size)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOCUMENT_LIST_FAILED"}
        )


@router.get("/{doc_id}/download", response_model=DocumentResponse)
async def download_document(
    application_id: int = Path(..., gt=0),
    doc_id: int = Path(..., gt=0),
    service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Download a specific document."""
    try:
        return await service.get_document(application_id, doc_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOWNLOAD_FAILED"}
        )


@router.put("/{doc_id}/verify", response_model=DocumentResponse)
async def verify_document(
    application_id: int = Path(..., gt=0),
    doc_id: int = Path(..., gt=0),
    service: DocumentService = Depends(get_document_service),
    user_id: int = Query(..., gt=0)  # In real app, this would come from auth token
) -> DocumentResponse:
    """Mark a document as verified."""
    try:
        return await service.verify_document(application_id, doc_id, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "VERIFY_FAILED"}
        )


@router.put("/{doc_id}/reject", response_model=DocumentResponse)
async def reject_document(
    application_id: int = Path(..., gt=0),
    doc_id: int = Path(..., gt=0),
    reason: str = Query(..., min_length=1, max_length=1000),
    service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Reject a document with a reason."""
    try:
        return await service.reject_document(application_id, doc_id, reason)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "REJECT_FAILED"}
        )


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    application_id: int = Path(..., gt=0),
    doc_id: int = Path(..., gt=0),
    service: DocumentService = Depends(get_document_service)
) -> None:
    """Delete a document."""
    try:
        await service.delete_document(application_id, doc_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DELETE_FAILED"}
        )