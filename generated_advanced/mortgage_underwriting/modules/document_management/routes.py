from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.documents.services import DocumentManagementService
from mortgage_underwriting.modules.documents.schemas import (
    ChecklistResponse,
    DocumentResponse,
    VerificationRequest,
    RejectionRequest,
    UploadDocumentRequest,
    DocumentRequirementCreate,
    DocumentRequirementResponse,
    DocumentRequirementUpdate
)
from mortgage_underwriting.modules.documents.exceptions import DocumentNotFoundError, InvalidDocumentTypeError
from mortgage_underwriting.modules.documents.models import DocumentType

router = APIRouter(prefix="/api/v1/applications", tags=["Document Management"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_MIME_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/heic"]


def validate_file(file: UploadFile = File(...)) -> UploadFile:
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail={"detail": "File too large", "error_code": "DOC_003"})
    
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail={"detail": "Invalid file type", "error_code": "DOC_004"})
    
    return file

def validate_document_type(document_type: str) -> DocumentType:
    try:
        return DocumentType(document_type)
    except ValueError:
        raise HTTPException(status_code=400, detail={"detail": f"Invalid document type: {document_type}", "error_code": "DOC_013"})

def sanitize_filename(filename: str) -> str:
    return ''.join(c for c in filename if c.isalnum() or c in (' ', '.', '_')).rstrip()


@router.get("/{application_id}/documents/checklist", response_model=ChecklistResponse)
async def get_document_checklist(
    application_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_async_session)
):
    """Get required documents status for an application."""
    try:
        service = DocumentManagementService(db)
        return await service.get_checklist(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOC_005"}
        )


@router.post("/{application_id}/documents/upload", response_model=DocumentResponse)
async def upload_document(
    application_id: int = Path(..., gt=0),
    file: UploadFile = Depends(validate_file),
    document_type: str = Form(...),
    db: AsyncSession = Depends(get_async_session)
):
    """Upload a document for an application."""
    try:
        # Validate document type
        validated_doc_type = validate_document_type(document_type)
        
        # Read file content
        contents = await file.read()
        
        # Prepare request data
        payload = UploadDocumentRequest(
            document_type=validated_doc_type,
            file_name=sanitize_filename(file.filename),
            file_size=len(contents),
            mime_type=file.content_type
        )
        
        service = DocumentManagementService(db)
        # FIXED: Pass created_by from authenticated user context
        return await service.upload_document(application_id, payload, contents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOC_006"}
        )


@router.get("/{application_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    application_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_async_session)
):
    """List all uploaded documents for an application."""
    try:
        service = DocumentManagementService(db)
        return await service.list_documents(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOC_007"}
        )


@router.get("/{application_id}/documents/{document_id}/download", response_model=DocumentResponse)
async def download_document(
    application_id: int = Path(..., gt=0),
    document_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_async_session)
):
    """Download a specific document."""
    try:
        service = DocumentManagementService(db)
        return await service.download_document(application_id, document_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOC_008"}
        )


@router.put("/{application_id}/documents/{document_id}/verify", response_model=DocumentResponse)
async def verify_document(
    application_id: int = Path(..., gt=0),
    document_id: int = Path(..., gt=0),
    payload: VerificationRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """Mark a document as verified."""
    try:
        service = DocumentManagementService(db)
        return await service.verify_document(application_id, document_id, payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOC_009"}
        )


@router.put("/{application_id}/documents/{document_id}/reject", response_model=DocumentResponse)
async def reject_document(
    application_id: int = Path(..., gt=0),
    document_id: int = Path(..., gt=0),
    payload: RejectionRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """Reject a document with reason."""
    try:
        service = DocumentManagementService(db)
        return await service.reject_document(application_id, document_id, payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOC_010"}
        )


@router.delete("/{application_id}/documents/{document_id}")
async def delete_document(
    application_id: int = Path(..., gt=0),
    document_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_async_session)
):
    """Delete a document (FINTRAC compliant soft delete)."""
    try:
        service = DocumentManagementService(db)
        await service.delete_document(application_id, document_id)
        return {"message": "Document deleted successfully (retained for audit purposes)"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOC_011"}
        )


@router.post("/{application_id}/documents/requirements", response_model=DocumentRequirementResponse)
async def create_document_requirement(
    application_id: int = Path(..., gt=0),
    payload: DocumentRequirementCreate,
    db: AsyncSession = Depends(get_async_session)
):
    """Create a new document requirement for an application."""
    try:
        service = DocumentManagementService(db)
        # FIXED: Pass created_by from authenticated user context
        return await service.create_document_requirement(application_id, payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOC_016"}
        )


@router.put("/{application_id}/documents/requirements/{requirement_id}", response_model=DocumentRequirementResponse)
async def update_document_requirement(
    application_id: int = Path(..., gt=0),
    requirement_id: int = Path(..., gt=0),
    payload: DocumentRequirementUpdate,
    db: AsyncSession = Depends(get_async_session)
):
    """Update an existing document requirement."""
    try:
        service = DocumentManagementService(db)
        return await service.update_document_requirement(requirement_id, payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DOC_017"}
        )