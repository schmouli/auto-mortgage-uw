import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import paths based on project conventions
from mortgage_underwriting.modules.underwriting_engine.services import UnderwritingService
from mortgage_underwriting.modules.underwriting_engine.models import UnderwritingDecision
from mortgage_underwriting.modules.underwriting_engine.exceptions import UnderwritingError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestUnderwritingService:

    @pytest.mark.asyncio
    async def test_calculate_stress_test_rate_below_floor(self):
        """
        OSFI B-20: Stress test rate must be max(contract + 2%, 5.25%).
        Contract 3.0% + 2% = 5.0%. Result should be 5.25%.
        """
        service = UnderwritingService(db=AsyncMock())
        rate = await service._calculate_qualifying_rate(Decimal("3.0"))
        assert rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_calculate_stress_test_rate_above_floor(self):
        """
        OSFI B-20: Contract 4.5% + 2% = 6.5%. Result should be 6.5%.
        """
        service = UnderwritingService(db=AsyncMock())
        rate = await service._calculate_qualifying_rate(Decimal("4.5"))
        assert rate == Decimal("6.50")

    @pytest.mark.asyncio
    async def test_calculate_gds_success(self):
        """
        Test GDS Calculation: (Mortgage + Tax + Heat) / Income
        """
        service = UnderwritingService(db=AsyncMock())
        # Monthly Mortgage approx 2400, Tax 250, Heat 150 = 2800 / 10000 = 28%
        monthly_payment = Decimal("2400.00")
        monthly_tax = Decimal("250.00")
        monthly_heat = Decimal("150.00")
        monthly_income = Decimal("10000.00")
        
        gds = await service._calculate_gds(monthly_payment, monthly_tax, monthly_heat, monthly_income)
        assert gds == Decimal("0.28") # 28%

    @pytest.mark.asyncio
    async def test_calculate_tds_success(self):
        """
        Test TDS Calculation: (Mortgage + Tax + Heat + Other) / Income
        """
        service = UnderwritingService(db=AsyncMock())
        monthly_payment = Decimal("2400.00")
        monthly_tax = Decimal("250.00")
        monthly_heat = Decimal("150.00")
        other_debt = Decimal("500.00")
        monthly_income = Decimal("10000.00")
        
        tds = await service._calculate_tds(monthly_payment, monthly_tax, monthly_heat, other_debt, monthly_income)
        assert tds == Decimal("0.33") # 33%

    @pytest.mark.asyncio
    async def test_calculate_ltv_and_insurance(self):
        """
        CMHC Logic:
        LTV = Loan / Value
        Tier 1: 80.01-85% = 2.80%
        Tier 2: 85.01-90% = 3.10%
        Tier 3: 90.01-95% = 4.00%
        """
        service = UnderwritingService(db=AsyncMock())
        
        # Case 1: 85% LTV (Boundary check)
        loan = Decimal("425000.00")
        value = Decimal("500000.00")
        ltv, required, premium = await service._calculate_cmhc_details(loan, value)
        assert ltv == Decimal("0.85")
        assert required is True
        assert premium == Decimal("0.0280") # 2.80%

        # Case 2: 92% LTV
        loan = Decimal("460000.00")
        ltv, required, premium = await service._calculate_cmhc_details(loan, value)
        assert ltv == Decimal("0.92")
        assert required is True
        assert premium == Decimal("0.0400") # 4.00%

        # Case 3: 75% LTV (No insurance)
        loan = Decimal("375000.00")
        ltv, required, premium = await service._calculate_cmhc_details(loan, value)
        assert ltv == Decimal("0.75")
        assert required is False
        assert premium == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_evaluate_application_approve(self, mock_db_session, valid_application_payload):
        """
        Happy Path: Ratios within limits (GDS <= 39%, TDS <= 44%)
        """
        # Mock the DB add/commit to prevent actual DB interaction
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        service = UnderwritingService(db=mock_db_session)
        
        # Convert payload dict to Pydantic model (simulated)
        from mortgage_underwriting.modules.underwriting_engine.schemas import UnderwritingRequest
        request_data = UnderwritingRequest(**valid_application_payload)
        
        result = await service.evaluate(request_data)
        
        assert result.decision == "APPROVED"
        assert result.gds <= Decimal("0.39")
        assert result.tds <= Decimal("0.44")
        assert result.insurance_required is True # LTV is 90%
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_application_decline_high_tds(self, mock_db_session, high_risk_payload):
        """
        OSFI B-20: Hard limit TDS <= 44%. 
        High risk payload is designed to exceed this.
        """
        from mortgage_underwriting.modules.underwriting_engine.schemas import UnderwritingRequest
        
        service = UnderwritingService(db=mock_db_session)
        request_data = UnderwritingRequest(**high_risk_payload)
        
        result = await service.evaluate(request_data)
        
        assert result.decision == "DECLINED"
        assert result.tds > Decimal("0.44")
        assert "TDS" in result.rejection_reason

    @pytest.mark.asyncio
    async def test_evaluate_application_decline_high_gds(self, mock_db_session):
        """
        OSFI B-20: Hard limit GDS <= 39%.
        """
        from mortgage_underwriting.modules.underwriting_engine.schemas import UnderwritingRequest
        
        payload = {
            "applicant_id": "test-gds-fail",
            "loan_amount": "400000.00",
            "property_value": "410000.00", # High LTV
            "annual_income": "40000.00", # Low income
            "property_tax": "4000.00",
            "heating_cost": "200.00",
            "other_debt": "0.00",
            "contract_rate": "5.0",
            "amortization_years": 25,
            "sin": "111111111",
            "dob": "1990-01-01"
        }
        
        service = UnderwritingService(db=mock_db_session)
        request_data = UnderwritingRequest(**payload)
        
        result = await service.evaluate(request_data)
        
        assert result.decision == "DECLINED"
        assert result.gds > Decimal("0.39")

    @pytest.mark.asyncio
    async def test_pii_encryption_service_call(self, mock_db_session, valid_application_payload):
        """
        PIPEDA: Verify SIN is encrypted before storage/logic.
        """
        from mortgage_underwriting.modules.underwriting_engine.schemas import UnderwritingRequest
        
        service = UnderwritingService(db=mock_db_session)
        request_data = UnderwritingRequest(**valid_application_payload)
        
        # Patch the encryption utility to verify it's called
        with patch('mortgage_underwriting.common.security.encrypt_pii') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_sin_value"
            
            await service.evaluate(request_data)
            
            # Verify encrypt was called with the raw SIN
            mock_encrypt.assert_called_with("123456789")

    @pytest.mark.asyncio
    async def test_invalid_loan_amount_raises(self, mock_db_session):
        """
        Input Validation: Loan amount cannot be negative or zero.
        """
        from mortgage_underwriting.modules.underwriting_engine.schemas import UnderwritingRequest
        from pydantic import ValidationError
        
        payload = {
            "applicant_id": "test-bad-loan",
            "loan_amount": "-100.00",
            "property_value": "500000.00",
            "annual_income": "100000.00",
            "property_tax": "3000.00",
            "heating_cost": "150.00",
            "other_debt": "0.00",
            "contract_rate": "4.0",
            "amortization_years": 25,
            "sin": "123456789",
            "dob": "1990-01-01"
        }
        
        # Pydantic validation should catch this before service logic
        with pytest.raises(ValidationError):
            UnderwritingRequest(**payload)