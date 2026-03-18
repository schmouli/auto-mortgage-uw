from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Tuple

from sqlalchemy import select, func
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.modules.document_management.models import Document, DocumentRequirement
from mortgage_underwriting.modules.document_management.schemas import (

    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentRequirementCreate,
    DocumentRequirementUpdate,
    DocumentRequirementResponse,
    DocumentChecklistResponse,
    ChecklistItem,
    ReceivedDocumentInfo
)

logger = structlog.get_logger()


class DocumentManagementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_document(self, payload: DocumentCreate) -> DocumentResponse:
        """Upload a new document."""
        logger.info("uploading_document", application_id=payload.application_id, document_type=payload.document_type.value)
        
        try:
            document = Document(**payload.model_dump())
            self.db.add(document)
            await self.db.commit()
            await self.db.refresh(document)
            
            # Update requirement status if applicable
            stmt = select(DocumentRequirement).where(
                DocumentRequirement.application_id == payload.application_id,
                DocumentRequirement.document_type == payload.document_type
            )
            result = await self.db.execute(stmt)
            req = result.scalar_one_or_none()
            if req and not req.is_received:
                req.is_received = True
                await self.db.commit()
                await self.db.refresh(req)
            
            return DocumentResponse.model_validate(document)
        except Exception as e:
            await self.db.rollback()
            logger.error("document_upload_failed", error=str(e))
            raise AppException(f"Failed to upload document: {str(e)}")

    async def get_document(self, doc_id: int) -> DocumentResponse:
        """Get a specific document by ID."""
        stmt = select(Document).where(Document.id == doc_id)
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError("Document not found")
            
        return DocumentResponse.model_validate(document)

    async def list_documents(self, application_id: int, page: int = 1, size: int = 20) -> Tuple[List[DocumentResponse], int]:
        """List documents for an application with pagination."""
        if size > 100:
            size = 100
            
        offset = (page - 1) * size
        
        # Count total
        count_stmt = select(func.count()).select_from(Document).where(Document.application_id == application_id)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        
        # Fetch paginated results
        stmt = (
            select(Document)
            .where(Document.application_id == application_id)
            .offset(offset)
            .limit(size)
            .order_by(Document.uploaded_at.desc())
        )
        
        result = await self.db.execute(stmt)
        documents = result.scalars().all()
        
        return [DocumentResponse.model_validate(d) for d in documents], total

    async def update_document_status(self, doc_id: int, update_data: DocumentUpdate) -> DocumentResponse:
        """Update document verification or rejection status."""
        stmt = select(Document).where(Document.id == doc_id)
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError("Document not found")
            
        logger.info("updating_document_status", document_id=doc_id, updates=update_data.model_dump(exclude_unset=True))
        
        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(document, field, value)
            
        await self.db.commit()
        await self.db.refresh(document)
        
        return DocumentResponse.model_validate(document)

    async def delete_document(self, doc_id: int) -> bool:
        """Delete a document."""
        stmt = select(Document).where(Document.id == doc_id)
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError("Document not found")
            
        await self.db.delete(document)
        await self.db.commit()
        
        logger.info("document_deleted", document_id=doc_id)
        return True

    async def get_checklist(self, application_id: int) -> DocumentChecklistResponse:
        """Get document checklist for an application."""
        logger.info("fetching_document_checklist", application_id=application_id)
        
        # Get all requirements for this application
        req_stmt = select(DocumentRequirement).where(DocumentRequirement.application_id == application_id)
        req_result = await self.db.execute(req_stmt)
        requirements = req_result.scalars().all()
        
        # Get all uploaded documents for this application
        doc_stmt = select(Document).where(Document.application_id == application_id)
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
        missing_required_count = 0
        
        for req in requirements:
            received_docs = []
            if req.document_type in docs_by_type:
                for doc in docs_by_type[req.document_type]:
                    received_docs.append(ReceivedDocumentInfo(
                        id=doc.id,
                        file_name=doc.file_name,
                        status=doc.status,
                        is_verified=doc.is_verified,
                        uploaded_at=doc.uploaded_at
                    ))
            
            # Determine item status
            status = "satisfied" if received_docs else ("overdue" if req.due_date and req.due_date < datetime.utcnow() else "pending")
            
            if req.is_required and not received_docs:
                missing_required_count += 1
                
            checklist_items.append(ChecklistItem(
                document_type=req.document_type,
                category=req.category,
                is_required=req.is_required,
                is_received=bool(received_docs),
                due_date=req.due_date,
                status=status,
                received_documents=received_docs
            ))
        
        # Overall status
        overall_status = "complete" if missing_required_count == 0 else "incomplete"
        
        return DocumentChecklistResponse(
            application_id=application_id,
            checklist_items=checklist_items,
            overall_status=overall_status,
            missing_required_count=missing_required_count
        )

    async def create_requirement(self, payload: DocumentRequirementCreate) -> DocumentRequirementResponse:
        """Create a new document requirement."""
        logger.info("creating_document_requirement", application_id=payload.application_id, document_type=payload.document_type.value)
        
        try:
            requirement = DocumentRequirement(**payload.model_dump())
            self.db.add(requirement)
            await self.db.commit()
            await self.db.refresh(requirement)
            
            return DocumentRequirementResponse.model_validate(requirement)
        except Exception as e:
            await self.db.rollback()
            logger.error("requirement_creation_failed", error=str(e))
            raise AppException(f"Failed to create requirement: {str(e)}")

    async def update_requirement(self, req_id: int, update_data: DocumentRequirementUpdate) -> DocumentRequirementResponse:
        """Update a document requirement."""
        stmt = select(DocumentRequirement).where(DocumentRequirement.id == req_id)
        result = await self.db.execute(stmt)
        requirement = result.scalar_one_or_none()
        
        if not requirement:
            raise NotFoundError("Document requirement not found")
            
        logger.info("updating_document_requirement", requirement_id=req_id, updates=update_data.model_dump(exclude_unset=True))
        
        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(requirement, field, value)
            
        await self.db.commit()
        await self.db.refresh(requirement)
        
        return DocumentRequirementResponse.model_validate(requirement)