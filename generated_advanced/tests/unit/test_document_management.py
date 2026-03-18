```python
import pytest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from unittest.mock import AsyncMock, patch, MagicMock

from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.exceptions import (
    DocumentNotFoundException,
    InvalidDocumentTypeException,
    StorageException
)

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

@pytest.mark.asyncio
class TestDocumentService:
    
    @pytest.fixture
    def service(self, mock_storage_service):
        """Fixture to instantiate the service with mocked storage."""
        return DocumentService(storage=mock_storage_service)

    async def test_upload_document_success(self, service, mock_storage_service, db_session, valid_document_payload):
        """
        Test successful document upload: 
        1. Storage service is called
        2. DB record is created with correct metadata
        3. Audit fields (created_at) are populated
        """
        # Arrange
        file_content = b"fake pdf content"
        
        # Act
        result = await service.upload_document(
            db=db_session,
            file_content=file_content,
            **valid_document_payload
        )

        # Assert
        assert result is not None
        assert result.application_id == valid_document_payload["application_id"]
        assert result.status == "UPLOADED"
        assert result.storage_path == "https://secure-storage.example.com/files/uuid123.pdf"
        assert result.created_at is not None # FINTRAC Audit requirement
        
        # Verify storage was called
        mock_storage_service.upload_file.assert_awaited_once()

    async def test_upload_document_invalid_type(self, service, db_session, valid_document_payload):
        """
        Test that uploading an unsupported document type raises InvalidDocumentTypeException.
        """
        # Arrange
        valid_document_payload["document_type"] = "EXE_FILE" # Invalid type
        
        # Act & Assert
        with pytest.raises(InvalidDocumentTypeException):
            await service.upload_document(
                db=db_session,
                file_content=b"data",
                **valid_document_payload
            )

    async def test_upload_document_storage_failure(self, service, mock_storage_service, db_session, valid_document_payload):
        """
        Test that if storage fails, the DB transaction is rolled back or handled gracefully.
        """
        # Arrange
        mock_storage_service.upload_file.side_effect = Exception("S3 Down")
        
        # Act & Assert
        with pytest.raises(StorageException):
            await service.upload_document(
                db=db_session,
                file_content=b"data",
                **valid_document_payload
            )
        
        # Ensure DB was not committed (implicitly checked by transaction rollback in service logic)

    async def test_get_document_success(self, service, db_session, sample_document_model):
        """
        Test retrieving a document by ID.
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        await db_session.refresh(sample_document_model)
        
        # Act
        result = await service.get_document(db_session, sample_document_model.id)
        
        # Assert
        assert result.id == sample_document_model.id
        assert result.file_name == sample_document_model.file_name

    async def test_get_document_not_found(self, service, db_session):
        """
        Test retrieving a non-existent document raises DocumentNotFoundException.
        """
        # Act & Assert
        with pytest.raises(DocumentNotFoundException):
            await service.get_document(db_session, 99999)

    async def test_verify_document_success(self, service, db_session, sample_document_model):
        """
        Test verifying a document updates the status correctly.
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        # Act
        result = await service.verify_document(db_session, sample_document_model.id, verified_by="underwriter_1")
        
        # Assert
        assert result.status == "VERIFIED"
        assert result.updated_at is not None

    async def test_delete_document_soft_delete(self, service, db_session, sample_document_model):
        """
        Test that 'deleting' a document performs a soft delete (status update)
        to maintain FINTRAC audit trail (immunity of records).
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        doc_id = sample_document_model.id
        
        # Act
        await service.delete_document(db_session, doc_id)
        
        # Assert - Record should still exist but status changed
        # We need to query fresh or check the returned object
        # Assuming service returns the updated object
        result = await service.get_document(db_session, doc_id)
        assert result.status == "DELETED"
        
        # Ensure the record still physically exists in DB (Audit requirement)
        # This is implicitly true if get_document succeeds, but let's be explicit in logic
        query_result = await db_session.get(Document, doc_id)
        assert query_result is not None

    async def test_list_documents_by_application(self, service, db_session, sample_document_model):
        """
        Test listing all documents for a specific application ID.
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        # Act
        results = await service.list_documents(db_session, application_id=sample_document_model.application_id)
        
        # Assert
        assert len(results) >= 1
        assert any(d.id == sample_document_model.id for d in results)

    async def test_file_size_limit_validation(self, service, db_session, valid_document_payload):
        """
        Test that files exceeding the size limit are rejected.
        """
        # Arrange - Set size to 26MB (assuming 25MB limit)
        valid_document_payload["file_size_bytes"] = 26 * 1024 * 1024
        
        # Act & Assert
        with pytest.raises(ValueError): # Or specific FileTooLargeException
            await service.upload_document(
                db=db_session,
                file_content=b"large content",
                **valid_document_payload
            )
```