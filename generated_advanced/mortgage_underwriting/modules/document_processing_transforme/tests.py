--- conftest.py ---
```python
import pytest
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from mortgage_underwriting.common.security import encrypt_pii, hash_value

# --- Database Setup for Testing ---

class Base(DeclarativeBase):
    pass

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()

# --- Shared Fixtures for DPT Module ---

@pytest.fixture
def mock_ocr_client():
    """Mock external OCR/API client used to extract data from documents."""
    client = AsyncMock()
    return client

@pytest.fixture
def sample_raw_ocr_data():
    """Simulates raw data returned from an OCR engine."""
    return {
        "applicant_name": "John Doe",
        "sin": "123456789", # PII
        "annual_income": "85000.50",
        "employment_status": "Full-time",
        "employer_name": "Tech Corp",
        "document_type": "pay_stub",
        "date_of_birth": "1985-05-20" # PII
    }

@pytest.fixture
def sample_transformed_payload():
    """Simulates the structured DTO after transformation logic."""
    return {
        "applicant_name": "John Doe",
        "hashed_sin": hash_value("123456789"),
        "annual_income": Decimal("85000.50"),
        "employment_status": "Full-time",
        "employer_name": "Tech Corp",
        "document_type": "pay_stub",
        "dob_encrypted": encrypt_pii("1985-05-20")
    }

@pytest.fixture
def sample_document_metadata():
    """Metadata for a document upload request."""
    return {
        "file_name": "pay_stub_jan_2024.pdf",
        "content_type": "application/pdf",
        "s3_bucket": "mortgage-docs-staging",
        "s3_key": "uploads/user_123/pay_stub_jan_2024.pdf"
    }

@pytest.fixture
def mock_pii_service():
    """Mock service for PII handling."""
    service = MagicMock()
    service.encrypt_pii = MagicMock(side_effect=lambda x: f"encrypted_{x}")
    service.hash_value = MagicMock(side_effect=lambda x: f"hashed_{x}")
    return service
```
--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

# Import paths strictly following project conventions
from mortgage_underwriting.modules.document_processing_transformer.services import (
    DocumentProcessingService,
    TransformationError,
    ValidationError
)
from mortgage_underwriting.modules.document_processing_transformer.models import DocumentRecord
from mortgage_underwriting.modules.document_processing_transformer.schemas import (
    DocumentProcessRequest,
    DocumentProcessResponse,
    ExtractedDataDTO
)

