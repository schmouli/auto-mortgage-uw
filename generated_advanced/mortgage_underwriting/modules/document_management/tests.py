Here are the comprehensive tests for the Document Management module of the OnLendHub project.

--- conftest.py ---
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from datetime import datetime
import enum
import io

# --- Mock Application Setup (Simulating the actual app structure) ---
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- Models ---
class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False) # in bytes
    s3_path = Column(String, nullable=True)
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.UPLOADED)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

class MortgageApplication(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    borrower_name = Column(String, nullable=False)

# --- Fixtures ---

@pytest.fixture(scope="function")
def db_session():
    """Creates a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Creates a TestClient that overrides the dependency for the database session.
    """
    from main import app, get_db # Assuming main.py exists
    
    # Dependency Override
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()

@pytest.fixture
def sample_application(db_session: Session):
    """Creates a sample mortgage application in the DB."""
    app = MortgageApplication(borrower_name="John Doe")
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)
    return app

@pytest.fixture
def mock_s3_service(mocker):
    """Mocks the S3 storage service."""
    mock_s3 = mocker.patch("services.storage_service.S3Service")
    mock_s3.return_value.upload_file.return_value = "https://onlendhub-s3-mock.ca/docs/file1.pdf"
    mock_s3.return_value.delete_file.return_value = True
    return mock_s3

@pytest.fixture
def mock_virus_scanner(mocker):
    """Mocks the external virus scanning API."""
    mock_vs = mocker.patch("services.security_service.VirusScanner")
    mock_vs.return_value.scan_file.return_value = True # True = Safe
    return mock_vs

@pytest.fixture
def valid_pdf_file():
    """Returns a valid PDF file-like object for upload."""
    file_content = b"%PDF-1.4 fake pdf content..."
    return io.BytesIO(file_content)

@pytest.fixture
def malicious_file():
    """Returns a file-like object simulating a malicious payload."""
    file_content = b"EICAR test string"
    return io.BytesIO(file_content)
