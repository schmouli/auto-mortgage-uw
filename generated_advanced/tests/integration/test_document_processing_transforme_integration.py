```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy import select

from mortgage_underwriting.modules.document_processing_transformer.routes import router
from mortgage_underwriting.modules.document_processing_transformer.models import DocumentRecord
from mortgage_underwriting.common.database import get_async_session

# Override dependency for testing
async def override_get_db():
    from mortgage_underwriting.tests.conftest import db_session
    # We need a way to get the session fixture into the dependency override.
    # However, in integration tests with FastAPI, we usually pass the session 
    # via the client fixture or override the dependency in the test setup.
    # For simplicity in this pattern, we will assume a global engine setup 
    # or use the fixture provided by conftest if accessible, 
    # but standard practice is to create a test engine.
    pass 

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentProcessingEndpoints:

    @pytest.fixture
    def app(self, db_session):
        """
        Create a test FastAPI app with the router and DB override.
        """
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/document-processing", tags=["DocumentProcessing"])

        # Dependency Override
        async def get_test_db():
            yield db_session

        app.dependency_overrides[get_async_session] = get_test_db
        yield app
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_upload_document_endpoint(self, app: FastAPI):
        """
        Test uploading a document for processing.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "application_id": "app_integration_01",
                "document_type": "pay_stub",
                "file_url": "https://s3.bucket/stub.pdf",
                "metadata": {"source": "mobile"}
            }

            # We must mock the OCR client here because the route handler instantiates the service.
            # Since we can't easily patch the service instantiation inside the route without 
            # dependency injection for the service itself, we will assume the Service 
            # uses a default OCR client or we patch the module where the route imports it.
            
            with pytest.mock.patch(
                "mortgage_underwriting.modules.document_processing_transformer.routes.OCRClient"
            ) as MockOCR:
                # Configure Mock
                mock_instance = AsyncMock()
                mock_instance.extract_data.return_value = {
                    "net_income": "5000.00",
                    "sin": "987654321"
                }
                MockOCR.return_value = mock_instance

                # Also mock encryption
                with pytest.mock.patch(
                    "mortgage_underwriting.modules.document_processing_transformer.routes.encrypt_pii",
                    return_value="hashed_sin"
                ):
                    response = await client.post("/api/v1/document-processing/upload", json=payload)

            assert response.status_code == 201
            data = response.json()
            assert data["application_id"] == "app_integration_01"
            assert data["status"] == "processed"
            assert "id" in data
            assert data["extracted_data"]["net_income"] == "5000.00"
            assert "sin" not in data["extracted_data"] # PII check

    @pytest.mark.asyncio
    async def test_get_document_endpoint(self, app: FastAPI, db_session):
        """
        Test retrieving a processed document.
        """
        # Pre-populate DB
        doc = DocumentRecord(
            application_id="app_get_01",
            file_url="url.pdf",
            document_type="bank_statement",
            status="processed"
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/document-processing/{doc.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == doc.id
            assert data["status"] == "processed"

    @pytest.mark.asyncio
    async def test_upload_invalid_payload(self, app: FastAPI):
        """
        Test validation error on missing required fields.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "application_id": "app_bad_01"
                # Missing document_type and file_url
            }

            response = await client.post("/api/v1/document-processing/upload", json=payload)

            assert response.status_code == 422
            assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_process_workflow_multiple_documents(self, app: FastAPI):
        """
        Test processing multiple documents for a single application to ensure aggregation logic works.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            
            app_id = "app_workflow_01"

            with pytest.mock.patch(
                "mortgage_underwriting.modules.document_processing_transformer.routes.OCRClient"
            ) as MockOCR, \
            pytest.mock.patch(
                "mortgage_underwriting.modules.document_processing_transformer.routes.encrypt_pii",
                return_value="hash"
            ):
                
                mock_instance = AsyncMock()
                MockOCR.return_value = mock_instance

                # Doc 1
                mock_instance.extract_data.return_value = {"net_income": "3000.00", "sin": "111"}
                await client.post("/api/v1/document-processing/upload", json={
                    "application_id": app_id,
                    "document_type": "pay_stub",
                    "file_url": "stub1.pdf"
                })

                # Doc 2
                mock_instance.extract_data.return_value = {"net_income": "3200.00", "sin": "111"}
                await client.post("/api/v1/document-processing/upload", json={
                    "application_id": app_id,
                    "document_type": "pay_stub",
                    "file_url": "stub2.pdf"
                })

            # Verify both exist in DB
            stmt = select(DocumentRecord).where(DocumentRecord.application_id == app_id)
            result = await db_session.execute(stmt)
            docs = result.scalars().all()

            assert len(docs) == 2
            assert all(d.status == "processed" for d in docs)

    @pytest.mark.asyncio
    async def test_get_non_existent_document(self, app: FastAPI):
        """
        Test 404 response for missing document.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/document-processing/99999")
            assert response.status_code == 404
```