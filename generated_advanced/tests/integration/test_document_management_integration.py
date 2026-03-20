import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from mortgage_underwriting.modules.document_management.models import Document, DocumentStatus
from mortgage_underwriting.common.database import get_async_session


@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_upload_document_workflow(self, app: FastAPI, db_session: AsyncSession):
        """
        Test the full workflow of uploading a document via API.
        Ensures database record is created correctly.
        """
        # Dependency override to use test session
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            files = {"file": ("pay_stub.pdf", b"%PDF-1.4 fake content", "application/pdf")}
            data = {
                "applicant_id": "applicant-uuid-1",
                "document_type": "PAY_STUB",
                "file_name": "pay_stub.pdf",
                "mime_type": "application/pdf",
                "file_size_bytes": 1024
            }
            
            response = await client.post("/api/v1/documents/upload", data=data, files=files)

            # Assert
            assert response.status_code == 201
            json_resp = response.json()
            assert "id" in json_resp
            assert json_resp["applicant_id"] == "applicant-uuid-1"
            assert json_resp["status"] == DocumentStatus.UPLOADED.value
            
            # Database Verification
            stmt = select(Document).where(Document.id == json_resp["id"])
            result = await db_session.execute(stmt)
            doc = result.scalar_one_or_none()
            
            assert doc is not None
            assert doc.file_name == "pay_stub.pdf"
            assert doc.created_at is not None # Compliance: Audit trail
            assert doc.created_by is not None # Compliance: Audit trail

        app.dependency_overrides.clear()

    async def test_get_document_endpoint(self, app: FastAPI, db_session: AsyncSession, sample_document: Document):
        """Test retrieving a specific document via GET."""
        # Setup
        db_session.add(sample_document)
        await db_session.commit()
        
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(f"/api/v1/documents/{sample_document.id}")

            # Assert
            assert response.status_code == 200
            json_resp = response.json()
            assert json_resp["id"] == sample_document.id
            assert json_resp["file_name"] == sample_document.file_name
            
            # Compliance Check: Ensure sensitive data isn't leaked
            assert "storage_key" not in json_resp # Internal detail should not be exposed

        app.dependency_overrides.clear()

    async def test_verify_document_endpoint(self, app: FastAPI, db_session: AsyncSession, sample_document: Document):
        """Test verifying a document via PATCH."""
        # Setup
        sample_document.status = DocumentStatus.UPLOADED
        db_session.add(sample_document)
        await db_session.commit()
        
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            payload = {"verified": True, "notes": "Matches payroll records"}
            response = await client.patch(f"/api/v1/documents/{sample_document.id}/verify", json=payload)

            # Assert
            assert response.status_code == 200
            json_resp = response.json()
            assert json_resp["status"] == DocumentStatus.VERIFIED.value
            assert json_resp["verified_by"] is not None
            
            # DB Verification
            await db_session.refresh(sample_document)
            assert sample_document.status == DocumentStatus.VERIFIED
            assert sample_document.verified_at is not None

        app.dependency_overrides.clear()

    async def test_list_documents_pagination(self, app: FastAPI, db_session: AsyncSession):
        """Test listing documents with pagination."""
        # Setup - Create multiple documents
        docs = []
        for i in range(5):
            docs.append(Document(
                id=f"doc-{i}",
                applicant_id="applicant-1",
                document_type="ID",
                file_name=f"file_{i}.pdf",
                mime_type="application/pdf",
                file_size_bytes=1000,
                storage_key=f"key-{i}",
                status=DocumentStatus.UPLOADED,
                created_at=datetime.utcnow(),
                created_by="system"
            ))
        db_session.add_all(docs)
        await db_session.commit()
        
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/api/v1/documents?applicant_id=applicant-1&limit=2&offset=0")

            # Assert
            assert response.status_code == 200
            json_resp = response.json()
            assert "items" in json_resp
            assert len(json_resp["items"]) == 2
            assert json_resp["total"] == 5
            assert json_resp["offset"] == 0

        app.dependency_overrides.clear()

    async def test_get_document_not_found_integration(self, app: FastAPI, db_session: AsyncSession):
        """Test 404 response when document does not exist."""
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents/does-not-exist")
            assert response.status_code == 404
            assert "detail" in response.json()

        app.dependency_overrides.clear()

    async def test_upload_unsupported_mime_type(self, app: FastAPI, db_session: AsyncSession):
        """Test rejection of unsafe file types at the API boundary."""
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("script.js", b"console.log('xss')", "application/javascript")}
            data = {
                "applicant_id": "applicant-1",
                "document_type": "OTHER",
                "file_name": "script.js",
                "mime_type": "application/javascript",
                "file_size_bytes": 100
            }
            
            response = await client.post("/api/v1/documents/upload", data=data, files=files)
            
            # Assert - Should be rejected by validation logic
            assert response.status_code == 400 or response.status_code == 422
            
            # Verify no record created
            stmt = select(Document).where(Document.file_name == "script.js")
            result = await db_session.execute(stmt)
            assert result.scalar_one_or_none() is None

        app.dependency_overrides.clear()