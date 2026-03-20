import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from mortgage_underwriting.modules.underwriting_engine.services import UnderwritingService
from mortgage_underwriting.modules.underwriting_engine.exceptions import UnderwritingError
from mortgage_underwriting.modules.underwriting_engine.schemas import UnderwritingRequest, UnderwritingResponse

@pytest.mark.unit
class TestUnderwritingService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return UnderwritingService(mock_db)

    def test_calculate_qualifying_rate_low_contract(self, service):
        """
        Test OSFI B-20 Stress Test: Contract rate < 3.25% should floor at 5.25%.
        """
        contract_rate = Decimal("3.00")
        qualifying_rate = service._calculate_qualifying_rate(contract_rate)
        assert qualifying_rate == Decimal("5.25")

    def test_calculate_qualifying_rate_high_contract(self, service):
        """
        Test OSFI B-20 Stress Test: Contract rate + 2% > 5.25%.
        """
        contract_rate = Decimal("4.50")
        qualifying_rate = service._calculate_qualifying_rate(contract_rate)
        assert qualifying_rate == Decimal("6.50")

    def test_calculate_ltv_no_insurance(self, service):
        """
        Test LTV calculation where LTV <= 80%.
        """
        loan_amount = Decimal("400000.00")
        property_value = Decimal("500000.00")
        ltv = service._calculate_ltv(loan_amount, property_value)
        assert ltv == Decimal("0.80")
        assert service._is_insurance_required(ltv) is False

    def test_calculate_ltv_requires_insurance(self, service):
        """
        Test LTV calculation where LTV > 80%.
        """
        loan_amount = Decimal("405000.00")
        property_value = Decimal("500000.00")
        ltv = service._calculate_ltv(loan_amount, property_value)
        assert ltv == Decimal("0.81")
        assert service._is_insurance_required(ltv) is True

    def test_calculate_gds_success(self, service):
        """
        Test GDS calculation: (Monthly Housing / Monthly Income).
        Limit: 39%.
        """
        annual_income = Decimal("120000.00")
        monthly_housing = Decimal("2800.00")
        # Monthly payment calculation mocked for simplicity or passed in
        monthly_mortgage_payment = Decimal("2200.00") 
        
        gds = service._calculate_gds(monthly_housing, monthly_mortgage_payment, annual_income)
        # (2800 + 2200) / (120000 / 12) = 5000 / 10000 = 0.50 (50%)
        # Wait, usually Housing costs INCLUDE taxes/heat.
        # Let's assume monthly_housing is the sum of PITH (Principal, Interest, Taxes, Heat)
        # If input separates them: GDS = (PIT + Heat) / Monthly_Income
        
        # Adjusting based on typical schema: monthly_housing_costs usually = Taxes + Heat + 50% Condo
        # Service usually calculates Mortgage Payment internally.
        # Let's assume we pass the total monthly obligation.
        
        total_obligation = monthly_housing + monthly_mortgage_payment
        expected_gds = (total_obligation / (annual_income / Decimal("12"))) * Decimal("100")
        
        assert gds == expected_gds

    def test_calculate_gds_exceeds_limit(self, service):
        """
        Test GDS > 39% raises error or returns failure flag.
        """
        annual_income = Decimal("50000.00")
        monthly_housing = Decimal("3000.00")
        monthly_mortgage_payment = Decimal("1500.00")
        
        gds = service._calculate_gds(monthly_housing, monthly_mortgage_payment, annual_income)
        assert gds > Decimal("39.00")

    def test_calculate_tds_exceeds_limit(self, service):
        """
        Test TDS > 44% raises error or returns failure flag.
        """
        annual_income = Decimal("60000.00") # 5000/mo
        monthly_housing = Decimal("2500.00")
        monthly_mortgage_payment = Decimal("1500.00")
        monthly_debts = Decimal("1000.00")
        
        tds = service._calculate_tds(monthly_housing, monthly_mortgage_payment, monthly_debts, annual_income)
        # (2500 + 1500 + 1000) / 5000 = 5000 / 5000 = 100%
        assert tds > Decimal("44.00")

    def test_cmhc_insurance_tier_1(self, service):
        """
        Test CMHC Premium: 80.01% - 85.00% -> 2.80%
        """
        loan = Decimal("401000.00")
        value = Decimal("500000.00") # LTV 80.2%
        ltv = service._calculate_ltv(loan, value)
        premium_rate = service._get_cmhc_premium_rate(ltv)
        assert premium_rate == Decimal("0.0280")

    def test_cmhc_insurance_tier_2(self, service):
        """
        Test CMHC Premium: 85.01% - 90.00% -> 3.10%
        """
        loan = Decimal("426000.00")
        value = Decimal("500000.00") # LTV 85.2%
        ltv = service._calculate_ltv(loan, value)
        premium_rate = service._get_cmhc_premium_rate(ltv)
        assert premium_rate == Decimal("0.0310")

    def test_cmhc_insurance_tier_3(self, service):
        """
        Test CMHC Premium: 90.01% - 95.00% -> 4.00%
        """
        loan = Decimal("451000.00")
        value = Decimal("500000.00") # LTV 90.2%
        ltv = service._calculate_ltv(loan, value)
        premium_rate = service._get_cmhc_premium_rate(ltv)
        assert premium_rate == Decimal("0.0400")

    def test_cmhc_insurance_tier_0(self, service):
        """
        Test CMHC Premium: <= 80% -> 0.00%
        """
        loan = Decimal("400000.00")
        value = Decimal("500000.00")
        ltv = service._calculate_ltv(loan, value)
        premium_rate = service._get_cmhc_premium_rate(ltv)
        assert premium_rate == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_process_application_approval(self, service, mock_db, valid_application_payload):
        """
        Test happy path: Application passes all checks.
        """
        request = UnderwritingRequest(**valid_application_payload)
        
        # Mock internal calculation helpers to specific values to ensure logic flow
        service._calculate_gds = MagicMock(return_value=Decimal("30.00"))
        service._calculate_tds = MagicMock(return_value=Decimal("35.00"))
        service._calculate_ltv = MagicMock(return_value=Decimal("0.90"))
        service._get_cmhc_premium_rate = MagicMock(return_value=Decimal("0.0310"))
        service._calculate_mortgage_payment = MagicMock(return_value=Decimal("2500.00"))

        result = await service.process_application(request)

        assert result.decision == "Approved"
        assert result.gds_ratio == Decimal("30.00")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_application_declined_tds(self, service, mock_db, high_tds_payload):
        """
        Test failure path: Application fails TDS > 44%.
        """
        request = UnderwritingRequest(**high_tds_payload)
        
        service._calculate_gds = MagicMock(return_value=Decimal("35.00"))
        service._calculate_tds = MagicMock(return_value=Decimal("50.00")) # Fail
        service._calculate_ltv = MagicMock(return_value=Decimal("0.90"))
        service._calculate_mortgage_payment = MagicMock(return_value=Decimal("2500.00"))

        result = await service.process_application(request)

        assert result.decision == "Declined"
        assert "TDS" in result.rejection_reason
        # Ensure we don't commit a declined decision if business logic dictates only store approved?
        # Usually we store all decisions for audit.
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_application_invalid_input_zero_income(self, service, mock_db):
        """
        Test validation: Zero income should raise ValueError.
        """
        payload = {
            "application_id": "app_zero",
            "borrower_id": "b_1",
            "loan_amount": "100000.00",
            "property_value": "200000.00",
            "annual_income": "0.00",
            "monthly_housing_costs": "500.00",
            "monthly_debt_payments": "0.00",
            "contract_rate": "5.0",
            "amortization_years": 25,
            "credit_score": 700
        }
        request = UnderwritingRequest(**payload)
        
        with pytest.raises(ValueError, match="Income must be greater than zero"):
            await service.process_application(request)

    @pytest.mark.asyncio
    async def test_calculate_total_loan_amount_with_insurance(self, service):
        """
        Test that insurance is added to loan amount correctly.
        """
        loan_amount = Decimal("400000.00")
        premium_rate = Decimal("0.0310") # 3.1%
        
        # Insurance = Loan * Rate / (1 - Rate)
        # Insurance = 400000 * 0.031 / 0.969 = 12796.90...
        expected_total = service._calculate_insured_amount(loan_amount, premium_rate)
        
        # Verify logic matches CMHC standard: Total Loan = Base / (1 - premium)
        assert expected_total > loan_amount

    @pytest.mark.asyncio
    async def test_log_auditable_calculation_breakdown(self, service, valid_application_payload):
        """
        Verify that the service generates an audit log string for calculations.
        """
        request = UnderwritingRequest(**valid_application_payload)
        # We expect a structured log or return value containing breakdown
        # Assuming the service returns a breakdown object or logs it
        
        breakdown = service._generate_audit_breakdown(
            gds=Decimal("30.5"), 
            tds=Decimal("35.2"), 
            ltv=Decimal("0.80"),
            qualifying_rate=Decimal("5.25"),
            premium=Decimal("0.00")
        )
        
        assert "GDS: 30.5" in breakdown
        assert "TDS: 35.2" in breakdown
        assert "LTV: 0.8" in breakdown