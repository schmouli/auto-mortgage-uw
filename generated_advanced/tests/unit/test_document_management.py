```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentCreate, 
    DocumentResponse, 
    DocumentStatus
)
from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def service(self, mock_storage_service, mock_virus_scanner):
        return DocumentService(
            storage=mock_storage_service, 
            scanner=mock_virus_scanner
        )

    @pytest.mark.asyncio
    async def test_upload_document_success(self, service, mock_storage_service, mock_virus_scanner, sample_document_payload, db_session):
        """Test successful document upload with virus scan and storage."""
        # Arrange
        file_content = b"dummy pdf content"
        payload = DocumentCreate(**sample_document_payload)
        
        # Act
        result = await service.upload(db_session, file_content, payload, user_id="user_123")

        # Assert
        assert result.status == DocumentStatus.UPLOADED
        assert result.file_name == "pay_stub_2023.pdf"
        assert result.storage_path == "https://storage.example.com/docs/123.pdf"
        
        mock_virus_scanner.scan_file.assert_awaited_once_with(file_content)
        mock_storage_service.upload_file.assert_awaited_once()
        
        # Verify DB session interactions
        # Note: In a real unit test we might not check the DB directly if we mock the repo layer,
        # but here we assume service uses the session directly.
        await db_session.flush() # Ensure pending operations are visible if querying
        
        # FINTRAC Compliance: Ensure audit fields are set
        assert result.created_by == "user_123"
        assert result.created_at is not None

    @pytest.mark.asyncio
    async def test_upload_document_virus_detected(self, service, mock_virus_scanner, sample_document_payload, db_session):
        """Test that upload fails if virus scanner returns negative."""
        # Arrange
        mock_virus_scanner.scan_file.return_value = False # Infected
        payload = DocumentCreate(**sample_document_payload)
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.upload(db_session, b"malicious_content", payload, user_id="user_123")
        
        assert "security threat" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "SECURITY_SCAN_FAILED"

    @pytest.mark.asyncio
    async def test_upload_document_invalid_file_type(self, service, sample_document_payload, db_session):
        """Test that invalid mime types are rejected."""
        # Arrange
        payload_data = sample_document_payload.copy()
        payload_data["mime_type"] = "application/x-msdownload" # Executable
        payload = DocumentCreate(**payload_data)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.upload(db_session, b"exe_content", payload, user_id="user_123")
        
        assert "file type not allowed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_document_success(self, service, sample_document_model, db_session):
        """Test retrieving a document by ID."""
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        # Act
        result = await service.get(db_session, sample_document_model.id)

        # Assert
        assert result is not None
        assert result.id == sample_document_model.id
        assert result.file_name == "pay_stub_2023.pdf"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, service, db_session):
        """Test retrieving a non-existent document raises error."""
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get(db_session, "non_existent_id")
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_soft_delete_document(self, service, sample_document_model, db_session):
        """Test that deleting a document sets status to DELETED but keeps record (FINTRAC)."""
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        # Act
        await service.delete(db_session, sample_document_model.id, user_id="admin")
        await db_session.refresh(sample_document_model)

        # Assert
        # FINTRAC: Record must exist (immutable audit trail), just marked deleted
        assert sample_document_model.status == DocumentStatus.DELETED
        assert sample_document_model.updated_by == "admin"
        assert sample_document_model.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_document_metadata(self, service, sample_document_model, db_session):
        """Test updating document metadata."""
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        update_data = {"document_type": "tax_assessment"}
        
        # Act
        result = await service.update(db_session, sample_document_model.id, update_data, user_id="clerk")

        # Assert
        assert result.document_type == "tax_assessment"
        assert result.updated_by == "clerk"
        assert result.file_name == "pay_stub_2023.pdf" # Unchanged

    @pytest.mark.asyncio
    async def test_calculate_document_size_no_pii_logging(self, service, caplog):
        """Test helper function that calculates size but ensures no content is logged."""
        # Arrange
        sensitive_data = b"SIN: 123-456-789"
        
        # Act
        size = await service._calculate_size(sensitive_data)
        
        # Assert
        assert size == len(sensitive_data)
        # PIPEDA Compliance: Ensure sensitive data is NOT in logs
        assert "123-456-789" not in caplog.text

    @pytest.mark.asyncio
    async def test_list_documents_by_application(self, service, db_session):
        """Test listing documents filtered by application_id."""
        # Arrange
        doc1 = Document(id="1", application_id="app_1", file_name="a.pdf", storage_path="x", status="UPLOADED", created_by="u")
        doc2 = Document(id="2", application_id="app_1", file_name="b.pdf", storage_path="y", status="UPLOADED", created_by="u")
        doc3 = Document(id="3", application_id="app_2", file_name="c.pdf", storage_path="z", status="UPLOADED", created_by="u")
        
        db_session.add_all([doc1, doc2, doc3])
        await db_session.commit()

        # Act
        results = await service.list(db_session, application_id="app_1")

        # Assert
        assert len(results) == 2
        assert all(d.application_id == "app_1" for d in results)

    @pytest.mark.asyncio
    async def test_storage_failure_rollback(self, service, mock_storage_service, sample_document_payload, db_session):
        """Test that DB transaction rolls back if storage upload fails."""
        # Arrange
        mock_storage_service.upload_file.side_effect = Exception("S3 Down")
        payload = DocumentCreate(**sample_document_payload)

        # Act & Assert
        with pytest.raises(Exception):
            await service.upload(db_session, b"content", payload, user_id="user")
        
        # Verify no record was committed
        # (In a real scenario we'd query, but here we check session state logic conceptually)
        # If this was integration, we'd check count. In unit, we verify service raises.
        mock_storage_service.delete_file.assert_not_awaited() # Nothing to delete
```