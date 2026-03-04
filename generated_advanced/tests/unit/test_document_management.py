```python
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from sqlalchemy.orm import Session
from conftest import Document, DocumentStatus, MortgageApplication

# Assuming the code structure exists in the project
from services.document_service import DocumentService 
from services.storage_service import S3Service
from services.security_service import VirusScanner
from core.exceptions import InvalidFileException, VirusDetectedException, StorageException

class TestDocumentServiceValidation:
    """Unit tests focusing on file validation logic."""

    def test_validate_pdf_extension_success(self):
        """Test that valid PDF extensions pass validation."""
        service = DocumentService()
        filename = "mortgage_statement.pdf"
        is_valid = service._validate_extension(filename)
        assert is_valid is True

    def test_validate_invalid_extension_failure(self):
        """Test that non-PDF extensions fail validation."""
        service = DocumentService()
        filename = "virus.exe"
        is_valid = service._validate_extension(filename)
        assert is_valid is False

    def test_validate_file_size_within_limit(self):
        """Test that files under 5MB are accepted."""
        service = DocumentService()
        size_bytes = 4 * 1024 * 1024 # 4MB
        is_valid = service._validate_size(size_bytes)
        assert is_valid is True

    def test_validate_file_size_exceeds_limit(self):
        """Test that files over 5MB are rejected."""
        service = DocumentService()
        size_bytes = 6 * 1024 * 1024 # 6MB
        is_valid = service._validate_size(size_bytes)
        assert is_valid is False

    def test_validate_content_type_pdf(self):
        """Test correct MIME type validation."""
        service = DocumentService()
        assert service._validate_content_type("application/pdf") is True
        assert service._validate_content_type("image/jpeg") is False

class TestDocumentServiceUpload:
    """Unit tests for the upload workflow logic."""

    def test_upload_document_happy_path(self, db_session, sample_application, mock_s3_service, mock_virus_scanner):
        """
        Test successful document upload:
        1. Validation passes
        2. Virus scan passes
        3. S3 upload succeeds
        4. DB record created
        """
        service = DocumentService(db=db_session)
        file_data = b"PDF content"
        filename = "income_proof.pdf"
        
        doc = service.upload_document(
            application_id=sample_application.id,
            filename=filename,
            file_data=file_data,
            content_type="application/pdf"
        )

        # Assertions
        assert doc.id is not None
        assert doc.filename == filename
        assert doc.status == DocumentStatus.UPLOADED
        assert doc.application_id == sample_application.id
        assert doc.s3_path == "https://onlendhub-s3-mock.ca/docs/file1.pdf"
        
        # Verify interactions
        mock_virus_scanner.return_value.scan_file.assert_called_once()
        mock_s3_service.return_value.upload_file.assert_called_once()

    def test_upload_document_virus_detected(self, db_session, sample_application, mock_virus_scanner):
        """Test that VirusDetectedException is raised when scan fails."""
        mock_virus_scanner.return_value.scan_file.return_value = False # Infected
        
        service = DocumentService(db=db_session)
        
        with pytest.raises(VirusDetectedException) as exc_info:
            service.upload_document(
                application_id=sample_application.id,
                filename="malware.pdf",
                file_data=b"bad content",
                content_type="application/pdf"
            )
        
        assert "Virus detected" in str(exc_info.value)

    def test_upload_document_invalid_type(self, db_session, sample_application):
        """Test that InvalidFileException is raised for .exe files."""
        service = DocumentService(db=db_session)
        
        with pytest.raises(InvalidFileException):
            service.upload_document(
                application_id=sample_application.id,
                filename="trojan.exe",
                file_data=b"exe content",
                content_type="application/x-msdownload"
            )

    def test_upload_document_s3_failure(self, db_session, sample_application, mock_s3_service, mock_virus_scanner):
        """Test handling of S3 storage failure."""
        mock_s3_service.return_value.upload_file.side_effect = Exception("S3 Connection Timeout")
        
        service = DocumentService(db=db_session)
        
        with pytest.raises(StorageException):
            service.upload_document(
                application_id=sample_application.id,
                filename="doc.pdf",
                file_data=b"content",
                content_type="application/pdf"
            )

class TestDocumentServiceStatusUpdate:
    """Unit tests for status transitions."""

    def test_update_status_to_approved(self, db_session, sample_application):
        """Test transition from UPLOADED to APPROVED."""
        doc = Document(
            filename="doc.pdf", 
            file_type="application/pdf", 
            file_size=1000, 
            application_id=sample_application.id,
            status=DocumentStatus.UPLOADED
        )
        db_session.add(doc)
        db_session.commit()

        service = DocumentService(db=db_session)
        updated_doc = service.update_status(doc.id, DocumentStatus.APPROVED)

        assert updated_doc.status == DocumentStatus.APPROVED
        assert updated_doc.id == doc.id

    def test_update_status_invalid_transition(self, db_session, sample_application):
        """Test that invalid transitions (e.g. APPROVED -> UPLOADED) are blocked."""
        doc = Document(
            filename="doc.pdf", 
            file_type="application/pdf", 
            file_size=1000, 
            application_id=sample_application.id,
            status=DocumentStatus.APPROVED
        )
        db_session.add(doc)
        db_session.commit()

        service = DocumentService(db=db_session)
        
        with pytest.raises(ValueError): # Assuming business logic raises ValueError for bad transitions
            service.update_status(doc.id, DocumentStatus.UPLOADED)

    def test_get_document_by_id(self, db_session, sample_application):
        """Test retrieving a document record."""
        doc = Document(
            filename="test.pdf", 
            file_type="application/pdf", 
            file_size=500, 
            application_id=sample_application.id,
            s3_path="s3://bucket/test.pdf"
        )
        db_session.add(doc)
        db_session.commit()

        service = DocumentService(db=db_session)
        retrieved = service.get_document(doc.id)

        assert retrieved is not None
        assert retrieved.filename == "test.pdf"
        assert retrieved.s3_path == "s3://bucket/test.pdf"
```