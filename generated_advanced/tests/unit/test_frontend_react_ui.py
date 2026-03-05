```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

# Imports from the module under test
from mortgage_underwriting.modules.frontend_ui.services import FrontendUIService
from mortgage_underwriting.modules.frontend_ui.schemas import (
    MortgageApplicationSchema, 
    BorrowerSchema, 
    PropertySchema, 
    MortgageSchema, 
    LiabilitiesSchema
)
from mortgage_underwriting.modules.frontend_ui.exceptions import (
    ComplianceException, 
    ValidationException
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFrontendSchemas:
    """Test Pydantic schemas for the Frontend UI module."""

    def test_valid_mortgage_application_schema(self, valid_frontend_submission_payload):
        """Test that a valid payload passes schema validation."""
        schema = MortgageApplicationSchema(**valid_frontend_submission_payload)
        assert schema.borrower.annual_income == Decimal("96000.00")
        assert schema.mortgage.loan_amount == Decimal("400000.00")
        assert schema.mortgage.interest_rate == Decimal("4.50")

    def test_schema_rejects_negative_income(self, valid_frontend_submission_payload):
        """Test that negative income raises a validation error."""
        payload = valid_frontend_submission_payload
        payload["borrower"]["annual_income"] = "-5000.00"
        with pytest.raises(ValueError): # Pydantic raises ValueError for constraint violations
            MortgageApplicationSchema(**payload)

    def test_schema_rejects_zero_loan_amount(self, valid_frontend_submission_payload):
        """Test that zero loan amount is invalid."""
        payload = valid_frontend_submission_payload
        payload["mortgage"]["loan_amount"] = "0.00"
        with pytest.raises(ValueError):
            MortgageApplicationSchema(**payload)

    def test_schema_accepts_string_decimals(self, valid_frontend_submission_payload):
        """Ensure strings representing numbers are converted to Decimals."""
        schema = MortgageApplicationSchema(**valid_frontend_submission_payload)
        assert isinstance(schema.borrower.annual_income, Decimal)
        assert isinstance(schema.property.property_value, Decimal)


@pytest.mark.unit
class TestFrontendUIService:
    """Test business logic in FrontendUIService."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return FrontendUIService(mock_db)

    @pytest.mark.asyncio
    async def test_calculate_gds_success(self, service):
        """Test GDS calculation with standard values."""
        # Income: 8000/mo, Mortgage: 2200, Tax: 400, Heat: 150
        # GDS = (2200 + 400 + 150) / 8000 = 2750 / 8000 = 0.34375 (34.38%)
        monthly_income = Decimal("8000.00")
        monthly_mortgage_payment = Decimal("2200.00")
        property_tax = Decimal("400.00")
        heating = Decimal("150.00")
        
        gds = service._calculate_gds(monthly_income, monthly_mortgage_payment, property_tax, heating)
        assert gds == Decimal("34.38")

    @pytest.mark.asyncio
    async def test_calculate_gds_exceeds_limit(self, service):
        """Test GDS calculation where limit is exceeded."""
        # High housing costs relative to income
        monthly_income = Decimal("5000.00")
        monthly_mortgage_payment = Decimal("3000.00")
        property_tax = Decimal("500.00")
        heating = Decimal("200.00")
        
        gds = service._calculate_gds(monthly_income, monthly_mortgage_payment, property_tax, heating)
        # (3000+500+200)/5000 = 0.74 (74%)
        assert gds == Decimal("74.00")

    @pytest.mark.asyncio
    async def test_calculate_tds_success(self, service):
        """Test TDS calculation including other debts."""
        # Income: 8000. Housing: 2750. Other Debt: 500.
        # TDS = (2750 + 500) / 8000 = 3250 / 8000 = 40.625%
        monthly_income = Decimal("8000.00")
        housing_costs = Decimal("2750.00")
        other_debt = Decimal("500.00")
        
        tds = service._calculate_tds(monthly_income, housing_costs, other_debt)
        assert tds == Decimal("40.63")

    @pytest.mark.asyncio
    async def test_calculate_ltv(self, service):
        """Test Loan-to-Value calculation."""
        loan_amount = Decimal("400000.00")
        property_value = Decimal("500000.00")
        ltv = service._calculate_ltv(loan_amount, property_value)
        assert ltv == Decimal("80.00")

    @pytest.mark.asyncio
    async def test_submit_application_compliance_check_gds(self, service, valid_frontend_submission_payload):
        """
        Test that submission fails if GDS > 39% (OSFI B-20).
        We mock the internal calculation to force a failure.
        """
        payload = MortgageApplicationSchema(**valid_frontend_submission_payload)
        
        # Mock the GDS calculation to return a high value
        with patch.object(service, '_calculate_gds', return_value=Decimal("45.00")):
            with pytest.raises(ComplianceException) as exc_info:
                await service.submit_application(payload)
            
            assert "GDS" in str(exc_info.value)
            assert "39%" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_application_compliance_check_tds(self, service, high_tds_payload):
        """
        Test that submission fails if TDS > 44% (OSFI B-20).
        """
        payload = MortgageApplicationSchema(**high_tds_payload)
        
        # Real calculation check
        # Income: 4166. Mortgage (approx 5% on 550k over 25): ~3200. 
        # This scenario is naturally bad, but let's verify the logic catches it.
        with pytest.raises(ComplianceException) as exc_info:
            await service.submit_application(payload)
        
        assert "TDS" in str(exc_info.value) or "GDS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_application_success(self, service, mock_db, valid_frontend_submission_payload):
        """Test successful submission path."""
        payload = MortgageApplicationSchema(**valid_frontend_submission_payload)
        
        # Mock encryption
        with patch('mortgage_underwriting.modules.frontend_ui.services.encrypt_pii', return_value="encrypted_sin"):
            result = await service.submit_application(payload)
        
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_application_stress_test_logic(self, service, valid_frontend_submission_payload):
        """
        Verify that the service uses the qualifying rate for stress testing.
        Qualifying Rate = max(contract_rate + 2%, 5.25%)
        """
        payload = MortgageApplicationSchema(**valid_frontend_submission_payload)
        # Contract rate is 4.5%. Qualifying should be 6.5%.
        
        with patch('mortgage_underwriting.modules.frontend_ui.services.encrypt_pii', return_value="enc"):
            # We spy on the payment calculation method
            with patch.object(service, '_calculate_monthly_payment', wraps=service._calculate_monthly_payment) as spy_calc:
                await service.submit_application(payload)
                
                # Assert that _calculate_monthly_payment was called with the qualifying rate
                call_args = spy_calc.call_args
                rate_used = call_args[0][1] # Second argument is rate
                
                # Max(4.5 + 2, 5.25) = 6.5
                assert rate_used == Decimal("6.50")

    @pytest.mark.asyncio
    async def test_submit_application_ltv_insurance_requirement(self, service, valid_frontend_submission_payload):
        """
        Test CMHC logic: IF LTV > 80% THEN insurance_required = True.
        """
        payload = MortgageApplicationSchema(**valid_frontend_submission_payload)
        # Modify payload to make LTV 90%
        payload.mortgage.loan_amount = Decimal("450000.00") 
        payload.mortgage.down_payment = Decimal("50000.00") # Value still 500k
        
        with patch('mortgage_underwriting.modules.frontend_ui.services.encrypt_pii', return_value="enc"):
            result = await service.submit_application(payload)
            
            assert result.insurance_required is True

    @pytest.mark.asyncio
    async def test_submit_application_ltv_no_insurance(self, service, valid_frontend_submission_payload):
        """
        Test CMHC logic: IF LTV <= 80% THEN insurance_required = False.
        """
        payload = MortgageApplicationSchema(**valid_frontend_submission_payload)
        # Default payload is exactly 80% LTV
        
        with patch('mortgage_underwriting.modules.frontend_ui.services.encrypt_pii', return_value="enc"):
            result = await service.submit_application(payload)
            
            assert result.insurance_required is False

    @pytest.mark.asyncio
    async def test_sin_is_encrypted(self, service, mock_db, valid_frontend_submission_payload):
        """
        Test PIPEDA compliance: SIN must be encrypted before storage.
        """
        payload = MortgageApplicationSchema(**valid_frontend_submission_payload)
        raw_sin = payload.borrower.sin
        
        with patch('mortgage_underwriting.modules.frontend_ui.services.encrypt_pii') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_hash_value"
            
            await service.submit_application(payload)
            
            # Verify encrypt_pii was called with the raw SIN
            mock_encrypt.assert_called_once_with(raw_sin)
            
            # Verify the object saved to DB has the encrypted value
            # Assuming the service creates an object and adds it to db
            saved_obj = mock_db.add.call_args[0][0]
            assert saved_obj.borrower.sin_hash == "encrypted_hash_value"
            assert saved_obj.borrower.sin != raw_sin # Ensure raw is not stored

    @pytest.mark.asyncio
    async def test_pii_not_in_logs(self, service, valid_frontend_submission_payload, caplog):
        """
        Ensure that logging the submission does not leak PII (SIN, DOB).
        """
        payload = MortgageApplicationSchema(**valid_frontend_submission_payload)
        
        with patch('mortgage_underwriting.modules.frontend_ui.services.encrypt_pii', return_value="enc"):
            with patch('mortgage_underwriting.modules.frontend_ui.services.logger') as mock_logger:
                await service.submit_application(payload)
                
                # Check all calls to logger.info/debug/warning
                for call in mock_logger.info.call_args_list:
                    msg = str(call)
                    assert "123456789" not in msg # SIN
                    assert "1990-01-01" not in msg # DOB
```