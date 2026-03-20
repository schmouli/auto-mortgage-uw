--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from unittest.mock import AsyncMock, MagicMock

# Assuming the project structure, we import the actual components
# If running in isolation, these might fail, but for the generated code context:
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_portal.routes import router as client_router
from mortgage_underwriting.modules.client_portal.models import Client, MortgageApplication
from mortgage_underwriting.modules.client_portal.schemas import ClientCreate, ApplicationCreate

# Test Database URL (In-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create async engine
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
AsyncTestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncTestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app() -> FastAPI:
    """
    Fixture for the FastAPI application instance.
    """
    app = FastAPI()
    app.include_router(client_router, prefix="/api/v1/portal", tags=["Client Portal"])
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for integration tests.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Data Fixtures ---

@pytest.fixture
def valid_client_payload() -> dict:
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone_number": "+14155552671",
        "date_of_birth": "1985-04-12",
        "sin": "123456789", # Will be mocked for encryption
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M5V1J1"
    }

@pytest.fixture
def valid_application_payload() -> dict:
    return {
        "client_id": 1, # Assumed ID from created client
        "property_value": Decimal("500000.00"),
        "down_payment": Decimal("100000.00"),
        "loan_amount": Decimal("400000.00"),
        "contract_rate": Decimal("4.50"),
        "amortization_years": 25,
        "annual_income": Decimal("120000.00"),
        "monthly_property_tax": Decimal("300.00"),
        "monthly_heating": Decimal("150.00"),
        "monthly_debts": Decimal("500.00")
    }

@pytest.fixture
def mock_security():
    """Mock security functions to avoid real encryption/hashing in tests."""
    with pytest.mock.patch("mortgage_underwriting.common.security.encrypt_pii", return_value="encrypted_string") as mock_enc, \
         pytest.mock.patch("mortgage_underwriting.common.security.hash_sin", return_value="hashed_sin") as mock_hash:
        yield {"encrypt": mock_enc, "hash": mock_hash}

--- unit_tests ---
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

--- integration_tests ---
import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.client_portal.models import Client, MortgageApplication
from mortgage_underwriting.modules.client_portal.schemas import ApplicationStatus

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_create_client_endpoint(client: AsyncClient):
    """
    Test creating a client via the API.
    PIPEDA Check: Ensure SIN is not returned in the response.
    """
    response = await client.post("/api/v1/portal/clients", json={
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice.smith@example.com",
        "phone_number": "+14155552672",
        "date_of_birth": "1990-05-20",
        "sin": "987654321",
        "address": "456 Oak Ave",
        "city": "Vancouver",
        "province": "BC",
        "postal_code": "V6C1G1"
    })

    assert response.status_code == 201
    data = response.json()
    
    assert data["id"] > 0
    assert data["first_name"] == "Alice"
    assert data["email"] == "alice.smith@example.com"
    
    # CRITICAL: PIPEDA Compliance - SIN must never be returned
    assert "sin" not in data
    assert "sin_hash" not in data # Internal field should not leak


async def test_create_duplicate_client_returns_error(client: AsyncClient):
    payload = {
        "first_name": "Bob",
        "last_name": "Jones",
        "email": "bob@example.com",
        "phone_number": "+14155552673",
        "date_of_birth": "1980-01-01",
        "sin": "111222333",
        "address": "789 Pine St",
        "city": "Montreal",
        "province": "QC",
        "postal_code": "H2X1Y1"
    }

    # First request
    response1 = await client.post("/api/v1/portal/clients", json=payload)
    assert response1.status_code == 201

    # Second request (Duplicate)
    response2 = await client.post("/api/v1/portal/clients", json=payload)
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"].lower()


