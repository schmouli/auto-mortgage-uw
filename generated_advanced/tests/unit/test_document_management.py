import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentUpload, DocumentResponse, DocumentUpdate
)
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
        return db

    @pytest.fixture
    def mock_storage(self):
        storage = AsyncMock()
        storage.upload_file.return_value = "https://secure-storage.mortgage-co/uploads/uuid.pdf"
        storage.generate_presigned_url.return_value = "https://secure-storage.mortgage-co/downloads/uuid.pdf"
        return storage

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_storage):
        """Test successful document upload with audit trail creation."""
        payload = DocumentUpload(
            application_id=1,
            file_name="tax_return.pdf",
            file_type="application/pdf",
            document_type="T1_GENERAL"
        )
        file_content = b"fake pdf content"
        
        service = DocumentService(mock_db, mock_storage)
        
        # Mock the result of the refresh to simulate DB returning the object
        mock_db.refresh.side_effect = lambda obj: setattr(obj, 'id', 123)

        result = await service.upload_document(payload, file_content, user_id="user_123")

        assert result.id == 123
        assert result.file_name == "tax_return.pdf"
        assert result.uploaded_by == "user_123"
        assert result.status == "UPLOADED"
        assert result.file_path == "https://secure-storage.mortgage-co/uploads/uuid.pdf"
        
        # FINTRAC Compliance: Audit fields must be set
        assert result.created_at is not None
        assert result.updated_at is not None
        
        mock_storage.upload_file.assert_awaited_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_invalid_file_type(self, mock_db, mock_storage):
        """Test rejection of disallowed file types (e.g., .exe)."""
        payload = DocumentUpload(
            application_id=1,
            file_name="virus.exe",
            file_type="application/x-msdownload",
            document_type="OTHER"
        )
        
        service = DocumentService(mock_db, mock_storage)
        
        with pytest.raises(AppException) as exc_info:
            await service.upload_document(payload, b"content", user_id="user_123")
        
        assert exc_info.value.error_code == "INVALID_FILE_TYPE"
        assert "not allowed" in exc_info.value.detail
        mock_storage.upload_file.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_document_storage_failure(self, mock_db, mock_storage):
        """Test handling of external storage failure."""
        payload = DocumentUpload(
            application_id=1,
            file_name="large_file.pdf",
            file_type="application/pdf",
            document_type="APPRAISAL"
        )
        
        mock_storage.upload_file.side_effect = Exception("S3 Bucket Full")
        service = DocumentService(mock_db, mock_storage)
        
        with pytest.raises(AppException) as exc_info:
            await service.upload_document(payload, b"content", user_id="user_123")
        
        assert exc_info.value.error_code == "STORAGE_ERROR"
        # Ensure DB transaction is rolled back or not committed
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, mock_db, mock_storage):
        """Test retrieving document metadata."""
        # Mock the DB return value
        mock_doc = Document(
            id=1,
            application_id=1,
            file_name="report.pdf",
            file_type="application/pdf",
            file_path="path/to/file",
            status="UPLOADED",
            uploaded_by="user_1"
        )
        mock_db.scalar.return_value = mock_doc
        
        service = DocumentService(mock_db, mock_storage)
        result = await service.get_document_by_id(document_id=1)
        
        assert isinstance(result, DocumentResponse)
        assert result.file_name == "report.pdf"
        # PIPEDA Compliance: Ensure sensitive fields aren't exposed if they existed
        # (In this module, we mostly store metadata, but we ensure no raw content in response)
        assert "file_content" not in result.model_dump()

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, mock_db, mock_storage):
        """Test 404 scenario when document does not exist."""
        mock_db.scalar.return_value = None
        service = DocumentService(mock_db, mock_storage)
        
        with pytest.raises(AppException) as exc_info:
            await service.get_document_by_id(999)
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_soft_delete_document_fintrac_compliance(self, mock_db, mock_storage):
        """Test that documents are soft-deleted to satisfy FINTRAC retention rules."""
        mock_doc = Document(
            id=1,
            application_id=1,
            file_name="old_doc.pdf",
            file_type="application/pdf",
            file_path="path/to/file",
            status="UPLOADED",
            uploaded_by="user_1"
        )
        mock_db.scalar.return_value = mock_doc
        
        service = DocumentService(mock_db, mock_storage)
        await service.delete_document(document_id=1, user_id="admin_user")
        
        # FINTRAC: Never deleted or modified (in the sense of hard delete)
        # We verify status change, not removal from DB
        assert mock_doc.status == "DELETED"
        assert mock_doc.deleted_at is not None
        assert mock_doc.deleted_by == "admin_user"
        
        mock_storage.delete_file.assert_not_awaited() # We keep the file for retention
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_document_status(self, mock_db, mock_storage):
        """Test updating document status (e.g., UPLOADED -> VERIFIED)."""
        mock_doc = Document(
            id=1,
            application_id=1,
            file_name="doc.pdf",
            file_type="application/pdf",
            file_path="path",
            status="UPLOADED",
            uploaded_by="user_1"
        )
        mock_db.scalar.return_value = mock_doc
        
        service = DocumentService(mock_db, mock_storage)
        update_schema = DocumentUpdate(status="VERIFIED", notes="Reviewed by agent")
        
        result = await service.update_document(1, update_schema)
        
        assert result.status == "VERIFIED"
        assert result.notes == "Reviewed by agent"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_documents_by_application(self, mock_db, mock_storage):
        """Test retrieving all documents for a specific mortgage application."""
        # Mocking the execute/scalar chain for listing
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            Document(id=1, file_name="a.pdf", application_id=10, status="UPLOADED", uploaded_by="u1", file_type="pdf", file_path="p1"),
            Document(id=2, file_name="b.jpg", application_id=10, status="UPLOADED", uploaded_by="u1", file_type="jpg", file_path="p2"),
        ]
        mock_db.execute.return_value = mock_result
        
        service = DocumentService(mock_db, mock_storage)
        results = await service.list_documents(application_id=10)
        
        assert len(results) == 2
        assert results[0].file_name == "a.pdf"
        assert results[1].file_name == "b.jpg"

    @pytest.mark.asyncio
    async def test_pipeda_check_no_logging_of_pii(self, mock_db, mock_storage, caplog):
        """Ensure that sensitive info (if passed) is not logged."""
        payload = DocumentUpload(
            application_id=1,
            file_name="sin_card.jpg", # Sensitive name
            file_type="image/jpeg",
            document_type="IDENTITY"
        )
        
        service = DocumentService(mock_db, mock_storage)
        
        # Suppress actual logging logic for this test, just verify logic flow
        with patch("mortgage_underwriting.modules.document_management.services.logger") as mock_logger:
            await service.upload_document(payload, b"img", user_id="user_123")
            
            # Verify any log calls do not contain raw binary data or specific PII strings if they were in payload
            for call in mock_logger.info.call_args_list:
                log_str = str(call)
                assert "sin_card.jpg" not in log_str or "sanitized" in log_str