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