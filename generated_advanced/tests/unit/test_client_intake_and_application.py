import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.modules.client_intake.schemas import ApplicationCreate, ClientCreate
from mortgage_underwriting.modules.client_intake.exceptions import (
    GDSLimitExceededError,
    TDSLimitExceededError,
    LTVLimitExceededError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def client_payload(self):
        return ClientCreate(
            first_name="Jane",
            last_name="Smith",
            sin="987654321",
            dob="1985-05-15",
            email="jane@example.com",
            phone="4165551234"
        )

    @pytest.mark.asyncio
    async def test_create_client_success(self, mock_db, client_payload):
        """Test successful client creation with PII encryption mocked."""
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "encrypted_hash"
            
            service = ClientService(mock_db)
            result = await service.create_client(client_payload)

            assert result.first_name == "Jane"
            assert result.sin == "encrypted_hash"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_create_client_db_failure(self, mock_db, client_payload):
        """Test handling of database integrity errors (e.g. duplicate email)."""
        mock_db.commit.side_effect = IntegrityError("Mock", "Mock", "Mock")
        
        with pytest.raises(AppException) as exc_info:
            service = ClientService(mock_db)
            await service.create_client(client_payload)
        
        assert exc_info.value.error_code == "DB_INTEGRITY_ERROR"


@pytest.mark.unit
class TestApplicationServiceCalculations:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def app_payload(self):
        # Loan: 400k, Rate: 5%, 25yr amortization -> Monthly P&I approx $2338
        # Income: 100k -> Monthly: 8333
        # Tax: 300/yr, Heat: 100/mo, Condo: 0
        return ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("100000.00"),
            property_tax=Decimal("3000.00"),
            heating_cost=Decimal("1200.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("5.00")
        )

    @pytest.mark.asyncio
    async def test_calculate_gds_within_limit(self, mock_db, app_payload):
        service = ApplicationService(mock_db)
        
        # GDS = (Mortgage + Tax + Heat + 50% Condo) / Income
        # Qualifying Rate: Max(5% + 2%, 5.25%) = 7.0%
        # Monthly P&I at 7% for 400k is approx $2820
        # Monthly Costs = 2820 + 250 + 100 = 3170
        # Monthly Income = 8333.33
        # GDS = 3170 / 8333.33 = 38.04% (Passes < 39%)
        
        # We verify the service logic runs without raising exception
        # (Actual math implementation is inside the service, we test the outcome)
        result = await service.create_application(app_payload)
        assert result.gds_ratio < Decimal("39.00")

    @pytest.mark.asyncio
    async def test_calculate_gds_exceeds_limit(self, mock_db):
        # Create payload with high housing costs relative to income
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("60000.00"), # Low income
            property_tax=Decimal("6000.00"),
            heating_cost=Decimal("500.00"),
            condo_fees=Decimal("800.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("5.00")
        )
        
        service = ApplicationService(mock_db)
        
        with pytest.raises(GDSLimitExceededError) as exc_info:
            await service.create_application(payload)
        
        assert "GDS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calculate_tds_exceeds_limit(self, mock_db):
        # Create payload with high debts
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("80000.00"),
            property_tax=Decimal="3000.00",
            heating_cost=Decimal("100.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("3000.00"), # Significant debt
            contract_rate=Decimal("5.00")
        )
        
        service = ApplicationService(mock_db)
        
        with pytest.raises(TDSLimitExceededError) as exc_info:
            await service.create_application(payload)
        
        assert "TDS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calculate_ltv_insurance_required_tier_1(self, mock_db):
        # 80.01% - 85% -> 2.80%
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("401000.00"), # 80.2% of 500k
            property_value=Decimal("500000.00"),
            annual_income=Decimal("200000.00"), # High income to pass GDS/TDS
            property_tax=Decimal("1000.00"),
            heating_cost=Decimal("100.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("4.00")
        )
        
        service = ApplicationService(mock_db)
        result = await service.create_application(payload)
        
        assert result.ltv_ratio == Decimal("80.20")
        assert result.insurance_required is True
        assert result.insurance_premium_rate == Decimal("0.0280")

    @pytest.mark.asyncio
    async def test_calculate_ltv_insurance_required_tier_3(self, mock_db):
        # 90.01% - 95% -> 4.00%
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("475000.00"), # 95% of 500k
            property_value=Decimal("500000.00"),
            annual_income=Decimal("200000.00"),
            property_tax=Decimal("1000.00"),
            heating_cost=Decimal("100.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("4.00")
        )
        
        service = ApplicationService(mock_db)
        result = await service.create_application(payload)
        
        assert result.ltv_ratio == Decimal("95.00")
        assert result.insurance_required is True
        assert result.insurance_premium_rate == Decimal("0.0400")

    @pytest.mark.asyncio
    async def test_ltv_exceeds_maximum(self, mock_db):
        # > 95% is invalid for standard insured
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("480000.00"), # 96%
            property_value=Decimal("500000.00"),
            annual_income=Decimal("200000.00"),
            property_tax=Decimal("1000.00"),
            heating_cost=Decimal("100.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("4.00")
        )
        
        service = ApplicationService(mock_db)
        
        with pytest.raises(LTVLimitExceededError):
            await service.create_application(payload)

    @pytest.mark.asyncio
    async def test_stress_test_rate_calculation(self, mock_db):
        # Contract rate 3.0% -> Qualifying should be 5.25% (floor)
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("300000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("150000.00"),
            property_tax=Decimal("1000.00"),
            heating_cost=Decimal("100.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("3.00") # Low rate
        )
        
        with patch("mortgage_underwriting.modules.client_intake.services.calculate_monthly_payment") as mock_calc:
            # We expect the service to call calc with rate 5.25% (0.0525)
            service = ApplicationService(mock_db)
            await service.create_application(payload)
            
            # Check that the calculation was called with the stress rate
            # The second argument to calculate_monthly_payment is the annual rate
            call_args = mock_calc.call_args
            assert call_args is not None
            qualifying_rate_used = call_args[0][1]
            assert qualifying_rate_used == Decimal("0.0525") # 5.25% floor