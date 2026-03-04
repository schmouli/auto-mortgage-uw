```python
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from app.testing_suite import underwriting_logic, calculations, validators

# Module: app.testing_suite.calculations

class TestCalculations:
    """
    Unit tests for financial calculation functions.
    """
    def test_calculate_gds_happy_path(self):
        """
        Test Gross Debt Service ratio calculation.
        GDS = (Mortgage Tax + Heat + Condo Fees) / Annual Income
        """
        # Scenario: Monthly costs = $2500, Annual Income = $100,000
        monthly_costs = Decimal('2500.00')
        annual_income = Decimal('100000.00')
        
        expected_gds = (monthly_costs * 12) / annual_income
        result = calculations.calculate_gds(monthly_costs, annual_income)
        
        assert result == pytest.approx(float(expected_gds), rel=1e-3)
        assert result < 0.39  # Standard Canadian threshold check

    def test_calculate_tds_happy_path(self):
        """
        Test Total Debt Service ratio calculation.
        TDS = (Housing Costs + Other Debts) / Annual Income
        """
        monthly_housing = Decimal('2000.00')
        other_debts = Decimal('500.00')
        annual_income = Decimal('80000.00')
        
        expected_tds = ((monthly_housing + other_debts) * 12) / annual_income
        result = calculations.calculate_tds(monthly_housing, other_debts, annual_income)
        
        assert result == pytest.approx(float(expected_tds), rel=1e-3)
        assert 0.0 < result < 1.0

    def test_calculate_loan_to_value(self):
        """
        Test LTV calculation.
        LTV = Loan Amount / Property Value
        """
        loan_amount = Decimal('400000.00')
        property_value = Decimal('500000.00')
        
        result = calculations.calculate_ltv(loan_amount, property_value)
        
        assert result == 0.80
        assert isinstance(result, float)

    def test_zero_income_handling(self):
        """
        Test that division by zero is handled gracefully in GDS calculation.
        """
        with pytest.raises(ValueError) as exc_info:
            calculations.calculate_gds(Decimal('2000.00'), Decimal('0.00'))
        assert "Income cannot be zero" in str(exc_info.value)

    def test_negative_debt_handling(self):
        """
        Test handling of negative debt inputs (invalid scenario).
        """
        with pytest.raises(ValueError):
            calculations.calculate_tds(Decimal('2000.00'), Decimal('-500.00'), Decimal('50000.00'))

# Module: app.testing_suite.validators

class TestValidators:
    """
    Unit tests for validation logic.
    """
    def test_validate_credit_score_success(self):
        """
        Test validation for acceptable credit score.
        """
        score = 720
        is_valid = validators.validate_credit_score(score)
        assert is_valid is True

    def test_validate_credit_score_failure_low(self):
        """
        Test validation for credit score below minimum (e.g., < 600).
        """
        score = 550
        is_valid = validators.validate_credit_score(score)
        assert is_valid is False

    def test_validate_borrower_age(self):
        """
        Test age of majority rule (18 in Canada).
        """
        assert validators.validate_age(25, "ON") is True
        assert validators.validate_age(17, "ON") is False
        assert validators.validate_age(18, "AB") is True

    def test_validate_down_payment_minimum(self):
        """
        Test minimum down payment rules (5% for first 500k, 10% for remainder).
        """
        purchase_price = 600000
        min_down = 30000 # 5% of 500k + 10% of 100k
        
        # Valid down payment
        assert validators.validate_down_payment(purchase_price, 35000) is True
        # Invalid down payment
        assert validators.validate_down_payment(purchase_price, 20000) is False

# Module: app.testing_suite.underwriting_logic

class TestUnderwritingLogic:
    """
    Unit tests for the main decision engine.
    """
    @patch('app.testing_suite.validators.validate_credit_score')
    @patch('app.testing_suite.calculations.calculate_gds')
    @patch('app.testing_suite.calculations.calculate_tds')
    def test_decision_engine_approved(
        self, mock_tds, mock_gds, mock_credit
    ):
        """
        Test happy path for application approval.
        """
        # Setup mocks
        mock_credit.return_value = True
        mock_gds.return_value = 0.30 # < 0.39
        mock_tds.return_value = 0.35 # < 0.44
        
        application_data = MagicMock()
        application_data.income = 100000
        application_data.loan_amount = 300000
        
        decision = underwriting_logic.make_decision(application_data)
        
        assert decision['status'] == 'APPROVED'
        assert decision['rate'] is not None
        mock_credit.assert_called_once()
        mock_gds.assert_called_once()
        mock_tds.assert_called_once()

    @patch('app.testing_suite.validators.validate_credit_score')
    def test_decision_engine_declined_credit(self, mock_credit):
        """
        Test decline path due to bad credit.
        """
        mock_credit.return_value = False
        
        application_data = MagicMock()
        decision = underwriting_logic.make_decision(application_data)
        
        assert decision['status'] == 'DECLINED'
        assert 'Credit score' in decision['reason']

    @patch('app.testing_suite.validators.validate_credit_score')
    @patch('app.testing_suite.calculations.calculate_tds')
    def test_decision_engine_declined_tds(self, mock_tds, mock_credit):
        """
        Test decline path due to high TDS.
        """
        mock_credit.return_value = True
        mock_tds.return_value = 0.50 # > 0.44 threshold
        
        application_data = MagicMock()
        decision = underwriting_logic.make_decision(application_data)
        
        assert decision['status'] == 'DECLINED'
        assert 'TDS' in decision['reason']

    def test_stress_test_calculation(self):
        """
        Test the mortgage stress test logic (Benchmark rate + 2%).
        """
        contract_rate = 0.045 # 4.5%
        benchmark_rate = 0.055 # 5.5%
        
        qualifying_rate = underwriting_logic.determine_qualifying_rate(contract_rate, benchmark_rate)
        
        # Should be the higher of (Contract + 2%) or Benchmark
        # Contract + 2% = 6.5%
        # Benchmark = 5.5%
        assert qualifying_rate == 0.065
```