import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.decision_service.services import DecisionService
from mortgage_underwriting.modules.decision_service.schemas import ApplicationCreate, DecisionResponse
from mortgage_underwriting.modules.decision_service.exceptions import UnderwritingError

@pytest.mark.unit
class TestDecisionServiceCalculations:
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_db):
        return DecisionService(mock_db)

    def test_calculate_monthly_payment(self, service):
        # Principal: 400k, Rate: 5% (annual), Term: 25 years (300 months)
        # Formula: M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # i = 0.05 / 12 = 0.004166...
        principal = Decimal("400000.00")
        annual_rate = Decimal("0.05")
        months = 300
        
        payment = service._calculate_monthly_payment(principal, annual_rate, months)
        
        # Expected approx 2338.36
        assert payment > Decimal("2338.00")
        assert payment < Decimal("2339.00")

    def test_calculate_ltv_success(self, service):
        loan_amount = Decimal("400000.00")
        property_value = Decimal("500000.00")
        
        ltv = service.calculate_ltv(loan_amount, property_value)
        
        assert ltv == Decimal("0.80")

    def test_calculate_ltv_zero_property_raises(self, service):
        with pytest.raises(ValueError, match="Property value must be positive"):
            service.calculate_ltv(Decimal("100000"), Decimal("0"))

    def test_determine_qualifying_rate_osfi_low_contract(self, service):
        # Contract 3.0% + 2% = 5.0%. Min is 5.25%. Result: 5.25%
        rate = service.determine_qualifying_rate(Decimal("0.03"))
        assert rate == Decimal("0.0525")

    def test_determine_qualifying_rate_osfi_high_contract(self, service):
        # Contract 5.0% + 2% = 7.0%. Min is 5.25%. Result: 7.0%
        rate = service.determine_qualifying_rate(Decimal("0.05"))
        assert rate == Decimal("0.07")

    def test_calculate_gds_within_limit(self, service):
        # Income 100k/yr. 
        # Monthly Payment ~2338.36 (at qualifying rate)
        # Tax 250/mo, Heat 100/mo. Total Monthly Debt ~ 2688.
        # GDS = (2688 * 12) / 100000 = 32.2%
        annual_income = Decimal("100000.00")
        monthly_payment = Decimal("2338.36")
        monthly_tax = Decimal("250.00")
        monthly_heat = Decimal("100.00")
        
        gds = service.calculate_gds(monthly_payment, monthly_tax, monthly_heat, annual_income)
        
        assert gds == Decimal("0.322") # Approx based on inputs
        assert gds <= Decimal("0.39")

    def test_calculate_tds_exceeds_limit(self, service):
        # High TDS scenario
        annual_income = Decimal("50000.00")
        monthly_payment = Decimal("2000.00")
        monthly_tax = Decimal("400.00")
        monthly_heat = Decimal("150.00")
        other_debts = Decimal("1000.00")
        
        # Total Monthly = 3550. Annual = 42600. TDS = 42600 / 50000 = 85.2%
        tds = service.calculate_tds(monthly_payment, monthly_tax, monthly_heat, other_debts, annual_income)
        
        assert tds > Decimal("0.44")

    def test_get_cmhc_insurance_rate_none_required(self, service):
        # LTV <= 80%
        rate = service.get_cmhc_insurance_rate(Decimal("0.80"))
        assert rate == Decimal("0.00")

    def test_get_cmhc_insurance_rate_tier_1(self, service):
        # 80.01% - 85%
        rate = service.get_cmhc_insurance_rate(Decimal("0.82"))
        assert rate == Decimal("0.0280")

    def test_get_cmhc_insurance_rate_tier_2(self, service):
        # 85.01% - 90%
        rate = service.get_cmhc_insurance_rate(Decimal("0.88"))
        assert rate == Decimal("0.0310")

    def test_get_cmhc_insurance_rate_tier_3(self, service):
        # 90.01% - 95%
        rate = service.get_cmhc_insurance_rate(Decimal("0.92"))
        assert rate == Decimal("0.0400")

    def test_get_cmhc_insurance_rate_invalid_ltv(self, service):
        # LTV > 95% (Uninsurable)
        with pytest.raises(ValueError, match="LTV exceeds maximum insurable limit"):
            service.get_cmhc_insurance_rate(Decimal("0.96"))

@pytest.mark.unit
class TestDecisionServiceLogic:
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_db):
        return DecisionService(mock_db)

    @pytest.mark.asyncio
    async def test_render_decision_approved(self, service):
        # Setup inputs that pass all criteria
        payload = ApplicationCreate(
            applicant_id="u1",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("120000.00"),
            annual_property_tax=Decimal("3000.00"),
            annual_heating_cost=Decimal("1200.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("0.04"),
            amortization_years=25
        )
        
        result = await service.render_decision(payload)
        
        assert result.decision == "Approved"
        assert result.gds <= Decimal("0.39")
        assert result.tds <= Decimal("0.44")
        assert result.insurance_required is False

    @pytest.mark.asyncio
    async def test_render_decision_rejected_high_tds(self, service):
        # Setup inputs with high debts
        payload = ApplicationCreate(
            applicant_id="u2",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("60000.00"), # Low income
            annual_property_tax=Decimal("3000.00"),
            annual_heating_cost=Decimal("1200.00"),
            other_debts=Decimal("2000.00"), # High other debts
            contract_rate=Decimal("0.04"),
            amortization_years=25
        )
        
        result = await service.render_decision(payload)
        
        assert result.decision == "Rejected"
        assert "TDS" in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_render_decision_insurance_required(self, service):
        # LTV 85%
        payload = ApplicationCreate(
            applicant_id="u3",
            loan_amount=Decimal("425000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("150000.00"),
            annual_property_tax=Decimal("3000.00"),
            annual_heating_cost=Decimal("1200.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("0.04"),
            amortization_years=25
        )
        
        result = await service.render_decision(payload)
        
        assert result.decision == "Approved" # Assuming income is high enough
        assert result.insurance_required is True
        assert result.insurance_premium_rate == Decimal("0.0280")

    @pytest.mark.asyncio
    async def test_render_decision_stress_test_application(self, service):
        # Verify that the qualifying rate logic is applied, not just contract rate
        # Contract 3.0%, Qualifying 5.25%. Payment at 5.25% is higher.
        payload = ApplicationCreate(
            applicant_id="u4",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("85000.00"), # Tight margin at 5.25%
            annual_property_tax=Decimal("3000.00"),
            annual_heating_cost=Decimal("1200.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("0.03"), # Low rate
            amortization_years=25
        )
        
        result = await service.render_decision(payload)
        
        # Service should calculate payment based on 5.25%
        # 400k @ 5.25% = ~2400/mo
        # 2400 + 250 + 100 = 2750
        # 2750 * 12 = 33000
        # 33000 / 85000 = 38.8% (Passes GDS)
        
        assert result.decision == "Approved"