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