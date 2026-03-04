import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.modules.client_intake.schemas import ApplicationCreate, ClientCreate
from mortgage_underwriting.modules.client_intake.exceptions import (
    ClientNotFoundError, 
    ApplicationValidationError,
    RegulatoryComplianceError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_client_success(self, mock_db, valid_client_payload):
        """Test successful client creation with PII encryption."""
        service = ClientService(mock_db)
        
        # Mock the return of execute to simulate no existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "encrypted_hash"
            
            result = await service.create_client(ClientCreate(**valid_client_payload))
            
            assert result.email == "john.doe@example.com"
            assert result.sin_hash == "encrypted_hash"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_encrypt.assert_called_once_with("123456789")

    @pytest.mark.asyncio
    async def test_create_client_duplicate_email(self, mock_db, valid_client_payload):
        """Test failure when trying to create a client with an existing email."""
        service = ClientService(mock_db)
        
        # Mock existing client
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        with pytest.raises(AppException) as exc_info:
            await service.create_client(ClientCreate(**valid_client_payload))
        
        assert "already exists" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_client_by_id_not_found(self, mock_db):
        service = ClientService(mock_db)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ClientNotFoundError):
            await service.get_client(999)


@pytest.mark.unit
class TestApplicationService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_app_payload(self):
        return ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("450000.00"),
            property_value=Decimal("550000.00"),
            down_payment=Decimal("100000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.50"),
            annual_property_tax=Decimal("3500.00"),
            estimated_heating_cost=Decimal("150.00"),
            monthly_debt_obligations=Decimal("500.00"),
            annual_income=Decimal("120000.00")
        )

    @pytest.mark.asyncio
    async def test_submit_application_success(self, mock_db, mock_app_payload):
        """Test successful application submission and GDS/TDS calculation."""
        service = ApplicationService(mock_db)
        
        # Mock client exists
        mock_client = MagicMock(id=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute.return_value = mock_result

        result = await service.submit_application(mock_app_payload)

        assert result.loan_amount == Decimal("450000.00")
        assert result.application_status == "SUBMITTED"
        # Assert audit fields are set
        assert result.created_at is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_application_client_not_found(self, mock_db, mock_app_payload):
        service = ApplicationService(mock_db)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ClientNotFoundError):
            await service.submit_application(mock_app_payload)

    @pytest.mark.asyncio
    async def test_calculate_gds_osfi_compliance(self, mock_db, mock_app_payload):
        """Test GDS calculation respects OSFI B-20 stress test."""
        service = ApplicationService(mock_db)
        
        # Mock client
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        # Rate is 4.50%, Stress test should be max(6.50%, 5.25%) = 6.50%
        # Monthly payment calculation (approximate for logic check)
        # P = 450k, r = 6.5/1200, n = 300 -> M ~ 3000
        # Tax = 3500/12 = 291.67, Heat = 150
        # GDS = (M + Tax + Heat) / (120k/12)
        
        result = await service.submit_application(mock_app_payload)
        
        # Verify qualifying rate was used
        assert result.qualifying_rate == Decimal("6.50")
        assert result.gds_ratio is not None
        assert result.gds_ratio <= Decimal("39.00")

    @pytest.mark.asyncio
    async def test_calculate_tds_osfi_compliance(self, mock_db, mock_app_payload):
        """Test TDS calculation respects OSFI B-20 limits."""
        service = ApplicationService(mock_db)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        result = await service.submit_application(mock_app_payload)
        
        assert result.tds_ratio is not None
        # TDS includes the $500 debt obligations
        assert result.tds_ratio <= Decimal("44.00")

    @pytest.mark.asyncio
    async def test_submit_application_high_gds_raises_error(self, mock_db):
        """Test that high GDS > 39% triggers RegulatoryComplianceError."""
        service = ApplicationService(mock_db)
        
        # Create payload that will fail GDS (Low income, high costs)
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("800000.00"),
            property_value=Decimal("800000.00"),
            down_payment=Decimal("0.01"), # 100% LTV to force high payments
            amortization_years=25,
            contract_rate=Decimal("5.00"),
            annual_property_tax=Decimal("10000.00"),
            estimated_heating_cost=Decimal("500.00"),
            monthly_debt_obligations=Decimal("0.00"),
            annual_income=Decimal("30000.00") # Very low income
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        with pytest.raises(RegulatoryComplianceError) as exc_info:
            await service.submit_application(payload)
        
        assert "GDS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_submit_application_high_tds_raises_error(self, mock_db):
        """Test that high TDS > 44% triggers RegulatoryComplianceError."""
        service = ApplicationService(mock_db)
        
        # Create payload that passes GDS but fails TDS due to other debts
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("300000.00"),
            property_value=Decimal("400000.00"),
            down_payment=Decimal("100000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.00"),
            annual_property_tax=Decimal("3000.00"),
            estimated_heating_cost=Decimal("100.00"),
            monthly_debt_obligations=Decimal("5000.00"), # Massive debt
            annual_income=Decimal("80000.00")
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        with pytest.raises(RegulatoryComplianceError) as exc_info:
            await service.submit_application(payload)
        
        assert "TDS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_cmhc_insurance_logic_80_percent_ltv(self, mock_db):
        """Test CMHC logic: LTV <= 80% means no insurance."""
        service = ApplicationService(mock_db)
        
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"), # 80% LTV
            down_payment=Decimal("100000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.00"),
            annual_property_tax=Decimal("3000.00"),
            estimated_heating_cost=Decimal("100.00"),
            monthly_debt_obligations=Decimal("0.00"),
            annual_income=Decimal("100000.00")
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        result = await service.submit_application(payload)
        
        assert result.ltv_ratio == Decimal("80.00")
        assert result.insurance_required is False
        assert result.insurance_premium_amount == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_cmhc_insurance_logic_95_percent_ltv(self, mock_db):
        """Test CMHC logic: LTV > 80% requires insurance (Tier 90.01-95% = 4.00%)."""
        service = ApplicationService(mock_db)
        
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("475000.00"),
            property_value=Decimal("500000.00"), # 95% LTV
            down_payment=Decimal("25000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.00"),
            annual_property_tax=Decimal("3000.00"),
            estimated_heating_cost=Decimal("100.00"),
            monthly_debt_obligations=Decimal("0.00"),
            annual_income=Decimal("100000.00")
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        result = await service.submit_application(payload)
        
        assert result.ltv_ratio == Decimal("95.00")
        assert result.insurance_required is True
        # Premium: 4.00% of loan amount
        assert result.insurance_premium_amount == (Decimal("475000.00") * Decimal("0.04"))

    @pytest.mark.asyncio
    async def test_pipeda_sin_not_logged(self, mock_db, mock_app_payload):
        """Ensure SIN is not passed through to logs or responses (handled by schema/model)."""
        service = ApplicationService(mock_db)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1, sin_hash="hashed_value")
        mock_db.execute.return_value = mock_result

        with patch("mortgage_underwriting.modules.client_intake.services.logger") as mock_logger:
            result = await service.submit_application(mock_app_payload)
            
            # Check logger calls
            for call in mock_logger.info.call_args_list:
                # Ensure raw SIN string is not in any log message
                assert "123456789" not in str(call)
                assert "sin" not in str(call).lower() or "hash" in str(call).lower()