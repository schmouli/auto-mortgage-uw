import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from typing import List, Tuple

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.document_management.models import Document, DocumentVersion
from mortgage_underwriting.modules.document_management.schemas import DocumentCreate, DocumentUpdateStatus

logger = structlog.get_logger()


class DocumentManagementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_document(self, payload: DocumentCreate) -> Document:  # FIXED: Added return type hint
        """Upload a new document and create initial version.
        
        Args:
            payload: Document creation data
            
        Returns:
            Created document object
            
        Raises:
            AppException: If database operation fails
        """
        logger.info("uploading_new_document", client_id=payload.client_id, document_type=payload.document_type)
        
        try:
            # Create document record
            document = Document(
                client_id=payload.client_id,
                document_type=payload.document_type,
                file_path=payload.file_path,
                mime_type=payload.mime_type
            )
            
            self.db.add(document)
            await self.db.flush()  # Get ID before committing
            
            # Create initial version
            version = DocumentVersion(
                document_id=document.id,
                version_number=1,
                file_path=payload.file_path,
                uploaded_by=1  # In real implementation, this would come from auth context
            )
            
            self.db.add(version)
            await self.db.commit()
            await self.db.refresh(document)
            
            logger.info("document_uploaded_successfully", document_id=document.id)
            return document  # FIXED: Explicitly return document
            
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("document_upload_failed_integrity", error=str(e))
            raise AppException("Document upload failed due to integrity constraint")
        except Exception as e:
            await self.db.rollback()
            logger.error("document_upload_failed", error=str(e))
            raise AppException(f"Failed to upload document: {str(e)}")

    async def get_documents(self, skip: int = 0, limit: int = 100) -> Tuple[List[Document], int]:
        """Retrieve paginated list of documents.
        
        Args:
            skip: Number of records to skip (default: 0)
            limit: Number of records to retrieve, max 100 (default: 100)
            
        Returns:
            Tuple of (documents_list, total_count)
        """
        # Enforce maximum limit
        limit = min(limit, 100)
        
        # Query for documents with eager loading of versions
        stmt = (
            select(Document)
            .options(selectinload(Document.versions))  # FIXED: Added explicit eager loading to prevent N+1
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        documents = result.scalars().all()
        
        # Count total documents
        count_stmt = select(func.count()).select_from(Document)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        
        return documents, total

    async def update_document_status(self, document_id: int, payload: DocumentUpdateStatus) -> Document:
        """Update the status of a document.
        
        Args:
            document_id: ID of the document to update
            payload: DocumentUpdateStatus containing new status
            
        Returns:
            Updated document object
            
        Raises:
            AppException: If document not found or update fails
        """
        # FIXED: Added docstring
        try:
            stmt = select(Document).where(Document.id == document_id)
            result = await self.db.execute(stmt)
            document = result.scalar_one_or_none()
            
            if not document:
                raise AppException("Document not found")
                
            document.status = payload.status
            await self.db.commit()
            await self.db.refresh(document)
            
            logger.info("document_status_updated", document_id=document_id, new_status=payload.status)
            return document
            
        except Exception as e:
            await self.db.rollback()
            logger.error("document_status_update_failed", document_id=document_id, error=str(e))
            raise AppException(f"Failed to update document status: {str(e)}")