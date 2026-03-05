import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List
from decimal import Decimal

from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicyDocument
from mortgage_underwriting.modules.xml_policy_service.schemas import (
    XmlPolicyDocumentCreate, 
    XmlPolicyDocumentUpdate,
    XmlPolicyDocumentResponse
)
from mortgage_underwriting.modules.xml_policy_service.exceptions import XmlPolicyServiceException

logger = structlog.get_logger()

class XmlPolicyDocumentService:
    """
    Service layer for managing XML policy documents.
    
    Regulatory Compliance:
    - FINTRAC: Audit trail through created_at/updated_at timestamps
    - PIPEDA: Minimizes data collection to only necessary fields
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_document(self, payload: XmlPolicyDocumentCreate) -> XmlPolicyDocument:
        """
        Create a new XML policy document.
        
        Args:
            payload: XmlPolicyDocumentCreate schema
            
        Returns:
            Created XmlPolicyDocument model
            
        Raises:
            XmlPolicyServiceException: If creation fails
        """
        logger.info("creating_xml_policy_document", application_id=payload.application_id)
        
        try:
            document = XmlPolicyDocument(**payload.model_dump())
            self.db.add(document)
            await self.db.commit()
            await self.db.refresh(document)
            
            logger.info("xml_policy_document_created", document_id=document.id)
            return document
        except Exception as e:
            await self.db.rollback()
            logger.error("failed_to_create_xml_policy_document", error=str(e))
            raise XmlPolicyServiceException(f"Failed to create document: {str(e)}")

    async def get_document(self, document_id: int) -> XmlPolicyDocument:
        """
        Retrieve an XML policy document by ID.
        
        Args:
            document_id: ID of the document to retrieve
            
        Returns:
            XmlPolicyDocument model
            
        Raises:
            XmlPolicyServiceException: If document not found
        """
        logger.info("retrieving_xml_policy_document", document_id=document_id)
        
        stmt = select(XmlPolicyDocument).where(XmlPolicyDocument.id == document_id)
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            logger.warning("xml_policy_document_not_found", document_id=document_id)
            raise XmlPolicyServiceException("Document not found")
            
        logger.info("xml_policy_document_retrieved", document_id=document_id)
        return document

    async def update_document(self, document_id: int, payload: XmlPolicyDocumentUpdate) -> XmlPolicyDocument:
        """
        Update an XML policy document.
        
        Args:
            document_id: ID of the document to update
            payload: XmlPolicyDocumentUpdate schema
            
        Returns:
            Updated XmlPolicyDocument model
            
        Raises:
            XmlPolicyServiceException: If document not found or update fails
        """
        logger.info("updating_xml_policy_document", document_id=document_id)
        
        document = await self.get_document(document_id)
        
        try:
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(document, field, value)
                
            await self.db.commit()
            await self.db.refresh(document)
            
            logger.info("xml_policy_document_updated", document_id=document_id)
            return document
        except Exception as e:
            await self.db.rollback()
            logger.error("failed_to_update_xml_policy_document", document_id=document_id, error=str(e))
            raise XmlPolicyServiceException(f"Failed to update document: {str(e)}")

    async def delete_document(self, document_id: int) -> bool:
        """
        Delete an XML policy document (soft delete by setting is_active=False).
        
        Args:
            document_id: ID of the document to delete
            
        Returns:
            True if successful
            
        Raises:
            XmlPolicyServiceException: If document not found or deletion fails
        """
        logger.info("deleting_xml_policy_document", document_id=document_id)
        
        document = await self.get_document(document_id)
        
        try:
            document.is_active = False
            await self.db.commit()
            
            logger.info("xml_policy_document_deleted", document_id=document_id)
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error("failed_to_delete_xml_policy_document", document_id=document_id, error=str(e))
            raise XmlPolicyServiceException(f"Failed to delete document: {str(e)}")

    async def get_policy_documents(self, application_id: int, skip: int = 0, limit: int = 100) -> tuple[List[XmlPolicyDocument], int]:
        """
        Get paginated list of policy documents for an application.
        
        Args:
            application_id: Filter by application ID
            skip: Number of records to skip (pagination)
            limit: Number of records to return (max 100)
            
        Returns:
            Tuple of (documents list, total count)
            
        Raises:
            XmlPolicyServiceException: If query fails
        """
        # FIXED: Implement pagination with skip/limit and enforce max limit of 100
        if limit > 100:
            limit = 100
            logger.info("limit_capped_to_100", original_limit=limit)
        
        logger.info("retrieving_xml_policy_documents", application_id=application_id, skip=skip, limit=limit)
        
        try:
            # Count total records
            count_stmt = select(func.count(XmlPolicyDocument.id)).where(
                XmlPolicyDocument.application_id == application_id,
                XmlPolicyDocument.is_active == True
            )
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar_one()
            
            # Fetch paginated records
            stmt = select(XmlPolicyDocument).where(
                XmlPolicyDocument.application_id == application_id,
                XmlPolicyDocument.is_active == True
            ).offset(skip).limit(limit)
            
            result = await self.db.execute(stmt)
            documents = list(result.scalars().all())
            
            logger.info("xml_policy_documents_retrieved", application_id=application_id, count=len(documents))
            return documents, total
        except Exception as e:
            logger.error("failed_to_retrieve_xml_policy_documents", error=str(e))
            raise XmlPolicyServiceException(f"Failed to retrieve documents: {str(e)}")
```

```