import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentUpload, DocumentResponse, DocumentStatus
from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_storage_service, valid_document_payload):
        # Arrange
        service = DocumentService(mock_db)
        schema = DocumentUpload(**valid_document_payload)
        
        # Mock the file content (bytes) not present in schema, usually passed separately
        file_content = b"fake pdf content"
        
        # Act
        result = await service.upload_document(schema, file_content)

        # Assert
        assert isinstance(result, DocumentResponse)
        assert result.application_id == valid_document_payload["application_id"]
        assert result.storage_path == "https://storage.example.com/docs/123.pdf"
        assert result.status == DocumentStatus.UPLOADED
        
        # Verify storage interaction
        mock_storage_service.upload_file.assert_awaited_once()
        
        # Verify DB interaction
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_storage_failure_rollback(self, mock_db, mock_storage_service, valid_document_payload):
        # Arrange
        service = DocumentService(mock_db)
        schema = DocumentUpload(**valid_document_payload)
        mock_storage_service.upload_file.side_effect = Exception("S3 Connection Error")

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.upload_document(schema, b"content")
        
        assert "Failed to upload document" in str(exc_info.value)
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_document_invalid_type(self, mock_db, valid_document_payload):
        # Arrange
        invalid_payload = valid_document_payload.copy()
        invalid_payload["document_type"] = "executable_exe" # Invalid type
        
        service = DocumentService(mock_db)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.upload_document(DocumentUpload(**invalid_payload), b"content")
        
        assert "Invalid document type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, mock_db, sample_document):
        # Arrange
        service = DocumentService(mock_db)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_document
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.get_document(document_id=1)

        # Assert
        assert result is not None
        assert result.id == 1
        assert result.file_name == "paystub.pdf"

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self, mock_db):
        # Arrange
        service = DocumentService(mock_db)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_document(document_id=999)
        
        assert exc_info.value.status_code == 404
        assert "Document not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_list_documents_by_application(self, mock_db, sample_document):
        # Arrange
        service = DocumentService(mock_db)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_document]
        mock_db.execute.return_value = mock_result

        # Act
        results = await service.list_documents(application_id="app-12345678")

        # Assert
        assert len(results) == 1
        assert results[0].application_id == "app-12345678"

    @pytest.mark.asyncio
    async def test_update_document_status_success(self, mock_db, sample_document):
        # Arrange
        service = DocumentService(mock_db)
        # Setup mock for fetching then updating
        mock_result_get = MagicMock()
        mock_result_get.scalar_one_or_none.return_value = sample_document
        mock_db.execute.return_value = mock_result_get

        # Act
        result = await service.update_document_status(document_id=1, new_status=DocumentStatus.VERIFIED)

        # Assert
        assert result.status == DocumentStatus.VERIFIED
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_document_soft_delete(self, mock_db, sample_document, mock_storage_service):
        # Arrange
        service = DocumentService(mock_db)
        mock_result_get = MagicMock()
        mock_result_get.scalar_one_or_none.return_value = sample_document
        mock_db.execute.return_value = mock_result_get

        # Act
        await service.delete_document(document_id=1)

        # Assert
        # Check that status changed to DELETED or similar, not actual DB deletion
        assert sample_document.status == DocumentStatus.DELETED
        # Verify file was not actually deleted from storage (Retention policy)
        mock_storage_service.delete_file.assert_not_awaited()
        mock_db.commit.assert_awaited_once()