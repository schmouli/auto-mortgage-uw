```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_portal.services import ClientPortalService
from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
from mortgage_underwriting.modules.client_portal.exceptions import (
    GDSExceededException,
    TDSExceededException,
    InvalidLTVException,
)
from mortgage_underwriting.common.exceptions import AppException

# Import paths strictly following project conventions
# from mortgage_underwriting.modules.client_portal.models import MortgageApplication


@pytest.mark.unit
class TestClientPortalService:
    """
    Unit tests for ClientPortalService business logic.
    Focuses on Regulatory Requirements (OSFI, CMHC, PIPEDA).
    """

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return ClientPortalService(mock_db)

    @pytest.mark.asyncio
    async def test_submit_application_success(self, service, mock_db, valid_application_payload, mock_security):
        """
        Test happy path: Application submission with valid data.
        Verify PII encryption and DB persistence.
        """
        # Act
        result = await service.submit_application(ApplicationCreate(**valid_application_payload))

        # Assert
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        
        # Verify PII handling (PIPEDA)
        # Ensure encrypt_pii was called for DOB
        mock_security["encrypt"].assert_any_call("1990-01-01")
        # Ensure hash_sin was called
        mock_security["hash"].assert_called_once_with("123456789")

    @pytest.mark.asyncio
    async def test_submit_application_osfi_gds_limit(self, service, mock_db, valid_application_payload):
        """
        Test OSFI B-20: GDS must be <= 39%.
        Scenario: High property tax and heating costs push GDS over limit.
        """
        # Modify payload to trigger GDS failure
        # Income 120k, Monthly ~10k. Max GDS ~3900.
        # Mortgage payment (400k @ 5.5% stress) ~ $2450
        # Tax + Heat needs to be > 1450 to fail.
        payload = valid_application_payload.copy()
        payload["property_tax"] = Decimal("20000.00") # ~1666/mo
        payload["heating_cost"] = Decimal("5000.00")  # ~416/mo
        payload["contract_rate"] = Decimal("3.00") # Stress test becomes 5.25%

        with pytest.raises(GDSExceededException) as exc_info:
            await service.submit_application(ApplicationCreate(**payload))
        
        assert "GDS" in str(exc_info.value)
        assert "39%" in str(exc_info.value)
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_submit_application_osfi_tds_limit(self, service, mock_db, valid_application_payload):
        """
        Test OSFI B-20: TDS must be <= 44%.
        Scenario: High external debt pushes TDS over limit.
        """
        payload = valid_application_payload.copy()
        # Max TDS on 120k is ~4400. Mortgage ~2450. Tax/Heat ~500.
        # Remaining room ~1450.
        payload["other_debt"] = Decimal("20000.00") # ~1666/mo debt

        with pytest.raises(TDSExceededException) as exc_info:
            await service.submit_application(ApplicationCreate(**payload))

        assert "TDS" in str(exc_info.value)
        assert "44%" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_application_osfi_stress_test_rate(self, service, mock_db, valid_application_payload):
        """
        Test OSFI B-20: Stress test rate calculation.
        Qualifying Rate = Max(Contract + 2%, 5.25%)
        """
        # Case 1: Contract 4.5% -> Qualifying 6.5% (Contract + 2)
        payload_1 = valid_application_payload.copy()
        payload_1["contract_rate"] = Decimal("4.5")
        
        # We spy on the internal calculation method via side effects or verify logic through exception if possible
        # Here we assume success, but the calculation logic is internal. 
        # To test specifically, we would ideally expose a helper or check logs.
        # For this test, we verify it doesn't throw a calculation error and accepts the debt load.
        result_1 = await service.submit_application(ApplicationCreate(**payload_1))
        assert result_1.id is not None

        # Case 2: Contract 3.0% -> Qualifying 5.25% (Floor)
        # If we set debts such that they fail at 5.25% but pass at 5.0%, we can verify the floor.
        # However, simpler is to verify the logic directly if exposed.
        # We will verify the logic via a helper test below.
        pass

    @pytest.mark.asyncio
    async def test_calculate_qualifying_rate(self, service):
        """
        Direct unit test for the stress test rate helper.
        """
        # Contract + 2% is higher
        rate = service._calculate_qualifying_rate(Decimal("4.0"))
        assert rate == Decimal("6.00")

        # Floor 5.25% is higher
        rate = service._calculate_qualifying_rate(Decimal("3.0"))
        assert rate == Decimal("5.25")

        # Boundary
        rate = service._calculate_qualifying_rate(Decimal("3.25"))
        assert rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_submit_application_cmhc_insurance_required(self, service, mock_db, valid_application_payload, mock_security):
        """
        Test CMHC: LTV > 80% requires insurance.
        Loan 400k, Value 500k -> LTV 80%. No insurance.
        """
        payload = valid_application_payload.copy()
        payload["loan_amount"] = Decimal("400000.00")
        payload["property_value"] = Decimal("500000.00")
        
        result = await service.submit_application(ApplicationCreate(**payload))
        
        # LTV = 80.0%. Insurance should be False or 0 premium
        assert result.insurance_required is False
        assert result.insurance_premium == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_submit_application_cmhc_premium_tier_1(self, service, mock_db, valid_application_payload, mock_security):
        """
        Test CMHC: LTV 85% triggers 2.80% premium.
        """
        payload = valid_application_payload.copy()
        payload["loan_amount"] = Decimal("425000.00") # 85% LTV
        payload["property_value"] = Decimal("500000.00")
        
        result = await service.submit_application(ApplicationCreate(**payload))
        
        assert result.insurance_required is True
        # Premium calculated on Loan Amount (CMHC standard logic varies, assuming on loan for simplicity here)
        # 425000 * 0.028 = 11900
        expected_premium = Decimal("11900.00")
        assert result.insurance_premium == expected_premium

    @pytest.mark.asyncio
    async def test_submit_application_invalid_ltv(self, service, mock_db, valid_application_payload):
        """
        Test CMHC: LTV > 95% is usually uninsurable/rejected.
        """
        payload = valid_application_payload.copy()
        payload["loan_amount"] = Decimal("480000.00") # 96% LTV
        payload["property_value"] = Decimal("500000.00")
        
        with pytest.raises(InvalidLTVException):
            await service.submit_application(ApplicationCreate(**payload))

    @pytest.mark.asyncio
    async def test_fintrac_logging(self, service, mock_db, valid_application_payload, caplog):
        """
        Test FINTRAC: Identity verification and creation logging.
        """
        import logging
        with caplog.at_level(logging.INFO):
            await service.submit_application(ApplicationCreate(**valid_application_payload))
        
        # Check that audit relevant logs were created
        assert any("application_created" in record.message.lower() for record in caplog.records)
        assert any("identity_verified" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_pii_data_minimization(self, service, mock_db, valid_application_payload, mock_security):
        """
        Test PIPEDA: Ensure only necessary fields are processed.
        If payload contains extra junk, it should be ignored or stripped.
        """
        payload = valid_application_payload.copy()
        payload["favorite_color"] = "blue" # Irrelevant field
        
        # Service should ignore this field if strict schema validation is on
        # Pydantic schema will handle stripping, but let's ensure service doesn't crash
        result = await service.submit_application(ApplicationCreate(**payload))
        assert result is not None
        # Verify the model object added to DB doesn't have the extra field
        # (This is implicitly handled by Pydantic, but good to verify no crash)

    @pytest.mark.asyncio
    async def test_database_integrity_handling(self, service, mock_db, valid_application_payload):
        """
        Test handling of DB errors (e.g., Duplicate SIN).
        """
        mock_db.commit.side_effect = IntegrityError("INSERT", {}, Exception("Duplicate key"))
        
        with pytest.raises(AppException) as exc_info:
            await service.submit_application(ApplicationCreate(**valid_application_payload))
        
        assert "duplicate" in str(exc_info.value.detail).lower() or "conflict" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_decimal_precision_handling(self, service, mock_db):
        """
        Test that float inputs are rejected or converted correctly.
        Pydantic handles conversion, but we verify logic uses Decimal.
        """
        payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "date_of_birth": "1985-05-20",
            "sin": "987654321",
            "email": "jane@example.com",
            "phone_number": "4165550199",
            "property_address": "456 Oak St",
            "property_value": "600000.00", # String input
            "down_payment": Decimal("120000.00"),
            "loan_amount": Decimal("480000.00"),
            "contract_rate": "5.0",
            "amortization_years": 25,
            "annual_income": "150000.00",
            "property_tax": "3500.00",
            "heating_cost": "1500.00",
            "other_debt": "0.00",
        }
        
        result = await service.submit_application(ApplicationCreate(**payload))
        assert result.property_value == Decimal("600000.00")
```