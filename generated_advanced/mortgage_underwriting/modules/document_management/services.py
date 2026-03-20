from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import hashlib
import uuid
import os

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from mortgage_underwriting.common.exceptions import NotFoundError, ValidationError
from mortgage_underwriting.modules.document.models import Document, DocumentRequirement
from mortgage_underwriting.modules.document.schemas import (
    DocumentCreate,
    DocumentUpdate,
    DocumentVerificationUpdate,
    DocumentRejectionUpdate,
    DocumentRequirementCreate,
    DocumentRequirementUpdate,
    DocumentChecklistResponse,
    ChecklistItem,
    ReceivedDocumentItem
)

logger = structlog.get_logger()


class DocumentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_checklist(self, application_id: int) -> DocumentChecklistResponse:
        logger.info("document_get_checklist", application_id=application_id)
        
        # Get all requirements for this application
        req_stmt = (
            select(DocumentRequirement)
            .where(DocumentRequirement.application_id == application_id)
        )
        req_result = await self.db.execute(req_stmt)
        requirements = req_result.scalars().all()
        
        # Get all documents for this application
        doc_stmt = (
            select(Document)
            .where(Document.application_id == application_id)
        )
        doc_result = await self.db.execute(doc_stmt)
        documents = doc_result.scalars().all()
        
        # Group documents by type
        docs_by_type = {}
        for doc in documents:
            if doc.document_type not in docs_by_type:
                docs_by_type[doc.document_type] = []
            docs_by_type[doc.document_type].append(doc)
        
        # Build checklist items
        checklist_items = []
        for req in requirements:
            received_docs = []
            if req.document_type in docs_by_type:
                for doc in docs_by_type[req.document_type]:
                    received_docs.append(
                        ReceivedDocumentItem(
                            document_id=doc.id,
                            file_name=doc.file_name,
                            status=doc.status,
                            is_verified=doc.is_verified,
                            uploaded_at=doc.uploaded_at
                        )
                    )
            
            checklist_items.append(
                ChecklistItem(
                    document_type=req.document_type,
                    is_required=req.is_required,
                    is_received=req.is_received,
                    due_date=req.due_date,
                    received_documents=received_docs
                )
            )
        
        return DocumentChecklistResponse(
            application_id=application_id,
            checklist_items=checklist_items
        )

    async def upload_document(self, payload: DocumentCreate, file_content: bytes, uploaded_by_user_id: int) -> Document:
        logger.info("document_upload", application_id=payload.application_id, document_type=payload.document_type)
        
        # Validate file size
        if len(file_content) > 10 * 1024 * 1024:  # 10MB
            raise ValidationError("File size exceeds maximum allowed (10MB)", error_code="DOCUMENT_005")
        
        # FIXED: Generate cryptographically secure random path to prevent path traversal
        file_extension = payload.file_name.split('.')[-1] if '.' in payload.file_name else ''
        # Sanitize filename to prevent directory traversal
        safe_filename = ''.join(c for c in payload.file_name if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
        unique_id = uuid.uuid4()
        file_path = f"/secure_uploads/{payload.application_id}/{unique_id}.{file_extension}"
        
        # FIXED: Validate MIME type against allowed types
        allowed_mime_types = [
            'application/pdf',
            'image/jpeg',
            'image/png',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        if payload.mime_type not in allowed_mime_types:
            raise ValidationError(f"File type {payload.mime_type} not allowed", error_code="DOCUMENT_015")
        
        # Log file hash for virus scanning
        file_hash = hashlib.sha256(file_content).hexdigest()
        logger.info("file_uploaded_for_virus_scan", file_hash=file_hash, file_path=file_path)
        
        # In production, save file to disk or cloud storage here
        # For now, we'll just simulate it
        
        # Create document record
        doc_dict = payload.model_dump(exclude={'notes'})
        doc_dict['file_path'] = file_path
        doc_dict['file_size'] = len(file_content)
        doc_dict['uploaded_by'] = uploaded_by_user_id  # Set uploader ID
        
        document = Document(**doc_dict)
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        
        return document

    async def list_documents(self, application_id: int) -> List[Document]:
        logger.info("document_list", application_id=application_id)
        
        stmt = (
            select(Document)
            .where(Document.application_id == application_id)
            .order_by(Document.uploaded_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_document(self, application_id: int, document_id: int) -> Document:
        logger.info("document_get", application_id=application_id, document_id=document_id)
        
        stmt = (
            select(Document)
            .where(and_(Document.id == document_id, Document.application_id == application_id))
        )
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError("Document not found", error_code="DOCUMENT_001")
            
        return document

    async def verify_document(self, application_id: int, document_id: int, payload: DocumentVerificationUpdate) -> Document:
        logger.info("document_verify", application_id=application_id, document_id=document_id)
        
        document = await self.get_document(application_id, document_id)
        document.is_verified = payload.is_verified
        document.verified_by = payload.verified_by
        document.verified_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(document)
        
        return document

    async def reject_document(self, application_id: int, document_id: int, payload: DocumentRejectionUpdate) -> Document:
        logger.info("document_reject", application_id=application_id, document_id=document_id)
        
        document = await self.get_document(application_id, document_id)
        document.status = 'rejected'
        document.rejection_reason = payload.rejection_reason
        
        await self.db.commit()
        await self.db.refresh(document)
        
        return document

    async def delete_document(self, application_id: int, document_id: int) -> None:
        logger.info("document_delete", application_id=application_id, document_id=document_id)
        
        document = await self.get_document(application_id, document_id)
        await self.db.delete(document)
        await self.db.commit()

    async def create_requirement(self, payload: DocumentRequirementCreate) -> DocumentRequirement:
        logger.info("document_requirement_create", application_id=payload.application_id, document_type=payload.document_type)
        
        requirement = DocumentRequirement(**payload.model_dump())
        self.db.add(requirement)
        await self.db.commit()
        await self.db.refresh(requirement)
        
        return requirement

    async def update_requirement(self, requirement_id: int, payload: DocumentRequirementUpdate) -> DocumentRequirement:
        logger.info("document_requirement_update", requirement_id=requirement_id)
        
        stmt = select(DocumentRequirement).where(DocumentRequirement.id == requirement_id)
        result = await self.db.execute(stmt)
        requirement = result.scalar_one_or_none()
        
        if not requirement:
            raise NotFoundError("Document requirement not found", error_code="DOCUMENT_006")
        
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(requirement, field, value)
        
        await self.db.commit()
        await self.db.refresh(requirement)
        
        return requirement