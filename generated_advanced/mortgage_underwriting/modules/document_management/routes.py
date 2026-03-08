from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentResponse, DocumentUploadRequest,
    ChecklistResponse, DocumentRequirementResponse
)
from mortgage_underwriting.modules.document_management.services import DocumentService

router = APIRouter(prefix="/api/v1/applications", tags=["Document Management"])

@router.get("/{application_id}/documents/checklist", response_model=ChecklistResponse)
async def get_documents_checklist(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> ChecklistResponse:
    """Retrieve the document requirements checklist for a mortgage application."""
    try:
        service = DocumentService(db)
        return await service.get_checklist(application_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "DOC_001"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": str(e),
                "error_code": "DOC_001"
            }
        )

@router.post("/{application_id}/documents/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    application_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    description: str = Form(None),
    db: AsyncSession = Depends(get_async_session),
) -> DocumentResponse:
    """Upload a document via multipart/form-data."""
    try:
        # Read file data
        file_data = await file.read()
        
        # In real implementation, get user ID from auth context
        uploaded_by = 1  # Placeholder
        
        service = DocumentService(db)
        return await service.upload_document(
            application_id=application_id,
            uploaded_by=uploaded_by,
            file_data=file_data,
            filename=file.filename,
            mime_type=file.content_type,
            document_type=document_type,
            description=description
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": str(e),
                "error_code": "DOC_002"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": str(e),
                "error_code": "DOC_002"
            }
        )

@router.get("/{application_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> List[DocumentResponse]:
    """List all uploaded documents for an application."""
    try:
        service = DocumentService(db)
        return await service.list_documents(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": str(e),
                "error_code": "DOC_003"
            }
        )

@router.get("/{application_id}/documents/{document_id}/download", response_model=dict)
async def download_document(
    application_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    """Download a specific document (returns file path/info)."""
    try:
        service = DocumentService(db)
        document = await service.get_document(application_id, document_id)
        # In real implementation, would stream file content
        # For now, return file info
        return {
            "file_path": document.file_path,
            "file_name": document.file_name,
            "mime_type": document.mime_type
        }
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "DOC_004"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": str(e),
                "error_code": "DOC_004"
            }
        )

@router.put("/{application_id}/documents/{document_id}/verify", response_model=DocumentResponse)
async def verify_document(
    application_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> DocumentResponse:
    """Mark a document as verified."""
    try:
        # In real implementation, get user ID from auth context
        verified_by = 1  # Placeholder
        
        service = DocumentService(db)
        return await service.verify_document(application_id, document_id, verified_by)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "DOC_005"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": str(e),
                "error_code": "DOC_005"
            }
        )

@router.put("/{application_id}/documents/{document_id}/reject", response_model=DocumentResponse)
async def reject_document(
    application_id: int,
    document_id: int,
    rejection_reason: str,
    db: AsyncSession = Depends(get_async_session),
) -> DocumentResponse:
    """Reject a document with a reason."""
    try:
        service = DocumentService(db)
        return await service.reject_document(application_id, document_id, rejection_reason)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "DOC_006"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": str(e),
                "error_code": "DOC_006"
            }
        )

@router.delete("/{application_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    application_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete a document."""
    try:
        service = DocumentService(db)
        await service.delete_document(application_id, document_id)
        return
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "DOC_007"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": str(e),
                "error_code": "DOC_007"
            }
        )