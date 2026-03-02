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