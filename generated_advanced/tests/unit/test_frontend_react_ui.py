import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from mortgage_underwriting.modules.frontend_react_ui.services import FrontendService
from mortgage_underwriting.modules.frontend_react_ui.exceptions import (
    ApplicationValidationError,
    ComplianceError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFrontendServiceCalculations:

    @pytest.mark.asyncio
    async def test_calculate_stress_test_rate_below_floor(self):
        """
        Test OSFI B-20 Stress Test: Contract rate + 2% < 5.25%
        Result should be 5.25%.
        """
        service = FrontendService(db=AsyncMock())
        rate = Decimal("3.00")
        stress_rate = await service._calculate_qualifying_rate(rate)
        assert stress_rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_calculate_stress_test_rate_above_floor(self):
        """
        Test OSFI B-20 Stress Test: Contract rate + 2% > 5.25%
        Result should be Contract + 2%.
        """
        service = FrontendService(db=AsyncMock())
        rate = Decimal("5.00")
        stress_rate = await service._calculate_qualifying_rate(rate)
        assert stress_rate == Decimal("7.00")

    @pytest.mark.asyncio
    async def test_calculate_gds_success(self):
        """
        Test GDS Calculation: (Property Tax + Heat + 50% Condo + Mortgage Pmt) / Income
        """
        service = FrontendService(db=AsyncMock())
        # Pmt = ~2000, Tax = 3000/12=250, Heat = 100, Condo = 0. Income = 10000/12=833.33
        # GDS = (2350) / 8333 = ~28%
        income = Decimal("100000.00")
        monthly_payment = Decimal("2000.00")
        property_tax = Decimal("3000.00")
        heating = Decimal("1200.00")
        condo_fees = Decimal("0.00")

        gds = await service._calculate_gds(
            income, monthly_payment, property_tax, heating, condo_fees
        )
        # 2000 + 250 + 100 = 2350. 2350 / 8333.33 = 0.282
        assert gds == Decimal("0.2820")

    @pytest.mark.asyncio
    async def test_calculate_tds_success(self):
        """
        Test TDS Calculation: (Housing Costs + Other Debt) / Income
        """
        service = FrontendService(db=AsyncMock())
        income = Decimal("100000.00")
        housing_costs = Decimal("2350.00") # From GDS calculation
        other_debt = Decimal("500.00")

        tds = await service._calculate_tds(income, housing_costs, other_debt)
        # 2850 / 8333.33 = 0.342
        assert tds == Decimal("0.3420")

    @pytest.mark.asyncio
    async def test_calculate_ltv_and_cmhc_premium(self):
        """
        Test CMHC Logic:
        LTV > 80% -> Insurance Required
        LTV 80.01-85% -> 2.80%
        """
        service = FrontendService(db=AsyncMock())
        loan_amount = Decimal("85000.00")
        property_value = Decimal("100000.00")
        
        ltv, premium_rate = await service._calculate_ltv_and_premium(loan_amount, property_value)
        
        assert ltv == Decimal("0.85")
        assert premium_rate == Decimal("0.0280")

@pytest.mark.unit
class TestFrontendServiceValidation:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_validate_application_osfi_compliance_pass(self, mock_db, valid_applicant_payload):
        """
        Happy Path: GDS <= 39%, TDS <= 44%
        """
        service = FrontendService(mock_db)
        # Mocking internal calculation helpers to focus on validation logic
        service._calculate_gds = AsyncMock(return_value=Decimal("0.35")) # 35%
        service._calculate_tds = AsyncMock(return_value=Decimal("0.40")) # 40%
        
        # Should not raise
        await service._validate_osfi_compliance(valid_applicant_payload)

    @pytest.mark.asyncio
    async def test_validate_application_osfi_gds_fail(self, mock_db, valid_applicant_payload):
        """
        OSFI B-20 Violation: GDS > 39%
        """
        service = FrontendService(mock_db)
        service._calculate_gds = AsyncMock(return_value=Decimal("0.40")) # 40% > 39%
        
        with pytest.raises(ApplicationValidationError) as exc_info:
            await service._validate_osfi_compliance(valid_applicant_payload)
        
        assert "GDS" in str(exc_info.value)
        assert "39%" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_application_osfi_tds_fail(self, mock_db, valid_applicant_payload):
        """
        OSFI B-20 Violation: TDS > 44%
        """
        service = FrontendService(mock_db)
        service._calculate_gds = AsyncMock(return_value=Decimal("0.30"))
        service._calculate_tds = AsyncMock(return_value=Decimal("0.45")) # 45% > 44%
        
        with pytest.raises(ApplicationValidationError) as exc_info:
            await service._validate_osfi_compliance(valid_applicant_payload)
        
        assert "TDS" in str(exc_info.value)
        assert "44%" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_fintrac_logging(self, mock_db, valid_applicant_payload):
        """
        FINTRAC: Ensure identity verification is logged (simulated via mock logger)
        """
        service = FrontendService(mock_db)
        
        with patch('mortgage_underwriting.modules.frontend_react_ui.services.logger') as mock_logger:
            await service._log_identity_verification(valid_applicant_payload)
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            # PIPEDA Check: Ensure SIN is NOT in the logs
            assert valid_applicant_payload['sin'] not in call_args
            assert "Identity verified" in call_args

    @pytest.mark.asyncio
    async def test_encrypt_pii_fields(self, mock_db):
        """
        PIPEDA: Verify SIN is encrypted before storage logic
        """
        service = FrontendService(mock_db)
        raw_sin = "123456789"
        
        encrypted = await service._encrypt_sin(raw_sin)
        
        assert encrypted != raw_sin
        assert isinstance(encrypted, str)

    @pytest.mark.asyncio
    async def test_create_application_persistence(self, mock_db, valid_applicant_payload):
        """
        Test that service calls DB add/commit and returns a response
        """
        service = FrontendService(mock_db)
        
        # Mock the model creation
        with patch('mortgage_underwriting.modules.frontend_react_ui.services.MortgageApplication') as MockModel:
            mock_instance = MagicMock()
            mock_instance.id = 1
            MockModel.return_value = mock_instance
            
            result = await service.create_application(valid_applicant_payload)
            
            mock_db.add.assert_called_once_with(mock_instance)
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once_with(mock_instance)
            assert result.id == 1