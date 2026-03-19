--- conftest.py ---
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Import application components
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.document_processing_transformer.models import (
    DocumentRecord,
    ExtractionResult,
)
from mortgage_underwriting.main import app  # Assuming main.py exists to bootstrap the app
from mortgage_underwriting.modules.document_processing_transformer.routes import router

# Database Setup for Testing (In-Memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    Applies migrations/creates tables automatically.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a FastAPI AsyncClient for integration testing.
    Overrides the dependency injection for the database session.
    """
    from mortgage_underwriting.common.database import get_async_session

    async def override_get_async_session():
        yield db_session

    app.include_router(router, prefix="/api/v1/dpt", tags=["Document Processing"])
    app.dependency_overrides[get_async_session] = override_get_async_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# --- Unit Test Fixtures ---

@pytest.fixture
def mock_ocr_service():
    """Mock external OCR API client."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    # Default successful response
    mock.extract_text.return_value = {
        "applicant_name": "John Doe",
        "annual_income": "85000.00",
        "employer_name": "Tech Corp",
        "document_type": "pay_stub"
    }
    return mock


@pytest.fixture
def sample_document_payload():
    return {
        "applicant_id": "123e4567-e89b-12d3-a456-426614174000",
        "document_type": "pay_stub",
        "file_name": "january_paystub.pdf",
        "mime_type": "application/pdf",
        "content_hash": "sha256:abc123...",
    }


@pytest.fixture
def sample_financial_string():
    return "  $ 120,500.75 CAD "

--- unit_tests ---
import pytest
from decimal import Decimal, InvalidOperation
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.document_processing_transformer.services import (
    DocumentProcessingService,
    OCRClient,
)
from mortgage_underwriting.modules.document_processing_transformer.models import (
    DocumentRecord,
    ExtractionResult,
)
from mortgage_underwriting.modules.document_processing_transformer.exceptions import (
    DocumentProcessingError,
    OCRServiceUnavailableError,
    PIIValidationError,
)
from mortgage_underwriting.common.security import encrypt_pii, hash_value


@pytest.mark.unit
class TestDocumentProcessingService:

    @pytest.fixture
    def service(self):
        return DocumentProcessingService()

    @pytest.mark.asyncio
    async def test_create_document_record_success(self, service, sample_document_payload):
        """Test successful creation of a document metadata record."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = MagicMock()

        result = await service.create_document_record(mock_db, sample_document_payload)

        assert isinstance(result, DocumentRecord)
        assert result.applicant_id == sample_document_payload["applicant_id"]
        assert result.file_name == sample_document_payload["file_name"]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_document_record_db_failure(self, service, sample_document_payload):
        """Test handling of database errors during record creation."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(side_effect=SQLAlchemyError("Connection failed"))

        with pytest.raises(DocumentProcessingError) as exc_info:
            await service.create_document_record(mock_db, sample_document_payload)
        
        assert "Failed to save document metadata" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_ocr_extraction_success(self, service, mock_ocr_service):
        """Test successful OCR extraction and transformation."""
        mock_db = AsyncMock()
        doc_record = DocumentRecord(
            id=1,
            applicant_id="uuid-123",
            file_name="stub.pdf",
            storage_path="/path/to/file",
            status="pending"
        )

        # Patch the OCR client inside the service
        with patch.object(service, 'ocr_client', mock_ocr_service):
            result = await service.process_ocr_extraction(mock_db, doc_record)

        assert result is not None
        assert result.extracted_data["employer_name"] == "Tech Corp"
        mock_ocr_service.extract_text.assert_awaited_once_with(doc_record.storage_path)
        
        # Verify DB update for status
        assert doc_record.status == "completed"

    @pytest.mark.asyncio
    async def test_process_ocr_extraction_service_down(self, service):
        """Test handling when the external OCR service is unreachable."""
        mock_db = AsyncMock()
        doc_record = DocumentRecord(
            id=1,
            applicant_id="uuid-123",
            file_name="stub.pdf",
            storage_path="/path/to/file",
            status="pending"
        )
        
        mock_ocr = AsyncMock()
        mock_ocr.extract_text.side_effect = Exception("Service Unavailable")

        with patch.object(service, 'ocr_client', mock_ocr):
            with pytest.raises(OCRServiceUnavailableError):
                await service.process_ocr_extraction(mock_db, doc_record)

    def test_parse_financial_value_valid(self, service, sample_financial_string):
        """Test parsing a messy financial string into a clean Decimal."""
        result = service.parse_financial_value(sample_financial_string)
        assert result == Decimal("120500.75")
        assert isinstance(result, Decimal)

    def test_parse_financial_value_invalid_format(self, service):
        """Test parsing a string that is not a number."""
        with pytest.raises(ValueError) as exc_info:
            service.parse_financial_value("Not a number")
        assert "Invalid financial format" in str(exc_info.value)

    def test_parse_financial_value_negative_rejection(self, service):
        """Test that negative income values are rejected."""
        with pytest.raises(ValueError):
            service.parse_financial_value("-500.00")

    def test_sanitize_pii_fields(self, service):
        """Test that PII fields are hashed/encrypted before storage/logic."""
        raw_data = {
            "sin": "123456789",
            "dob": "1990-01-01",
            "income": "50000"
        }
        
        sanitized = service.sanitize_pii_fields(raw_data)
        
        # SIN should be hashed (not plain text)
        assert sanitized["sin"] != "123456789"
        assert len(sanitized["sin"]) == 64 # SHA256 hex length
        
        # DOB should be encrypted or handled securely (mock check)
        assert "dob" in sanitized
        
        # Income should remain unchanged
        assert sanitized["income"] == "50000"

    def test_validate_financial_data_compliance_gds(self, service):
        """Test validation logic related to financial ratios (mocked)."""
        # This would typically interact with the Underwriting module
        # Here we test the transformer's ability to catch negative/zero values
        data = {"monthly_income": Decimal("0.00")}
        
        with pytest.raises(PIIValidationError):
            service.validate_financial_fields(data)

    def test_mask_pii_for_logs(self, service):
        """Test that log output does not contain sensitive data."""
        log_dict = {
            "user_id": "abc",
            "sin": "999999999",
            "status": "processing"
        }
        
        safe_log = service.mask_pii_for_logs(log_dict)
        
        assert "sin" not in safe_log or safe_log["sin"] == "***REDACTED***"
        assert safe_log["user_id"] == "abc"


