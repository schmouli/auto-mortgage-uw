import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.document_management.models import Document, DocumentStatus
from mortgage_underwriting.modules.document_management.schemas import DocumentUpload, DocumentResponse
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
        db.scalar = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.fixture
    def mock_storage(self):
        storage = MagicMock()
        storage.upload_file = AsyncMock(return_value="s3://bucket/key.pdf")
        return storage

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_storage, document_payload):
        """Test successful document upload and record creation."""
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        payload = DocumentUpload(**document_payload)

        # Act
        result = await service.upload_document(file_content=b"fake_pdf_content", payload=payload)

        # Assert
        assert isinstance(result, DocumentResponse)
        assert result.applicant_id == document_payload["applicant_id"]
        assert result.status == DocumentStatus.UPLOADED
        assert result.file_name == document_payload["file_name"]
        
        mock_storage.upload_file.assert_awaited_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_storage_failure(self, mock_db, mock_storage, document_payload):
        """Test rollback when storage service fails."""
        # Arrange
        mock_storage.upload_file = AsyncMock(side_effect=Exception("S3 Connection Error"))
        service = DocumentService(mock_db, mock_storage)
        payload = DocumentUpload(**document_payload)

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.upload_document(file_content=b"fake_pdf_content", payload=payload)
        
        assert "Failed to upload document" in str(exc_info.value)
        mock_db.rollback.assert_awaited_once()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_document_db_failure(self, mock_db, mock_storage, document_payload):
        """Test handling of database errors during save."""
        # Arrange
        mock_db.commit = AsyncMock(side_effect=SQLAlchemyError("DB constraint violation"))
        service = DocumentService(mock_db, mock_storage)
        payload = DocumentUpload(**document_payload)

        # Act & Assert
        with pytest.raises(AppException):
            await service.upload_document(file_content=b"fake", payload=payload)
        
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, mock_db, sample_document):
        """Test retrieving a document by ID."""
        # Arrange
        mock_db.scalar.return_value = sample_document
        service = DocumentService(mock_db, MagicMock())

        # Act
        result = await service.get_document(document_id="uuid-doc-123")

        # Assert
        assert result is not None
        assert result.id == sample_document.id
        assert result.file_name == sample_document.file_name
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, mock_db):
        """Test retrieving a non-existent document."""
        # Arrange
        mock_db.scalar.return_value = None
        service = DocumentService(mock_db, MagicMock())

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_document(document_id="non-existent-id")
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_verify_document_success(self, mock_db, sample_document):
        """Test verifying a document (status update)."""
        # Arrange
        mock_db.scalar.return_value = sample_document
        service = DocumentService(mock_db, MagicMock())

        # Act
        result = await service.verify_document(document_id="uuid-doc-123", verified_by="underwriter_1")

        # Assert
        assert result.status == DocumentStatus.VERIFIED
        assert result.verified_by == "underwriter_1"
        assert result.verified_at is not None
        
        # Compliance: Ensure audit fields are updated
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_documents_by_applicant(self, mock_db, sample_document):
        """Test listing all documents for a specific applicant."""
        # Arrange
        # Mocking the execute().scalars().all() chain
        mock_result = AsyncMock()
        mock_result.all.return_value = [sample_document]
        mock_db.execute.return_value = mock_result
        
        service = DocumentService(mock_db, MagicMock())

        # Act
        results = await service.list_documents(applicant_id="uuid-applicant-123")

        # Assert
        assert len(results) == 1
        assert results[0].applicant_id == "uuid-applicant-123"

    @pytest.mark.asyncio
    async def test_delete_document_success(self, mock_db, sample_document, mock_storage):
        """Test soft delete or marking as deleted."""
        # Arrange
        mock_db.scalar.return_value = sample_document
        service = DocumentService(mock_db, mock_storage)

        # Act
        await service.delete_document(document_id="uuid-doc-123")

        # Assert
        # Compliance: FINTRAC requires immutable records, so we check for status change or soft delete flag
        # Assuming 'is_deleted' flag or status change to DELETED
        assert sample_document.is_deleted is True 
        mock_db.commit.assert_awaited_once()
        # Storage should eventually be cleaned up, maybe via async task, 
        # but for now let's assume service handles it or just marks DB
        # If service deletes from storage immediately:
        # mock_storage.delete_file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_file_type(self, mock_db, mock_storage, document_payload):
        """Test rejection of unauthorized file types (e.g., .exe)."""
        # Arrange
        document_payload["file_name"] = "virus.exe"
        document_payload["mime_type"] = "application/x-msdownload"
        service = DocumentService(mock_db, mock_storage)
        payload = DocumentUpload(**document_payload)

        # Act & Assert
        with pytest.raises(ValueError): # Or AppException depending on implementation
            await service.upload_document(file_content=b"binary", payload=payload)
        
        mock_db.add.assert_not_called()