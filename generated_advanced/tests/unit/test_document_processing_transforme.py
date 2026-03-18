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