import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_portal.services import ClientService, ApplicationService
from mortgage_underwriting.modules.client_portal.exceptions import (
    ClientAlreadyExistsError,
    InvalidApplicationDataError,
    ComplianceError
)
from mortgage_underwriting.modules.client_portal.models import Client, MortgageApplication
from mortgage_underwriting.modules.client_portal.schemas import ClientCreate, ApplicationCreate, ApplicationStatus

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


@pytest.mark.asyncio
class TestClientService:
    
    @pytest.fixture
    def service(self, mock_db):
        return ClientService(mock_db)

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    async def test_create_client_success(self, service, mock_db, valid_client_payload, mock_security):
        # Arrange
        payload = ClientCreate(**valid_client_payload)
        mock_db.scalar.return_value = None  # No existing client

        # Act
        result = await service.create_client(payload)

        # Assert
        assert result.first_name == "John"
        assert result.email == "john.doe@example.com"
        assert result.sin_hash == "hashed_sin"
        assert result.sin == "encrypted_string" # Verify encryption was called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_security["encrypt"].assert_called_with("123456789")

    async def test_create_client_duplicate_email(self, service, mock_db, valid_client_payload, mock_security):
        # Arrange
        payload = ClientCreate(**valid_client_payload)
        existing_client = Client(id=1, email="john.doe@example.com")
        mock_db.scalar.return_value = existing_client

        # Act & Assert
        with pytest.raises(ClientAlreadyExistsError):
            await service.create_client(payload)
        
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    async def test_create_client_invalid_sin_format(self, service, mock_db, mock_security):
        # Arrange
        invalid_payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane@example.com",
            "sin": "123", # Too short
            "date_of_birth": "1990-01-01"
        }
        payload = ClientCreate(**invalid_payload)

        # Act & Assert
        with pytest.raises(ValueError): # Pydantic validation error
            await service.create_client(payload)


@pytest.mark.asyncio
class TestApplicationService:

    @pytest.fixture
    def service(self, mock_db):
        return ApplicationService(mock_db)

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.get = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    async def test_submit_application_success_calculates_ratios(self, service, mock_db, valid_application_payload):
        # Arrange
        payload = ApplicationCreate(**valid_application_payload)
        mock_client = Client(id=1, first_name="John")
        mock_db.get.return_value = mock_client

        # Act
        result = await service.submit_application(payload)

        # Assert - OSFI B-20 Compliance Checks
        # Qualifying Rate = max(4.5 + 2, 5.25) = 6.5%
        # Monthly Payment (approx): M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # i = 0.065 / 12 = 0.005416, n = 300
        # Payment ~ 2528.00
        # GDS = (M + Tax + Heat) / Income
        # TDS = (M + Tax + Heat + Debts) / Income
        
        assert result.client_id == 1
        assert result.qualifying_rate == Decimal("6.50")
        assert result.ltv_ratio == Decimal("80.00") # 400k / 500k
        assert result.status == ApplicationStatus.SUBMITTED
        
        # Verify Audit Fields (FINTRAC)
        assert result.created_at is not None
        assert result.updated_at is not None
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    async def test_submit_application_high_ltv_triggers_insurance(self, service, mock_db):
        # Arrange - LTV > 80%
        payload_data = {
            "client_id": 1,
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("25000.00"), # 5% down
            "loan_amount": Decimal("475000.00"),
            "contract_rate": Decimal("5.0"),
            "amortization_years": 25,
            "annual_income": Decimal("150000.00"),
            "monthly_property_tax": Decimal("300.00"),
            "monthly_heating": Decimal("150.00"),
            "monthly_debts": Decimal("0.00")
        }
        payload = ApplicationCreate(**payload_data)
        mock_db.get.return_value = Client(id=1)

        # Act
        result = await service.submit_application(payload)

        # Assert - CMHC Logic
        assert result.ltv_ratio == Decimal("95.00")
        assert result.insurance_required is True
        assert result.insurance_premium_rate == Decimal("4.00") # 90.01-95% tier

    async def test_submit_application_gds_limit_enforcement(self, service, mock_db):
        # Arrange - Low income to trigger GDS > 39%
        payload_data = {
            "client_id": 1,
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("100000.00"),
            "loan_amount": Decimal("400000.00"),
            "contract_rate": Decimal("5.0"),
            "amortization_years": 25,
            "annual_income": Decimal("40000.00"), # Very low income
            "monthly_property_tax": Decimal("500.00"),
            "monthly_heating": Decimal("200.00"),
            "monthly_debts": Decimal("0.00")
        }
        payload = ApplicationCreate(**payload_data)
        mock_db.get.return_value = Client(id=1)

        # Act & Assert
        # Service should raise error if GDS > 39%
        with pytest.raises(ComplianceError) as exc_info:
            await service.submit_application(payload)
        
        assert "GDS" in str(exc_info.value)
        assert "39%" in str(exc_info.value)

    async def test_submit_application_client_not_found(self, service, mock_db, valid_application_payload):
        # Arrange
        payload = ApplicationCreate(**valid_application_payload)
        mock_db.get.return_value = None

        # Act & Assert
        with pytest.raises(ValueError):
            await service.submit_application(payload)

    async def test_calculate_stress_test_rate_boundary(self):
        # Test the helper logic directly or via service
        # Case 1: Contract Rate 3.0% -> Qualifying 5.25% (Floor)
        rate1 = ApplicationService._calculate_qualifying_rate(Decimal("3.00"))
        assert rate1 == Decimal("5.25")

        # Case 2: Contract Rate 5.0% -> Qualifying 7.0% (Contract + 2)
        rate2 = ApplicationService._calculate_qualifying_rate(Decimal("5.00"))
        assert rate2 == Decimal("7.00")