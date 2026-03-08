```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentStatus

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_upload_document_endpoint_success(self, client: AsyncClient, db_session):
        """Test full integration of file upload endpoint."""
        # Arrange
        file_data = b"%PDF-1.4 fake pdf content..."
        files = {"file": ("mortgage_statement.pdf", file_data, "application/pdf")}
        data = {
            "application_id": "app_integration_01",
            "document_type": "mortgage_statement",
            "metadata": '{"lender": "RBC", "amount": "500000.00"}'
        }

        # Act
        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        # Assert
        assert response.status_code == 201
        json_resp = response.json()
        assert json_resp["file_name"] == "mortgage_statement.pdf"
        assert json_resp["application_id"] == "app_integration_01"
        assert json_resp["status"] == "UPLOADED"
        assert "id" in json_resp

        # Verify DB state
        result = await db_session.execute(select(Document).where(Document.id == json_resp["id"]))
        doc = result.scalar_one()
        assert doc is not None
        assert doc.storage_path is not None # Should point to mocked storage or local temp

    async def test_upload_document_missing_file(self, client: AsyncClient):
        """Test validation error when file is missing."""
        # Arrange
        data = {"application_id": "app_01", "document_type": "id_proof"}

        # Act
        response = await client.post("/api/v1/documents/upload", data=data)

        # Assert
        assert response.status_code == 422 # Unprocessable Entity

    async def test_get_document_endpoint(self, client: AsyncClient, db_session):
        """Test retrieving a specific document."""
        # Arrange
        new_doc = Document(
            id="doc_get_test",
            application_id="app_01",
            file_name="test.pdf",
            storage_path="/path/to/file",
            status="UPLOADED",
            created_by="test_user"
        )
        db_session.add(new_doc)
        await db_session.commit()

        # Act
        response = await client.get(f"/api/v1/documents/{new_doc.id}")

        # Assert
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp["id"] == "doc_get_test"
        assert json_resp["created_at"] is not None # Audit trail presence

    async def test_get_document_not_found(self, client: AsyncClient):
        """Test 404 response for missing document."""
        # Act
        response = await client.get("/api/v1/documents/nonexistent")

        # Assert
        assert response.status_code == 404
        assert "error_code" in response.json()

    async def test_list_documents_endpoint(self, client: AsyncClient, db_session):
        """Test listing documents with pagination/filtering."""
        # Arrange
        docs = [
            Document(id="d1", application_id="app_list", file_name="1.pdf", storage_path="x", status="UPLOADED", created_by="u"),
            Document(id="d2", application_id="app_list", file_name="2.pdf", storage_path="y", status="PROCESSED", created_by="u"),
            Document(id="d3", application_id="app_other", file_name="3.pdf", storage_path="z", status="UPLOADED", created_by="u"),
        ]
        db_session.add_all(docs)
        await db_session.commit()

        # Act
        response = await client.get("/api/v1/documents?application_id=app_list")

        # Assert
        assert response.status_code == 200
        json_resp = response.json()
        assert "items" in json_resp
        assert len(json_resp["items"]) == 2
        assert all(item["application_id"] == "app_list" for item in json_resp["items"])

    async def test_delete_document_endpoint_soft_delete(self, client: AsyncClient, db_session):
        """Test that DELETE endpoint performs a soft delete (FINTRAC compliance)."""
        # Arrange
        doc = Document(
            id="doc_del",
            application_id="app_del",
            file_name="del.pdf",
            storage_path="/path",
            status="UPLOADED",
            created_by="u"
        )
        db_session.add(doc)
        await db_session.commit()

        # Act
        response = await client.delete(f"/api/v1/documents/{doc.id}")

        # Assert
        assert response.status_code == 200
        
        # Verify record still exists but is deleted
        await db_session.refresh(doc)
        assert doc.status == DocumentStatus.DELETED
        assert doc.id == "doc_del" # Record persists for audit trail

    async def test_update_document_metadata_endpoint(self, client: AsyncClient, db_session):
        """Test updating document metadata."""
        # Arrange
        doc = Document(
            id="doc_up",
            application_id="app_up",
            file_name="up.pdf",
            storage_path="/path",
            status="UPLOADED",
            created_by="u"
        )
        db_session.add(doc)
        await db_session.commit()

        update_payload = {
            "document_type": "updated_type",
            "metadata": {"reviewed": True}
        }

        # Act
        response = await client.put(f"/api/v1/documents/{doc.id}", json=update_payload)

        # Assert
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp["document_type"] == "updated_type"
        assert json_resp["updated_at"] is not None

    async def test_restricted_file_type_upload(self, client: AsyncClient):
        """Test that uploading an executable file is rejected."""
        # Arrange
        files = {"file": ("virus.exe", b"EXE CONTENT", "application/x-msdownload")}
        data = {"application_id": "app_sec", "document_type": "other"}

        # Act
        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        # Assert
        assert response.status_code == 400
        assert "security" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()

    async def test_metadata_with_financial_decimal(self, client: AsyncClient, db_session):
        """Test handling of Decimal values in metadata (CMHC/Financial compliance)."""
        # Arrange
        # Using string representation in JSON to ensure precision
        metadata_str = '{"property_value": "450000.00", "down_payment": "90000.50"}'
        files = {"file": ("doc.pdf", b"pdf", "application/pdf")}
        data = {
            "application_id": "app_dec",
            "document_type": "property_appraisal",
            "metadata": metadata_str
        }

        # Act
        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        # Assert
        assert response.status_code == 201
        json_resp = response.json()
        # Verify metadata is preserved correctly
        assert json_resp["metadata"]["property_value"] == "450000.00"
        
        # Check DB representation
        result = await db_session.execute(select(Document).where(Document.id == json_resp["id"]))
        doc = result.scalar_one()
        # Assuming metadata is stored as JSONB or dict
        assert doc.metadata["property_value"] == "450000.00"
```