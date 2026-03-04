```python
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from onlendhub.engine import UnderwritingEngine
from onlendhub.exceptions import UnderwritingError
from onlendhub.models import DecisionEnum

# Test Configuration Constants
MAX_LTV_INSURABLE = Decimal("0.80")  # 80%
MIN_CREDIT_SCORE = 600
MAX_GDS = Decimal("0.39")  # 39%
MAX_TDS = Decimal("0.44")  # 44%

class TestUnderwritingCalculations:
    """Unit tests for mathematical calculations within the engine."""

    def test_calculate_ltv_happy_path(self):
        engine = UnderwritingEngine()
        # Loan 400k, Value 500k = 80%
        ltv = engine._calculate_ltv(Decimal("400000"), Decimal("500000"))
        assert ltv == Decimal("0.80")

    def test_calculate_ltv_high_ratio(self):
        engine = UnderwritingEngine()
        # Loan 450k, Value 500k = 90%
        ltv = engine._calculate_ltv(Decimal("450000"), Decimal("500000"))
        assert ltv == Decimal("0.90")
        assert ltv > MAX_LTV_INSURABLE

    def test_calculate_ltv_zero_value_error(self):
        engine = UnderwritingEngine()
        with pytest.raises(UnderwritingError):
            engine._calculate_ltv(Decimal("100000"), Decimal("0"))

    def test_calculate_gds_within_limits(self):
        engine = UnderwritingEngine()
        # Mortgage: 2000/mo, Tax: 300/mo, Heat: 150/mo. Income: 6500/mo
        # (2000 + 300 + 150) / 6500 = ~38.4%
        gds = engine._calculate_gds(
            mortgage_payment=Decimal("2000"),
            property_tax=Decimal("300"),
            heating=Decimal("150"),
            income=Decimal("6500")
        )
        assert gds <= MAX_GDS
        assert gds == Decimal("0.384615").quantize(Decimal("0.000001"))

    def test_calculate_gds_exceeds_limit(self):
        engine = UnderwritingEngine()
        gds = engine._calculate_gds(
            mortgage_payment=Decimal("3000"),
            property_tax=Decimal("500"),
            heating=Decimal("200"),
            income=Decimal("6500")
        )
        assert gds > MAX_GDS

    def test_calculate_tds_within_limits(self):
        engine = UnderwritingEngine()
        # GDS components (2450) + Other Debts (500) / Income (6500)
        tds = engine._calculate_tds(
            housing_costs=Decimal("2450"),
            other_debts=Decimal("500"),
            income=Decimal("6500")
        )
        assert tds <= MAX_TDS

    def test_calculate_tds_exceeds_limit(self):
        engine = UnderwritingEngine()
        tds = engine._calculate_tds(
            housing_costs=Decimal("2450"),
            other_debts=Decimal("2000"),
            income=Decimal("6500")
        )
        assert tds > MAX_TDS

class TestUnderwritingLogic:
    """Unit tests for decision logic and rules."""

    def test_evaluate_credit_score_approval(self):
        engine = UnderwritingEngine()
        result = engine._evaluate_credit(720)
        assert result == DecisionEnum.APPROVED

    def test_evaluate_credit_score_rejection(self):
        engine = UnderwritingEngine()
        result = engine._evaluate_credit(550)
        assert result == DecisionEnum.REJECTED

    def test_evaluate_credit_score_boundary(self):
        engine = UnderwritingEngine()
        # Test exactly on the boundary
        result = engine._evaluate_credit(600)
        # Assuming 600 is the floor for approval
        assert result in [DecisionEnum.APPROVED, DecisionEnum.REFER]

    @patch('onlendhub.engine.UnderwritingEngine._calculate_ltv')
    @patch('onlendhub.engine.UnderwritingEngine._calculate_gds')
    @patch('onlendhub.engine.UnderwritingEngine._calculate_tds')
    def test_decision_matrix_perfect_candidate(self, mock_tds, mock_gds, mock_ltv):
        """Test a candidate that passes all metrics."""
        engine = UnderwritingEngine()
        mock_ltv.return_value = Decimal("0.75")
        mock_gds.return_value = Decimal("0.30")
        mock_tds.return_value = Decimal("0.35")

        decision = engine._apply_rules(
            ltv=Decimal("0.75"),
            gds=Decimal("0.30"),
            tds=Decimal("0.35"),
            credit_score=750
        )
        assert decision == DecisionEnum.APPROVED

    @patch('onlendhub.engine.UnderwritingEngine._calculate_ltv')
    def test_insurance_requirement_detection(self, mock_ltv):
        engine = UnderwritingEngine()
        mock_ltv.return_value = Decimal("0.85")
        
        is_required = engine._check_insurance_required(ltv=Decimal("0.85"))
        assert is_required is True

    @patch('onlendhub.engine.UnderwritingEngine._calculate_ltv')
    def test_insurance_not_required_conventional(self, mock_ltv):
        engine = UnderwritingEngine()
        mock_ltv.return_value = Decimal("0.80")
        
        is_required = engine._check_insurance_required(ltv=Decimal("0.80"))
        assert is_required is False

    def test_process_application_missing_field(self):
        engine = UnderwritingEngine()
        incomplete_data = {
            "loan_amount": 100000,
            # Missing property_value
        }
        with pytest.raises(KeyError):
            engine.process(incomplete_data)

    def test_process_application_negative_income(self):
        engine = UnderwritingEngine()
        with pytest.raises(UnderwritingError):
            engine._validate_income(Decimal("-50000"))

    def test_process_application_zero_downpayment(self):
        engine = UnderwritingEngine()
        # In Canada, 0% down is generally not allowed for standard residential
        with pytest.raises(UnderwritingError):
            engine._validate_downpayment(loan=Decimal("400000"), down=Decimal("0"))

    @patch('onlendhub.services.credit_bureau.CreditBureauClient')
    def test_integration_with_credit_bureau_mock(self, mock_client_class):
        engine = UnderwritingEngine()
        mock_instance = MagicMock()
        mock_instance.get_score.return_value = 680
        mock_client_class.return_value = mock_instance

        score = engine._get_external_credit_score("sin_123")
        assert score == 680
        mock_instance.get_score.assert_called_once_with("sin_123")

    def test_amortization_limit_validation(self):
        engine = UnderwritingEngine()
        # Canada max amortization is usually 25y (insured) or 30y (uninsured)
        # Testing strict 25 year limit for this engine
        is_valid = engine._validate_amortization(30)
        assert is_valid is False
        
        is_valid = engine._validate_amortization(25)
        assert is_valid is True

    def test_calculate_monthly_mortgage_payment(self):
        engine = UnderwritingEngine()
        # Principal 300k, Rate 5%, 25 years (300 months)
        # M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # i = 0.05/12 = 0.004166
        payment = engine._calculate_payment(
            principal=Decimal("300000"), 
            annual_rate=Decimal("0.05"), 
            months=300
        )
        # Rough check
        assert payment > Decimal("1500") and payment < Decimal("2000")
```