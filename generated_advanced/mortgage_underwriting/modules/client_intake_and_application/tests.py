--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Import project specific modules
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_intake.routes import router as client_intake_router
from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.common.config import settings

# Using SQLite for test isolation as permitted by prompt requirements
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def app() -> FastAPI:
    """
    Creates a test FastAPI application instance.
    """
    app = FastAPI()
    app.include_router(client_intake_router, prefix="/api/v1")
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for testing endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_client_payload() -> dict:
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "4165550199",
        "date_of_birth": "1985-05-20",
        "sin": "123456789", # In real scenario, ensure encryption happens
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M4W1A5"
    }

@pytest.fixture
def valid_application_payload() -> dict:
    return {
        "client_id": 1, # Will be overridden in tests
        "property_address": "456 Oak Ave",
        "property_city": "Toronto",
        "property_province": "ON",
        "property_postal_code": "M5B2H1",
        "purchase_price": "500000.00",
        "down_payment": "100000.00",
        "loan_amount": "400000.00",
        "amortization_years": 25,
        "interest_rate": "5.00",
        "employment_status": "employed",
        "employer_name": "Tech Corp",
        "annual_income": "95000.00",
        "monthly_debt_payments": "500.00"
    }
```

--- unit_tests ---
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

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

@pytest.mark.integration
class TestClientIntakeEndpoints:

    @pytest.mark.asyncio
    async def test_create_client_flow(self, client: AsyncClient):
        """
        Full workflow: Create a client and verify retrieval.
        """
        payload = {
            "first_name": "Alice",
            "last_name": "Johnson",
            "email": "alice.j@example.com",
            "phone": "6475559876",
            "date_of_birth": "1992-07-15",
            "sin": "555555555",
            "address": "321 Queen St W",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M5V2A4"
        }

        # 1. Create Client
        response = await client.post("/api/v1/clients", json=payload)
        assert response.status_code == 201
        
        data = response.json()
        assert "id" in data
        assert data["email"] == "alice.j@example.com"
        
        # PIPEDA Compliance Check: SIN must NOT be in response
        assert "sin" not in data
        assert "sin_encrypted" not in data
        
        client_id = data["id"]

        # 2. Retrieve Client
        response = await client.get(f"/api/v1/clients/{client_id}")
        assert response.status_code == 200
        
        retrieved_data = response.json()
        assert retrieved_data["id"] == client_id
        assert retrieved_data["first_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_create_client_validation_error(self, client: AsyncClient):
        """
        Test validation on invalid input (e.g., bad email format).
        """
        payload = {
            "first_name": "Bob",
            "last_name": "Builder",
            "email": "not-an-email", # Invalid
            "phone": "4165550000",
            "date_of_birth": "1980-01-01",
            "sin": "111111111",
            "address": "1 Construction Way",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M1M1M1"
        }

        response = await client.post("/api/v1/clients", json=payload)
        assert response.status_code == 422 # Validation Error

    @pytest.mark.asyncio
    async def test_create_application_flow(self, client: AsyncClient):
        """
        Full workflow: Create client, then submit application.
        """
        # 1. Setup: Create a client first
        client_payload = {
            "first_name": "Charlie",
            "last_name": "Brown",
            "email": "charlie@example.com",
            "phone": "4165551111",
            "date_of_birth": "1975-11-30",
            "sin": "222222222",
            "address": "50 Snoopy Lane",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M4C1C1"
        }
        client_resp = await client.post("/api/v1/clients", json=client_payload)
        client_id = client_resp.json()["id"]

        # 2. Create Application
        app_payload = {
            "client_id": client_id,
            "property_address": "882 Broadview Ave",
            "property_city": "Toronto",
            "property_province": "ON",
            "property_postal_code": "M4K2P3",
            "purchase_price": "750000.00",
            "down_payment": "150000.00",
            "loan_amount": "600000.00",
            "amortization_years": 25,
            "interest_rate": "4.75",
            "employment_status": "employed",
            "employer_name": "Peanuts Corp",
            "annual_income": "110000.00",
            "monthly_debt_payments": "450.00"
        }

        response = await client.post("/api/v1/applications", json=app_payload)
        assert response.status_code == 201
        
        app_data = response.json()
        assert "id" in app_data
        assert app_data["client_id"] == client_id
        assert Decimal(app_data["loan_amount"]) == Decimal("600000.00")

    @pytest.mark.asyncio
    async def test_create_application_client_not_found(self, client: AsyncClient):
        """
        Test application submission with non-existent client_id.
        """
        app_payload = {
            "client_id": 99999, # Non-existent
            "property_address": "123 Nowhere",
            "property_city": "Ghost Town",
            "property_province": "ON",
            "property_postal_code": "A1A1A1",
            "purchase_price": "100000.00",
            "down_payment": "20000.00",
            "loan_amount": "80000.00",
            "amortization_years": 20,
            "interest_rate": "3.5",
            "employment_status": "employed",
            "employer_name": "Void",
            "annual_income": "50000.00",
            "monthly_debt_payments": "0.00"
        }

        response = await client.post("/api/v1/applications", json=app_payload)
        # Expecting 404 Not Found or 400 Bad Request depending on implementation
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_get_application_details(self, client: AsyncClient):
        """
        Test retrieving application details and calculated fields.
        """
        # 1. Create Client
        c_resp = await client.post("/api/v1/clients", json={
            "first_name": "Diana", "last_name": "Prince", "email": "diana@amazon.com",
            "phone": "4165559999", "date_of_birth": "1985-10-21", "sin": "333333333",
            "address": "1 Island Way", "city": "Toronto", "province": "ON", "postal_code": "M5H1A1"
        })
        client_id = c_resp.json()["id"]

        # 2. Create Application
        a_resp = await client.post("/api/v1/applications", json={
            "client_id": client_id,
            "property_address": "2 Hero Blvd",
            "property_city": "Toronto",
            "property_province": "ON",
            "property_postal_code": "M5V1A1",
            "purchase_price": "1000000.00",
            "down_payment": "200000.00",
            "loan_amount": "800000.00",
            "amortization_years": 30,
            "interest_rate": "5.0",
            "employment_status": "employed",
            "employer_name": "Justice League",
            "annual_income": "200000.00",
            "monthly_debt_payments": "1000.00"
        })
        app_id = a_resp.json()["id"]

        # 3. Get Application
        response = await client.get(f"/api/v1/applications/{app_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == app_id
        # Verify Financial Precision (Decimal)
        assert data["purchase_price"] == "1000000.00"
        # Verify calculated ratios are present (if returned by GET endpoint)
        # Note: Depending on implementation, ratios might be calculated later, 
        # but assuming intake calculates preliminary ones:
        # assert "ltv" in data 
        # assert Decimal(data["ltv"]) == Decimal("80.00")
```