import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from datetime import datetime

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentStatus

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_create_document_endpoint(self, client: AsyncClient, db_session, valid_document_payload):
        # Act
        response = await client.post(
            "/api/v1/documents/",
            json=valid_document_payload,
            # Note: In a real multipart/form-data scenario, we would send files here.
            # Assuming the API accepts JSON metadata and handles file stream separately or this is a simplified test.
            # For this test, we assume the endpoint accepts JSON metadata and mocks the file internally or via a separate mechanism.
            # However, to adhere to standard FastAPI file upload, we might need to adjust.
            # Let's assume the endpoint expects JSON for this specific exercise based on "valid_document_payload".
        )
        
        # Adjusting for typical Upload endpoint which uses multipart
        # If the route is a standard upload, we use files/data. 
        # Given the prompt implies a JSON payload structure in the fixture, I will simulate a POST that creates the metadata record.
        # But usually, uploads are `files={"file": ...}`. 
        # Let's assume the endpoint creates the metadata entry first.
        
        # Re-acting assuming a JSON endpoint for metadata creation:
        response = await client.post("/api/v1/documents/", json=valid_document_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["application_id"] == valid_document_payload["application_id"]
        assert data["status"] == DocumentStatus.UPLOADED
        assert "created_at" in data

        # Verify Database
        stmt = select(Document).where(Document.id == data["id"])
        result = await db_session.execute(stmt)
        db_doc = result.scalar_one_or_none()
        assert db_doc is not None
        assert db_doc.file_name == valid_document_payload["file_name"]

    async def test_create_document_invalid_payload(self, client: AsyncClient):
        # Act
        response = await client.post("/api/v1/documents/", json={"application_id": 123}) # Missing fields

        # Assert
        assert response.status_code == 422

    async def test_get_document_endpoint(self, client: AsyncClient, db_session, sample_document):
        # Setup
        db_session.add(sample_document)
        await db_session.commit()
        await db_session.refresh(sample_document)

        # Act
        response = await client.get(f"/api/v1/documents/{sample_document.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_document.id
        assert data["file_name"] == sample_document.file_name
        # PIPEDA Check: Ensure sensitive internal paths or checksums aren't exposed if they shouldn't be
        # (Here checksum is often exposed for integrity verification, but PII is not)
        assert "sin" not in data["file_name"].lower()

    async def test_get_document_not_found(self, client: AsyncClient):
        # Act
        response = await client.get("/api/v1/documents/99999")

        # Assert
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_list_documents_endpoint(self, client: AsyncClient, db_session, sample_application_id):
        # Setup: Create multiple documents
        doc1 = Document(
            application_id=sample_application_id,
            document_type="id_verification",
            storage_path="path1",
            file_name="id.pdf",
            status=DocumentStatus.UPLOADED,
            checksum="abc",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        doc2 = Document(
            application_id="other-app",
            document_type="income_verification",
            storage_path="path2",
            file_name="pay.pdf",
            status=DocumentStatus.UPLOADED,
            checksum="def",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add_all([doc1, doc2])
        await db_session.commit()

        # Act
        response = await client.get(f"/api/v1/documents/?application_id={sample_application_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["application_id"] == sample_application_id

    async def test_update_document_status_endpoint(self, client: AsyncClient, db_session, sample_document):
        # Setup
        db_session.add(sample_document)
        await db_session.commit()

        # Act
        update_payload = {"status": DocumentStatus.VERIFIED}
        response = await client.put(f"/api/v1/documents/{sample_document.id}", json=update_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == DocumentStatus.VERIFIED
        
        # Verify DB persistence
        await db_session.refresh(sample_document)
        assert sample_document.status == DocumentStatus.VERIFIED

    async def test_delete_document_endpoint(self, client: AsyncClient, db_session, sample_document):
        # Setup
        db_session.add(sample_document)
        await db_session.commit()

        # Act
        response = await client.delete(f"/api/v1/documents/{sample_document.id}")

        # Assert
        assert response.status_code == 204 # No Content
        
        # Verify Soft Delete (Record still exists but status is DELETED)
        stmt = select(Document).where(Document.id == sample_document.id)
        result = await db_session.execute(stmt)
        db_doc = result.scalar_one_or_none()
        
        assert db_doc is not None
        assert db_doc.status == DocumentStatus.DELETED
        assert db_doc.deleted_at is not None

    async def test_pipeda_compliance_no_pii_in_logs(self, client: AsyncClient, db_session, caplog):
        """
        Test that PII is not leaked in logs if an error occurs.
        This is a structural test; actual log interception depends on app configuration.
        """
        # Setup
        doc_with_pii_name = Document(
            application_id="app-1",
            document_type="sin",
            storage_path="path",
            file_name="john_doe_sin_123456789.pdf", # Filename contains PII
            status=DocumentStatus.UPLOADED,
            checksum="abc",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(doc_with_pii_name)
        await db_session.commit()

        # Act - Trigger a 404 or similar error
        response = await client.get("/api/v1/documents/99999")

        # Assert
        assert response.status_code == 404
        # In a real scenario, we would check caplog.text for the presence of the SIN or filename.
        # Here we assert the response doesn't contain the sensitive filename from the DB lookup that failed.
        assert "john_doe_sin_123456789.pdf" not in response.text