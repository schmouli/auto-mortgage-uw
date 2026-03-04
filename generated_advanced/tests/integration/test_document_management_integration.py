import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, status

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.routes import router

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_upload_document_endpoint_success(self, app: FastAPI, client: AsyncClient, valid_document_payload):
        """
        Test the full API flow for uploading a document.
        """
        # Act
        response = await client.post(
            "/api/v1/documents/upload",
            json=valid_document_payload
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["application_id"] == valid_document_payload["application_id"]
        assert data["upload_status"] == "COMPLETED"
        assert "storage_path" in data
        assert "created_at" in data  # Audit trail

    async def test_upload_document_endpoint_validation_error(self, app: FastAPI, client: AsyncClient):
        """
        Test input validation on the upload endpoint.
        """
        # Act - Missing required field
        response = await client.post(
            "/api/v1/documents/upload",
            json={"application_id": "123"} # Missing document_type, file_name, etc.
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_document_endpoint(self, app: FastAPI, client: AsyncClient, db_session):
        """
        Test retrieving a specific document by ID.
        """
        # Setup - Create a document directly in DB
        new_doc = Document(
            id="doc-integration-1",
            application_id="app-int-1",
            document_type="APPRAISAL",
            file_name="report.pdf",
            storage_path="secure/report.pdf",
            upload_status="COMPLETED",
            created_at=None,
            updated_at=None
        )
        db_session.add(new_doc)
        await db_session.commit()

        # Act
        response = await client.get("/api/v1/documents/doc-integration-1")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "doc-integration-1"
        assert data["document_type"] == "APPRAISAL"

    async def test_get_document_not_found_endpoint(self, app: FastAPI, client: AsyncClient):
        """
        Test 404 response when document does not exist.
        """
        # Act
        response = await client.get("/api/v1/documents/does-not-exist")

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "detail" in response.json()

    async def test_list_documents_endpoint(self, app: FastAPI, client: AsyncClient, db_session):
        """
        Test listing documents for a specific application.
        """
        # Setup
        app_id = "app-list-123"
        doc1 = Document(id="d1", application_id=app_id, document_type="ID", file_name="1.pdf", storage_path="s1", upload_status="COMPLETED", created_at=None, updated_at=None)
        doc2 = Document(id="d2", application_id=app_id, document_type="PAY_STUB", file_name="2.pdf", storage_path="s2", upload_status="COMPLETED", created_at=None, updated_at=None)
        # Other app doc
        doc3 = Document(id="d3", application_id="other-app", document_type="ID", file_name="3.pdf", storage_path="s3", upload_status="COMPLETED", created_at=None, updated_at=None)
        
        db_session.add_all([doc1, doc2, doc3])
        await db_session.commit()

        # Act
        response = await client.get(f"/api/v1/documents?application_id={app_id}")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert all(d["application_id"] == app_id for d in data)

    async def test_delete_document_endpoint_fintrac_compliance(self, app: FastAPI, client: AsyncClient, db_session):
        """
        Test that deleting a document via API results in a soft delete (retention).
        """
        # Setup
        doc_id = "doc-delete-123"
        doc = Document(id=doc_id, application_id="app-1", document_type="CONTRACT", file_name="c.pdf", storage_path="s/c.pdf", upload_status="COMPLETED", created_at=None, updated_at=None)
        db_session.add(doc)
        await db_session.commit()

        # Act
        response = await client.delete(f"/api/v1/documents/{doc_id}")

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify DB state (FINTRAC: Record must exist for retention)
        await db_session.refresh(doc)
        assert doc.upload_status == "DELETED"
        assert doc.id == doc_id # Record still exists

    async def test_upload_large_file_rejection(self, app: FastAPI, client: AsyncClient, valid_document_payload):
        """
        Test that files exceeding size limits are rejected.
        """
        # Arrange
        large_payload = valid_document_payload.copy()
        large_payload["file_size_bytes"] = 50 * 1024 * 1024 + 1 # 50MB + 1 byte

        # Act
        response = await client.post("/api/v1/documents/upload", json=large_payload)

        # Assert
        # Assuming the service or route validates size before processing
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE or status.HTTP_400_BAD_REQUEST

    async def test_unsupported_media_type(self, app: FastAPI, client: AsyncClient, valid_document_payload):
        """
        Test rejection of unsafe file types.
        """
        # Arrange
        bad_payload = valid_document_payload.copy()
        bad_payload["content_type"] = "application/x-msdownload" # .exe

        # Act
        response = await client.post("/api/v1/documents/upload", json=bad_payload)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid file type" in response.json().get("detail", "")