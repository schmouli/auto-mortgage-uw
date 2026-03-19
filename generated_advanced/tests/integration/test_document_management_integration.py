import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.document_management.models import Document

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_create_document_success(self, client: AsyncClient, db_session, sample_application_payload):
        """
        Test full workflow: Create Application -> Upload Document -> Verify Record.
        """
        # 1. Create an application first (Foreign Key dependency)
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        assert app_resp.status_code == 201
        app_id = app_resp.json()["id"]

        # 2. Upload a document
        files = {
            "file": ("pay_stub.pdf", b"%PDF-1.4 fake content...", "application/pdf")
        }
        data = {
            "application_id": str(app_id),
            "document_type": "INCOME_VERIFICATION",
            "content_type": "PAY_STUB"
        }
        
        doc_resp = await client.post("/api/v1/documents", files=files, data=data)
        assert doc_resp.status_code == 201
        
        json_data = doc_resp.json()
        assert json_data["file_name"] == "pay_stub.pdf"
        assert json_data["application_id"] == app_id
        assert json_data["status"] == "UPLOADED"
        assert json_data["uploaded_by"] == "test_user" # Assuming auth sets this
        
        # FINTRAC Compliance: Verify Audit fields in response
        assert "created_at" in json_data
        assert "id" in json_data

        # 3. Verify Database Record
        stmt = select(Document).where(Document.id == json_data["id"])
        result = await db_session.execute(stmt)
        doc_obj = result.scalar_one_or_none()
        
        assert doc_obj is not None
        assert doc_obj.file_name == "pay_stub.pdf"
        assert doc_obj.file_path is not None # Should point to storage

    async def test_create_document_unsupported_type(self, client: AsyncClient, db_session, sample_application_payload):
        """Test that uploading an executable file is rejected."""
        # Create App
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]

        # Upload malicious file type
        files = {
            "file": ("script.exe", b"MZ\x90\x00", "application/x-msdownload")
        }
        data = {
            "application_id": str(app_id),
            "document_type": "OTHER",
            "content_type": "OTHER"
        }
        
        doc_resp = await client.post("/api/v1/documents", files=files, data=data)
        assert doc_resp.status_code == 400
        assert "error_code" in doc_resp.json()

    async def test_get_document(self, client: AsyncClient, db_session, sample_application_payload):
        """Test retrieving a specific document."""
        # Setup
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]
        
        files = {"file": ("id.pdf", b"pdf", "application/pdf")}
        data = {"application_id": str(app_id), "document_type": "IDENTITY", "content_type": "DRIVER_LICENSE"}
        upload_resp = await client.post("/api/v1/documents", files=files, data=data)
        doc_id = upload_resp.json()["id"]

        # Act
        get_resp = await client.get(f"/api/v1/documents/{doc_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == doc_id
        assert data["document_type"] == "IDENTITY"

    async def test_list_documents_by_application(self, client: AsyncClient, db_session, sample_application_payload):
        """Test filtering documents by application ID."""
        # Setup App
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]

        # Upload 2 docs
        for i in range(2):
            files = {"file": (f"doc_{i}.pdf", b"pdf", "application/pdf")}
            data = {"application_id": str(app_id), "document_type": "INCOME_VERIFICATION", "content_type": "PAY_STUB"}
            await client.post("/api/v1/documents", files=files, data=data)

        # List
        list_resp = await client.get(f"/api/v1/documents?application_id={app_id}")
        
        assert list_resp.status_code == 200
        docs = list_resp.json()["items"]
        assert len(docs) == 2
        # Verify all belong to the app
        for doc in docs:
            assert doc["application_id"] == app_id

    async def test_delete_document_soft_delete(self, client: AsyncClient, db_session, sample_application_payload):
        """
        Test FINTRAC compliance: Ensure delete endpoint soft-deletes (retains record).
        """
        # Setup
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]
        
        files = {"file": ("to_delete.pdf", b"pdf", "application/pdf")}
        data = {"application_id": str(app_id), "document_type": "OTHER", "content_type": "OTHER"}
        upload_resp = await client.post("/api/v1/documents", files=files, data=data)
        doc_id = upload_resp.json()["id"]

        # Delete
        del_resp = await client.delete(f"/api/v1/documents/{doc_id}")
        assert del_resp.status_code == 200 # OK, not 204 No Content, to confirm action

        # Verify in DB
        stmt = select(Document).where(Document.id == doc_id)
        result = await db_session.execute(stmt)
        doc_obj = result.scalar_one()
        
        # FINTRAC: Record still exists
        assert doc_obj is not None
        # But marked deleted
        assert doc_obj.status == "DELETED"
        assert doc_obj.deleted_at is not None

        # Verify it doesn't appear in normal list
        list_resp = await client.get(f"/api/v1/documents?application_id={app_id}")
        docs = list_resp.json()["items"]
        # Should be empty or not contain the deleted doc depending on filter implementation
        # Assuming list endpoint filters out DELETED status
        assert doc_id not in [d["id"] for d in docs]

    async def test_update_document_status(self, client: AsyncClient, db_session, sample_application_payload):
        """Test updating a document's verification status."""
        # Setup
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]
        
        files = {"file": ("review.pdf", b"pdf", "application/pdf")}
        data = {"application_id": str(app_id), "document_type": "APPRAISAL", "content_type": "OTHER"}
        upload_resp = await client.post("/api/v1/documents", files=files, data=data)
        doc_id = upload_resp.json()["id"]

        # Update
        update_payload = {
            "status": "VERIFIED",
            "notes": "Matches property records"
        }
        patch_resp = await client.patch(f"/api/v1/documents/{doc_id}", json=update_payload)
        
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["status"] == "VERIFIED"
        assert data["notes"] == "Matches property records"

    async def test_get_non_existent_document(self, client: AsyncClient):
        """Test 404 response."""
        resp = await client.get("/api/v1/documents/99999")
        assert resp.status_code == 404
        assert "error_code" in resp.json()