Here are the comprehensive tests for the Document Processing Transformer (DPT) Service within the Canadian Mortgage Underwriting System.

--- conftest.py ---
```python
import pytest
import io
from typing import Generator, Dict, Any
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Assuming the project structure and imports
# from app.main import app
# from app.db.base import Base
# from app.models.document import DocumentModel
# from app.schemas.document import DocumentStatus

# Mocking the application for the context of this test generation
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# --- Mock Models for Context ---
class DocumentStatus:
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class DocumentModel:
    def __init__(self, id, filename, status, doc_type, content):
        self.id = id
        self.filename = filename
        self.status = status
        self.doc_type = doc_type
        self.content = content

# --- Database Fixture ---

@pytest.fixture(scope="function")
def db_engine():
    """Creates an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Base.metadata.create_all(bind=engine) # Uncomment in real scenario
    yield engine
    # Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Creates a new database session for a test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

# --- Mock API Client Fixture ---

@pytest.fixture
def mock_ocr_client():
    """Mocks the external OCR/AI extraction service."""
    with patch("app.services.dpt_service.OCRClient") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        
        # Default success response
        mock_instance.extract_text.return_value = {
            "text": "Sample Mortgage Document Content",
            "confidence": 0.98
        }
        yield mock_instance

# --- Test Data Fixtures ---

@pytest.fixture
def sample_t4_pdf_content() -> bytes:
    """Raw bytes representing a fake PDF file."""
    return b"%PDF-1.4 fake pdf content for T4 slip..."

@pytest.fixture
def sample_paystub_jpg_content() -> bytes:
    """Raw bytes representing a fake JPG file."""
    return b"\xff\xd8\xff\xe0 fake jpg content for Paystub..."

@pytest.fixture
def sample_mortgage_app_json() -> Dict[str, Any]:
    """Structured data representing a parsed mortgage application."""
    return {
        "applicant_name": "John Doe",
        "sin": "123-456-789",
        "annual_income": 85000.00,
        "employer": "Tech Corp Canada",
        "document_type": "T4",
        "currency": "CAD"
    }

@pytest.fixture
def sample_invalid_file_content() -> bytes:
    """Corrupt or unsupported file data."""
    return b"corrupt data %%&&&&"

# --- App Client Fixture ---

@pytest.fixture
def client(db_session: Session):
    """Creates a TestClient for the FastAPI app with DB dependency override."""
    # def override_get_db():
    #     try:
    #         yield db_session
    #     finally:
    #         pass
    # app.dependency_overrides[get_db] = override_get_db
    
    # Setup minimal routes for integration testing
    @app.post("/documents/upload")
    async def upload_doc():
        return {"id": "doc_123", "status": "UPLOADED"}

    @app.get("/documents/{doc_id}")
    async def get_doc(doc_id: str):
        return {"id": doc_id, "status": "COMPLETED", "data": {}}

    @app.post("/documents/{doc_id}/process")
    async def process_doc(doc_id: str):
        return {"id": doc_id, "status": "PROCESSING"}

    with TestClient(app) as test_client:
        yield test_client
    
    # app.dependency_overrides = {}
```

