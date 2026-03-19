from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import hashlib

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.modules.documents.models import Document, DocumentRequirement, DocumentStatus
from mortgage_underwriting.modules.documents.schemas import (
    DocumentCreate,
    DocumentUpdate,
    DocumentRequirementCreate,
    DocumentRequirementUpdate,
    ChecklistItem,
    ChecklistResponse,
    VerificationRequest,
    RejectionRequest,
    UploadDocumentRequest
)
from mortgage_underwriting.modules.applications.models import Application

logger = structlog.get_logger()

class DocumentManagementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_checklist(self, application_id: int) -> ChecklistResponse:
        logger.info("document_checklist_requested", application_id=application_id)
        
        # Verify application exists
        app_result = await self.db.execute(select(Application).where(Application.id == application_id))
        application = app_result.scalar_one_or_none()
        if not application:
            raise NotFoundError(f"Application {application_id} not found")
        
        # Get all document requirements for this application
        req_query = select(DocumentRequirement).where(DocumentRequirement.application_id == application_id)
        req_result = await self.db.execute(req_query)
        requirements = req_result.scalars().all()
        
        # Get all uploaded documents for this application (excluding deleted)
        doc_query = select(Document).where(
            and_(Document.application_id == application_id, Document.is_deleted == False)
        )
        doc_result = await self.db.execute(doc_query)
        documents = doc_result.scalars().all()
        
        # Map documents by type for quick lookup
        docs_by_type = {doc.document_type: doc for doc in documents}
        
        checklist_items = []
        missing_required_count = 0
        pending_verification_count = 0
        
        now = datetime.utcnow()
        
        for req in requirements:
            received_doc = docs_by_type.get(req.document_type)
            
            item = ChecklistItem(
                document_type=req.document_type,
                category=req.category,
                is_required=req.is_required,
                is_received=bool(received_doc),
                due_date=req.due_date,
                days_until_due=(req.due_date - now).days if req.due_date else None,
                received_document_id=received_doc.id if received_doc else None,
                received_at=received_doc.uploaded_at if received_doc else None,
                status=received_doc.status if received_doc else DocumentStatus.PENDING
            )
            
            checklist_items.append(item)
            
            if req.is_required and not received_doc:
                missing_required_count += 1
                
            if received_doc and not received_doc.is_verified:
                pending_verification_count += 1
        
        # Determine overall status
        if missing_required_count > 0:
            overall_status = "pending"
        elif pending_verification_count > 0:
            overall_status = "pending"
        else:
            overdue_found = any(
                item.due_date and item.due_date < now and item.status != DocumentStatus.ACCEPTED
                for item in checklist_items
            )
            overall_status = "overdue" if overdue_found else "complete"
        
        return ChecklistResponse(
            application_id=application_id,
            overall_status=overall_status,
            requirements=checklist_items,
            missing_required_count=missing_required_count,
            pending_verification_count=pending_verification_count
        )

    async def upload_document(self, application_id: int, payload: UploadDocumentRequest, file_content: bytes, uploaded_by: int = None, created_by: int = None) -> Document:
        logger.info("document_upload_started", application_id=application_id, document_type=payload.document_type.value)
        
        # Validate file size
        if len(file_content) > 10 * 1024 * 1024:  # 10MB limit
            raise AppException("File too large", "DOC_003")
        
        # Generate file path
        safe_filename = ''.join(c for c in payload.file_name if c.isalnum() or c in (' ', '.', '_')).rstrip()
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_path = f"/uploads/{application_id}/{payload.document_type.value}/{file_hash}_{safe_filename}"
        
        # Log for virus scanning
        logger.info("virus_scan_placeholder", file_hash=file_hash)
        
        # Create document record
        doc_data = DocumentCreate(
            document_type=payload.document_type,
            file_name=safe_filename,
            file_size=len(file_content),
            mime_type=payload.mime_type
        )
        
        document = Document(
            application_id=application_id,
            uploaded_by=uploaded_by,
            created_by=created_by,  # FIXED: Track who created the document
            **doc_data.model_dump(),
            file_path=file_path
        )
        
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        
        logger.info("document_uploaded", document_id=document.id)
        return document

    async def list_documents(self, application_id: int) -> List[Document]:
        logger.info("document_list_requested", application_id=application_id)
        
        result = await self.db.execute(
            select(Document)
            .where(and_(Document.application_id == application_id, Document.is_deleted == False))
            .options(selectinload(Document.uploader))
        )
        return result.scalars().all()

    async def download_document(self, application_id: int, document_id: int) -> Document:
        logger.info("document_download_requested", application_id=application_id, document_id=document_id)
        
        result = await self.db.execute(
            select(Document)
            .where(and_(Document.id == document_id, Document.application_id == application_id, Document.is_deleted == False))
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError(f"Document {document_id} not found for application {application_id}")
            
        return document

    async def verify_document(self, application_id: int, document_id: int, payload: VerificationRequest) -> Document:
        logger.info("document_verification_requested", application_id=application_id, document_id=document_id)
        
        result = await self.db.execute(
            select(Document)
            .where(and_(Document.id == document_id, Document.application_id == application_id, Document.is_deleted == False))
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError(f"Document {document_id} not found for application {application_id}")
            
        document.is_verified = True
        document.verified_by = payload.verified_by
        document.verified_at = payload.verified_at
        document.status = DocumentStatus.ACCEPTED
        
        await self.db.commit()
        await self.db.refresh(document)
        
        logger.info("document_verified", document_id=document.id, verified_by=payload.verified_by)
        return document

    async def reject_document(self, application_id: int, document_id: int, payload: RejectionRequest) -> Document:
        logger.info("document_rejection_requested", application_id=application_id, document_id=document_id)
        
        result = await self.db.execute(
            select(Document)
            .where(and_(Document.id == document_id, Document.application_id == application_id, Document.is_deleted == False))
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError(f"Document {document_id} not found for application {application_id}")
            
        document.rejection_reason = payload.rejection_reason
        document.status = DocumentStatus.REJECTED
        
        await self.db.commit()
        await self.db.refresh(document)
        
        logger.info("document_rejected", document_id=document.id)
        return document

    # FIXED: Soft delete implementation for FINTRAC compliance
    async def delete_document(self, application_id: int, document_id: int, deleted_by: int = None) -> None:
        logger.info("document_delete_requested", application_id=application_id, document_id=document_id)
        
        result = await self.db.execute(
            select(Document)
            .where(and_(Document.id == document_id, Document.application_id == application_id, Document.is_deleted == False))
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError(f"Document {document_id} not found for application {application_id}")
        
        # Soft delete instead of hard delete for audit trail
        document.is_deleted = True
        document.deleted_at = datetime.utcnow()
        document.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info("document_soft_deleted", document_id=document.id, deleted_by=deleted_by)

    async def create_document_requirement(self, application_id: int, payload: DocumentRequirementCreate, created_by: int = None) -> DocumentRequirement:
        logger.info("document_requirement_create", application_id=application_id)
        
        requirement = DocumentRequirement(
            application_id=application_id,
            document_type=payload.document_type,
            category=payload.category,
            is_required=payload.is_required,
            is_received=payload.is_received,
            due_date=payload.due_date,
            created_by=created_by  # FIXED: Track who created the requirement
        )
        
        self.db.add(requirement)
        await self.db.commit()
        await self.db.refresh(requirement)
        
        return requirement

    async def update_document_requirement(self, requirement_id: int, payload: DocumentRequirementUpdate) -> DocumentRequirement:
        logger.info("document_requirement_update", requirement_id=requirement_id)
        
        result = await self.db.execute(select(DocumentRequirement).where(DocumentRequirement.id == requirement_id))
        requirement = result.scalar_one_or_none()
        
        if not requirement:
            raise NotFoundError(f"Document requirement {requirement_id} not found")
        
        if payload.is_received is not None:
            requirement.is_received = payload.is_received
        if payload.due_date is not None:
            requirement.due_date = payload.due_date
            
        requirement.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(requirement)
        
        return requirement