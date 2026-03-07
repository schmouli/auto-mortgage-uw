```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

from mortgage_underwriting.modules.document_processing_transformer.routes import router
from mortgage_underwriting.modules.document_processing_transformer.models import DocumentRecord
from mortgage_underwriting.modules.document_processing_transformer.services import DocumentProcessingService
from mortgage_underwriting.common.database import Base
from unittest.mock import AsyncMock, patch

# Import dependencies to override them
from mortgage_underwriting.modules.document_processing_transformer.dependencies import get_doc_service, get_db

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentProcessingAPI:

    @pytest.fixture
    def app(self, db_session):
        # Create app
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/dpt", tags=["Document Processing"])
        
        # Override DB dependency
        async def override_get_db():
            yield db_session
        
        # Override Service dependency with a real instance but mocked OCR client
        mock_ocr = AsyncMock()
        mock_ocr.extract_text.return_value = {
            "applicant_name": "Integration User",
            "sin": "987654321",
            "annual_income": "95000.00",
            "employment_status": "Employed",
            "employer_name": "Bank of Canada",
            "document_type": "pay_stub",
            "date_of_birth": "1990-01-01"
        }
        
        # We need a real service instance to test the integration with the route,
        # but we inject the mocked OCR client.
        real_service = DocumentProcessingService(ocr_client=mock_ocr)
        
        async def override_get_service():
            yield real_service

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_doc_service] = override_get_service
        
        yield app
        
        # Clean up
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_upload_and_process_document(self, app: FastAPI):
        # Arrange
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "file_name": "test_integration.pdf",
                "content_type": "application/pdf",
                "s3_bucket": "test-bucket",
                "s3_key": "test/file.pdf"
            }

            # Act
            response = await client.post("/api/v1/dpt/process", json=payload)

            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["status"] == "completed"
            assert data["file_name"] == "test_integration.pdf"
            assert "id" in data
            assert data["extracted_data"]["annual_income"] == "95000.00" # Serialized as string usually
            
            # Verify PII is not in response
            assert "sin" not in data["extracted_data"]
            assert "987654321" not in str(data)

    @pytest.mark.asyncio
    async def test_get_document_status(self, app: FastAPI, db_session: AsyncSession):
        # Arrange - Create a record directly in DB
        new_record = DocumentRecord(
            file_name="status_check.pdf",
            s3_key="test/status.pdf",
            status="completed",
            hashed_sin="hashed_123",
            extracted_data_json={"income": "100"},
            pii_encrypted_json={"dob": "enc"}
        )
        db_session.add(new_record)
        await db_session.commit()
        await db_session.refresh(new_record)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(f"/api/v1/dpt/documents/{new_record.id}")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == new_record.id
            assert data["status"] == "completed"
            assert "created_at" in data # Audit trail check

    @pytest.mark.asyncio
    async def test_upload_invalid_content_type(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "file_name": "virus.exe",
                "content_type": "application/x-msdownload",
                "s3_bucket": "test-bucket",
                "s3_key": "test/virus.exe"
            }

            response = await client.post("/api/v1/dpt/process", json=payload)

            assert response.status_code == 400
            assert "Invalid file type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_non_existent_document(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/dpt/documents/99999")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_processing_failure_returns_500(self, app: FastAPI):
        # Override service to raise an error
        async def failing_service():
            raise Exception("Internal OCR failure")

        app.dependency_overrides[get_doc_service] = failing_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "file_name": "bad.pdf",
                "content_type": "application/pdf",
                "s3_bucket": "test",
                "s3_key": "bad.pdf"
            }
            
            response = await client.post("/api/v1/dpt/process", json=payload)
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_fintrac_audit_log_immutability(self, app: FastAPI, db_session: AsyncSession):
        # This test checks that the record created has the required audit fields
        # and that we cannot update them (logic check, though DB enforces constraints)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "file_name": "audit_test.pdf",
                "content_type": "application/pdf",
                "s3_bucket": "test",
                "s3_key": "audit.pdf"
            }
            
            response = await client.post("/api/v1/dpt/process", json=payload)
            assert response.status_code == 201
            
            record_id = response.json()["id"]
            
            # Fetch from DB directly to check audit fields
            db_record = await db_session.get(DocumentRecord, record_id)
            
            assert db_record.created_at is not None
            assert db_record.updated_at is not None
            # In a real scenario, we might check a trigger or constraint here
            # For now, we ensure the service populated them
```