```python
import pytest
from unittest.mock import Mock, patch
from decimal import Decimal

# Assuming these imports from the business logic layer
from app.services.intake_service import (
    calculate_gds, 
    calculate_tds, 
    validate_sin, 
    determine_eligibility,
    process_intake_form
)
from app.schemas.application import ApplicationStatus
from app.exceptions import InvalidSinError, IncomeValidationError

class TestFinancialCalculations:
    """
    Unit tests for financial ratio calculations (GDS/TDS).
    Critical for Canadian mortgage underwriting.
    """

    def test_calculate_gds_happy_path(self):
        """
        Test Gross Debt Service ratio calculation.
        Formula: (Mortgage + Tax + Heat) / Annual Income
        """
        # Monthly mortgage payment approx: (600k loan @ 5% for 25yrs) ~ $3500
        monthly_mortgage = Decimal("3500.00")
        monthly_tax = Decimal("250.00")
        monthly_heat = Decimal("150.00")
        annual_income = Decimal("120000.00")

        gds = calculate_gds(monthly_mortgage, monthly_tax, monthly_heat, annual_income)
        
        expected_numerator = (3500 + 250 + 150) * 12 # 46800
        expected_gds = expected_numerator / 120000 # 0.39 (39%)
        
        assert abs(gds - Decimal("0.39")) < Decimal("0.01")

    def test_calculate_tds_happy_path(self):
        """
        Test Total Debt Service ratio calculation.
        Formula: (Mortgage + Tax + Heat + Other Debts) / Annual Income
        """
        monthly_mortgage = Decimal("3500.00")
        monthly_tax = Decimal("250.00")
        monthly_heat = Decimal("150.00")
        monthly_debts = Decimal("500.00")
        annual_income = Decimal("120000.00")

        tds = calculate_tds(monthly_mortgage, monthly_tax, monthly_heat, monthly_debts, annual_income)
        
        expected_numerator = (3500 + 250 + 150 + 500) * 12 # 52800
        expected_tds = expected_numerator / 120000 # 0.44 (44%)
        
        assert abs(tds - Decimal("0.44")) < Decimal("0.01")

    def test_calculations_zero_income_raises_error(self):
        """
        Test that division by zero is handled gracefully for income.
        """
        with pytest.raises(IncomeValidationError):
            calculate_gds(100, 100, 100, 0)
        
        with pytest.raises(IncomeValidationError):
            calculate_tds(100, 100, 100, 100, 0)

    def test_calculations_negative_values(self):
        """
        Ensure negative inputs don't result in negative ratios (logic check).
        """
        with pytest.raises(ValueError):
            calculate_gds(-100, 100, 100, 1000)

class TestSinValidation:
    """
    Unit tests for Social Insurance Number (SIN) validation.
    Uses Luhn algorithm validation logic.
    """

    def test_valid_sin_format(self):
        valid_sin = "046454286"
        assert validate_sin(valid_sin) is True

    def test_invalid_sin_checksum(self):
        # Correct format, fails Luhn check
        invalid_sin = "046454287"
        with pytest.raises(InvalidSinError):
            validate_sin(invalid_sin)

    def test_sin_non_numeric(self):
        with pytest.raises(InvalidSinError):
            validate_sin("ABCDEFGHIJ")

    def test_sin_wrong_length(self):
        with pytest.raises(InvalidSinError):
            validate_sin("123456")
        
        with pytest.raises(InvalidSinError):
            validate_sin("1234567890123")


class TestEligibilityLogic:
    """
    Unit tests for business rules regarding application eligibility.
    """

    @patch('app.services.intake_service.get_credit_score')
    def test_eligibility_approved(self, mock_credit_score):
        """
        Scenario: High credit score, GDS < 32%, TDS < 40%.
        Expected: Approved.
        """
        mock_credit_score.return_value = 750
        
        gds = Decimal("0.30")
        tds = Decimal("0.35")
        client_id = 1
        
        status = determine_eligibility(client_id, gds, tds)
        assert status == ApplicationStatus.APPROVED

    @patch('app.services.intake_service.get_credit_score')
    def test_eligibility_rejected_low_credit(self, mock_credit_score):
        """
        Scenario: Credit score too low (below 600).
        Expected: Rejected regardless of ratios.
        """
        mock_credit_score.return_value = 550
        
        gds = Decimal("0.20")
        tds = Decimal("0.25")
        client_id = 1
        
        status = determine_eligibility(client_id, gds, tds)
        assert status == ApplicationStatus.REJECTED

    @patch('app.services.intake_service.get_credit_score')
    def test_eligibility_rejected_high_tds(self, mock_credit_score):
        """
        Scenario: Good credit, but TDS > 42% (Strict limit).
        Expected: Referred or Rejected.
        """
        mock_credit_score.return_value = 700
        
        gds = Decimal("0.30")
        tds = Decimal("0.45") # Too high
        client_id = 1
        
        status = determine_eligibility(client_id, gds, tds)
        assert status == ApplicationStatus.REFER

class TestIntakeProcessing:
    """
    Unit tests for the orchestration service that processes the form.
    """

    @patch('app.services.intake_service.determine_eligibility')
    @patch('app.services.intake_service.calculate_tds')
    @patch('app.services.intake_service.calculate_gds')
    @patch('app.services.intake_service.validate_sin')
    def test_process_intake_success_flow(
        self, mock_sin, mock_gds, mock_tds, mock_eligibility
    ):
        """
        Test the happy path of the service layer processing valid data.
        """
        mock_sin.return_value = True
        mock_gds.return_value = Decimal("0.30")
        mock_tds.return_value = Decimal("0.35")
        mock_eligibility.return_value = ApplicationStatus.APPROVED

        payload = {
            "sin": "123456789",
            "income": 100000,
            "mortgage": 2000,
            "tax": 200,
            "heat": 100,
            "debts": 0
        }

        # Mock DB repo
        mock_repo = Mock()
        mock_repo.create.return_value = Mock(id=1)

        result = process_intake_form(payload, mock_repo)
        
        mock_sin.assert_called_once_with("123456789")
        mock_gds.assert_called_once()
        mock_eligibility.assert_called_once()
        mock_repo.create.assert_called_once()
        assert result.status == ApplicationStatus.APPROVED

    @patch('app.services.intake_service.validate_sin')
    def test_process_intake_invalid_sin_stops_execution(self, mock_sin):
        """
        Test that invalid SIN prevents database writes.
        """
        mock_sin.side_effect = InvalidSinError("Bad SIN")
        mock_repo = Mock()

        payload = {"sin": "000", "income": 0}

        with pytest.raises(InvalidSinError):
            process_intake_form(payload, mock_repo)
            
        mock_repo.create.assert_not_called()
```