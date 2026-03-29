```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

# Absolute imports as per project conventions
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentUpload,
    DocumentResponse,
    DocumentStatusUpdate
)
from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.modules.document_management.exceptions import (
    DocumentUploadError,
    DocumentNotFoundError,
    InvalidFileTypeError
)

@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def mock_db(self):
        """Mock async database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.fixture
    def mock_storage(self):
        """Mock S3/Storage client."""
        storage = MagicMock()
        storage.upload_fileobj = AsyncMock()
        storage.delete_object = AsyncMock()
        storage.generate_presigned_url = MagicMock(return_value="http://secure.url/file")
        return storage

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_storage):
        """Test successful document upload and DB record creation."""
        service = DocumentService(mock_db, mock_storage)
        
        payload = DocumentUpload(
            borrower_id=1,
            file_name="paystub_2023.pdf",
            document_type="income_verification",
            mime_type="application/pdf",
            file_data=b"fake_pdf_content"
        )

        # Mock the DB result after commit to return the object with ID
        def refresh_side_effect(obj):
            obj.id = 999
            obj.created_at = datetime.utcnow()
            obj.updated_at = datetime.utcnow()
        
        mock_db.refresh.side_effect = refresh_side_effect

        result = await service.upload_document(payload)

        # Assertions
        assert isinstance(result, Document)
        assert result.id == 999
        assert result.file_name == "paystub_2023.pdf"
        assert result.status == "uploaded"
        assert result.s3_key is not None
        
        # Verify interactions
        mock_storage.upload_fileobj.assert_awaited_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_invalid_file_type(self, mock_db, mock_storage):
        """Test that uploading an executable file is rejected (Security)."""
        service = DocumentService(mock_db, mock_storage)
        
        payload = DocumentUpload(
            borrower_id=1,
            file_name="virus.exe",
            document_type="other",
            mime_type="application/x-msdownload",
            file_data=b"malicious"
        )

        with pytest.raises(InvalidFileTypeError):
            await service.upload_document(payload)

        # Ensure no DB or S3 operations occurred
        mock_db.add.assert_not_called()
        mock_storage.upload_fileobj.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_document_s3_failure(self, mock_db, mock_storage):
        """Test handling of S3 upload failure."""
        service = DocumentService(mock_db, mock_storage)
        
        payload = DocumentUpload(
            borrower_id=1,
            file_name="doc.pdf",
            document_type="id",
            mime_type="application/pdf",
            file_data=b"data"
        )

        mock_storage.upload_fileobj.side_effect = Exception("S3 Connection Timeout")

        with pytest.raises(DocumentUploadError):
            await service.upload_document(payload)

        # Verify transaction rollback logic (service should handle rollback)
        mock_db.rollback.assert_awaited_once()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, mock_db, mock_storage):
        """Test retrieving an existing document."""
        service = DocumentService(mock_db, mock_storage)
        
        # Mock DB return
        mock_doc = Document(
            id=1,
            borrower_id=1,
            file_name="test.pdf",
            s3_key="docs/test.pdf",
            status="uploaded"
        )
        mock_db.scalar.return_value = mock_doc

        result = await service.get_document_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.file_name == "test.pdf"

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self, mock_db, mock_storage):
        """Test retrieving a non-existent document raises error."""
        service = DocumentService(mock_db, mock_storage)
        mock_db.scalar.return_value = None

        with pytest.raises(DocumentNotFoundError):
            await service.get_document_by_id(999)

    @pytest.mark.asyncio
    async def test_update_document_status_success(self, mock_db, mock_storage):
        """Test updating document status (e.g., Verified)."""
        service = DocumentService(mock_db, mock_storage)
        
        mock_doc = Document(
            id=1,
            borrower_id=1,
            file_name="test.pdf",
            s3_key="docs/test.pdf",
            status="uploaded"
        )
        mock_db.scalar.return_value = mock_doc

        update_payload = DocumentStatusUpdate(status="verified", notes="Clear")
        result = await service.update_document_status(1, update_payload)

        assert result.status == "verified"
        assert result.verification_notes == "Clear"
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_document_soft_delete_logic(self, mock_db, mock_storage):
        """
        Test document deletion. 
        Per FINTRAC, records should be immutable. 
        We expect a soft delete (status change to 'archived' or 'deleted') 
        rather than a hard DB delete, or a specific audit log entry.
        """
        service = DocumentService(mock_db, mock_storage)
        
        mock_doc = Document(
            id=1,
            borrower_id=1,
            file_name="test.pdf",
            s3_key="docs/test.pdf",
            status="uploaded"
        )
        mock_db.scalar.return_value = mock_doc

        await service.delete_document(1)

        # Assuming soft delete implementation for compliance
        assert mock_doc.status == "deleted" or mock_doc.status == "archived"
        mock_db.commit.assert_awaited_once()
        
        # Verify S3 file is also removed for security
        mock_storage.delete_object.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_documents_by_borrower(self, mock_db, mock_storage):
        """Test filtering documents by borrower_id."""
        service = DocumentService(mock_db, mock_storage)
        
        mock_docs = [
            Document(id=1, borrower_id=5, file_name="a.pdf", s3_key="a", status="uploaded"),
            Document(id=2, borrower_id=5, file_name="b.pdf", s3_key="b", status="verified"),
        ]
        
        # Mocking the scalars().all() chain
        mock_result = MagicMock()
        mock_result.all.return_value = mock_docs
        mock_db.scalars.return_value = mock_result

        results = await service.list_documents(borrower_id=5)

        assert len(results) == 2
        assert all(doc.borrower_id == 5 for doc in results)
```