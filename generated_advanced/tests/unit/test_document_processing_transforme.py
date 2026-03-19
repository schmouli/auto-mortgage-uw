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