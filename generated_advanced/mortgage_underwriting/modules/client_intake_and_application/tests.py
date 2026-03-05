--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from unittest.mock import AsyncMock, MagicMock

# Mock models and schemas to avoid import errors if module doesn't exist yet in the environment
# In a real scenario, these would be imported from mortgage_underwriting.modules.client_intake
Base = declarative_base()

# Use in-memory SQLite for integration tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


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


@pytest.fixture
def app() -> FastAPI:
    """
    Creates a FastAPI app instance including the client_intake router.
    """
    from mortgage_underwriting.modules.client_intake.routes import router
    from mortgage_underwriting.common.database import get_async_session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-intake", tags=["Client Intake"])

    # Dependency override for testing
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for integration testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_security():
    """
    Mocks security functions to avoid actual encryption overhead during unit tests.
    """
    with pytest.mock.patch("mortgage_underwriting.common.security.encrypt_pii") as mock_enc, \
         pytest.mock.patch("mortgage_underwriting.common.security.hash_value") as mock_hash:
        mock_enc.return_value = "encrypted_string"
        mock_hash.return_value = "hashed_string"
        yield mock_enc, mock_hash


@pytest.fixture
def valid_client_payload():
    return {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-01",
        "sin": "123456789",
        "email": "john.doe@example.com",
        "phone_number": "+14155552671",
        "address": {
            "street": "123 Main St",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M5V1A1"
        }
    }

