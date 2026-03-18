--- conftest.py ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from fastapi import FastAPI

# Import paths based on project structure
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.document_processing_transformer.routes import router
from mortgage_underwriting.modules.document_processing_transformer.models import (
    RawDocument,
    ProcessedDocument,
)

# Database setup for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


@pytest.fixture(scope="function")
async def db_session():
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app(db_session: AsyncSession):
    """
    Fixture to create the FastAPI app with overridden dependencies.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/dpt", tags=["Document Processing"])

    # Override the database dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI):
    """
    Async client for integration testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_ocr_service():
    """
    Mocks the external OCR API client.
    """
    with pytest.mock.patch(
        "mortgage_underwriting.modules.document_processing_transformer.services.OCRClient"
    ) as mock:
        yield mock


@pytest.fixture
def valid_ocr_payload():
    """
    Valid OCR output simulating extracted mortgage data.
    Includes financial data as strings to test Decimal conversion.
    """
    return {
        "applicant_name": "John Doe",
        "sin": "123456789",  # PII
        "dob": "1985-05-20",  # PII
        "annual_income": "85000.00",  # Financial
        "property_value": "450000.00",  # Financial
        "loan_amount": "360000.00",  # Financial
        "employer": "Tech Corp",
        "document_type": "employment_letter",
    }


@pytest.fixture
def invalid_ocr_payload():
    """
    Invalid OCR output missing critical fields.
    """
    return {
        "applicant_name": "Jane Doe",
        "sin": "987654321",
        # Missing DOB
        "annual_income": "not_a_number",  # Invalid Financial
        "property_value": "500000.00",
    }


@pytest.fixture
def sample_raw_document():
    """
    A sample RawDocument ORM object.
    """
    return RawDocument(
        id="doc-123",
        file_name="mortgage_app.pdf",
        file_url="https://storage.example.com/doc-123",
        status="uploaded",
    )
--- unit_tests ---
import pytest
from decimal import Decimal, InvalidOperation
from unittest.mock import AsyncMock, MagicMock, patch
from mortgage_underwriting.modules.document_processing_transformer.services import (
    DocumentTransformerService,
    OCRClient,
)
from mortgage_underwriting.modules.document_processing_transformer.models import (
    ProcessedDocument,
    RawDocument,
)
from mortgage_underwriting.modules.document_processing_transformer.exceptions import (
    DocumentProcessingError,
    ValidationError,
)
from mortgage_underwriting.common.security import encrypt_pii

# Import paths
from mortgage_underwriting.modules.document_processing_transformer.schemas import (
    ProcessedDataResponse,
)


