from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple
import hashlib
import os
import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError, ValidationError
from mortgage_underwriting.modules.document_management.models import Document, DocumentRequirement
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentVerifyRequest,
    DocumentRejectRequest,
    DocumentSummary,
    DocumentRequirementItem,
    DocumentChecklistResponse,
    DocumentListResponse,
    DocumentDownloadResponse
)

logger = structlog.get_logger()

ALLOWED_MIME_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/heic']
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
UPLOAD_DIR = '/uploads'

async def sanitize_filename(filename: str) -> str:
    """Sanitize filename to contain only alphanumeric, dots, hyphens, underscores."""
    import re
    name, ext = os.path.splitext(filename)
    clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '', name)
    return f"{clean_name}{ext}"

async def calculate_days_until_due(due_date: Optional[datetime]) -> Optional[int]:
    if not due_date:
        return None
    delta = due_date - datetime.utcnow()
    return delta.days

class DocumentManagementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upload_document(
        self, 
        application_id: int, 
        uploaded_by: int,
        document_type: str,
        file_content: bytes,
        original_filename: str,
        mime_type: str
    ) -> DocumentUploadResponse:
        # Validate inputs
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(detail="Invalid file type", error_code="DOC_INVALID_TYPE")
        
        if len(file_content) > MAX_FILE_SIZE_BYTES:
            raise ValidationError(detail="File too large", error_code="DOC_TOO_LARGE")
        
        sanitized_name = await sanitize_filename(original_filename)
        
        # Generate path
        relative_path = f"{application_id}/{document_type}/{sanitized_name}"
        full_path = os.path.join(UPLOAD_DIR, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Write file
        with open(full_path, 'wb') as f:
            f.write(file_content)
        
        # Log hash for virus scan
        file_hash = hashlib.sha256(file_content).hexdigest()
        logger.info("file_uploaded", file_hash=file_hash, path=full_path)
        
        # Create DB record
        doc = Document(
            application_id=application_id,
            uploaded_by=uploaded_by,
            document_type=document_type,
            file_name=sanitized_name,
            file_path=relative_path,
            file_size=len(file_content),
            mime_type=mime_type,
            status="pending",
            uploaded_at=datetime.now()
        )
        
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        
        return DocumentUploadResponse(
            doc_id=doc.id,
            file_name=doc.file_name,
            status=doc.status,
            message="Document uploaded successfully"
        )

    async def get_checklist(self, application_id: int) -> DocumentChecklistResponse:
        # Get requirements
        req_stmt = select(DocumentRequirement).where(DocumentRequirement.application_id == application_id)
        req_result = await self.db.execute(req_stmt)
        requirements = req_result.scalars().all()
        
        # Get uploaded documents grouped by type
        doc_stmt = select(Document).where(Document.application_id == application_id)
        doc_result = await self.db.execute(doc_stmt)
        documents = doc_result.scalars().all()
        
        doc_map = {}
        for doc in documents:
            if doc.document_type not in doc_map:
                doc_map[doc.document_type] = []
            doc_map[doc.document_type].append(DocumentSummary(
                doc_id=doc.id,
                file_name=doc.file_name,
                status=doc.status,
                is_verified=doc.is_verified,
                uploaded_at=doc.uploaded_at
            ))
        
        items = []
        overdue_count = 0
        incomplete_count = 0
        
        for req in requirements:
            docs_for_type = doc_map.get(req.document_type, [])
            days_left = await calculate_days_until_due(req.due_date)
            
            if days_left is not None and days_left < 0 and req.is_required and not req.is_received:
                overdue_count += 1
            elif req.is_required and not req.is_received:
                incomplete_count += 1
                
            items.append(DocumentRequirementItem(
                document_type=req.document_type,
                is_required=req.is_required,
                is_received=req.is_received,
                due_date=req.due_date,
                days_until_due=days_left,
                uploaded_documents=docs_for_type
            ))
        
        overall_status = "complete"
        if incomplete_count > 0:
            overall_status = "incomplete"
        if overdue_count > 0:
            overall_status = "overdue"
        
        return DocumentChecklistResponse(
            application_id=application_id,
            requirements=items,
            overall_status=overall_status
        )

    async def list_documents(self, application_id: int) -> List[DocumentListResponse]:
        stmt = select(Document).where(Document.application_id == application_id)
        result = await self.db.execute(stmt)
        docs = result.scalars().all()
        
        return [
            DocumentListResponse(
                id=doc.id,
                document_type=doc.document_type,
                file_name=doc.file_name,
                status=doc.status,
                is_verified=doc.is_verified,
                uploaded_at=doc.uploaded_at
            )
            for doc in docs
        ]

    async def verify_document(self, doc_id: int, payload: DocumentVerifyRequest) -> None:
        stmt = select(Document).where(Document.id == doc_id)
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise NotFoundError(detail="Document not found", error_code="DOC_NOT_FOUND")
        
        doc.is_verified = True
        doc.verified_by = payload.verified_by
        doc.verified_at = datetime.now()
        doc.status = "accepted"
        
        await self.db.commit()
        logger.info("document_verified", doc_id=doc_id, verified_by=payload.verified_by)

    async def reject_document(self, doc_id: int, payload: DocumentRejectRequest) -> None:
        stmt = select(Document).where(Document.id == doc_id)
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise NotFoundError(detail="Document not found", error_code="DOC_NOT_FOUND")
        
        doc.status = "rejected"
        doc.rejection_reason = payload.rejection_reason
        
        await self.db.commit()
        logger.info("document_rejected", doc_id=doc_id, reason=payload.rejection_reason)

    async def delete_document(self, doc_id: int) -> None:
        stmt = select(Document).where(Document.id == doc_id)
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise NotFoundError(detail="Document not found", error_code="DOC_NOT_FOUND")
        
        # Delete physical file
        full_path = os.path.join(UPLOAD_DIR, doc.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        
        # Delete from DB
        await self.db.delete(doc)
        await self.db.commit()
        logger.info("document_deleted", doc_id=doc_id)

    async def generate_download_link(self, doc_id: int) -> DocumentDownloadResponse:
        stmt = select(Document).where(Document.id == doc_id)
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise NotFoundError(detail="Document not found", error_code="DOC_NOT_FOUND")
        
        # In real implementation, this would generate a signed URL
        # For now we'll just return a placeholder
        expires_at = datetime.now() + timedelta(hours=1)
        download_url = f"/api/v1/documents/{doc_id}/download-file"  # Placeholder URL
        
        return DocumentDownloadResponse(download_url=download_url, expires_at=expires_at)