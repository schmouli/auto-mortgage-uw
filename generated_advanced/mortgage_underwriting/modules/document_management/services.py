from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import os
from sqlalchemy import select, and_
import structlog
from mortgage_underwriting.common.exceptions import NotFoundError, ValidationError
from mortgage_underwriting.modules.document_management.models import Document, DocumentRequirement
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentCreate, DocumentUpdate, DocumentResponse,
    DocumentRequirementCreate, DocumentRequirementUpdate, DocumentRequirementResponse,
    ChecklistItemResponse, ChecklistResponse, DocumentCategory
)

logger = structlog.get_logger()


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_checklist(self, application_id: int) -> ChecklistResponse:
        """Get document requirements checklist for an application."""
        logger.info("getting_document_checklist", application_id=application_id)
        
        # Get all requirements for this application
        stmt = select(DocumentRequirement).where(DocumentRequirement.application_id == application_id)
        result = await self.db.execute(stmt)
        requirements = result.scalars().all()
        
        if not requirements:
            raise NotFoundError(f"No document requirements found for application {application_id}")
            
        # Get uploaded documents for this application
        doc_stmt = select(Document).where(Document.application_id == application_id)
        doc_result = await self.db.execute(doc_stmt)
        documents = doc_result.scalars().all()
        
        # Create mapping of document_type to document for quick lookup
        doc_map = {doc.document_type: doc for doc in documents}
        
        checklist_items = []
        required_received = 0
        required_total = 0
        
        for req in requirements:
            if req.is_required:
                required_total += 1
                
            # Determine category based on document type
            category = self._get_document_category(req.document_type)
            
            # Check if document exists and is accepted
            doc = doc_map.get(req.document_type)
            is_received = False
            received_at = None
            document_id = None
            status = "pending"
            
            if doc and doc.status == "accepted":
                is_received = True
                received_at = doc.uploaded_at
                document_id = doc.id
                status = "received"
            elif doc and doc.status == "rejected":
                status = "rejected"
            elif req.due_date and req.due_date < datetime.utcnow():
                status = "overdue"
                
            if is_received and req.is_required:
                required_received += 1
                
            checklist_items.append(ChecklistItemResponse(
                document_type=req.document_type,
                category=category,
                is_required=req.is_required,
                is_received=is_received,
                due_date=req.due_date,
                status=status,
                received_at=received_at,
                document_id=document_id
            ))
            
        # Calculate completion percentage
        percentage = (required_received / required_total * 100) if required_total > 0 else 0
        
        return ChecklistResponse(
            application_id=application_id,
            checklist=checklist_items,
            overall_completion={
                "required_received": required_received,
                "required_total": required_total,
                "percentage": round(percentage, 2)
            }
        )

    async def upload_document(self, application_id: int, uploaded_by: int, file_data: bytes, filename: str, mime_type: str, document_type: str, description: Optional[str] = None) -> DocumentResponse:
        """Upload a new document."""
        logger.info("uploading_document", application_id=application_id, document_type=document_type)
        
        # Validate file size
        if len(file_data) > 10 * 1024 * 1024:  # 10MB
            raise ValidationError("File size exceeds maximum allowed size of 10MB")
            
        # Validate MIME type
        allowed_mime_types = ["application/pdf", "image/jpeg", "image/png", "image/heic"]
        if mime_type not in allowed_mime_types:
            raise ValidationError(f"Unsupported MIME type: {mime_type}")
            
        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)
        
        # Generate file path
        file_path = f"uploads/{application_id}/{document_type}/{safe_filename}"
        
        # Convert HEIC to PDF if needed (placeholder)
        if mime_type == "image/heic":
            # In real implementation, convert HEIC to PDF
            # For now, we'll just log it
            logger.info("converting_heic_to_pdf", filename=safe_filename)
            
        # Log file hash for virus scanning (placeholder)
        file_hash = self._calculate_file_hash(file_data)
        logger.info("file_uploaded_for_virus_scan", file_hash=file_hash)
        
        # Create document record
        doc_create = DocumentCreate(
            application_id=application_id,
            uploaded_by=uploaded_by,
            document_type=document_type,
            file_name=safe_filename,
            file_path=file_path,
            file_size=len(file_data),
            mime_type=mime_type
        )
        
        document = Document(**doc_create.model_dump())
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        
        return DocumentResponse.model_validate(document)

    async def list_documents(self, application_id: int) -> List[DocumentResponse]:
        """List all documents for an application."""
        logger.info("listing_documents", application_id=application_id)
        
        stmt = select(Document).where(Document.application_id == application_id)
        result = await self.db.execute(stmt)
        documents = result.scalars().all()
        
        return [DocumentResponse.model_validate(doc) for doc in documents]

    async def get_document(self, application_id: int, document_id: int) -> DocumentResponse:
        """Get a specific document."""
        logger.info("getting_document", application_id=application_id, document_id=document_id)
        
        stmt = select(Document).where(and_(Document.id == document_id, Document.application_id == application_id))
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError(f"Document {document_id} not found for application {application_id}")
            
        return DocumentResponse.model_validate(document)

    async def verify_document(self, application_id: int, document_id: int, verified_by: int) -> DocumentResponse:
        """Mark a document as verified."""
        logger.info("verifying_document", application_id=application_id, document_id=document_id)
        
        stmt = select(Document).where(and_(Document.id == document_id, Document.application_id == application_id))
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError(f"Document {document_id} not found for application {application_id}")
            
        document.is_verified = True
        document.verified_by = verified_by
        document.verified_at = datetime.utcnow()
        document.status = "accepted"
        
        await self.db.commit()
        await self.db.refresh(document)
        
        return DocumentResponse.model_validate(document)

    async def reject_document(self, application_id: int, document_id: int, rejection_reason: str) -> DocumentResponse:
        """Reject a document with a reason."""
        logger.info("rejecting_document", application_id=application_id, document_id=document_id)
        
        stmt = select(Document).where(and_(Document.id == document_id, Document.application_id == application_id))
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError(f"Document {document_id} not found for application {application_id}")
            
        document.status = "rejected"
        document.rejection_reason = rejection_reason
        
        await self.db.commit()
        await self.db.refresh(document)
        
        return DocumentResponse.model_validate(document)

    async def delete_document(self, application_id: int, document_id: int) -> bool:
        """Delete a document."""
        logger.info("deleting_document", application_id=application_id, document_id=document_id)
        
        stmt = select(Document).where(and_(Document.id == document_id, Document.application_id == application_id))
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise NotFoundError(f"Document {document_id} not found for application {application_id}")
            
        await self.db.delete(document)
        await self.db.commit()
        
        return True

    def _get_document_category(self, document_type: str) -> DocumentCategory:
        """Determine document category based on type."""
        identity_types = ["government_id", "proof_of_sin"]
        income_types = ["t4_slip", "noa", "pay_stub", "employment_letter", "t1_general", "financial_statements", "rental_income_statement"]
        property_types = ["purchase_agreement", "mls_listing", "property_tax_bill", "condo_status_cert"]
        banking_types = ["bank_statement", "void_cheque"]
        down_payment_types = ["gift_letter", "rrsp_withdrawal_confirmation", "sale_proceeds_confirmation"]
        
        if document_type in identity_types:
            return DocumentCategory.IDENTITY
        elif document_type in income_types:
            return DocumentCategory.INCOME
        elif document_type in property_types:
            return DocumentCategory.PROPERTY
        elif document_type in banking_types:
            return DocumentCategory.BANKING
        elif document_type in down_payment_types:
            return DocumentCategory.DOWN_PAYMENT
        else:
            return DocumentCategory.OTHER

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename by removing special characters."""
        # Remove path components and special characters except dots, hyphens, and underscores
        clean_name = os.path.basename(filename)
        clean_name = "".join(c for c in clean_name if c.isalnum() or c in ".-_ ")
        return clean_name.strip()

    def _calculate_file_hash(self, file_data: bytes) -> str:
        """Calculate SHA256 hash of file data (placeholder)."""
        # In real implementation, calculate actual hash
        # For now, return placeholder
        return "sha256:" + str(hash(file_data))[:32]