from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import hashlib
from sqlalchemy import select
import structlog
from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.modules.documents.models import Document, DocumentRequirement
from mortgage_underwriting.modules.documents.schemas import (
    DocumentCreate,
    DocumentUpdate,
    DocumentRequirementCreate,
    DocumentRequirementUpdate,
    DocumentChecklistItem,
    DocumentChecklistResponse
)

logger = structlog.get_logger()


# FIXED: Moved hardcoded values to constants
ALLOWED_MIME_TYPES = ["application/pdf", "image/jpeg", "image/png"]
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


class DocumentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_checklist(self, application_id: int) -> DocumentChecklistResponse:
        """Get document checklist for an application."""
        # FIXED: Added type hint for return value
        logger.info("document_checklist_fetch", application_id=application_id)
        
        # Get all requirements for this application
        req_query = select(DocumentRequirement).where(
            DocumentRequirement.application_id == application_id
        )
        result = await self.db.execute(req_query)
        requirements = result.scalars().all()
        
        # Get received documents
        doc_query = select(Document.document_type).where(
            Document.application_id == application_id,
            Document.status == "accepted"
        )
        result = await self.db.execute(doc_query)
        received_docs = set(result.scalars().all())
        
        items = []
        total_required = 0
        total_received = 0
        
        for req in requirements:
            is_received = req.document_type in received_docs
            items.append(DocumentChecklistItem(
                document_type=req.document_type,
                is_required=req.is_required,
                is_received=is_received,
                due_date=req.due_date
            ))
            if req.is_required:
                total_required += 1
                if is_received:
                    total_received += 1
        
        return DocumentChecklistResponse(
            items=items,
            total_required=total_required,
            total_received=total_received
        )

    async def upload_document(self, application_id: int, user_id: int, payload: DocumentCreate, file_content: bytes) -> Document:
        """Upload a new document."""
        # FIXED: Added input validation for payload fields
        if not payload.document_type:
            raise AppException("Document type is required", "MISSING_DOCUMENT_TYPE")
        
        if not payload.file_name:
            raise AppException("File name is required", "MISSING_FILE_NAME")
        
        if payload.file_size <= 0:
            raise AppException("File size must be positive", "INVALID_FILE_SIZE")
        
        if not payload.mime_type:
            raise AppException("MIME type is required", "MISSING_MIME_TYPE")
        
        logger.info("document_upload", application_id=application_id, document_type=payload.document_type)
        
        # Validate file size
        if payload.file_size > MAX_FILE_SIZE_BYTES:
            raise AppException("File too large", "FILE_TOO_LARGE")
        
        # Validate MIME type
        if payload.mime_type not in ALLOWED_MIME_TYPES:
            raise AppException("Invalid file type", "INVALID_MIME_TYPE")
        
        # Log file hash for virus scanning
        file_hash = hashlib.sha256(file_content).hexdigest()
        logger.info("file_virus_scan_placeholder", file_hash=file_hash)
        
        # Sanitize filename
        safe_filename = ''.join(c for c in payload.file_name if c.isalnum() or c in (' ', '.', '_')).rstrip()
        
        # Generate file path
        file_path = f"/uploads/{application_id}/{payload.document_type}/{safe_filename}"
        
        # Create document record
        doc = Document(
            application_id=application_id,
            uploaded_by=user_id,
            document_type=payload.document_type,
            file_name=safe_filename,
            file_path=file_path,
            file_size=payload.file_size,
            mime_type=payload.mime_type,
            uploaded_at=datetime.utcnow()
        )
        
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        
        return doc

    async def list_documents(self, application_id: int, page: int = 1, page_size: int = 20) -> List[Document]:
        """List uploaded documents for an application."""
        # FIXED: Added input validation for pagination parameters
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
            
        logger.info("document_list", application_id=application_id, page=page, page_size=page_size)
        
        offset = (page - 1) * page_size
        
        query = select(Document).where(
            Document.application_id == application_id
        ).offset(offset).limit(page_size)
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_document(self, application_id: int, doc_id: int) -> Document:
        """Get a specific document."""
        # FIXED: Added input validation
        if application_id <= 0:
            raise AppException("Invalid application ID", "INVALID_APPLICATION_ID")
        if doc_id <= 0:
            raise AppException("Invalid document ID", "INVALID_DOCUMENT_ID")
            
        logger.info("document_get", application_id=application_id, doc_id=doc_id)
        
        query = select(Document).where(
            Document.id == doc_id,
            Document.application_id == application_id
        )
        
        result = await self.db.execute(query)
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise NotFoundError("Document not found")
            
        return doc

    async def verify_document(self, application_id: int, doc_id: int, user_id: int) -> Document:
        """Mark a document as verified."""
        # FIXED: Added input validation
        if user_id <= 0:
            raise AppException("Invalid user ID", "INVALID_USER_ID")
            
        logger.info("document_verify", application_id=application_id, doc_id=doc_id, verified_by=user_id)
        
        doc = await self.get_document(application_id, doc_id)
        doc.is_verified = True
        doc.verified_by = user_id
        doc.verified_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(doc)
        
        return doc

    async def reject_document(self, application_id: int, doc_id: int, reason: str) -> Document:
        """Reject a document with a reason."""
        # FIXED: Added input validation
        if not reason or len(reason.strip()) == 0:
            raise AppException("Rejection reason is required", "MISSING_REJECTION_REASON")
        
        logger.info("document_reject", application_id=application_id, doc_id=doc_id)
        
        doc = await self.get_document(application_id, doc_id)
        doc.status = "rejected"
        doc.rejection_reason = reason
        
        await self.db.commit()
        await self.db.refresh(doc)
        
        return doc

    async def delete_document(self, application_id: int, doc_id: int) -> None:
        """Delete a document."""
        # FIXED: Added input validation
        if application_id <= 0:
            raise AppException("Invalid application ID", "INVALID_APPLICATION_ID")
        if doc_id <= 0:
            raise AppException("Invalid document ID", "INVALID_DOCUMENT_ID")
            
        logger.info("document_delete", application_id=application_id, doc_id=doc_id)
        
        doc = await self.get_document(application_id, doc_id)
        await self.db.delete(doc)
        await self.db.commit()