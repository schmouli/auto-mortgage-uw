```python
import pytest
from unittest.mock import patch, MagicMock
from app.services.dpt_service import DocumentTransformer, DataNormalizer, DocumentClassifier
from app.exceptions import DocumentProcessingError, UnsupportedFileTypeError

# Module to test: app.services.dpt_service
# Assuming these classes exist in the service module

class TestDataNormalizer:
    """Tests for utility functions that clean and format extracted data."""

    def test_normalize_currency_string_valid_cad(self):
        """Test converting a string with dollar sign and commas to float."""
        raw = "$1,250.50"
        result = DataNormalizer.normalize_currency(raw)
        assert result == 1250.50

    def test_normalize_currency_string_simple(self):
        """Test converting a simple number string."""
        raw = "50000"
        result = DataNormalizer.normalize_currency(raw)
        assert result == 50000.00

    def test_normalize_currency_invalid_string(self):
        """Test handling of garbage string data."""
        raw = "N/A"
        with pytest.raises(ValueError):
            DataNormalizer.normalize_currency(raw)

    def test_format_sin_valid(self):
        """Test formatting a 9-digit number into Canadian SIN format."""
        raw_sin = "123456789"
        formatted = DataNormalizer.format_sin(raw_sin)
        assert formatted == "123-456-789"

    def test_format_sin_already_formatted(self):
        """Test that an already formatted SIN is not double-formatted."""
        raw_sin = "123-456-789"
        formatted = DataNormalizer.format_sin(raw_sin)
        assert formatted == "123-456-789"

    def test_parse_date_american_vs_canadian(self):
        """Test resolving ambiguous dates (04/05/2023). Should default to DD/MM/YYYY for CA."""
        raw_date = "04/05/2023"
        parsed = DataNormalizer.parse_date(raw_date, region="CA")
        assert parsed.day == 4
        assert parsed.month == 5


class TestDocumentClassifier:
    """Tests for logic that determines document type (T4, Paystub, etc.)."""

    def test_classify_t4_slip(self):
        """Test identifying a T4 slip based on keywords."""
        text_content = "Employment Income, CPP Contributions, Box 14"
        doc_type = DocumentClassifier.identify_type(text_content)
        assert doc_type == "T4"

    def test_classify_paystub(self):
        """Test identifying a Paystub based on keywords."""
        text_content = "YTD Gross Pay, Current Pay Period, Deductions"
        doc_type = DocumentClassifier.identify_type(text_content)
        assert doc_type == "PAYSTUB"

    def test_classify_bank_statement(self):
        """Test identifying a Bank Statement."""
        text_content = "Account Summary, RBC Royal Bank, Closing Balance"
        doc_type = DocumentClassifier.identify_type(text_content)
        assert doc_type == "BANK_STATEMENT"

    def test_classify_unknown_document(self):
        """Test handling of document with no known keywords."""
        text_content = "This is a random letter with no financial keywords."
        with pytest.raises(UnsupportedFileTypeError):
            DocumentClassifier.identify_type(text_content)

    def test_classify_empty_string(self):
        """Test handling of empty input."""
        with pytest.raises(ValueError):
            DocumentClassifier.identify_type("")


class TestDocumentTransformer:
    """Tests for the main service orchestration."""

    @patch("app.services.dpt_service.OCRClient")
    def test_transform_document_success_happy_path(self, mock_ocr, sample_t4_pdf_content, sample_mortgage_app_json):
        """Test end-to-end transformation of a valid PDF."""
        # Setup mock
        mock_ocr_instance = MagicMock()
        mock_ocr.return_value = mock_ocr_instance
        mock_ocr_instance.extract.return_value = sample_mortgage_app_json

        transformer = DocumentTransformer(ocr_client=mock_ocr_instance)
        result = transformer.transform(sample_t4_pdf_content, "application/pdf")

        assert result.status == "COMPLETED"
        assert result.data["annual_income"] == 85000.00
        assert result.doc_type == "T4"
        mock_ocr_instance.extract.assert_called_once()

    @patch("app.services.dpt_service.OCRClient")
    def test_transform_document_ocr_failure(self, mock_ocr, sample_t4_pdf_content):
        """Test handling when the external OCR service fails."""
        mock_ocr_instance = MagicMock()
        mock_ocr.return_value = mock_ocr_instance
        mock_ocr_instance.extract.side_effect = Exception("OCR Service Timeout")

        transformer = DocumentTransformer(ocr_client=mock_ocr_instance)
        
        with pytest.raises(DocumentProcessingError):
            transformer.transform(sample_t4_pdf_content, "application/pdf")

    @patch("app.services.dpt_service.OCRClient")
    def test_transform_document_missing_critical_field(self, mock_ocr, sample_t4_pdf_content):
        """Test validation failure when required fields (SIN) are missing."""
        incomplete_data = {
            "applicant_name": "Jane Doe",
            "annual_income": 60000,
            # Missing SIN
        }
        
        mock_ocr_instance = MagicMock()
        mock_ocr.return_value = mock_ocr_instance
        mock_ocr_instance.extract.return_value = incomplete_data

        transformer = DocumentTransformer(ocr_client=mock_ocr_instance)
        
        # Assuming the transformer validates schema
        with pytest.raises(DocumentProcessingError, match="Missing required field: sin"):
            transformer.transform(sample_t4_pdf_content, "application/pdf")

    @patch("app.services.dpt_service.OCRClient")
    def test_transform_unsupported_mime_type(self, mock_ocr, sample_invalid_file_content):
        """Test rejection of unsupported file types (e.g., .exe)."""
        transformer = DocumentTransformer(ocr_client=mock_ocr)
        
        with pytest.raises(UnsupportedFileTypeError):
            transformer.transform(sample_invalid_file_content, "application/x-msdownload")

    @patch("app.services.dpt_service.OCRClient")
    def test_transform_data_normalization_integration(self, mock_ocr, sample_t4_pdf_content):
        """Test that raw data is normalized during transformation."""
        raw_data = {
            "applicant_name": "  Alice Smith  ", # Whitespace
            "sin": "987654321", # Needs formatting
            "annual_income": "$ 70,000.00", # Currency string
            "document_type": "PAYSTUB"
        }

        mock_ocr_instance = MagicMock()
        mock_ocr.return_value = mock_ocr_instance
        mock_ocr_instance.extract.return_value = raw_data

        transformer = DocumentTransformer(ocr_client=mock_ocr_instance)
        result = transformer.transform(sample_t4_pdf_content, "application/pdf")

        assert result.data["sin"] == "987-654-321"
        assert result.data["annual_income"] == 70000.00
        assert result.data["applicant_name"] == "Alice Smith"

```