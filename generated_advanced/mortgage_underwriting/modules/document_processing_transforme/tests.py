--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from unittest.mock import AsyncMock, MagicMock

# Import paths based on project structure
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.document_processing_transformer.models import (
    DocumentRecord,
    ExtractedData,
)

# Use in-memory SQLite for fast testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        yield session

    # Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def mock_ocr_client():
    """
    Mocks the external OCR/AI extraction service.
    """
    client = AsyncMock()
    return client

@pytest.fixture
def sample_document_payload():
    """
    Sample payload for document upload.
    """
    return {
        "application_id": "app_12345",
        "document_type": "pay_stub",
        "file_url": "https://secure-storage.example.com/files/stub_001.pdf",
        "metadata": {
            "upload_source": "portal",
            "applicant_id": "borrower_001"
        }
    }

@pytest.fixture
def sample_extracted_data():
    """
    Sample data returned by the mock OCR service.
    """
    return {
        "applicant_name": "John Doe",
        "sin": "123456789", # Should be encrypted
        "net_income": Decimal("3500.00"),
        "pay_period_start": "2023-01-01",
        "pay_period_end": "2023-01-15",
        "year_to_date": Decimal("42000.00")
    }

@pytest.fixture
def mock_security_service():
    """
    Mocks the security service for PII encryption.
    """
    with pytest.mock.patch(
        "mortgage_underwriting.modules.document_processing_transformer.services.encrypt_pii"
    ) as mock_enc:
        # Default behavior: return a dummy hash
        mock_enc.return_value = "encrypted_hash_123"
        yield mock_enc
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, call
from sqlalchemy import select

