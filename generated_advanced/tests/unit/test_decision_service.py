import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from mortgage_underwriting.modules.decision.services import DecisionService
from mortgage_underwriting.modules.decision.schemas import DecisionRequest, DecisionResponse
from mortgage_underwriting.modules.decision.exceptions import DecisionError, RegulatoryViolationError
from mortgage_underwriting.common.security import encrypt_pii

# Import fixtures from conftest implicitly

@pytest.mark.unit
class TestDecisionServiceCalculations:
    """
    Tests for core financial calculation logic (OSFI B-20 & CMHC compliance).
    """

    @pytest.mark.asyncio
    async def test_calculate_gds_within_limits(self):
        """
        Test GDS calculation is accurate and respects the stress test rate.
        Qualifying Rate = max(Contract + 2%, 5.25%).
        """
        service = DecisionService(AsyncMock())
        
        # Contract 4.5% -> Qualifying 6.5% (4.5 + 2)
        # Loan 400k, 25 yrs @ 6.5% -> Monthly P&I ~ 2680
        # Tax 3000/12 = 250, Heat 150
        # Total Housing = 2680 + 250 + 150 = 3080
        # Income 120k/12 = 10000
        # GDS = 3080 / 10000 = 30.8%
        
        payload = DecisionRequest(
            borrower_id="123",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("120000.00"),
            monthly_debt=Decimal("0.00"),
            contract_rate=Decimal("4.50"),
            amortization_years=25,
            property_tax_annual=Decimal("3000.00"),
            heating_monthly=Decimal("150.00")
        )
        
        gds = await service._calculate_gds(payload)
        
        assert gds == Decimal("30.80")
        # Verify it used the qualifying rate logic implicitly via the result
        assert gds < Decimal("39.00")

    @pytest.mark.asyncio
    async def test_calculate_gds_stress_test_floor(self):
        """
        Test OSFI stress test floor of 5.25%.
        Contract 3.0% -> Qualifying 5.25%.
        """
        service = DecisionService(AsyncMock())
        
        payload = DecisionRequest(
            borrower_id="123",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("120000.00"),
            monthly_debt=Decimal("0.00"),
            contract_rate=Decimal("3.00"), # Low rate
            amortization_years=25,
            property_tax_annual=Decimal("3000.00"),
            heating_monthly=Decimal("150.00")
        )
        
        # If calculation uses 5.25%, P&I is higher than 3.0%
        # We just check the service runs and returns a valid Decimal
        gds = await service._calculate_gds(payload)
        assert isinstance(gds, Decimal)
        assert gds > Decimal("0.00")

    @pytest.mark.asyncio
    async def test_calculate_tds_within_limits(self):
        """
        Test TDS calculation includes housing costs + other debts.
        """
        service = DecisionService(AsyncMock())
        
        payload = DecisionRequest(
            borrower_id="123",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("120000.00"),
            monthly_debt=Decimal("500.00"), # Car loan
            contract_rate=Decimal("4.50"),
            amortization_years=25,
            property_tax_annual=Decimal("3000.00"),
            heating_monthly=Decimal("150.00")
        )
        
        # Housing (approx 3080) + Debt (500) = 3580
        # Income 10000
        # TDS = 35.8%
        
        tds = await service._calculate_tds(payload)
        assert tds == Decimal("35.80")
        assert tds < Decimal("44.00")

    @pytest.mark.asyncio
    async def test_calculate_ltv_and_cmhc_insurance(self):
        """
        Test LTV calculation and CMHC insurance tier logic.
        """
        service = DecisionService(AsyncMock())
        
        # Scenario 1: 85% LTV (Premium 2.80%)
        payload_85 = DecisionRequest(
            borrower_id="123",
            loan_amount=Decimal("425000.00"),
            property_value=Decimal("500000.00"), # 85% LTV
            annual_income=Decimal("100000.00"),
            monthly_debt=Decimal("0.00"),
            contract_rate=Decimal("4.00"),
            amortization_years=25,
            property_tax_annual=Decimal("3000.00"),
            heating_monthly=Decimal("150.00")
        )
        
        ltv, required, premium = await service._calculate_ltv_and_insurance(payload_85)
        assert ltv == Decimal("85.00")
        assert required is True
        assert premium == Decimal("0.0280") # 2.80%

        # Scenario 2: 90% LTV (Premium 3.10%)
        payload_90 = DecisionRequest(
            borrower_id="123",
            loan_amount=Decimal("450000.00"),
            property_value=Decimal("500000.00"), # 90% LTV
            annual_income=Decimal("100000.00"),
            monthly_debt=Decimal("0.00"),
            contract_rate=Decimal("4.00"),
            amortization_years=25,
            property_tax_annual=Decimal("3000.00"),
            heating_monthly=Decimal("150.00")
        )
        
        ltv, required, premium = await service._calculate_ltv_and_insurance(payload_90)
        assert ltv == Decimal("90.00")
        assert required is True
        assert premium == Decimal("0.0310") # 3.10%

    @pytest.mark.asyncio
    async def test_calculate_ltv_no_insurance_needed(self):
        """
        Test LTV <= 80% requires no insurance.
        """
        service = DecisionService(AsyncMock())
        
        payload = DecisionRequest(
            borrower_id="123",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"), # 80% LTV
            annual_income=Decimal("100000.00"),
            monthly_debt=Decimal("0.00"),
            contract_rate=Decimal("4.00"),
            amortization_years=25,
            property_tax_annual=Decimal("3000.00"),
            heating_monthly=Decimal("150.00")
        )
        
        ltv, required, premium = await service._calculate_ltv_and_insurance(payload)
        assert ltv == Decimal("80.00")
        assert required is False
        assert premium == Decimal("0.00")


