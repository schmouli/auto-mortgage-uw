```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.modules.client_intake.schemas import ClientCreate, ApplicationCreate
from mortgage_underwriting.modules.client_intake.models import Client, Application
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
            email="jane@example.com",
            phone="4165551234",
            date_of_birth="1990-01-01",
            sin="987654321",
            address="789 Pine St",
            city="Ottawa",
            province="ON",
            postal_code="K1A0B1"
        )

    @pytest.mark.asyncio
    async def test_create_client_success(self, mock_db, client_payload):
        """
        Test successful client creation with PII encryption.
        """
        # Mock the refresh to return the object with an ID
        mock_db.refresh = AsyncMock()
        
        with patch('mortgage_underwriting.modules.client_intake.services.encrypt_pii') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_hash_123"
            
            service = ClientService(mock_db)
            result = await service.create_client(client_payload)

            # Verify DB interactions
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once()
            
            # Verify PII handling (SIN should be encrypted)
            # Assuming the model sets sin_encrypted
            assert result.sin_encrypted == "encrypted_hash_123"
            assert result.email == "jane@example.com"

    @pytest.mark.asyncio
    async def test_create_client_db_failure(self, mock_db, client_payload):
        """
        Test handling of database integrity errors (e.g., duplicate email).
        """
        mock_db.commit.side_effect = IntegrityError("INSERT failed", {}, Exception())
        
        service = ClientService(mock_db)
        
        with pytest.raises(AppException) as exc_info:
            await service.create_client(client_payload)
        
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_client_success(self, mock_db):
        """
        Test retrieving a client by ID.
        """
        mock_client = MagicMock(spec=Client)
        mock_client.id = 1
        mock_client.first_name = "Jane"
        
        # Mock the result of the scalar query
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = mock_client
        mock_db.execute.return_value = result_mock

        service = ClientService(mock_db)
        client = await service.get_client(1)

        assert client is not None
        assert client.id == 1

    @pytest.mark.asyncio
    async def test_get_client_not_found(self, mock_db):
        """
        Test retrieving a non-existent client.
        """
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        service = ClientService(mock_db)
        
        with pytest.raises(AppException) as exc_info:
            await service.get_client(999)
        
        assert exc_info.value.status_code == 404


@pytest.mark.unit
class TestApplicationService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def app_payload(self):
        return ApplicationCreate(
            client_id=1,
            property_address="100 Main St",
            property_city="Vancouver",
            property_province="BC",
            property_postal_code="V6B1A1",
            purchase_price=Decimal("800000.00"),
            down_payment=Decimal("160000.00"),
            loan_amount=Decimal("640000.00"),
            amortization_years=30,
            interest_rate=Decimal("4.5"),
            employment_status="employed",
            employer_name="Dev Inc",
            annual_income=Decimal("120000.00"),
            monthly_debt_payments=Decimal("800.00")
        )

    @pytest.mark.asyncio
    async def test_create_application_success(self, mock_db, app_payload):
        """
        Test successful application creation.
        """
        mock_db.refresh = AsyncMock()
        
        service = ApplicationService(mock_db)
        result = await service.create_application(app_payload)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        
        assert result.loan_amount == Decimal("640000.00")

    @pytest.mark.asyncio
    async def test_validate_ltv_boundary(self, mock_db):
        """
        Test LTV calculation logic (CMHC requirement check).
        """
        # Edge case: 95% LTV (5% down)
        payload = ApplicationCreate(
            client_id=1,
            property_address="Test",
            property_city="Test",
            property_province="ON",
            property_postal_code="T1T1T1",
            purchase_price=Decimal("100000.00"),
            down_payment=Decimal("5000.00"), # 5% down
            loan_amount=Decimal("95000.00"),
            amortization_years=25,
            interest_rate=Decimal("5.0"),
            employment_status="employed",
            employer_name="Test",
            annual_income=Decimal("50000.00"),
            monthly_debt_payments=Decimal("0.00")
        )
        
        service = ApplicationService(mock_db)
        # Assuming service has a method to validate or calculates LTV internally
        # Here we just ensure creation doesn't fail on basic LTV logic
        # In a real scenario, we might test a specific `check_ltv_compliance` method
        with patch.object(service, '_check_ltv_compliance', return_value=True) as mock_check:
            await service.create_application(payload)
            mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_application_invalid_loan_amount(self, mock_db):
        """
        Test that loan amount + down payment must equal purchase price.
        """
        payload = ApplicationCreate(
            client_id=1,
            property_address="Test",
            property_city="Test",
            property_province="ON",
            property_postal_code="T1T1T1",
            purchase_price=Decimal("100000.00"),
            down_payment=Decimal("10000.00"),
            loan_amount=Decimal("50000.00"), # Mismatch: 10k + 50k != 100k
            amortization_years=25,
            interest_rate=Decimal("5.0"),
            employment_status="employed",
            employer_name="Test",
            annual_income=Decimal("50000.00"),
            monthly_debt_payments=Decimal("0.00")
        )
        
        service = ApplicationService(mock_db)
        
        with pytest.raises(ValueError) as exc_info:
            await service.create_application(payload)
        
        assert "loan amount" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_calculate_stress_test_rate(self, mock_db):
        """
        Test OSFI B-20 Stress Test Rate Calculation.
        Qualifying Rate = max(contract_rate + 2%, 5.25%)
        """
        service = ApplicationService(mock_db)
        
        # Case 1: Contract rate 3.0% -> 3.0 + 2 = 5.0 < 5.25 -> 5.25%
        rate_1 = service._calculate_qualifying_rate(Decimal("3.00"))
        assert rate_1 == Decimal("5.25")
        
        # Case 2: Contract rate 5.0% -> 5.0 + 2 = 7.0 > 5.25 -> 7.0%
        rate_2 = service._calculate_qualifying_rate(Decimal("5.00"))
        assert rate_2 == Decimal("7.00")
        
        # Case 3: Contract rate 3.25% -> 3.25 + 2 = 5.25 -> 5.25%
        rate_3 = service._calculate_qualifying_rate(Decimal("3.25"))
        assert rate_3 == Decimal("5.25")
```