```

--- unit_tests ---
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

--- integration_tests ---
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from conftest import Document, DocumentStatus, MortgageApplication

class TestDocumentUploadAPI:
    """Integration tests for the Document Upload Endpoint."""

    def test_upload_document_success(self, client: TestClient, sample_application, valid_pdf_file):
        """Test successful file upload via API."""
        url = f"/api/v1/applications/{sample_application.id}/documents"
        files = {"file": ("income_verification.pdf", valid_pdf_file, "application/pdf")}
        data = {"document_type": "PAY_STUB"}
        
        response = client.post(url, files=files, data=data)
        
        # Assertions
        assert response.status_code == 201
        json_resp = response.json()
        assert json_resp["filename"] == "income_verification.pdf"
        assert json_resp["application_id"] == sample_application.id
        assert json_resp["status"] == DocumentStatus.UPLOADED
        assert "id" in json_resp
        assert "uploaded_at" in json_resp

    def test_upload_document_missing_file(self, client: TestClient, sample_application):
        """Test API response when no file is sent."""
        url = f"/api/v1/applications/{sample_application.id}/documents"
        response = client.post(url)
        
        assert response.status_code == 422 # Unprocessable Entity

    def test_upload_document_unsupported_type(self, client: TestClient, sample_application):
        """Test uploading an executable file (should be rejected by API)."""
        url = f"/api/v1/applications/{sample_application.id}/documents"
        bad_file = io.BytesIO(b"executable content")
        files = {"file": ("script.exe", bad_file, "application/x-msdownload")}
        
        response = client.post(url, files=files)
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_upload_to_non_existent_application(self, client: TestClient, valid_pdf_file):
        """Test uploading to an application ID that does not exist."""
        url = "/api/v1/applications/99999/documents"
        files = {"file": ("doc.pdf", valid_pdf_file, "application/pdf")}
        
        response = client.post(url, files=files)
        
        assert response.status_code == 404

class TestDocumentRetrievalAPI:
    """Integration tests for fetching documents."""

    def test_get_document_details(self, client: TestClient, db_session: Session, sample_application):
        """Test GET /documents/{id}."""
        # Setup: Create a doc directly in DB
        doc = Document(
            filename="t4_slip.pdf",
            file_type="application/pdf",
            file_size=1024,
            application_id=sample_application.id,
            status=DocumentStatus.PENDING_REVIEW
        )
        db_session.add(doc)
        db_session.commit()

        response = client.get(f"/api/v1/documents/{doc.id}")
        
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp["id"] == doc.id
        assert json_resp["status"] == DocumentStatus.PENDING_REVIEW
        assert json_resp["filename"] == "t4_slip.pdf"

    def test_get_documents_by_application(self, client: TestClient, db_session: Session, sample_application):
        """Test GET /applications/{id}/documents list."""
        # Setup: Add 2 docs
        doc1 = Document(filename="doc1.pdf", file_type="application/pdf", file_size=100, application_id=sample_application.id)
        doc2 = Document(filename="doc2.pdf", file_type="application/pdf", file_size=200, application_id=sample_application.id)
        db_session.add_all([doc1, doc2])
        db_session.commit()

        response = client.get(f"/api/v1/applications/{sample_application.id}/documents")
        
        assert response.status_code == 200
        json_resp = response.json()
        assert len(json_resp) == 2
        filenames = [d["filename"] for d in json_resp]
        assert "doc1.pdf" in filenames
        assert "doc2.pdf" in filenames

class TestDocumentStatusWorkflow:
    """Integration tests for multi-step workflows."""

    def test_upload_and_approve_workflow(self, client: TestClient, db_session: Session, sample_application, valid_pdf_file):
        """
        Complete workflow:
        1. Upload Document
        2. Verify it is UPLOADED
        3. Underwriter updates to APPROVED
        4. Verify status change
        """
        # Step 1: Upload
        upload_url = f"/api/v1/applications/{sample_application.id}/documents"
        files = {"file": ("appraisal.pdf", valid_pdf_file, "application/pdf")}
        upload_resp = client.post(upload_url, files=files)
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        # Step 2: Verify Initial State
        get_resp = client.get(f"/api/v1/documents/{doc_id}")
        assert get_resp.json()["status"] == DocumentStatus.UPLOADED

        # Step 3: Update Status (Underwriter Action)
        update_url = f"/api/v1/documents/{doc_id}/status"
        update_payload = {"status": "APPROVED", "notes": "Looks good"}
        update_resp = client.patch(update_url, json=update_payload)
        
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == DocumentStatus.APPROVED
        assert update_resp.json()["notes"] == "Looks good"

        # Step 4: Verify Persistence
        final_get = client.get(f"/api/v1/documents/{doc_id}")
        assert final_get.json()["status"] == DocumentStatus.APPROVED

    def test_reject_document_workflow(self, client: TestClient, db_session: Session, sample_application, valid_pdf_file):
        """
        Workflow for rejection:
        1. Upload
        2. Reject with reason
        3. Check audit log (simulated by checking response)
        """
        # Upload
        upload_url = f"/api/v1/applications/{sample_application.id}/documents"
        files = {"file": ("id_card.pdf", valid_pdf_file, "application/pdf")}
        upload_resp = client.post(upload_url, files=files)
        doc_id = upload_resp.json()["id"]

        # Reject
        update_url = f"/api/v1/documents/{doc_id}/status"
        update_payload = {"status": "REJECTED", "notes": "Image is blurry"}
        update_resp = client.patch(update_url, json=update_payload)
        
        assert update_resp.status_code == 200
        json_resp = update_resp.json()
        assert json_resp["status"] == DocumentStatus.REJECTED
        assert json_resp["notes"] == "Image is blurry"
        
        # Verify DB state via API
        final_get = client.get(f"/api/v1/documents/{doc_id}")
        assert final_get.json()["status"] == DocumentStatus.REJECTED
```