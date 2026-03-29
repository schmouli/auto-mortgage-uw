```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from datetime import datetime

# Absolute imports
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_upload_document_endpoint_success(self, app, db_session, mock_s3_client):
        """
        Test the full flow: API Request -> Service -> S3 Mock -> DB.
        """
        # Override the DB dependency to use our test session
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Prepare multipart form data
            files = {
                "file": ("test_income.pdf", b"%PDF-1.4 fake content", "application/pdf")
            }
            data = {
                "borrower_id": "101",
                "document_type": "income_verification"
            }

            response = await client.post("/api/v1/documents/upload", files=files, data=data)

            assert response.status_code == 201
            
            json_resp = response.json()
            assert "id" in json_resp
            assert json_resp["file_name"] == "test_income.pdf"
            assert json_resp["status"] == "uploaded"
            assert json_resp["borrower_id"] == 101
            
            # Verify DB record
            stmt = select(Document).where(Document.id == json_resp["id"])
            result = await db_session.execute(stmt)
            db_doc = result.scalar_one_or_none()
            
            assert db_doc is not None
            assert db_doc.s3_key is not None
            assert db_doc.created_at is not None  # FINTRAC audit check

        app.dependency_overrides.clear()

    async def test_upload_document_unsupported_type(self, app, db_session, mock_s3_client):
        """Test API rejects .exe files."""
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {
                "file": ("bad.exe", b"binary content", "application/x-msdownload")
            }
            data = {
                "borrower_id": "101",
                "document_type": "other"
            }

            response = await client.post("/api/v1/documents/upload", files=files, data=data)

            assert response.status_code == 400
            assert "error_code" in response.json()

        app.dependency_overrides.clear()

    async def test_get_document_endpoint(self, app, db_session, mock_s3_client):
        """Test retrieving a specific document."""
        # Seed data
        new_doc = Document(
            borrower_id=202,
            file_name="id_card.jpg",
            document_type="id_verification",
            s3_key="uploads/id_card.jpg",
            status="uploaded",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(new_doc)
        await db_session.commit()
        await db_session.refresh(new_doc)

        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/documents/{new_doc.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == new_doc.id
            assert data["file_name"] == "id_card.jpg"
            # Ensure PIPEDA compliance: No raw PII in logs (implicit, but we check response structure)
            assert "s3_key" in data # Internal ID might be exposed or not depending on schema, assuming yes here

        app.dependency_overrides.clear()

    async def test_update_status_endpoint(self, app, db_session, mock_s3_client):
        """Test updating document status to 'verified'."""
        # Seed data
        new_doc = Document(
            borrower_id=303,
            file_name="stmt.pdf",
            document_type="income_verification",
            s3_key="u/stmt.pdf",
            status="uploaded",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(new_doc)
        await db_session.commit()
        await db_session.refresh(new_doc)

        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "status": "verified",
                "notes": "Matches application data"
            }
            response = await client.patch(f"/api/v1/documents/{new_doc.id}", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "verified"
            assert data["verification_notes"] == "Matches application data"

            # Verify DB update
            await db_session.refresh(new_doc)
            assert new_doc.status == "verified"
            # Verify audit timestamp update
            assert new_doc.updated_at > new_doc.created_at

        app.dependency_overrides.clear()

    async def test_list_documents_filtering(self, app, db_session, mock_s3_client):
        """Test listing documents filtered by borrower_id."""
        # Seed data for two borrowers
        doc1 = Document(borrower_id=404, file_name="a.pdf", s3_key="a", status="uploaded", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        doc2 = Document(borrower_id=404, file_name="b.pdf", s3_key="b", status="uploaded", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        doc3 = Document(borrower_id=505, file_name="c.pdf", s3_key="c", status="uploaded", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        
        db_session.add_all([doc1, doc2, doc3])
        await db_session.commit()

        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Filter for borrower 404
            response = await client.get("/api/v1/documents", params={"borrower_id": 404})

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert all(d["borrower_id"] == 404 for d in data)

        app.dependency_overrides.clear()

    async def test_delete_document_endpoint(self, app, db_session, mock_s3_client):
        """Test soft delete via endpoint."""
        new_doc = Document(
            borrower_id=606,
            file_name="to_delete.pdf",
            s3_key="del.pdf",
            status="uploaded",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(new_doc)
        await db_session.commit()
        
        doc_id = new_doc.id

        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/documents/{doc_id}")

            assert response.status_code == 204 # No Content

            # Verify Soft Delete in DB
            await db_session.refresh(new_doc)
            assert new_doc.status == "deleted"
            
            # Verify S3 cleanup was called
            mock_s3_client.delete_object.assert_called_once()

        app.dependency_overrides.clear()
```