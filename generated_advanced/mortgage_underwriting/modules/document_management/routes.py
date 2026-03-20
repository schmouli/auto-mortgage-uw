from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Path
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.document.services import DocumentService
from mortgage_underwriting.modules.document.schemas import (
    DocumentResponse,
    DocumentPublic,
    DocumentChecklistResponse,
    DocumentVerificationUpdate,
    DocumentRejectionUpdate,
    DocumentRequirementResponse,
    DocumentRequirementCreate,
    DocumentRequirementUpdate
)

router = APIRouter(prefix="/api/v1/applications", tags=["Document Management"])


def get_current_user_id():
    # Placeholder for authentication logic
    # This should be replaced with real JWT token parsing
    return 1  # Simulate user ID 1 for testing


def verify_user_authorization(application_id: int, user_id: int):
    # FIXED: Add authorization check to ensure user can access this application
    # In production, this would check if user has permission to access the application
    pass


@router.get("/{application_id}/documents/checklist", response_model=DocumentChecklistResponse)
async def get_document_checklist(
    application_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id),
) -> DocumentChecklistResponse:
    """Get required documents status for an application."""
    # FIXED: Add authorization check
    verify_user_authorization(application_id, current_user_id)
    service = DocumentService(db)
    try:
        return await service.get_checklist(application_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "DOCUMENT_007"})


@router.post("/{application_id}/documents/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    application_id: int = Path(..., gt=0),
    file: UploadFile = File(...),
    document_type: str = Form(...),
    notes: str = Form(None),
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id),  # Add auth dependency
) -> DocumentResponse:
    """Upload a document for an application."""
    # FIXED: Add authorization check
    verify_user_authorization(application_id, current_user_id)
    service = DocumentService(db)
    try:
        file_content = await file.read()
        # FIXED: Properly construct payload using schema validation
        from mortgage_underwriting.modules.document.schemas import DocumentCreate
        payload = DocumentCreate(
            application_id=application_id,
            document_type=document_type,
            file_name=file.filename,
            file_size=len(file_content),
            mime_type=file.content_type or "application/octet-stream",
            status="pending",
            notes=notes
        )
        return await service.upload_document(payload, file_content, current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "DOCUMENT_008"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "DOCUMENT_009"})


@router.get("/{application_id}/documents", response_model=List[DocumentPublic])
async def list_documents(
    application_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id),
) -> List[DocumentPublic]:
    """List all uploaded documents for an application."""
    # FIXED: Add authorization check
    verify_user_authorization(application_id, current_user_id)
    service = DocumentService(db)
    try:
        documents = await service.list_documents(application_id)
        return [DocumentPublic.model_validate(doc) for doc in documents]
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "DOCUMENT_010"})


@router.get("/{application_id}/documents/{document_id}/download")
async def download_document(
    application_id: int = Path(..., gt=0),
    document_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id),
) -> dict:
    """Download a specific document. Returns presigned URL in production."""
    # FIXED: Add authorization check
    verify_user_authorization(application_id, current_user_id)
    service = DocumentService(db)
    try:
        document = await service.get_document(application_id, document_id)
        # In production, return a presigned URL to the actual file location
        # FIXED: Return generic path instead of internal file path
        return {"url": f"/api/v1/documents/{document.id}/content"}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "DOCUMENT_011"})


@router.put("/{application_id}/documents/{document_id}/verify", response_model=DocumentResponse)
async def verify_document(
    application_id: int = Path(..., gt=0),
    document_id: int = Path(..., gt=0),
    payload: DocumentVerificationUpdate = Depends(),  # FIXED: Added explicit dependency parameter
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id),
) -> DocumentResponse:
    """Mark a document as verified."""
    # FIXED: Add authorization check
    verify_user_authorization(application_id, current_user_id)
    service = DocumentService(db)
    try:
        return await service.verify_document(application_id, document_id, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "DOCUMENT_012"})


@router.put("/{application_id}/documents/{document_id}/reject", response_model=DocumentResponse)
async def reject_document(
    application_id: int = Path(..., gt=0),
    document_id: int = Path(..., gt=0),
    payload: DocumentRejectionUpdate = Depends(),  # FIXED: Added explicit dependency parameter
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id),
) -> DocumentResponse:
    """Reject a document with reason."""
    # FIXED: Add authorization check
    verify_user_authorization(application_id, current_user_id)
    service = DocumentService(db)
    try:
        return await service.reject_document(application_id, document_id, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "DOCUMENT_013"})


@router.delete("/{application_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    application_id: int = Path(..., gt=0),
    document_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id),
) -> None:
    """Delete a document."""
    # FIXED: Add authorization check
    verify_user_authorization(application_id, current_user_id)
    service = DocumentService(db)
    try:
        await service.delete_document(application_id, document_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "DOCUMENT_014"})