from mortgage_underwriting.modules.document_processing_transformer.models import (
    DocumentRecord,
    ExtractedData,
)
from mortgage_underwriting.modules.document_processing_transformer.services import (
    DocumentProcessingService,
)
from mortgage_underwriting.modules.document_processing_transformer.exceptions import (
    DocumentProcessingError,
    ValidationError,
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDocumentProcessingService:

    @pytest.mark.asyncio
    async def test_process_document_success(
        self, db_session, mock_ocr_client, sample_document_payload, sample_extracted_data, mock_security_service
    ):
        """
        Test successful processing of a document: OCR extraction, PII encryption, and DB persistence.
        """
        # Configure mock OCR response
        mock_ocr_client.extract_data.return_value = sample_extracted_data

        service = DocumentProcessingService(db_session, mock_ocr_client)
        
        result = await service.process_document(sample_document_payload)

        # 1. Verify OCR was called with the file URL
        mock_ocr_client.extract_data.assert_awaited_once_with(sample_document_payload["file_url"])

        # 2. Verify PII (SIN) was encrypted
        # Note: service should call encrypt_pii on the SIN before saving
        assert mock_security_service.call_count >= 1 

        # 3. Verify Database Record Creation
        stmt = select(DocumentRecord).where(DocumentRecord.application_id == sample_document_payload["application_id"])
        doc_result = await db_session.execute(stmt)
        doc_record = doc_result.scalar_one()

        assert doc_record.file_url == sample_document_payload["file_url"]
        assert doc_record.status == "processed"
        assert doc_record.document_type == sample_document_payload["document_type"]

        # 4. Verify Extracted Data Persistence
        stmt_data = select(ExtractedData).where(ExtractedData.document_id == doc_record.id)
        data_result = await db_session.execute(stmt_data)
        extracted_record = data_result.scalar_one()

        assert extracted_record.net_income == Decimal("3500.00")
        assert extracted_record.sin_hash == "encrypted_hash_123" # Ensure encrypted value is stored, not raw

        # 5. Verify Response DTO
        assert result.id == doc_record.id
        assert result.status == "processed"
        assert "sin" not in result.extracted_data.model_dump() # Ensure PII not leaked in response

    @pytest.mark.asyncio
    async def test_process_document_ocr_failure(self, db_session, mock_ocr_client, sample_document_payload):
        """
        Test handling of OCR service failure.
        """
        mock_ocr_client.extract_data.side_effect = Exception("OCR Service Unavailable")

        service = DocumentProcessingService(db_session, mock_ocr_client)

        with pytest.raises(DocumentProcessingError) as exc_info:
            await service.process_document(sample_document_payload)

        assert "Failed to process document" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_document_invalid_income_format(
        self, db_session, mock_ocr_client, sample_document_payload
    ):
        """
        Test validation when OCR returns unparsable financial data.
        """
        bad_data = {
            "applicant_name": "Jane Doe",
            "net_income": "not_a_number", # Invalid format
            "pay_period_start": "2023-01-01"
        }
        mock_ocr_client.extract_data.return_value = bad_data

        service = DocumentProcessingService(db_session, mock_ocr_client)

        with pytest.raises(ValidationError) as exc_info:
            await service.process_document(sample_document_payload)
        
        assert "Income format" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_mask_pii_in_logs(
        self, db_session, mock_ocr_client, sample_document_payload, sample_extracted_data, caplog
    ):
        """
        Ensure that sensitive data (SIN) is never logged in plain text.
        """
        mock_ocr_client.extract_data.return_value = sample_extracted_data
        
        service = DocumentProcessingService(db_session, mock_ocr_client)
        
        with caplog.at_level("INFO"):
            await service.process_document(sample_document_payload)

        # Check logs for the raw SIN
        raw_sin = sample_extracted_data["sin"]
        for record in caplog.records:
            assert raw_sin not in record.message, "SIN detected in logs!"

    @pytest.mark.asyncio
    async def test_calculate_annual_income_from_ytd_and_period(
        self, db_session
    ):
        """
        Test helper logic that extrapolates annual income if YTD is missing but period income is present.
        """
        # This tests a private or protected method logic within the service
        # Assuming the service has a method to normalize income
        service = DocumentProcessingService(db_session, AsyncMock())
        
        # Mock data: Bi-weekly pay (26 periods/year)
        period_income = Decimal("2500.00")
        pay_frequency = "bi_weekly"
        
        # Logic: 2500 * 26 = 65,000
        annualized = service._annualize_income(period_income, pay_frequency)
        
        assert annualized == Decimal("65000.00")

    @pytest.mark.asyncio
    async def test_get_document_by_id(self, db_session, sample_document_payload):
        """
        Test retrieving a document record.
        """
        # Setup: Create a record manually
        doc = DocumentRecord(
            application_id=sample_document_payload["application_id"],
            file_url=sample_document_payload["file_url"],
            document_type="employment_letter",
            status="uploaded"
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        service = DocumentProcessingService(db_session, AsyncMock())
        retrieved = await service.get_document(doc.id)

        assert retrieved.id == doc.id
        assert retrieved.file_url == doc.file_url

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, db_session):
        """
        Test retrieval of non-existent document raises error.
        """
        service = DocumentProcessingService(db_session, AsyncMock())
        
        with pytest.raises(AppException) as exc_info:
            await service.get_document(999)
        
        assert exc_info.value.status_code == 404

    def test_validate_financial_decimal_precision(self):
        """
        Test that Decimal conversion handles high precision correctly without float errors.
        """
        service = DocumentProcessingService(None, None)
        
        raw_string = "1234.567890"
        result = service._parse_decimal(raw_string)
        
        assert isinstance(result, Decimal)
        assert result == Decimal("1234.567890")

    def test_validate_financial_decimal_zero(self):
        """
        Test boundary condition: Zero income.
        """
        service = DocumentProcessingService(None, None)
        
        with pytest.raises(ValidationError):
            service._validate_income_amount(Decimal("0.00"))

    @pytest.mark.asyncio
    async def test_update_document_status(self, db_session):
        """
        Test updating the status of an existing document.
        """
        doc = DocumentRecord(
            application_id="app_1",
            file_url="url",
            document_type="id",
            status="uploaded"
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        service = DocumentProcessingService(db_session, AsyncMock())
        updated = await service.update_status(doc.id, "verified")

        assert updated.status == "verified"
        assert updated.updated_at > doc.created_at
```

--- integration_tests ---
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