@pytest.fixture
def valid_application_payload():
    return {
        "client_id": 1, # Assumed existing client
        "property_value": "500000.00",
        "down_payment": "100000.00",
        "loan_amount": "400000.00",
        "amortization_years": 25,
        "interest_rate": "5.00",
        "income_monthly": "8000.00",
        "property_tax_monthly": "300.00",
        "heating_monthly": "150.00"
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

# Import paths based on project structure
from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.modules.client_intake.exceptions import (
    ClientNotFoundException,
    InvalidApplicationDataException,
    DuplicateClientException
)
from mortgage_underwriting.modules.client_intake.schemas import ClientCreate, ApplicationCreate

@pytest.mark.unit
class TestClientService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_create_client_success(self, mock_db, mock_security, valid_client_payload):
        # Arrange
        mock_enc, mock_hash = mock_security
        payload = ClientCreate(**valid_client_payload)
        
        # Mock the result of a potential duplicate check
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        
        service = ClientService(mock_db)

        # Act
        result = await service.create_client(payload)

        # Assert
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        # Verify SIN was encrypted
        assert result.sin == "encrypted_string"
        # Verify DOB was handled (and potentially encrypted based on implementation)
        assert result.date_of_birth == payload.date_of_birth
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_create_client_duplicate_sin(self, mock_db, valid_client_payload):
        # Arrange
        payload = ClientCreate(**valid_client_payload)
        
        # Mock DB returning an existing client (duplicate)
        mock_existing_client = MagicMock()
        mock_existing_client.id = 999
        mock_result = MagicMock()
        mock_result.first.return_value = mock_existing_client
        mock_db.execute.return_value = mock_result
        
        service = ClientService(mock_db)

        # Act & Assert
        with pytest.raises(DuplicateClientException) as exc_info:
            await service.create_client(payload)
        
        assert "already exists" in str(exc_info.value)
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_client_by_id_success(self, mock_db):
        # Arrange
        client_id = 1
        mock_client = MagicMock()
        mock_client.id = client_id
        mock_client.first_name = "Jane"
        
        mock_result = MagicMock()
        mock_result.first.return_value = mock_client
        mock_db.execute.return_value = mock_result
        
        service = ClientService(mock_db)

        # Act
        result = await service.get_client(client_id)

        # Assert
        assert result.id == client_id
        assert result.first_name == "Jane"

    @pytest.mark.asyncio
    async def test_get_client_not_found(self, mock_db):
        # Arrange
        client_id = 999
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        
        service = ClientService(mock_db)

        # Act & Assert
        with pytest.raises(ClientNotFoundException):
            await service.get_client(client_id)


@pytest.mark.unit
class TestApplicationService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_create_application_success(self, mock_db, valid_application_payload):
        # Arrange
        payload = ApplicationCreate(**valid_application_payload)
        
        # Mock client lookup
        mock_client = MagicMock()
        mock_client.id = 1
        mock_client.first_name = "John"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute.return_value = mock_result
        
        service = ApplicationService(mock_db)

        # Act
        result = await service.create_application(payload)

        # Assert
        assert result.loan_amount == Decimal("400000.00")
        assert result.client_id == 1
        # Ensure Decimal type is preserved
        assert isinstance(result.loan_amount, Decimal)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_client_not_found(self, mock_db, valid_application_payload):
        # Arrange
        payload = ApplicationCreate(**valid_application_payload)
        
        # Mock client lookup returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        service = ApplicationService(mock_db)

        # Act & Assert
        with pytest.raises(ClientNotFoundException):
            await service.create_application(payload)

    @pytest.mark.asyncio
    async def test_create_application_invalid_ltv(self, mock_db, valid_application_payload):
        # Arrange
        # Modify payload to have 0 down payment (100% LTV), which should fail validation
        invalid_payload = valid_application_payload.copy()
        invalid_payload["down_payment"] = "0.00"
        invalid_payload["loan_amount"] = "500000.00"
        
        payload = ApplicationCreate(**invalid_payload)
        
        # Mock client lookup (pass validation to fail logic)
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute.return_value = mock_result
        
        service = ApplicationService(mock_db)

        # Act & Assert
        # Assuming service validates LTV logic (e.g., max 95%)
        with pytest.raises(InvalidApplicationDataException) as exc_info:
            await service.create_application(payload)
        
        assert "LTV" in str(exc_info.value) or "Loan to Value" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_gds_tds_logic(self, mock_db):
        # Arrange
        # Test the calculation logic helper (if exposed or part of create)
        # GDS = (PIT + Heat) / Income
        # TDS = (PIT + Heat + Other) / Income
        
        income = Decimal("5000.00")
        mortgage_payment = Decimal("1500.00")
        property_tax = Decimal("300.00")
        heating = Decimal("100.00")
        other_debt = Decimal("500.00")
        
        service = ApplicationService(mock_db)
        
        # Act
        gds = service._calculate_gds(mortgage_payment, property_tax, heating, income)
        tds = service._calculate_tds(mortgage_payment, property_tax, heating, other_debt, income)
        
        # Assert
        # (1500 + 300 + 100) / 5000 = 1900 / 5000 = 0.38 (38%)
        assert gds == Decimal("0.38")
        # (1900 + 500) / 5000 = 2400 / 5000 = 0.48 (48%)
        assert tds == Decimal("0.48")

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.client_intake.models import Client, Application

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_client_endpoint_success(self, client: AsyncClient, valid_client_payload):
        # Act
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        # PIPEDA Compliance Check: SIN must NOT be in response
        assert "sin" not in data
        assert "date_of_birth" not in data # Usually PII, check requirements
        assert "created_at" in data

    async def test_create_client_validation_error(self, client: AsyncClient):
        # Arrange - Invalid Email
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "not-an-email",
            "sin": "123"
        }

        # Act
        response = await client.post("/api/v1/client-intake/clients", json=payload)

        # Assert
        assert response.status_code == 422 # Unprocessable Entity

    async def test_get_client_endpoint_success(self, client: AsyncClient, valid_client_payload):
        # Arrange - Create a client first
        create_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = create_resp.json()["id"]

        # Act
        get_resp = await client.get(f"/api/v1/client-intake/clients/{client_id}")

        # Assert
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == client_id
        assert "sin" not in data

    async def test_get_client_not_found(self, client: AsyncClient):
        # Act
        response = await client.get("/api/v1/client-intake/clients/99999")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_create_application_endpoint_success(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        # Arrange - Create a client first
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]
        
        # Update application payload with the new client ID
        valid_application_payload["client_id"] = client_id

        # Act
        app_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Assert
        assert app_resp.status_code == 201
        data = app_resp.json()
        assert "id" in data
        assert data["client_id"] == client_id
        # Financial fields should be strings in JSON
        assert data["loan_amount"] == "400000.00"
        assert data["property_value"] == "500000.00"
        # Check LTV calculation (100k / 500k = 20%)
        assert data["ltv_percentage"] == "20.00"

    async def test_create_application_non_existent_client(self, client: AsyncClient, valid_application_payload):
        # Arrange
        valid_application_payload["client_id"] = 99999

        # Act
        response = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Assert
        assert response.status_code == 404
        assert "client" in response.json()["detail"].lower()

    async def test_create_application_high_ltv_rejection(self, client: AsyncClient, valid_client_payload):
        # Arrange
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]

        # Create payload with 0 down payment (100% LTV) - should be rejected
        payload = {
            "client_id": client_id,
            "property_value": "500000.00",
            "down_payment": "0.00", # Invalid
            "loan_amount": "500000.00",
            "amortization_years": 25,
            "interest_rate": "5.00",
            "income_monthly": "10000.00",
            "property_tax_monthly": "300.00",
            "heating_monthly": "150.00"
        }

        # Act
        response = await client.post("/api/v1/client-intake/applications", json=payload)

        # Assert
        # Depending on implementation, could be 422 (validation) or 400 (business logic)
        assert response.status_code in [400, 422]

    async def test_workflow_intake_to_application(self, client: AsyncClient):
        # Full workflow test
        
        # 1. Create Client
        client_payload = {
            "first_name": "Alice",
            "last_name": "Smith",
            "date_of_birth": "1985-05-15",
            "sin": "987654321",
            "email": "alice@example.com",
            "phone_number": "+14155552672",
            "address": {
                "street": "456 Elm St",
                "city": "Vancouver",
                "province": "BC",
                "postal_code": "V6A1A1"
            }
        }
        c_resp = await client.post("/api/v1/client-intake/clients", json=client_payload)
        assert c_resp.status_code == 201
        client_id = c_resp.json()["id"]

        # 2. Submit Application
        app_payload = {
            "client_id": client_id,
            "property_value": "800000.00",
            "down_payment": "160000.00", # 20% down
            "loan_amount": "640000.00",
            "amortization_years": 30,
            "interest_rate": "4.5",
            "income_monthly": "12000.00",
            "property_tax_monthly": "400.00",
            "heating_monthly": "200.00"
        }
        a_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        assert a_resp.status_code == 201
        app_data = a_resp.json()
        
        # 3. Verify Calculations
        # LTV: 640k / 800k = 80%
        assert app_data["ltv_percentage"] == "80.00"
        
        # 4. Retrieve Client's Applications (Assuming endpoint exists or check via DB)
        # For now, we verify the application ID exists
        app_id = app_data["id"]
        
        get_app = await client.get(f"/api/v1/client-intake/applications/{app_id}")
        assert get_app.status_code == 200
        assert get_app.json()["status"] == "SUBMITTED" # Default status