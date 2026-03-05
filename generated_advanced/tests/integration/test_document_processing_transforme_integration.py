```python
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from mortgage_underwriting.modules.document_processing.routes import router
from mortgage_underwriting.modules.document_processing.models import DocumentRecord
from mortgage_underwriting.common.database import get_async_session

# We need a test app that includes the router
from fastapi import FastAPI

@pytest.fixture(scope="function")
def app(db_session):
    """Create a test FastAPI app with the router and overridden DB dependency."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/document-processing", tags=["documents"])

    # Dependency Override
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentProcessingAPI:
    """Integration tests for the Document Processing Transformer API."""

    async def test_upload_document_endpoint_success(self, app: FastAPI):
        """Test the full workflow of uploading a document via API."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.post(
                "/api/v1/document-processing/upload",
                json={
                    "applicant_id": "550e8400-e29b-41d4-a716-446655440000",
                    "document_type": "pay_stub",
                    "file_name": "jan_2024.pdf",
                    "mime_type": "application/pdf"
                },
                # Note: In real integration, we might use `files=` but here we mock the S3 upload logic
                # inside the service layer. The API likely expects a presigned URL or base64 in JSON 
                # given the structure, or multipart/form-data. Assuming JSON payload for metadata 
                # and the file handling is mocked or abstracted.
            )
            
            # Assert
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["status"] == "processing" or data["status"] == "completed"
            assert "applicant_id" in data

    async def test_upload_missing_required_fields(self, app: FastAPI):
        """Test validation error when required fields are missing."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/document-processing/upload",
                json={
                    "applicant_id": "550e8400-e29b-41d4-a716-446655440000",
                    # Missing document_type and file_name
                }
            )
            
            assert response.status_code == 422 # Validation Error

    async def test_retrieve_document_metadata(self, app: FastAPI, db_session):
        """Test retrieving a processed document by ID."""
        # Arrange: Create a document directly in DB
        doc = DocumentRecord(
            applicant_id="550e8400-e29b-41d4-a716-446655440000",
            document_type="id_verification",
            file_url="http://s3/test.pdf",
            status="completed",
            extracted_data={"sin_hash": "hash123"},
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(f"/api/v1/document-processing/{doc.id}")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(doc.id)
            assert data["status"] == "completed"
            # Regulatory: Ensure raw PII is not in response
            assert "sin" not in data.get("extracted_data", {})
            assert "sin_hash" in data.get("extracted_data", {})

    async def test_list_documents_by_applicant(self, app: FastAPI, db_session):
        """Test listing all documents for a specific applicant."""
        applicant_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Arrange
        doc1 = DocumentRecord(
            applicant_id=applicant_id,
            document_type="pay_stub",
            file_url="s3://1.pdf",
            status="completed",
        )
        doc2 = DocumentRecord(
            applicant_id=applicant_id,
            document_type="id_verification",
            file_url="s3://2.pdf",
            status="completed",
        )
        db_session.add_all([doc1, doc2])
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(f"/api/v1/document-processing/applicant/{applicant_id}")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert all(d["applicant_id"] == applicant_id for d in data)

    async def test_update_document_review_status(self, app: FastAPI, db_session):
        """Test marking a document as reviewed by an underwriter."""
        # Arrange
        doc = DocumentRecord(
            applicant_id="550e8400-e29b-41d4-a716-446655440000",
            document_type="insurance_quote",
            file_url="s3://quote.pdf",
            status="completed",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.patch(
                f"/api/v1/document-processing/{doc.id}/review",
                json={"review_status": "approved", "reviewer_id": "user_123"}
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["review_status"] == "approved"
            
            # Verify DB update
            await db_session.refresh(doc)
            assert doc.review_status == "approved"

    async def test_nonexistent_document_returns_404(self, app: FastAPI):
        """Test retrieving a document that does not exist."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            fake_id = "00000000-0000-0000-0000-000000000000"
            response = await client.get(f"/api/v1/document-processing/{fake_id}")
            assert response.status_code == 404

    async def test_fintrac_flag_visibility_on_high_value(self, app: FastAPI, db_session):
        """Test that high value transactions are visible in the API response."""
        # Arrange
        doc = DocumentRecord(
            applicant_id="550e8400-e29b-41d4-a716-446655440000",
            document_type="bank_statement",
            file_url="s3://bank.pdf",
            status="completed",
            extracted_data={"large_cash_transaction": Decimal("15000.00")},
            fintrac_flag=True
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(f"/api/v1/document-processing/{doc.id}")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            # Ensure compliance flags are present for underwriters
            assert data["fintrac_flag"] is True
```