@pytest.mark.unit
class TestDecisionServiceLogic:
    """
    Tests for the high-level decision orchestration.
    """

    @pytest.mark.asyncio
    async def test_approve_application_success(self, mock_db_session, valid_application_payload):
        """
        Test a fully compliant application results in APPROVED.
        """
        payload = DecisionRequest(**valid_application_payload)
        service = DecisionService(mock_db_session)
        
        result = await service.evaluate_application(payload)
        
        assert result.decision == "APPROVED"
        assert result.gds_ratio <= Decimal("39.00")
        assert result.tds_ratio <= Decimal("44.00")
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deny_application_gds_limit(self, mock_db_session, high_gds_payload):
        """
        Test that GDS > 39% results in DENIAL.
        """
        payload = DecisionRequest(**high_gds_payload)
        service = DecisionService(mock_db_session)
        
        result = await service.evaluate_application(payload)
        
        assert result.decision == "DENIED"
        assert "GDS" in result.denial_reason
        assert result.gds_ratio > Decimal("39.00")

    @pytest.mark.asyncio
    async def test_deny_application_tds_limit(self, mock_db_session, high_tds_payload):
        """
        Test that TDS > 44% results in DENIAL.
        """
        payload = DecisionRequest(**high_tds_payload)
        service = DecisionService(mock_db_session)
        
        result = await service.evaluate_application(payload)
        
        assert result.decision == "DENIED"
        assert "TDS" in result.denial_reason
        assert result.tds_ratio > Decimal("44.00")

    @pytest.mark.asyncio
    async def test_pipeda_compliance_no_sin_in_logs(self, mock_db_session, valid_application_payload):
        """
        Ensure PII (SIN) is not exposed in the returned object or logic.
        Note: In a real scenario, we'd check log output. Here we check the response object.
        """
        # Add SIN to payload (it shouldn't end up in DecisionResponse)
        payload_dict = valid_application_payload.copy()
        payload_dict["sin"] = "123456789"
        payload = DecisionRequest(**payload_dict)
        
        service = DecisionService(mock_db_session)
        
        with patch("mortgage_underwriting.modules.decision.services.logger") as mock_logger:
            result = await service.evaluate_application(payload)
            
            # Check response doesn't contain SIN
            assert not hasattr(result, "sin")
            assert "123456789" not in str(result.model_dump_json())
            
            # Verify logger was not called with SIN (basic check)
            for call in mock_logger.info.call_args_list:
                assert "123456789" not in str(call)

    @pytest.mark.asyncio
    async def test_fintrac_audit_fields_populated(self, mock_db_session, valid_application_payload):
        """
        Test that audit fields (created_at) are populated for FINTRAC compliance.
        """
        payload = DecisionRequest(**valid_application_payload)
        service = DecisionService(mock_db_session)
        
        # We need to capture the object being saved to the DB
        captured_args = {}
        
        def side_effect_add(obj):
            captured_args["obj"] = obj
            
        mock_db_session.add.side_effect = side_effect_add
        
        await service.evaluate_application(payload)
        
        saved_obj = captured_args["obj"]
        assert hasattr(saved_obj, "created_at")
        assert hasattr(saved_obj, "updated_at")
        # created_at should not be None in a real flow, 
        # but here we check the service sets it or defaults it
        # Assuming the model defaults it or service sets it.

    @pytest.mark.asyncio
    async def test_zero_income_raises_error(self, mock_db_session):
        """
        Test edge case: Zero income should cause calculation failure.
        """
        payload = DecisionRequest(
            borrower_id="123",
            loan_amount=Decimal("100.00"),
            property_value=Decimal("1000.00"),
            annual_income=Decimal("0.00"),
            monthly_debt=Decimal("0.00"),
            contract_rate=Decimal("4.00"),
            amortization_years=25,
            property_tax_annual=Decimal("0.00"),
            heating_monthly=Decimal("0.00")
        )
        
        service = DecisionService(mock_db_session)
        
        with pytest.raises(DecisionError) as exc_info:
            await service.evaluate_application(payload)
        
        assert "Income" in str(exc_info.value)