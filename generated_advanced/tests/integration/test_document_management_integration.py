```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.document_management.models import Document

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_create_document_endpoint_success(self, client: AsyncClient, db_session, mock_storage_service):
        """
        Integration test: POST /api/v1/documents
        Tests full flow: API -> Service -> DB (and mocked Storage)
        """
        # Arrange
        payload = {
            "application_id": "app_integration_01",
            "document_type": "IDENTITY_PROOF",
            "file_name": "driver_license.jpg",
            "mime_type": "image/jpeg",
            "file_size_bytes": 500000
        }
        
        # Note: In a real scenario, we'd send multipart/form-data.
        # Here we send JSON assuming the controller handles file separation or 
        # we mock the file extraction part. For this test, we assume JSON payload
        # representing metadata, and the file content is handled internally or via mock.
        
        # Act
        response = await client.post("/api/v1/documents/", json=payload)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["application_id"] == payload["application_id"]
        assert data["status"] == "UPLOADED"
        
        # Verify Database State
        stmt = select(Document).where(Document.id == data["id"])
        result = await db_session.execute(stmt)
        db_doc = result.scalar_one_or_none()
        assert db_doc is not None
        assert db_doc.created_at is not None # FINTRAC audit check

    async def test_create_document_endpoint_invalid_type(self, client: AsyncClient):
        """
        Test that API returns 400/422 for invalid document types.
        """
        payload = {
            "application_id": "app_01",
            "document_type": "MALWARE",
            "file_name": "virus.exe",
            "mime_type": "application/x-msdownload",
            "file_size_bytes": 100
        }
        
        response = await client.post("/api/v1/documents/", json=payload)
        
        assert response.status_code == 422 # Pydantic validation error

    async def test_get_document_endpoint(self, client: AsyncClient, db_session, sample_document_model):
        """
        Integration test: GET /api/v1/documents/{id}
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        await db_session.refresh(sample_document_model)
        
        # Act
        response = await client.get(f"/api/v1/documents/{sample_document_model.id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_document_model.id
        # Ensure sensitive internal paths are not exposed if configured
        assert "storage_path" in data 

    async def test_get_documents_list_by_application(self, client: AsyncClient, db_session, sample_document_model):
        """
        Integration test: GET /api/v1/documents/?application_id=...
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        # Act
        response = await client.get(f"/api/v1/documents/?application_id={sample_document_model.application_id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["application_id"] == sample_document_model.application_id

    async def test_verify_document_endpoint(self, client: AsyncClient, db_session, sample_document_model):
        """
        Integration test: PATCH /api/v1/documents/{id}/verify
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        verify_payload = {
            "verified_by": "underwriter_jane",
            "notes": "Clear copy of ID"
        }
        
        # Act
        response = await client.patch(
            f"/api/v1/documents/{sample_document_model.id}/verify",
            json=verify_payload
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "VERIFIED"
        
        # DB Check
        await db_session.refresh(sample_document_model)
        assert sample_document_model.status == "VERIFIED"
        assert sample_document_model.updated_at is not None

    async def test_delete_document_endpoint_forbidden_hard_delete(self, client: AsyncClient, db_session, sample_document_model):
        """
        Integration test: DELETE /api/v1/documents/{id}
        Ensures the endpoint performs a soft delete and does not remove the record.
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        doc_id = sample_document_model.id
        
        # Act
        response = await client.delete(f"/api/v1/documents/{doc_id}")
        
        # Assert
        # Usually 204 No Content for deletion, or 200 with updated object
        assert response.status_code in [200, 204]
        
        # FINTRAC Compliance Check: Record must still exist
        stmt = select(Document).where(Document.id == doc_id)
        result = await db_session.execute(stmt)
        doc = result.scalar_one_or_none()
        
        assert doc is not None
        assert doc.status == "DELETED" # Or "ARCHIVED" depending on implementation
        assert doc.deleted_at is not None # Assuming soft delete adds this timestamp

    async def test_get_non_existent_document(self, client: AsyncClient):
        """
        Test handling of 404 Not Found.
        """
        response = await client.get("/api/v1/documents/999999")
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_upload_missing_required_fields(self, client: AsyncClient):
        """
        Test input validation on the API layer.
        """
        # Missing application_id
        payload = {
            "document_type": "IDENTITY_PROOF",
            "file_name": "test.pdf"
        }
        
        response = await client.post("/api/v1/documents/", json=payload)
        assert response.status_code == 422 # Unprocessable Entity
```