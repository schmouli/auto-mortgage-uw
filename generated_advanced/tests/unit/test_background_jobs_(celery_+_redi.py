```python
import pytest
from unittest.mock import patch, call, MagicMock
from app.tasks import credit_tasks, risk_tasks
from app.core.exceptions import ExternalServiceError
from app.models.schemas import ApplicationStatus

# Module to test: Background Tasks Logic (Celery functions executed synchronously for testing)

class TestCreditCheckTask:
    """
    Unit tests for the Celery task: process_credit_check
    """

    @patch("app.tasks.credit_tasks.update_application_status")
    @patch("app.tasks.credit_tasks.BureauAPI")
    @patch("app.tasks.credit_tasks.get_db")
    def test_process_credit_check_happy_path(
        self, mock_get_db, mock_bureau_api, mock_update_status, sample_application_data
    ):
        """
        Test successful credit check flow.
        Scenario: API returns score, DB is updated, status moves to REVIEW.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_bureau_instance = mock_bureau_api.return_value
        mock_bureau_instance.get_score.return_value = 750
        
        mock_app = MagicMock()
        mock_app.id = sample_application_data["id"]
        mock_app.applicant_id = sample_application_data["applicant_id"]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app

        # Act
        result = credit_tasks.process_credit_check(application_id=1)

        # Assert
        assert result["status"] == "success"
        assert result["score"] == 750
        mock_bureau_instance.get_score.assert_called_once_with(sin="100-200-300", province="ON")
        assert mock_app.credit_score == 750
        mock_update_status.assert_called_once_with(
            db=mock_db, 
            app_id=1, 
            status=ApplicationStatus.UNDERWRITING_REVIEW
        )
        # Multiple assertions on state
        assert mock_db.commit.call_count == 1
        assert mock_db.refresh.call_count >= 1

    @patch("app.tasks.credit_tasks.BureauAPI")
    @patch("app.tasks.credit_tasks.get_db")
    def test_process_credit_check_api_failure(
        self, mock_get_db, mock_bureau_api, sample_application_data
    ):
        """
        Test handling of external API failure.
        Scenario: Bureau API times out or returns 500.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_bureau_api.return_value.get_score.side_effect = ExternalServiceError("Service Unavailable")
        
        mock_app = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app

        # Act & Assert
        with pytest.raises(ExternalServiceError):
            credit_tasks.process_credit_check(application_id=1)
        
        # Verify transaction rollback
        mock_db.rollback.assert_called_once()
        assert mock_db.commit.call_count == 0

    @patch("app.tasks.credit_tasks.BureauAPI")
    @patch("app.tasks.credit_tasks.get_db")
    def test_process_credit_check_application_not_found(
        self, mock_get_db, mock_bureau_api
    ):
        """
        Test behavior when Application ID does not exist.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Application not found"):
            credit_tasks.process_credit_check(application_id=999)

        # Verify external API was NOT called
        mock_bureau_api.return_value.get_score.assert_not_called()


class TestRiskAssessmentTask:
    """
    Unit tests for the Celery task: calculate_debt_service_ratios
    """

    @patch("app.tasks.risk_tasks.logger")
    @patch("app.tasks.risk_tasks.update_application_status")
    @patch("app.tasks.risk_tasks.get_db")
    def test_calculate_ratios_approval_path(
        self, mock_get_db, mock_update_status, mock_logger
    ):
        """
        Test LTV and TDS calculations resulting in approval.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_app = MagicMock()
        mock_app.id = 1
        mock_app.loan_amount = 400000
        mock_app.property_value = 500000  # 80% LTV
        mock_app.annual_income = 120000
        mock_app.annual_property_tax = 3000
        mock_app.annual_heating = 1200
        mock_app.monthly_debt_payments = 1000 # $12,000/year
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app

        # Act
        result = risk_tasks.calculate_debt_service_ratios(application_id=1)

        # Assert
        assert result["ltv"] == 0.8
        # TDS = (Mortgage_Pmt + Tax + Heat + Debts) / Income
        # Assuming 20yr @ 5% approx $31,600/yr mortgage
        # (31600 + 3000 + 1200 + 12000) / 120000 ~= 39.8%
        assert "tds" in result
        assert result["tds"] < 0.40 # Validating logic
        
        # Check status update logic (assuming < 40% TDS is auto-approve for this tier)
        mock_update_status.assert_called_once()
        status_arg = mock_update_status.call_args[1]['status']
        assert status_arg == ApplicationStatus.APPROVED

    @patch("app.tasks.risk_tasks.update_application_status")
    @patch("app.tasks.risk_tasks.get_db")
    def test_calculate_ratios_high_risk_rejection(
        self, mock_get_db, mock_update_status
    ):
        """
        Test high LTV and high TDS resulting in referral/rejection.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_app = MagicMock()
        mock_app.id = 2
        mock_app.loan_amount = 475000 # 95% LTV
        mock_app.property_value = 500000 
        mock_app.annual_income = 50000
        mock_app.annual_property_tax = 4000
        mock_app.annual_heating = 1500
        mock_app.monthly_debt_payments = 2000 # $24,000/year
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app

        # Act
        result = risk_tasks.calculate_debt_service_ratios(application_id=2)

        # Assert
        assert result["ltv"] > 0.90
        assert result["tds"] > 0.50 # Very high risk
        mock_update_status.assert_called_with(
            db=mock_db, 
            app_id=2, 
            status=ApplicationStatus.MANUAL_REVIEW
        )

    @patch("app.tasks.risk_tasks.get_db")
    def test_calculate_ratios_zero_income_handling(self, mock_get_db):
        """
        Test division by zero safety or edge case handling.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_app = MagicMock()
        mock_app.annual_income = 0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app

        # Act & Assert
        with pytest.raises(ZeroDivisionError) or pytest.raises(ValueError):
             risk_tasks.calculate_debt_service_ratios(application_id=3)
        
        # Ensure DB was not committed on error
        mock_db.commit.assert_not_called()

class TestDocumentProcessingTask:
    """
    Unit tests for OCR/PDF processing tasks.
    """
    
    @patch("app.tasks.doc_tasks.extract_text_from_pdf")
    @patch("app.tasks.doc_tasks.get_db")
    def test_process_employment_letter_success(self, mock_get_db, mock_ocr):
        """
        Test successful parsing of employment letter.
        """
        # Arrange
        mock_ocr.return_value = "Annual Salary: $85,000 Start Date: 2020-01-01"
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_doc = MagicMock()
        mock_doc.id = 55
        mock_doc.type = "EMPLOYMENT_LETTER"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_doc

        # Act
        result = doc_tasks.process_document(document_id=55)

        # Assert
        assert result["parsed_salary"] == 85000
        assert result["status"] == "VERIFIED"
        mock_ocr.assert_called_once()
        assert mock_doc.processed_at is not None

    @patch("app.tasks.doc_tasks.extract_text_from_pdf")
    @patch("app.tasks.doc_tasks.get_db")
    def test_process_document_corrupted_file(self, mock_get_db, mock_ocr):
        """
        Test handling of corrupted PDF where OCR fails.
        """
        # Arrange
        mock_ocr.side_effect = IOError("File corrupted")
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_doc = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_doc

        # Act
        result = doc_tasks.process_document(document_id=56)

        # Assert
        assert result["status"] == "FAILED"
        assert "error" in result
        # Verify retry logic or error logging was triggered (conceptual)
        assert mock_db.commit.called # Error status saved
```