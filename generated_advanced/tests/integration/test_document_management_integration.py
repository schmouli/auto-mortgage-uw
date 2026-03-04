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