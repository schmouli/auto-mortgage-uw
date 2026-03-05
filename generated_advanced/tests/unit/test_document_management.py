```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentUpload, DocumentStatus
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def service(self, mock_db: AsyncSession, mock_storage_service, mock_virus_scanner):
        return DocumentService(mock_db, mock_storage_service, mock_virus_scanner)

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_upload_document_success(self, service, mock_db, mock_storage_service, mock_virus_scanner, sample_document_payload):
        # Arrange
        payload = DocumentUpload(**sample_document_payload)
        file_content = b"fake pdf content"
        
        # Mock DB result for refresh
        mock_doc = Document(
            id=uuid4(),
            applicant_id=payload.applicant_id,
            file_name=payload.file_name,
            storage_key="test_key",
            status=DocumentStatus.UPLOADED
        )
        mock_db.refresh.side_effect = lambda x: None # Simulate refresh

        # Act
        result = await service.upload_document(payload, file_content)

        # Assert
        assert result.status == DocumentStatus.UPLOADED
        mock_storage_service.upload_file.assert_awaited_once()
        mock_virus_scanner.scan_file.assert_awaited_once_with(file_content)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_virus_detected(self, service, mock_storage_service, mock_virus_scanner, sample_document_payload):
        # Arrange
        payload = DocumentUpload(**sample_document_payload)
        file_content = b"malicious content"
        mock_virus_scanner.scan_file.return_value = False # Virus found

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.upload_document(payload, file_content)
        
        assert "security" in str(exc_info.value).lower()
        mock_storage_service.upload_file.assert_not_awaited() # Should not upload if virus found
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_document_unsupported_type(self, service, sample_document_payload):
        # Arrange
        invalid_payload_dict = sample_document_payload.copy()
        invalid_payload_dict["file_type"] = "application/exe"
        payload = DocumentUpload(**invalid_payload_dict)
        file_content = b"content"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.upload_document(payload, file_content)
        
        assert "file type" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, service, mock_db):
        # Arrange
        doc_id = uuid4()
        mock_doc = Document(id=doc_id, file_name="test.pdf", status=DocumentStatus.UPLOADED)
        
        # Mock the SQLAlchemy query chain
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.get_document_by_id(doc_id)

        # Assert
        assert result is not None
        assert result.id == doc_id
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_soft_delete_document_fintrac_compliance(self, service, mock_db):
        # Arrange
        doc_id = uuid4()
        mock_doc = Document(id=doc_id, file_name="test.pdf", status=DocumentStatus.UPLOADED)
        
        # Mock fetching the document
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db.execute.return_value = mock_result

        # Act
        await service.delete_document(doc_id)

        # Assert
        # FINTRAC: Verify record is NOT deleted from DB, but status updated
        assert mock_doc.status == DocumentStatus.DELETED
        # Verify we did NOT call session.delete(mock_doc)
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_documents_by_applicant(self, service, mock_db):
        # Arrange
        applicant_id = uuid4()
        mock_docs = [
            Document(id=uuid4(), applicant_id=applicant_id, file_name="doc1.pdf"),
            Document(id=uuid4(), applicant_id=applicant_id, file_name="doc2.pdf")
        ]
        
        # Mock scalars().all()
        mock_scalars = AsyncMock()
        mock_scalars.all.return_value = mock_docs
        mock_db.execute.return_value.scalars.return_value = mock_scalars

        # Act
        results = await service.list_documents(applicant_id)

        # Assert
        assert len(results) == 2
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_document_status_success(self, service, mock_db):
        # Arrange
        doc_id = uuid4()
        mock_doc = Document(id=doc_id, file_name="test.pdf", status=DocumentStatus.PENDING)
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db.execute.return_value = mock_result

        # Act
        updated = await service.update_document_status(doc_id, DocumentStatus.APPROVED)

        # Assert
        assert updated.status == DocumentStatus.APPROVED
        mock_db.commit.assert_awaited_once()
```