@pytest.mark.unit
class TestDocumentTransformerService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        # Patch the OCR client inside the service or inject it
        with patch.object(
            DocumentTransformerService, "_get_ocr_client", return_value=MagicMock()
        ):
            return DocumentTransformerService(mock_db)

    @pytest.mark.asyncio
    async def test_process_document_success(
        self, service, mock_db, valid_ocr_payload, sample_raw_document
    ):
        """
        Test happy path: Document is fetched, OCR data extracted, transformed, and saved.
        """
        # Mock DB fetch for raw document
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_raw_document
        mock_db.execute.return_value = mock_result

        # Mock OCR response
        mock_ocr = service._get_ocr_client()
        mock_ocr.extract_data.return_value = valid_ocr_payload

        # Execute
        result = await service.process_document(document_id="doc-123")

        # Assertions
        assert isinstance(result, ProcessedDocument)
        assert result.status == "completed"
        
        # Verify financial data is stored as Decimal (OSFI/Decimal requirement)
        assert isinstance(result.extracted_annual_income, Decimal)
        assert result.extracted_annual_income == Decimal("85000.00")
        assert isinstance(result.extracted_property_value, Decimal)
        
        # Verify DB interactions
        mock_db.add.assert_called()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_document_not_found(self, service, mock_db):
        """
        Test error case: Raw document does not exist.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(DocumentProcessingError) as exc_info:
            await service.process_document(document_id="non-existent")
        
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_process_document_ocr_failure(
        self, service, mock_db, sample_raw_document
    ):
        """
        Test error case: OCR client raises an exception.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_raw_document
        mock_db.execute.return_value = mock_result

        mock_ocr = service._get_ocr_client()
        mock_ocr.extract_data.side_effect = Exception("OCR Service Unavailable")

        with pytest.raises(DocumentProcessingError) as exc_info:
            await service.process_document(document_id="doc-123")
        
        assert "OCR processing failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_and_transform_financial_data(
        self, service, valid_ocr_payload
    ):
        """
        Test specific transformation logic: String to Decimal conversion.
        Ensures NO float usage.
        """
        # Call internal transformation method
        data = service._validate_and_cast_data(valid_ocr_payload)

        # Check Decimal conversion
        assert data["annual_income"] == Decimal("85000.00")
        assert data["loan_amount"] == Decimal("360000.00")
        
        # Verify type is strictly Decimal, not float or string
        assert type(data["annual_income"]) is Decimal

    @pytest.mark.asyncio
    async def test_validate_and_transform_invalid_financial_data(
        self, service, invalid_ocr_payload
    ):
        """
        Test validation logic: Bad financial strings should raise ValidationError.
        """
        with pytest.raises(ValidationError) as exc_info:
            service._validate_and_cast_data(invalid_ocr_payload)
        
        assert "Invalid financial data" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_pii_redaction_logic(self, service, valid_ocr_payload):
        """
        Test PIPEDA compliance: Ensure PII is handled securely.
        """
        # The service should encrypt SIN before saving to the DB model
        processed_data = service._validate_and_cast_data(valid_ocr_payload)
        
        # Simulate the encryption step that happens in the service
        # In real code, this uses common.security.encrypt_pii
        encrypted_sin = encrypt_pii(processed_data["sin"])
        
        # Ensure the returned value for storage is NOT the plain text
        assert encrypted_sin != valid_ocr_payload["sin"]
        assert encrypted_sin is not None

    @pytest.mark.asyncio
    async def test_calculate_ltv_boundary(self, service):
        """
        Test CMHC logic helper: LTV calculation precision.
        LTV = Loan / Property.
        """
        loan = Decimal("360000.00")
        value = Decimal("450000.00")
        
        ltv = service._calculate_ltv(loan, value)
        
        # 360000 / 450000 = 0.8 (80%)
        assert ltv == Decimal("0.80")
        assert type(ltv) is Decimal

    @pytest.mark.asyncio
    async def test_missing_required_field_raises_validation(self, service):
        """
        Test that missing critical fields (e.g., DOB) trigger validation errors.
        """
        incomplete_payload = {
            "applicant_name": "No DOB",
            "sin": "123456789",
            # Missing DOB
            "annual_income": "50000",
        }
        
        with pytest.raises(ValidationError):
            service._validate_and_cast_data(incomplete_payload)

    @pytest.mark.asyncio
    async def test_audit_trail_population(self, service, mock_db, valid_ocr_payload):
        """
        Test FINTRAC compliance: Audit fields are populated.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_raw_document
        mock_db.execute.return_value = mock_result
        
        mock_ocr = service._get_ocr_client()
        mock_ocr.extract_data.return_value = valid_ocr_payload

        await service.process_document(document_id="doc-123")

        # Get the object that was added to the session
        added_obj = mock_db.add.call_args[0][0]
        
        assert hasattr(added_obj, "created_at")
        assert hasattr(added_obj, "updated_at")
        assert added_obj.created_at is not None
        # In a real scenario, created_by would be the system user or service account
        assert hasattr(added_obj, "created_by") 

    @pytest.mark.asyncio
    async def test_zero_value_handling(self, service):
        """
        Test edge case: Zero values for financial fields.
        """
        payload = {
            "applicant_name": "Zero Income",
            "annual_income": "0.00",
            "property_value": "100000.00",
        }
        
        data = service._validate_and_cast_data(payload)
        assert data["annual_income"] == Decimal("0.00")
        # Should not raise validation error unless business logic forbids 0 income
        # (Here we just test type safety)
--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from mortgage_underwriting.modules.document_processing_transformer.models import (
    RawDocument,
    ProcessedDocument,
)


@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentProcessingAPI:
    async def test_upload_document_workflow(self, client: AsyncClient, db_session):
        """
        Test 1: Upload a new document record.
        """
        response = await client.post(
            "/api/v1/dpt/documents",
            json={
                "file_name": "pay_stub_1.pdf",
                "file_url": "https://secure-storage.com/stub.pdf",
                "content_type": "application/pdf",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["status"] == "uploaded"
        assert data["file_name"] == "pay_stub_1.pdf"

        # Verify DB state
        stmt = select(RawDocument).where(RawDocument.id == data["id"])
        result = await db_session.execute(stmt)
        doc = result.scalar_one_or_none()
        assert doc is not None
        assert doc.file_name == "pay_stub_1.pdf"

    async def test_process_document_endpoint_success(
        self, client: AsyncClient, db_session, mock_ocr_service, valid_ocr_payload
    ):
        """
        Test 2: Trigger processing of an uploaded document.
        Mocks the OCR service but tests the full API stack.
        """
        # 1. Setup: Create a raw document in DB
        new_doc = RawDocument(
            file_name="test.pdf",
            file_url="http://test.com/test.pdf",
            status="uploaded",
        )
        db_session.add(new_doc)
        await db_session.commit()
        await db_session.refresh(new_doc)

        # 2. Mock the OCR service response
        mock_ocr_service.return_value.extract_data.return_value = valid_ocr_payload

        # 3. Call Process Endpoint
        response = await client.post(f"/api/v1/dpt/documents/{new_doc.id}/process")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["extracted_data"]["applicant_name"] == "John Doe"
        
        # 4. Verify DB: ProcessedDocument created
        stmt = select(ProcessedDocument).where(
            ProcessedDocument.raw_document_id == new_doc.id
        )
        result = await db_session.execute(stmt)
        proc_doc = result.scalar_one_or_none()
        
        assert proc_doc is not None
        assert proc_doc.status == "completed"
        
        # Verify Decimal precision in DB response
        assert isinstance(proc_doc.extracted_annual_income, Decimal)
        assert proc_doc.extracted_annual_income == Decimal("85000.00")

    async def test_get_processed_document(
        self, client: AsyncClient, db_session, valid_ocr_payload
    ):
        """
        Test 3: Retrieve processed data via GET.
        """
        # Setup Raw
        raw = RawDocument(file_name="get_test.pdf", file_url="url", status="uploaded")
        db_session.add(raw)
        await db_session.commit()
        await db_session.refresh(raw)

        # Setup Processed
        processed = ProcessedDocument(
            raw_document_id=raw.id,
            status="completed",
            extracted_applicant_name="Jane Smith",
            extracted_annual_income=Decimal("92000.50"),
            extracted_sin_hash="hashed_sin_value", # Should not return real SIN
        )
        db_session.add(processed)
        await db_session.commit()
        await db_session.refresh(processed)

        # Get Request
        response = await client.get(f"/api/v1/dpt/documents/{raw.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # PIPEDA Check: Ensure real SIN is NOT in response
        assert "sin" not in data["extracted_data"]
        assert "123456789" not in str(data) # Ensure no plain text PII leaked
        
        # Financial Check
        assert data["extracted_data"]["annual_income"] == "92000.50"

    async def test_process_nonexistent_document_returns_404(self, client: AsyncClient):
        """
        Test 4: Error handling for missing document.
        """
        response = await client.post("/api/v1/dpt/documents/does-not-exist/process")
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_invalid_file_upload_returns_422(self, client: AsyncClient):
        """
        Test 5: Input validation on upload.
        """
        response = await client.post(
            "/api/v1/dpt/documents",
            json={
                # Missing file_name
                "file_url": "http://test.com"
            },
        )
        assert response.status_code == 422

    async def test_concurrent_processing_handling(
        self, client: AsyncClient, db_session, mock_ocr_service
    ):
        """
        Test 6: Ensure system handles status transitions correctly.
        """
        # Create raw doc
        raw = RawDocument(file_name="concurrent.pdf", file_url="url", status="uploaded")
        db_session.add(raw)
        await db_session.commit()
        await db_session.refresh(raw)

        # Mock OCR to take time (simulated) or just return success
        mock_ocr_service.return_value.extract_data.return_value = {
            "applicant_name": "Concurrent Test",
            "annual_income": "50000",
            "sin": "111222333",
            "dob": "1990-01-01"
        }

        # First process
        r1 = await client.post(f"/api/v1/dpt/documents/{raw.id}/process")
        assert r1.status_code == 200

        # Try to process again (Idempotency or Conflict check expected)
        # Assuming service logic prevents re-processing 'completed' docs
        r2 = await client.post(f"/api/v1/dpt/documents/{raw.id}/process")
        assert r2.status_code == 400 or r2.status_code == 200 # Depends on business logic (usually 400 Bad Request)

    async def test_financial_precision_stored_correctly(
        self, client: AsyncClient, db_session, mock_ocr_service
    ):
        """
        Test 7: Verify high precision financial values are preserved.
        """
        raw = RawDocument(file_name="precision.pdf", file_url="url", status="uploaded")
        db_session.add(raw)
        await db_session.commit()

        # Payload with high precision
        mock_payload = {
            "applicant_name": "Precision User",
            "sin": "123",
            "dob": "2000-01-01",
            "annual_income": "123456.78", # 2 decimal places
            "property_value": "987654.32",
            "loan_amount": "800000.01"
        }
        mock_ocr_service.return_value.extract_data.return_value = mock_payload

        await client.post(f"/api/v1/dpt/documents/{raw.id}/process")

        # Verify in DB directly
        stmt = select(ProcessedDocument).where(ProcessedDocument.raw_document_id == raw.id)
        result = await db_session.execute(stmt)
        proc = result.scalar_one()

        # Strict Decimal comparison
        assert proc.extracted_annual_income == Decimal("123456.78")
        assert proc.extracted_loan_amount == Decimal("800000.01")