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