--- unit_tests ---
```python
import pytest
from unittest.mock import patch, MagicMock
from app.services.dpt_service import DocumentTransformer, DataNormalizer, DocumentClassifier
from app.exceptions import DocumentProcessingError, UnsupportedFileTypeError

# Module to test: app.services.dpt_service
# Assuming these classes exist in the service module

class TestDataNormalizer:
    """Tests for utility functions that clean and format extracted data."""

    def test_normalize_currency_string_valid_cad(self):
        """Test converting a string with dollar sign and commas to float."""
        raw = "$1,250.50"
        result = DataNormalizer.normalize_currency(raw)
        assert result == 1250.50

    def test_normalize_currency_string_simple(self):
        """Test converting a simple number string."""
        raw = "50000"
        result = DataNormalizer.normalize_currency(raw)
        assert result == 50000.00

    def test_normalize_currency_invalid_string(self):
        """Test handling of garbage string data."""
        raw = "N/A"
        with pytest.raises(ValueError):
            DataNormalizer.normalize_currency(raw)

    def test_format_sin_valid(self):
        """Test formatting a 9-digit number into Canadian SIN format."""
        raw_sin = "123456789"
        formatted = DataNormalizer.format_sin(raw_sin)
        assert formatted == "123-456-789"

    def test_format_sin_already_formatted(self):
        """Test that an already formatted SIN is not double-formatted."""
        raw_sin = "123-456-789"
        formatted = DataNormalizer.format_sin(raw_sin)
        assert formatted == "123-456-789"

    def test_parse_date_american_vs_canadian(self):
        """Test resolving ambiguous dates (04/05/2023). Should default to DD/MM/YYYY for CA."""
        raw_date = "04/05/2023"
        parsed = DataNormalizer.parse_date(raw_date, region="CA")
        assert parsed.day == 4
        assert parsed.month == 5


class TestDocumentClassifier:
    """Tests for logic that determines document type (T4, Paystub, etc.)."""

    def test_classify_t4_slip(self):
        """Test identifying a T4 slip based on keywords."""
        text_content = "Employment Income, CPP Contributions, Box 14"
        doc_type = DocumentClassifier.identify_type(text_content)
        assert doc_type == "T4"

    def test_classify_paystub(self):
        """Test identifying a Paystub based on keywords."""
        text_content = "YTD Gross Pay, Current Pay Period, Deductions"
        doc_type = DocumentClassifier.identify_type(text_content)
        assert doc_type == "PAYSTUB"

    def test_classify_bank_statement(self):
        """Test identifying a Bank Statement."""
        text_content = "Account Summary, RBC Royal Bank, Closing Balance"
        doc_type = DocumentClassifier.identify_type(text_content)
        assert doc_type == "BANK_STATEMENT"

    def test_classify_unknown_document(self):
        """Test handling of document with no known keywords."""
        text_content = "This is a random letter with no financial keywords."
        with pytest.raises(UnsupportedFileTypeError):
            DocumentClassifier.identify_type(text_content)

    def test_classify_empty_string(self):
        """Test handling of empty input."""
        with pytest.raises(ValueError):
            DocumentClassifier.identify_type("")


class TestDocumentTransformer:
    """Tests for the main service orchestration."""

    @patch("app.services.dpt_service.OCRClient")
    def test_transform_document_success_happy_path(self, mock_ocr, sample_t4_pdf_content, sample_mortgage_app_json):
        """Test end-to-end transformation of a valid PDF."""
        # Setup mock
        mock_ocr_instance = MagicMock()
        mock_ocr.return_value = mock_ocr_instance
        mock_ocr_instance.extract.return_value = sample_mortgage_app_json

        transformer = DocumentTransformer(ocr_client=mock_ocr_instance)
        result = transformer.transform(sample_t4_pdf_content, "application/pdf")

        assert result.status == "COMPLETED"
        assert result.data["annual_income"] == 85000.00
        assert result.doc_type == "T4"
        mock_ocr_instance.extract.assert_called_once()

    @patch("app.services.dpt_service.OCRClient")
    def test_transform_document_ocr_failure(self, mock_ocr, sample_t4_pdf_content):
        """Test handling when the external OCR service fails."""
        mock_ocr_instance = MagicMock()
        mock_ocr.return_value = mock_ocr_instance
        mock_ocr_instance.extract.side_effect = Exception("OCR Service Timeout")

        transformer = DocumentTransformer(ocr_client=mock_ocr_instance)
        
        with pytest.raises(DocumentProcessingError):
            transformer.transform(sample_t4_pdf_content, "application/pdf")

    @patch("app.services.dpt_service.OCRClient")
    def test_transform_document_missing_critical_field(self, mock_ocr, sample_t4_pdf_content):
        """Test validation failure when required fields (SIN) are missing."""
        incomplete_data = {
            "applicant_name": "Jane Doe",
            "annual_income": 60000,
            # Missing SIN
        }
        
        mock_ocr_instance = MagicMock()
        mock_ocr.return_value = mock_ocr_instance
        mock_ocr_instance.extract.return_value = incomplete_data

        transformer = DocumentTransformer(ocr_client=mock_ocr_instance)
        
        # Assuming the transformer validates schema
        with pytest.raises(DocumentProcessingError, match="Missing required field: sin"):
            transformer.transform(sample_t4_pdf_content, "application/pdf")

    @patch("app.services.dpt_service.OCRClient")
    def test_transform_unsupported_mime_type(self, mock_ocr, sample_invalid_file_content):
        """Test rejection of unsupported file types (e.g., .exe)."""
        transformer = DocumentTransformer(ocr_client=mock_ocr)
        
        with pytest.raises(UnsupportedFileTypeError):
            transformer.transform(sample_invalid_file_content, "application/x-msdownload")

    @patch("app.services.dpt_service.OCRClient")
    def test_transform_data_normalization_integration(self, mock_ocr, sample_t4_pdf_content):
        """Test that raw data is normalized during transformation."""
        raw_data = {
            "applicant_name": "  Alice Smith  ", # Whitespace
            "sin": "987654321", # Needs formatting
            "annual_income": "$ 70,000.00", # Currency string
            "document_type": "PAYSTUB"
        }

        mock_ocr_instance = MagicMock()
        mock_ocr.return_value = mock_ocr_instance
        mock_ocr_instance.extract.return_value = raw_data

        transformer = DocumentTransformer(ocr_client=mock_ocr_instance)
        result = transformer.transform(sample_t4_pdf_content, "application/pdf")

        assert result.data["sin"] == "987-654-321"
        assert result.data["annual_income"] == 70000.00
        assert result.data["applicant_name"] == "Alice Smith"

```

