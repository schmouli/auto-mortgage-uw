from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.document_management.services import DocumentManagementService
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentCreate, 
    DocumentUpdateStatus, 
    DocumentResponse,
    DocumentListResponse
)

router = APIRouter(prefix="/api/v1/documents", tags=["Document Management"])


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    payload: DocumentCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Upload a new document.
    
    Creates both document metadata and initial version entry.
    
    Args:
        payload: Document creation parameters
        db: Database session dependency
        
    Returns:
        Created document details
        
    Raises:
        HTTPException: 400 if validation fails or upload fails
    """
    service = DocumentManagementService(db)
    try:
        return await service.upload_document(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "UPLOAD_FAILED"}
        )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100, gt=0),
    db: AsyncSession = Depends(get_async_session),
):
    """Retrieve paginated list of documents.
    
    Args:
        skip: Number of records to skip
        limit: Number of records to retrieve (max 100)
        db: Database session dependency
        
    Returns:
        Paginated list of documents with total count
    """
    service = DocumentManagementService(db)
    documents, total = await service.get_documents(skip, limit)
    return DocumentListResponse(
        items=documents,
        total=total,
        skip=skip,
        limit=min(limit, 100)
    )


@router.patch("/{document_id}/status", response_model=DocumentResponse)
async def update_document_status_endpoint(
    document_id: int,
    payload: DocumentUpdateStatus,
    db: AsyncSession = Depends(get_async_session),
):
    """Update the status of a specific document.
    
    Args:
        document_id: ID of document to update
        payload: New status information
        db: Database session dependency
        
    Returns:
        Updated document details
        
    Raises:
        HTTPException: 404 if document not found, 400 if update fails
    """
    # FIXED: Added docstring
    service = DocumentManagementService(db)
    try:
        document = await service.update_document_status(document_id, payload)
        return document
    except AppException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "STATUS_UPDATE_FAILED"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"}
        )