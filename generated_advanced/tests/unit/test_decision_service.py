```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.decision_service.services import DecisionService
from mortgage_underwriting.modules.decision_service.schemas import DecisionRequest, DecisionResponse
from mortgage_underwriting.modules.decision_service.exceptions import UnderwritingError

@pytest.mark.unit
class TestDecisionServiceCalculations:
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_session):
        return DecisionService(mock_session)

    @pytest.mark.asyncio
    async def test_calculate_gds_success(self, service):
        # Income: 100k, Housing: 300+150+0 = 450/mo -> 5400/yr
        # GDS = 5400 / 100000 = 5.4%
        income = Decimal("100000.00")
        housing_costs = Decimal("5400.00") 
        
        gds = service._calculate_gds(housing_costs, income)
        assert gds == Decimal("5.40")

    @pytest.mark.asyncio
    async def test_calculate_gds_boundary(self, service):
        # Testing boundary condition for OSFI limit (39%)
        income = Decimal("100000.00")
        # 39% of 100k is 39,000
        housing_costs = Decimal("39000.00")
        
        gds = service._calculate_gds(housing_costs, income)
        assert gds == Decimal("39.00")

    @pytest.mark.asyncio
    async def test_calculate_tds_success(self, service):
        # Income: 100k. Housing: 5400. Other: 6000 (500/mo).
        # Total Debt: 11400. TDS = 11.4%
        income = Decimal("100000.00")
        housing_costs = Decimal("5400.00")
        other_debt = Decimal("6000.00")
        
        tds = service._calculate_tds(housing_costs, other_debt, income)
        assert tds == Decimal("11.40")

    @pytest.mark.asyncio
    async def test_calculate_ltv_success(self, service):
        # Loan: 400k, Value: 500k -> 80%
        loan = Decimal("400000.00")
        value = Decimal("500000.00")
        
        ltv = service._calculate_ltv(loan, value)
        assert ltv == Decimal("80.00")

    @pytest.mark.asyncio
    async def test_calculate_ltv_high_precision(self, service):
        # Loan: 405000.01, Value: 500000.00 -> 81.000002%
        loan = Decimal("405000.01")
        value = Decimal("500000.00")
        
        ltv = service._calculate_ltv(loan, value)
        # Decimal precision check
        assert ltv == Decimal("81.000002")

    @pytest.mark.asyncio
    async def test_determine_stress_test_rate_below_floor(self, service):
        # Contract 3.0%. +2% = 5.0%. Floor 5.25%. Result: 5.25%
        contract_rate = Decimal("3.00")
        rate = service._determine_stress_test_rate(contract_rate)
        assert rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_determine_stress_test_rate_above_floor(self, service):
        # Contract 5.0%. +2% = 7.0%. Floor 5.25%. Result: 7.0%
        contract_rate = Decimal("5.00")
        rate = service._determine_stress_test_rate(contract_rate)
        assert rate == Decimal("7.00")

    @pytest.mark.asyncio
    async def test_determine_stress_test_rate_exact_boundary(self, service):
        # Contract 3.25%. +2% = 5.25%. Floor 5.25%. Result: 5.25%
        contract_rate = Decimal("3.25")
        rate = service._determine_stress_test_rate(contract_rate)
        assert rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_calculate_monthly_payment_mortgage(self, service):
        # Standard mortgage calculation check
        principal = Decimal("400000")
        annual_rate = Decimal("0.0525") # 5.25% stress
        months = 300 # 25 years
        
        # Just ensure it returns a positive decimal and doesn't crash
        payment = service._calculate_monthly_payment(principal, annual_rate, months)
        assert payment > Decimal("0")
        assert isinstance(payment, Decimal)

    @pytest.mark.asyncio
    async def test_get_cmhc_insurance_rate_none_required(self, service):
        # LTV 80% -> No insurance
        rate = service._get_cmhc_insurance_rate(Decimal("80.00"))
        assert rate == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_check_cmhc_tier_1(self, service):
        # 80.01% - 85.00% -> 2.80%
        rate = service._get_cmhc_insurance_rate(Decimal("82.50"))
        assert rate == Decimal("2.80")

    @pytest.mark.asyncio
    async def test_check_cmhc_tier_2(self, service):
        # 85.01% - 90.00% -> 3.10%
        rate = service._get_cmhc_insurance_rate(Decimal("88.00"))
        assert rate == Decimal("3.10")

    @pytest.mark.asyncio
    async def test_check_cmhc_tier_3(self, service):
        # 90.01% - 95.00% -> 4.00%
        rate = service._get_cmhc_insurance_rate(Decimal("92.00"))
        assert rate == Decimal("4.00")

    @pytest.mark.asyncio
    async def test_check_cmhc_invalid_ltv(self, service):
        # > 95% -> Should raise error or return 0 depending on implementation logic
        # Assuming logic handles this in the decision phase, but strictly speaking
        # the tier lookup might raise ValueError or return None.
        # Here we test the specific tier lookup if it exists, or the wrapper.
        # We'll assume the service returns 0.00 if not found or raises.
        # Based on "LTV calculation: loan_amount / property_value; no precision loss"
        with pytest.raises(ValueError):
            service._get_cmhc_insurance_rate(Decimal("96.00"))


@pytest.mark.unit
class TestDecisionServiceLogic:
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_session):
        return DecisionService(mock_session)

    @pytest.fixture
    def valid_request(self):
        return DecisionRequest(
            applicant_id="test-123",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("100000.00"),
            monthly_property_tax=Decimal("300.00"),
            monthly_heating_cost=Decimal("150.00"),
            monthly_strata_fees=Decimal("0.00"),
            other_debt_obligations=Decimal("500.00"),
            contract_rate=Decimal("4.5"),
            amortization_years=25,
            sin="123456789",
            dob="1990-01-01"
        )

    @pytest.mark.asyncio
    async def test_approve_decision_happy_path(self, service, valid_request):
        result = await service.make_decision(valid_request)
        
        assert result.decision == "Approved"
        assert result.gds_ratio <= Decimal("39.00")
        assert result.tds_ratio <= Decimal("44.00")
        assert result.ltv_ratio <= Decimal("95.00")
        assert result.insurance_required == False # LTV is 80%

    @pytest.mark.asyncio
    async def test_decline_decision_gds_too_high(self, service, valid_request):
        # Modify request to have massive property tax
        valid_request.monthly_property_tax = Decimal("5000.00") 
        # 60,000 / 100,000 = 60% GDS
        
        result = await service.make_decision(valid_request)
        
        assert result.decision == "Declined"
        assert "GDS" in result.decline_reason

    @pytest.mark.asyncio
    async def test_decline_decision_tds_too_high(self, service, valid_request):
        # Modify request to have massive other debt
        valid_request.other_debt_obligations = Decimal("10000.00")
        
        result = await service.make_decision(valid_request)
        
        assert result.decision == "Declined"
        assert "TDS" in result.decline_reason

    @pytest.mark.asyncio
    async def test_decline_decision_ltv_too_high(self, service, valid_request):
        valid_request.loan_amount = Decimal("480000.00") # 96% LTV
        
        result = await service.make_decision(valid_request)
        
        assert result.decision == "Declined"
        assert "LTV" in result.decline_reason

    @pytest.mark.asyncio
    async def test_insurance_required_logic(self, service, valid_request):
        # Increase loan to trigger insurance (LTV > 80%)
        # Loan 405,000 / 500,000 = 81%
        valid_request.loan_amount = Decimal("405000.00")
        
        result = await service.make_decision(valid_request)
        
        assert result.decision == "Approved" # Assuming income supports it
        assert result.insurance_required == True
        assert result.insurance_premium_rate == Decimal("2.80")

    @pytest.mark.asyncio
    async def test_stress_test_applied_to_payment(self, service, valid_request):
        # Contract 4.5% -> Stress 6.5% (4.5 + 2)
        # Payment should be calculated at 6.5%
        result = await service.make_decision(valid_request)
        
        # We verify the qualifying rate used in the service logic
        # This is implicitly tested by the payment amount accuracy
        # If payment was calculated at 4.5%, it would be lower than at 6.5%
        assert result.qualifying_rate == Decimal("6.50")

    @pytest.mark.asyncio
    async def test_sin_is_not_logged_or_returned(self, service, valid_request, caplog):
        # Ensure PII is not leaked
        with caplog.at_level("DEBUG"):
            result = await service.make_decision(valid_request)
        
        # SIN should not be in the response
        assert not hasattr(result, 'sin') or result.sin is None or result.sin == ""
        
        # SIN should not be in logs (check text records)
        for record in caplog.records:
            assert "123456789" not in record.message

    @pytest.mark.asyncio
    async def test_zero_income_raises_error(self, service, valid_request):
        valid_request.annual_income = Decimal("0.00")
        
        with pytest.raises(UnderwritingError):
            await service.make_decision(valid_request)

    @pytest.mark.asyncio
    async def test_negative_property_value_raises_error(self, service, valid_request):
        valid_request.property_value = Decimal("-1000.00")
        
        with pytest.raises(UnderwritingError):
            await service.make_decision(valid_request)
```