--- integration_tests ---
```python
import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Assuming app.main imports
# from app.main import app
# from app.crud import document_crud

class TestDocumentUploadWorkflow:
    """Tests for the API endpoints handling file uploads."""

    def test_upload_document_success(self, client: TestClient, sample_t4_pdf_content):
        """Test successful upload of a PDF document."""
        files = {"file": ("mortgage_t4.pdf", io.BytesIO(sample_t4_pdf_content), "application/pdf")}
        metadata = {"applicant_id": "cust_001", "document_type": "T4"}
        
        response = client.post(
            "/documents/upload",
            files=files,
            data=metadata
        )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "mortgage_t4.pdf"
        assert data["status"] == "UPLOADED"
        assert "id" in data

    def test_upload_document_missing_file(self, client: TestClient):
        """Test upload request without a file attached."""
        response = client.post("/documents/upload")
        assert response.status_code == 422  # Unprocessable Entity

    def test_upload_document_unsupported_type(self, client: TestClient, sample_invalid_file_content):
        """Test upload of an executable file (should be blocked)."""
        files = {"file": ("virus.exe", io.BytesIO(sample_invalid_file_content), "application/exe")}
        
        response = client.post("/documents/upload", files=files)
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_large_file_rejection(self, client: TestClient):
        """Test that files exceeding the size limit are rejected."""
        # Create a fake 11MB byte array
        large_content = b"x" * (11 * 1024 * 1024)
        files = {"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")}
        
        response = client.post("/documents/upload", files=files)
        assert response.status_code == 413  # Payload Too Large


class TestDocumentProcessingWorkflow:
    """Tests for triggering and retrieving processed data."""

    def test_process_document_workflow(self, client: TestClient, db_session: Session, sample_t4_pdf_content, mock_ocr_client):
        """
        Multi-step test:
        1. Upload Document
        2. Trigger Processing
        3. Verify Status changes
        4. Retrieve Extracted Data
        """
        
        # 1. Upload
        files = {"file": ("paystub.jpg", io.BytesIO(sample_t4_pdf_content), "application/pdf")}
        upload_resp = client.post("/documents/upload", files=files)
        doc_id = upload_resp.json()["id"]
        
        assert upload_resp.status_code == 201

        # 2. Trigger Processing
        # Mocking the internal call to the transformer service
        process_resp = client.post(f"/documents/{doc_id}/process")
        assert process_resp.status_code == 202 # Accepted
        
        # 3. Check Status (Polling simulation)
        status_resp = client.get(f"/documents/{doc_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] in ["PROCESSING", "COMPLETED"]

        # 4. Retrieve Data
        # Assuming the service processes synchronously for this test or we mock the final state
        details_resp = client.get(f"/documents/{doc_id}/extracted_data")
        assert details_resp.status_code == 200
        
        extracted = details_resp.json()
        assert "parsed_data" in extracted
        # Verify contract structure
        assert "sin" in extracted["parsed_data"]
        assert "annual_income" in extracted["parsed_data"]

    def test_get_nonexistent_document(self, client: TestClient):
        """Test retrieving a document that does not exist."""
        fake_id = "non-existent-id-123"
        response = client.get(f"/documents/{fake_id}")
        assert response.status_code == 404

    def test_process_already_processed_document(self, client: TestClient, sample_t4_pdf_content):
        """Test idempotency or error handling when processing an already processed doc."""
        # Upload
        files = {"file": ("doc.pdf", io.BytesIO(sample_t4_pdf_content), "application/pdf")}
        upload_resp = client.post("/documents/upload", files=files)
        doc_id = upload_resp.json()["id"]

        # Process 1st time
        client.post(f"/documents/{doc_id}/process")
        
        # Process 2nd time (Should return 200 OK or 409 Conflict depending on design)
        # Here assuming it returns the existing result
        process_resp_2 = client.post(f"/documents/{doc_id}/process")
        assert process_resp_2.status_code in [200, 409]


class TestDataContracts:
    """Tests to ensure API response contracts match the frontend expectations."""

    def test_document_list_response_structure(self, client: TestClient, sample_t4_pdf_content):
        """Test that listing documents returns the correct pagination structure."""
        # Upload a few docs
        for i in range(3):
            files = {"file": (f"doc_{i}.pdf", io.BytesIO(sample_t4_pdf_content), "application/pdf")}
            client.post("/documents/upload", files=files)

        response = client.get("/documents?limit=10&offset=0")
        assert response.status_code == 200
        
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert len(body["items"]) == 3
        
        # Verify item structure
        for item in body["items"]:
            assert "id" in item
            assert "created_at" in item
            assert "status" in item

    def test_extracted_data_response_contains_canadian_fields(self, client: TestClient, sample_t4_pdf_content):
        """Verify that the extracted data specifically contains Canadian mortgage fields."""
        # Upload
        files = {"file": ("t4.pdf", io.BytesIO(sample_t4_pdf_content), "application/pdf")}
        upload_resp = client.post("/documents/upload", files=files)
        doc_id = upload_resp.json()["id"]
        
        # Process
        client.post(f"/documents/{doc_id}/process")
        
        # Get Data
        data_resp = client.get(f"/documents/{doc_id}/extracted_data")
        content = data_resp.json()
        
        # Verify Canadian specific fields exist in the contract
        assert "sin" in content["parsed_data"] or "social_insurance_number" in content["parsed_data"]
        assert "income_cad" in content["parsed_data"] or "annual_income" in content["parsed_data"]
```