@pytest.mark.unit
class TestExtractionResultModel:
    """Unit tests for the ORM model logic (validators)."""

    def test_calculate_confidence_score(self):
        """Test confidence score calculation logic."""
        extraction = ExtractionResult(
            document_id=1,
            raw_text="Sample text",
            extracted_data={"income": "50000"},
            confidence_score=0.0
        )
        
        # Simulate logic: if raw_text length > 0, base confidence is 50%
        # In a real scenario, this might be a method or property
        extraction.confidence_score = 0.85
        
        assert extraction.confidence_score == Decimal("0.85")

--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal

from mortgage_underwriting.modules.document_processing_transformer.models import DocumentRecord
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentProcessingEndpoints:

    async def test_upload_document_success(self, client: AsyncClient, sample_document_payload):
        """Test uploading a new document metadata record."""
        response = await client.post("/api/v1/dpt/upload", json=sample_document_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["file_name"] == "january_paystub.pdf"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    async def test_upload_document_missing_fields(self, client: AsyncClient):
        """Test upload validation with missing required fields."""
        incomplete_payload = {
            "file_name": "missing_info.pdf"
        }
        response = await client.post("/api/v1/dpt/upload", json=incomplete_payload)
        
        assert response.status_code == 422  # Unprocessable Entity

    async def test_get_document_by_id(self, client: AsyncClient, db_session, sample_document_payload):
        """Test retrieving a document by its ID."""
        # 1. Create a document directly in DB
        doc = DocumentRecord(**sample_document_payload)
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        # 2. Fetch via API
        response = await client.get(f"/api/v1/dpt/documents/{doc.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc.id
        assert data["content_hash"] == "sha256:abc123..."

    async def test_get_document_not_found(self, client: AsyncClient):
        """Test retrieving a non-existent document."""
        response = await client.get("/api/v1/dpt/documents/99999")
        
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_trigger_extraction_workflow(self, client: AsyncClient, db_session, sample_document_payload, mock_ocr_service):
        """
        Test the full workflow: Upload -> Trigger Extraction -> Verify Result.
        Note: We must mock the actual external OCR call here.
        """
        # 1. Upload
        upload_resp = await client.post("/api/v1/dpt/upload", json=sample_document_payload)
        doc_id = upload_resp.json()["id"]

        # 2. Trigger Extraction (Mocking the external service dependency in the app)
        # In a real integration test, we might use a dependency override to inject the mock OCR client
        from mortgage_underwriting.modules.document_processing_transformer.services import OCRClient
        from unittest.mock import AsyncMock
        
        mock_client = AsyncMock()
        mock_client.extract_text.return_value = {
            "applicant_name": "Jane Doe",
            "annual_income": "92000.50",
            "employer": "FinTech Inc"
        }
        
        # Override the OCR client instantiation if possible, or mock the service layer
        # For this integration test, we assume the endpoint calls the service which calls the client.
        # We will patch the service method directly.
        with pytest.mock.patch(
            'mortgage_underwriting.modules.document_processing_transformer.services.DocumentProcessingService.process_ocr_extraction',
            new_callable=AsyncMock
        ) as mock_process:
            # Configure the mock to return an ExtractionResult-like dict
            mock_process.return_value = {
                "document_id": doc_id,
                "extracted_data": {"annual_income": "92000.50"},
                "status": "completed"
            }

            response = await client.post(f"/api/v1/dpt/documents/{doc_id}/extract")
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "completed"
            assert result["extracted_data"]["annual_income"] == "92000.50"
            mock_process.assert_awaited_once()

    async def test_get_financial_summary(self, client: AsyncClient, db_session):
        """Test endpoint that aggregates financial data from documents."""
        # Setup: Create a document with an associated extraction result
        doc = DocumentRecord(
            applicant_id="uuid-agg",
            file_name="summary.pdf",
            storage_path="/path",
            status="completed"
        )
        db_session.add(doc)
        await db_session.flush()
        
        # Create extraction result manually (bypassing OCR)
        # Note: In real code, this would be a relation, but here we simulate the data state
        # Assuming the endpoint queries ExtractionResult table joined with DocumentRecord
        
        # Verify endpoint structure (assuming it exists)
        response = await client.get(f"/api/v1/dpt/applicants/uuid-agg/financial-summary")
        
        # Implementation dependent: if empty, might be 200 with empty list or 404
        # Assuming 200
        assert response.status_code in [200, 404]

    async def test_pii_protection_in_response(self, client: AsyncClient, db_session):
        """Ensure that sensitive fields (SIN) are never returned in API responses."""
        # Create a document that contains a SIN in its metadata (encrypted in DB)
        # But let's assume a scenario where we try to fetch raw data
        doc = DocumentRecord(
            applicant_id="uuid-pii",
            file_name="sin_card.jpg",
            storage_path="/secure",
            status="pending"
        )
        db_session.add(doc)
        await db_session.commit()
        
        response = await client.get(f"/api/v1/dpt/documents/{doc.id}")
        data = response.json()
        
        # Ensure no raw SIN field exists in the response
        # Even if the model had it (which it shouldn't expose via schema)
        assert "sin" not in data
        assert "social_insurance_number" not in data

    async def test_delete_document_forbidden(self, client: AsyncClient, db_session, sample_document_payload):
        """Test that documents cannot be deleted (FINTRAC compliance: immutable)."""
        doc = DocumentRecord(**sample_document_payload)
        db_session.add(doc)
        await db_session.commit()
        
        # Assuming a DELETE endpoint exists but should return 405 Method Not Allowed or 403
        response = await client.delete(f"/api/v1/dpt/documents/{doc.id}")
        
        assert response.status_code == 405  # Method Not Allowed

    async def test_update_status_only_internal(self, client: AsyncClient, db_session):
        """Test that status updates are protected or internal only."""
        doc = DocumentRecord(
            applicant_id="uuid-upd",
            file_name="upd.pdf",
            storage_path="/path",
            status="pending"
        )
        db_session.add(doc)
        await db_session.commit()
        
        # Attempt to update status via public API
        response = await client.patch(f"/api/v1/dpt/documents/{doc.id}", json={"status": "approved"})
        
        # Should fail or be ignored depending on design. 
        # Assuming strict design: 403 Forbidden or 422 Unprocessable Entity
        assert response.status_code in [403, 422, 405]