async def test_submit_application_workflow(client: AsyncClient, valid_client_payload, valid_application_payload):
    """
    Full workflow: Create Client -> Submit Application -> Verify Calculations.
    """
    # 1. Create Client
    client_resp = await client.post("/api/v1/portal/clients", json=valid_client_payload)
    assert client_resp.status_code == 201
    client_id = client_resp.json()["id"]

    # 2. Submit Application linked to client
    app_payload = valid_application_payload.copy()
    app_payload["client_id"] = client_id
    
    app_resp = await client.post("/api/v1/portal/applications", json=app_payload)
    assert app_resp.status_code == 201
    app_data = app_resp.json()

    # 3. Verify Response Data
    assert app_data["client_id"] == client_id
    assert app_data["status"] == "SUBMITTED"
    
    # Verify OSFI B-20 Stress Test Calculation
    # Contract 4.5 + 2 = 6.5 vs 5.25 -> 6.5
    assert app_data["qualifying_rate"] == "6.50"
    
    # Verify LTV
    assert app_data["ltv_ratio"] == "80.00"
    
    # Verify CMHC Insurance Logic (80% LTV usually doesn't require insurance depending on exact cut off, 
    # but logic says > 80%. Here it is exactly 80, so False)
    assert app_data["insurance_required"] is False

    # Verify Audit Trail (FINTRAC)
    assert "created_at" in app_data
    assert "updated_at" in app_data


async def test_get_application_status(client: AsyncClient, valid_client_payload, valid_application_payload):
    # Setup
    client_resp = await client.post("/api/v1/portal/clients", json=valid_client_payload)
    client_id = client_resp.json()["id"]
    
    app_payload = valid_application_payload.copy()
    app_payload["client_id"] = client_id
    app_resp = await client.post("/api/v1/portal/applications", json=app_payload)
    app_id = app_resp.json()["id"]

    # Get Status
    status_resp = await client.get(f"/api/v1/portal/applications/{app_id}")
    
    assert status_resp.status_code == 200
    data = status_resp.json()
    
    # Ensure financial precision is maintained
    assert Decimal(data["loan_amount"]) == Decimal("400000.00")
    assert data["status"] == "SUBMITTED"


async def test_submit_application_compliance_validation_gds(client: AsyncClient, valid_client_payload):
    """
    Test that the API rejects applications violating GDS > 39% rule.
    """
    # Create Client
    client_resp = await client.post("/api/v1/portal/clients", json=valid_client_payload)
    client_id = client_resp.json()["id"]

    # Submit High Risk Application (Low Income)
    bad_payload = {
        "client_id": client_id,
        "property_value": "600000.00",
        "down_payment": "120000.00",
        "loan_amount": "480000.00",
        "contract_rate": "5.00",
        "amortization_years": 25,
        "annual_income": "30000.00", # Very low
        "monthly_property_tax": "400.00",
        "monthly_heating": "200.00",
        "monthly_debts": "100.00"
    }

    response = await client.post("/api/v1/portal/applications", json=bad_payload)
    
    # Should return 400 or 422 depending on how exception is mapped
    assert response.status_code == 400
    assert "GDS" in response.json()["detail"]


async def test_piipa_data_leak_prevention(client: AsyncClient, db_session):
    """
    Verify that even if we query the DB directly or via API, PII fields are handled.
    This is a safety check for the API layer.
    """
    # Create a client directly in DB for testing retrieval
    new_client = Client(
        first_name="Test",
        last_name="User",
        email="test@test.com",
        sin="encrypted_sin_value", # Mocked encrypted value
        sin_hash="hash123",
        date_of_birth="1990-01-01"
    )
    db_session.add(new_client)
    await db_session.commit()
    await db_session.refresh(new_client)

    # Fetch via API
    response = await client.get(f"/api/v1/portal/clients/{new_client.id}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Explicitly check that raw SIN is absent
    assert "sin" not in data
    # Check that raw DOB is absent (PIPEDA minimization/logging risk)
    # Note: Depending on business requirement, DOB might be needed for verification, 
    # but usually masked. Assuming strict PIPEDA here.
    assert "date_of_birth" not in data or data["date_of_birth"] != "1990-01-01"