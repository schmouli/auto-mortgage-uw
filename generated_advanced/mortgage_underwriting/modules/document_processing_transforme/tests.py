--- conftest.py ---
```python
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from decimal import Decimal

# Project imports
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.main import app  # Assuming main app entry point
from mortgage_underwriting.modules.document_processing.models import (
    DocumentRecord,
    ExtractedData,
)
from mortgage_underwriting.modules.document_processing.schemas import (
    DocumentUploadRequest,
    DocumentProcessingResponse,
)

# Database Configuration for Testing (In-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def async_engine():
    """Create a new database engine for each test function."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test function."""
    async_session_maker = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session
        await session.rollback()

@pytest.fixture
def mock_s3_client():
    """Mock the S3 client for file storage."""
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.upload_fileobj = MagicMock(return_value="https://s3-bucket/key.pdf")
    return mock

@pytest.fixture
def mock_ocr_service():
    """Mock the external OCR/Transformer service."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    # Default successful response
    mock.extract_text.return_value = {
        "raw_text": "Employment Verification\nName: John Doe\nAnnual Income: 85000.00",
        "confidence": 0.98
    }
    return mock

@pytest.fixture
def valid_document_payload() -> dict:
    """Valid payload for document upload."""
    return {
        "applicant_id": "123e4567-e89b-12d3-a456-426614174000",
        "document_type": "employment_letter",
        "file_name": "paystub_2023.pdf",
        "mime_type": "application/pdf"
    }

@pytest.fixture
def sample_extracted_financial_data() -> dict:
    """Simulated data extracted by the DPT service."""
    return {
        "annual_income": Decimal("85000.00"),
        "employer_name": "Tech Corp",
        "employment_status": "full_time",
        "sin_hash": "a1b2c3d4e5f6", # Hashed SIN per PIPEDA
    }
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from mortgage_underwriting.modules.document_processing.services import DPTService
from mortgage_underwriting.modules.document_processing.models import DocumentRecord
from mortgage_underwriting.modules.document_processing.exceptions import (
    DocumentProcessingError,
    UnsupportedFileTypeError,
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDPTService:
    """Unit tests for the Document Processing Transformer Service."""

    @pytest.fixture
    def service(self, db_session):
        """Instantiate the service with a mocked DB session."""
        # Mocking the S3 client and OCR client via dependency injection or patching
        with patch("mortgage_underwriting.modules.document_processing.services.S3Client") as mock_s3, \
             patch("mortgage_underwriting.modules.document_processing.services.OCRTransformer") as mock_ocr:
            
            mock_s3.return_value.upload_fileobj = MagicMock(return_value="s3://key")
            mock_ocr.return_value.extract = AsyncMock(return_value={
                "income": Decimal("75000.00"),
                "employer": "Acme Inc",
                "sin": "encrypted-sin-value"
            })
            
            return DPTService(db_session, s3_client=mock_s3.return_value, ocr_client=mock_ocr.return_value)

    @pytest.mark.asyncio
    async def test_process_document_success(self, service, valid_document_payload, db_session):
        """Test successful processing of a document: upload -> OCR -> Save."""
        # Arrange
        file_content = b"fake pdf content"
        payload = valid_document_payload

        # Act
        result = await service.process_document(
            applicant_id=payload["applicant_id"],
            file_name=payload["file_name"],
            file_content=file_content,
            mime_type=payload["mime_type"]
        )

        # Assert
        assert result is not None
        assert result.status == "completed"
        assert result.extracted_data is not None
        
        # Verify Database Record
        stmt = select(DocumentRecord).where(DocumentRecord.id == result.id)
        db_record = await db_session.execute(stmt)
        record = db_record.scalar_one_or_none()
        
        assert record is not None
        assert record.file_url is not None
        assert record.applicant_id == payload["applicant_id"]
        
        # Regulatory: FINTRAC Audit Trail
        assert record.created_at is not None
        assert record.updated_at is not None

    @pytest.mark.asyncio
    async def test_process_document_unsupported_type(self, service, valid_document_payload):
        """Test that unsupported file types raise UnsupportedFileTypeError."""
        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            await service.process_document(
                applicant_id=valid_document_payload["applicant_id"],
                file_name="malware.exe",
                file_content=b"content",
                mime_type="application/exe"
            )
        assert "Unsupported file type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_financial_data_precision(self, service):
        """Test that financial data is extracted with Decimal precision, not float."""
        # Arrange
        raw_text = "Total Income: $1,250,000.50"
        
        # Act
        income = service._extract_income_field(raw_text)
        
        # Assert
        assert isinstance(income, Decimal)
        assert income == Decimal("1250000.50")

    @pytest.mark.asyncio
    async def test_pipeda_sin_hashing(self, service, db_session):
        """Test that SIN is hashed/encrypted before storage (PIPEDA Compliance)."""
        # Arrange
        raw_text_with_sin = "SIN: 123-456-789"
        
        # Act
        hashed_sin = service._hash_sin(raw_text_with_sin)
        
        # Assert
        assert hashed_sin != "123-456-789"
        assert "123-456-789" not in hashed_sin # Ensure raw SIN is not stored
        assert isinstance(hashed_sin, str)

    @pytest.mark.asyncio
    async def test_ocr_failure_handling(self, service, valid_document_payload):
        """Test handling of OCR service failures."""
        # Arrange
        service.ocr_client.extract = AsyncMock(side_effect=Exception("OCR Service Unavailable"))
        
        # Act & Assert
        with pytest.raises(DocumentProcessingError) as exc_info:
            await service.process_document(
                applicant_id=valid_document_payload["applicant_id"],
                file_name="bad_scan.pdf",
                file_content=b"content",
                mime_type="application/pdf"
            )
        assert "Failed to process document" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_data_minimization(self, service):
        """Test that only relevant fields are extracted (PIPEDA Data Minimization)."""
        # Arrange
        raw_text = """
        Name: John Doe
        Address: 123 Main St
        Favorite Color: Blue
        Annual Salary: 60000.00
        """
        
        # Act
        data = service._transform_and_validate(raw_text)
        
        # Assert
        assert "annual_salary" in data
        assert "favorite_color" not in data # Verify minimization
        assert "address" not in data # Verify minimization unless required

    @pytest.mark.asyncio
    async def test_high_risk_document_flag(self, service):
        """Test detection of potentially fraudulent or high-risk documents."""
        # Arrange
        raw_text_suspicious = "This document is manually edited and void."
        
        # Act
        risk_score = service._calculate_risk_score(raw_text_suspicious)
        
        # Assert
        assert risk_score > Decimal("0.5") # High threshold

    @pytest.mark.asyncio
    async def test_empty_file_handling(self, service, valid_document_payload):
        """Test handling of empty file uploads."""
        with pytest.raises(AppException):
            await service.process_document(
                applicant_id=valid_document_payload["applicant_id"],
                file_name="empty.pdf",
                file_content=b"",
                mime_type="application/pdf"
            )

    @pytest.mark.asyncio
    async def test_large_file_rejection(self, service, valid_document_payload):
        """Test that files exceeding size limits are rejected."""
        # Simulate a file larger than 10MB (10 * 1024 * 1024)
        large_content = b"x" * (11 * 1024 * 1024)
        
        with pytest.raises(AppException) as exc_info:
            await service.process_document(
                applicant_id=valid_document_payload["applicant_id"],
                file_name="large.pdf",
                file_content=large_content,
                mime_type="application/pdf"
            )
        assert "File size exceeds limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transaction_type_flag_fintrac(self, service, db_session, valid_document_payload):
        """Test that documents related to large transactions are flagged (FINTRAC)."""
        # Arrange
        # Mock extraction to return a large cash deposit amount
        service.ocr_client.extract = AsyncMock(return_value={
            "transaction_amount": Decimal("12000.00"), # > 10k CAD
            "transaction_type": "cash_deposit"
        })

        # Act
        result = await service.process_document(
            applicant_id=valid_document_payload["applicant_id"],
            file_name="large_deposit.pdf",
            file_content=b"content",
            mime_type="application/pdf"
        )

        # Assert
        assert result.requires_review is True
        assert result.fintrac_flag is True
```

--- integration_tests ---
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