import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentCreate, DocumentResponse
from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.modules.document_management.exceptions import DocumentStorageError, DocumentNotFoundError

# Mock Models for Service Layer testing without full DB hit
@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.fixture
    def mock_storage(self):
        storage = AsyncMock()
        storage.upload_file.return_value = "secure_path/abc123.pdf"
        return storage

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_storage, valid_document_payload):
        """
        Test successful document upload, storage service call, and DB persistence.
        """
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        schema = DocumentCreate(**valid_document_payload)

        # Simulate DB returning the created object
        def mock_refresh(obj):
            obj.id = "doc-123"
            obj.created_at = datetime.utcnow()
            obj.updated_at = datetime.utcnow()

        mock_db.refresh.side_effect = mock_refresh

        # Act
        result = await service.upload_document(schema, file_content=b"fake_pdf_content")

        # Assert
        assert result.id == "doc-123"
        assert result.storage_path == "secure_path/abc123.pdf"
        assert result.upload_status == "COMPLETED"
        
        mock_storage.upload_file.assert_awaited_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_storage_failure(self, mock_db, mock_storage, valid_document_payload):
        """
        Test that DB transaction is rolled back if storage upload fails.
        """
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        schema = DocumentCreate(**valid_document_payload)
        mock_storage.upload_file.side_effect = Exception("S3 Connection Failed")

        # Act & Assert
        with pytest.raises(DocumentStorageError):
            await service.upload_document(schema, file_content=b"data")

        mock_db.add.assert_called_once()
        mock_db.commit.assert_not_awaited() # Should not commit if storage fails
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_invalid_file_type(self, mock_db, mock_storage):
        """
        Test validation of allowed file types (PIPEDA/Security compliance).
        """
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        payload = {
            "application_id": "123",
            "document_type": "ID",
            "file_name": "malware.exe",
            "content_type": "application/x-msdownload",
            "file_size_bytes": 500
        }
        schema = DocumentCreate(**payload)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid file type"):
            await service.upload_document(schema, b"exe_content")

        mock_storage.upload_file.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, mock_db):
        """
        Test retrieving a document metadata record.
        """
        # Arrange
        service = DocumentService(mock_db, AsyncMock())
        doc_id = "doc-123"
        
        mock_doc = Document(
            id=doc_id,
            application_id="app-123",
            document_type="PAY_STUB",
            storage_path="path/to/file",
            upload_status="COMPLETED",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_db.scalar.return_value = mock_doc

        # Act
        result = await service.get_document(doc_id)

        # Assert
        assert result.id == doc_id
        assert result.document_type == "PAY_STUB"
        mock_db.scalar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, mock_db):
        """
        Test exception when document ID does not exist.
        """
        # Arrange
        service = DocumentService(mock_db, AsyncMock())
        mock_db.scalar.return_value = None

        # Act & Assert
        with pytest.raises(DocumentNotFoundError):
            await service.get_document("non-existent-id")

    @pytest.mark.asyncio
    async def test_list_documents_by_application(self, mock_db):
        """
        Test listing all documents for a specific mortgage application.
        """
        # Arrange
        service = DocumentService(mock_db, AsyncMock())
        app_id = "app-456"
        
        # Mocking the execute result to return a list of scalars
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            Document(id="1", application_id=app_id, document_type="ID", storage_path="a", upload_status="COMPLETED", created_at=datetime.utcnow(), updated_at=datetime.utcnow()),
            Document(id="2", application_id=app_id, document_type="PAY_STUB", storage_path="b", upload_status="COMPLETED", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        ]
        mock_db.execute.return_value = mock_result

        # Act
        results = await service.list_documents(app_id)

        # Assert
        assert len(results) == 2
        assert all(doc.application_id == app_id for doc in results)

    @pytest.mark.asyncio
    async def test_delete_document_soft_delete(self, mock_db, mock_storage):
        """
        Test that document deletion is a soft delete (FINTRAC retention requirement).
        The record remains in DB but status changes, file might be archived.
        """
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        doc_id = "doc-999"
        
        mock_doc = Document(
            id=doc_id,
            application_id="app-1",
            document_type="CONTRACT",
            storage_path="active/file.pdf",
            upload_status="COMPLETED",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_db.scalar.return_value = mock_doc

        # Act
        await service.delete_document(doc_id)

        # Assert
        assert mock_doc.upload_status == "DELETED" # Soft delete
        # Verify file was moved to archive or deleted from storage
        mock_storage.archive_file.assert_awaited_once_with("active/file.pdf") 
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_verify_pii_not_logged(self, mock_db, mock_storage, valid_document_payload, caplog):
        """
        Verify that sensitive PII (e.g., SIN inside filename or content) is not logged.
        """
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        
        # Simulate a filename containing potential PII
        pii_payload = valid_document_payload.copy()
        pii_payload["file_name"] = "john_doe_SIN_123456789.pdf"
        schema = DocumentCreate(**pii_payload)

        # Mock logger
        with patch("mortgage_underwriting.modules.document_management.services.logger") as mock_logger:
            # Act
            await service.upload_document(schema, b"content")

            # Assert - Check that info/debug logs do not contain the raw filename or path if it includes PII
            # In a real scenario, the service should hash the filename before logging
            for call in mock_logger.info.call_args_list:
                log_message = str(call)
                assert "123456789" not in log_message, "PII found in logs!"
                assert "john_doe" not in log_message, "PII found in logs!"