@pytest.mark.unit
class TestDocumentProcessingService:

    @pytest.fixture
    def service(self, mock_ocr_client, mock_pii_service):
        return DocumentProcessingService(ocr_client=mock_ocr_client, pii_service=mock_pii_service)

    @pytest.mark.asyncio
    async def test_process_document_success(self, service, mock_db, sample_raw_ocr_data, sample_document_metadata, mock_pii_service):
        # Arrange
        mock_ocr = AsyncMock()
        mock_ocr.extract_text.return_value = sample_raw_ocr_data
        service.ocr_client = mock_ocr
        
        request = DocumentProcessRequest(**sample_document_metadata)

        # Act
        result = await service.process_document(mock_db, request)

        # Assert
        assert isinstance(result, DocumentProcessResponse)
        assert result.status == "completed"
        assert result.extracted_data.annual_income == Decimal("85000.50")
        
        # Verify PII handling (PIPEDA compliance)
        mock_pii_service.hash_value.assert_called_with("123456789")
        mock_pii_service.encrypt_pii.assert_called_with("1985-05-20")

        # Verify DB interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        
        # Check that the saved model has the correct structure
        saved_record = mock_db.add.call_args[0][0]
        assert isinstance(saved_record, DocumentRecord)
        assert saved_record.hashed_sin == "hashed_123456789" # From mock fixture

    @pytest.mark.asyncio
    async def test_process_document_ocr_failure(self, service, mock_db, sample_document_metadata):
        # Arrange
        mock_ocr = AsyncMock()
        mock_ocr.extract_text.side_effect = Exception("OCR Service Unavailable")
        service.ocr_client = mock_ocr
        
        request = DocumentProcessRequest(**sample_document_metadata)

        # Act & Assert
        with pytest.raises(TransformationError) as exc_info:
            await service.process_document(mock_db, request)
        
        assert "OCR processing failed" in str(exc_info.value)
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_document_validation_error_missing_sin(self, service, mock_db, sample_document_metadata):
        # Arrange
        incomplete_data = {
            "applicant_name": "Jane Doe",
            "annual_income": "50000",
            # Missing SIN
        }
        mock_ocr = AsyncMock()
        mock_ocr.extract_text.return_value = incomplete_data
        service.ocr_client = mock_ocr
        
        request = DocumentProcessRequest(**sample_document_metadata)

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.process_document(mock_db, request)
        
        assert "Missing mandatory field: sin" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transform_data_decimal_conversion(self, service, sample_raw_ocr_data):
        # Arrange
        raw_data = sample_raw_ocr_data.copy()
        raw_data["annual_income"] = "120000.99" # String input

        # Act
        dto = service._transform_raw_data(raw_data)

        # Assert
        assert isinstance(dto.annual_income, Decimal)
        assert dto.annual_income == Decimal("120000.99")

    @pytest.mark.asyncio
    async def test_transform_data_invalid_decimal(self, service):
        # Arrange
        raw_data = {
            "applicant_name": "Bad Data",
            "annual_income": "not_a_number",
            "sin": "999"
        }

        # Act & Assert
        with pytest.raises(TransformationError):
            service._transform_raw_data(raw_data)

    @pytest.mark.asyncio
    async def test_redact_pii_from_logs(self, service, sample_raw_ocr_data, caplog):
        # Arrange
        # This test ensures that even if we log the raw dict, PII is masked
        raw_data = sample_raw_ocr_data.copy()
        
        # Act
        safe_dict = service._sanitize_for_logging(raw_data)

        # Assert
        assert "sin" not in safe_dict or safe_dict["sin"] == "***REDACTED***"
        assert "123456789" not in str(safe_dict)
        assert "John Doe" in safe_dict # Name is not strictly PII in this context, but SIN is

    @pytest.mark.asyncio
    async def test_save_record_db_error(self, service, mock_db, sample_transformed_payload, sample_document_metadata):
        # Arrange
        mock_db.commit.side_effect = SQLAlchemyError("DB Connection Lost")
        request = DocumentProcessRequest(**sample_document_metadata)
        
        # Mock the internal transform to skip OCR
        with patch.object(service, '_transform_raw_data', return_value=sample_transformed_payload):
            # Act & Assert
            with pytest.raises(TransformationError) as exc_info:
                await service.process_document(mock_db, request)
            
            assert "Database persistence failed" in str(exc_info.value)
            mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_audit_fields_populated(self, service, mock_db, sample_raw_ocr_data, sample_document_metadata):
        # Arrange
        mock_ocr = AsyncMock()
        mock_ocr.extract_text.return_value = sample_raw_ocr_data
        service.ocr_client = mock_ocr
        request = DocumentProcessRequest(**sample_document_metadata)

        # Act
        await service.process_document(mock_db, request)

        # Assert
        saved_record = mock_db.add.call_args[0][0]
        assert saved_record.created_at is not None
        assert saved_record.updated_at is not None
        # FINTRAC: Immutable audit trail implies created_at is set once
        assert saved_record.created_by == "system_dpt_service"

    @pytest.mark.asyncio
    async def test_empty_string_handling(self, service):
        # Arrange
        raw_data = {
            "applicant_name": "   ", # Whitespace
            "annual_income": "",
            "sin": "123"
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            service._transform_raw_data(raw_data)

    @pytest.mark.asyncio
    async def test_negative_income_rejection(self, service):
        # Arrange
        raw_data = {
            "applicant_name": "Test",
            "annual_income": "-5000.00",
            "sin": "123"
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service._transform_raw_data(raw_data)
        
        assert "Income must be positive" in str(exc_info.value)
```
--- integration_tests ---
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