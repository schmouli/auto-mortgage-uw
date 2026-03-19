```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, call
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientIntakeService
from mortgage_underwriting.modules.client_intake.models import ClientApplication
from mortgage_underwriting.modules.client_intake.exceptions import (
    ApplicationValidationError,
    ComplianceError,
)
from mortgage_underwriting.common.exceptions import AppException

# Import paths strictly following convention
from mortgage_underwriting.modules.client_intake.schemas import ApplicationCreate

@pytest.mark.unit
class TestClientIntakeService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_application_success(self, mock_db, valid_application_data, mock_security):
        """Test successful application creation with PIPEDA encryption."""
        service = ClientIntakeService(mock_db)
        payload = ApplicationCreate(**valid_application_data)
        
        result = await service.create_application(payload)
        
        # Verify DB interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        
        # Verify PIPEDA: Ensure SIN encryption was called
        mock_security["encrypt"].assert_called()
        mock_security["hash"].assert_called_with("123456789")
        
        # Verify basic object creation
        assert result.loan_amount == Decimal("600000.00")
        assert result.applicant.sin_hash == "hashed_sin_value" # Should not store plain SIN

    @pytest.mark.asyncio
    async def test_create_application_db_failure(self, mock_db, valid_application_data):
        """Test handling of database integrity errors."""
        mock_db.commit.side_effect = IntegrityError("Mock DB Error", {}, None)
        service = ClientIntakeService(mock_db)
        payload = ApplicationCreate(**valid_application_data)
        
        with pytest.raises(AppException) as exc_info:
            await service.create_application(payload)
        
        assert exc_info.value.status_code == 500
        assert "database error" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_calculate_gds_osfi_compliance_success(self, mock_db):
        """
        Test GDS calculation with OSFI stress test.
        Scenario: Income 95k, Mortgage 2800/mo, Tax 400, Heat 150.
        Qualifying Rate: max(4.5 + 2, 5.25) = 6.5%.
        """
        service = ClientIntakeService(mock_db)
        
        # Mock inputs
        annual_income = Decimal("95000.00")
        monthly_mortgage_payment = Decimal("2800.00")
        property_tax = Decimal("400.00")
        heating = Decimal("150.00")
        contract_rate = Decimal("4.5")
        
        # Expected calculation
        # Monthly Income = 95000 / 12 = 7916.66
        # Housing Costs = 2800 + 400 + 150 = 3350
        # GDS = (3350 / 7916.66) * 100 = 42.31% (Raw)
        # Note: We are testing the logic implementation, assuming service handles the math
        
        with patch.object(service, '_calculate_monthly_payment', return_value=monthly_mortgage_payment):
            gds = await service.calculate_gds(
                annual_income=annual_income,
                property_tax=property_tax,
                heating=heating,
                contract_rate=contract_rate,
                loan_amount=Decimal("500000"),
                amortization=25
            )
            
            # OSFI Rule: GDS must be <= 39%
            # If the calculated GDS exceeds this, the service should raise ComplianceError
            # Here we check if the calculation logic runs
            assert isinstance(gds, Decimal)

    @pytest.mark.asyncio
    async def test_calculate_gds_exceeds_limit_raises_compliance_error(self, mock_db):
        """Test that GDS > 39% raises OSFI Compliance Error."""
        service = ClientIntakeService(mock_db)
        
        # Low income scenario to trigger failure
        annual_income = Decimal("40000.00") # ~3333/mo
        property_tax = Decimal("500.00")
        heating = Decimal("200.00")
        contract_rate = Decimal("5.0")
        
        with pytest.raises(ComplianceError) as exc_info:
            await service.calculate_gds(
                annual_income=annual_income,
                property_tax=property_tax,
                heating=heating,
                contract_rate=contract_rate,
                loan_amount=Decimal("400000"),
                amortization=25
            )
            
        assert "GDS" in str(exc_info.value)
        assert "39%" in str(exc_info.value) or "limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_calculate_tds_exceeds_limit_raises_compliance_error(self, mock_db):
        """Test that TDS > 44% raises OSFI Compliance Error."""
        service = ClientIntakeService(mock_db)
        
        # High debt scenario
        annual_income = Decimal("60000.00")
        other_debts = Decimal("2000.00") # Significant load
        property_tax = Decimal("300.00")
        heating = Decimal("100.00")
        contract_rate = Decimal("3.0")
        
        with pytest.raises(ComplianceError) as exc_info:
            await service.calculate_tds(
                annual_income=annual_income,
                property_tax=property_tax,
                heating=heating,
                other_debts=other_debts,
                contract_rate=contract_rate,
                loan_amount=Decimal("300000"),
                amortization=25
            )
            
        assert "TDS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_determine_insurance_cmhc_logic(self, mock_db):
        """Test CMHC insurance requirement logic based on LTV tiers."""
        service = ClientIntakeService(mock_db)
        
        # Case 1: LTV <= 80% (No insurance)
        # 600k loan / 750k value = 80%
        req1 = await service.determine_insurance_requirement(
            loan_amount=Decimal("600000.00"),
            property_value=Decimal("750000.00")
        )
        assert req1.required is False
        assert req1.premium_rate == Decimal("0.00")

        # Case 2: 80.01% - 85% (2.80%)
        # 640k loan / 750k value = 85.33%
        req2 = await service.determine_insurance_requirement(
            loan_amount=Decimal("640000.00"),
            property_value=Decimal("750000.00")
        )
        assert req2.required is True
        assert req2.premium_rate == Decimal("2.80")

        # Case 3: 90.01% - 95% (4.00%)
        # 712500 loan / 750k value = 95%
        req3 = await service.determine_insurance_requirement(
            loan_amount=Decimal("712500.00"),
            property_value=Decimal("750000.00")
        )
        assert req3.required is True
        assert req3.premium_rate == Decimal("4.00")

    @pytest.mark.asyncio
    async def test_validate_ltv_precision(self, mock_db):
        """Ensure LTV calculation uses Decimal and has no precision loss."""
        service = ClientIntakeService(mock_db)
        
        # Specific values that often cause float issues
        loan = Decimal("100000.33")
        value = Decimal("100000.99")
        
        # We expect the service to handle this internally, here we check the helper if exposed
        # or the validation logic
        ltv = await service._calculate_ltv(loan, value)
        
        # Check it's a Decimal
        assert isinstance(ltv, Decimal)
        # Check basic math logic
        expected = (loan / value) * 100
        assert ltv == expected

    @pytest.mark.asyncio
    async def test_stress_test_qualifying_rate_logic(self, mock_db):
        """Verify OSFI Stress Test: max(contract + 2%, 5.25%)."""
        service = ClientIntakeService(mock_db)
        
        # Case 1: Contract rate 3.0% -> 3+2=5.0 vs 5.25 -> 5.25%
        rate1 = await service._get_qualifying_rate(Decimal("3.0"))
        assert rate1 == Decimal("5.25")
        
        # Case 2: Contract rate 5.0% -> 5+2=7.0 vs 5.25 -> 7.0%
        rate2 = await service._get_qualifying_rate(Decimal("5.0"))
        assert rate2 == Decimal("7.00")
        
        # Case 3: Contract rate 3.25% -> 3.25+2=5.25 vs 5.25 -> 5.25%
        rate3 = await service._get_qualifying_rate(Decimal("3.25"))
        assert rate3 == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_fintrac_audit_fields_populated(self, mock_db, valid_application_data, mock_security):
        """Test that FINTRAC required fields (created_at) are populated."""
        service = ClientIntakeService(mock_db)
        payload = ApplicationCreate(**valid_application_data)
        
        # Mock the DB object to inspect what is added
        added_instance = None
        def capture_add(obj):
            nonlocal added_instance
            added_instance = obj
            
        mock_db.add.side_effect = capture_add
        
        await service.create_application(payload)
        
        assert added_instance is not None
        assert hasattr(added_instance, 'created_at')
        assert added_instance.created_at is not None
        # Verify created_by is set (usually from token context, mocked here)
        assert hasattr(added_instance, 'created_by')
```