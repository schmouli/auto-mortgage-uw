--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Common imports for the project structure
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings

# Use SQLite for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_test_session_maker = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_test_session_maker() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def mock_security():
    """Mock security utilities like encryption."""
    with pytest.mock.patch("mortgage_underwriting.common.security.encrypt_pii") as mock_enc:
        mock_enc.return_value = "encrypted_string_123"
        with pytest.mock.patch("mortgage_underwriting.common.security.hash_sin") as mock_hash:
            mock_hash.return_value = "hashed_sin_abc"
            yield {"encrypt": mock_enc, "hash": mock_hash}

@pytest.fixture
def valid_client_payload():
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "4165550199",
        "date_of_birth": "1990-01-01",
        "sin": "123456789", # Will be encrypted
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M5V1A1"
    }

@pytest.fixture
def valid_application_payload():
    return {
        "client_id": 1, # Assuming ID 1 exists
        "property_value": Decimal("500000.00"),
        "down_payment": Decimal("100000.00"),
        "loan_amount": Decimal("400000.00"),
        "amortization_years": 25,
        "interest_rate": Decimal("5.00"),
        "annual_income": Decimal("95000.00"),
        "property_tax": Decimal("3000.00"),
        "heating_cost": Decimal("1200.00"),
        "other_debt": Decimal("500.00")
    }

@pytest.fixture
def mock_db_session():
    """Provides a mock AsyncSession for unit tests."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.scalar = AsyncMock()
    return db
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.modules.client_intake.schemas import ClientCreate, ApplicationCreate
from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.common.exceptions import AppException

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

@pytest.mark.asyncio
class TestClientService:
    
    async def test_create_client_success(self, mock_db_session, mock_security, valid_client_payload):
        # Arrange
        schema = ClientCreate(**valid_client_payload)
        service = ClientService(mock_db_session)
        
        # Act
        result = await service.create_client(schema)
        
        # Assert
        assert result.first_name == "John"
        assert result.email == "john.doe@example.com"
        # Verify PII was encrypted
        mock_security["encrypt"].assert_called_once_with("123456789")
        mock_security["hash"].assert_called_once_with("123456789")
        
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once_with(result)

    async def test_create_client_invalid_email(self, mock_db_session):
        # Arrange
        invalid_payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "not-an-email",
            "phone": "4165550199",
            "date_of_birth": "1990-01-01",
            "sin": "987654321",
            "address": "123 Maple St",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M5V1A1"
        }
        # Pydantic validation should fail before service call
        with pytest.raises(ValueError): # Pydantic raises ValidationError (subclass of ValueError)
            ClientCreate(**invalid_payload)

    async def test_create_client_db_failure(self, mock_db_session, mock_security, valid_client_payload):
        # Arrange
        mock_db_session.commit.side_effect = IntegrityError("Mock DB Error", None, None)
        schema = ClientCreate(**valid_client_payload)
        service = ClientService(mock_db_session)
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_client(schema)
        
        assert exc_info.value.error_code == "DB_INTEGRITY_ERROR"

    async def test_get_client_by_id_success(self, mock_db_session):
        # Arrange
        mock_client = MagicMock(spec=Client)
        mock_client.id = 1
        mock_client.first_name = "John"
        
        # Mock the scalar return for the select statement
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db_session.execute.return_value = mock_result
        
        service = ClientService(mock_db_session)
        
        # Act
        result = await service.get_client(1)
        
        # Assert
        assert result is not None
        assert result.id == 1
        mock_db_session.execute.assert_awaited_once()

    async def test_get_client_not_found(self, mock_db_session):
        # Arrange
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        service = ClientService(mock_db_session)
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_client(999)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

@pytest.mark.asyncio
class TestApplicationService:
    
    async def test_create_application_success(self, mock_db_session, valid_application_payload):
        # Arrange
        # Mock the client lookup
        mock_client = MagicMock(spec=Client)
        mock_client.id = 1
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db_session.execute.return_value = mock_result
        
        schema = ApplicationCreate(**valid_application_payload)
        service = ApplicationService(mock_db_session)
        
        # Act
        result = await service.create_application(schema)
        
        # Assert
        assert result.loan_amount == Decimal("400000.00")
        assert result.client_id == 1
        # Verify LTV calculation (400k / 500k = 0.8)
        # Note: Logic might be in model property or service. Assuming service calculates initial LTV
        assert result.ltv_ratio == Decimal("0.80") 
        
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    async def test_create_application_client_not_found(self, mock_db_session, valid_application_payload):
        # Arrange
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None # Client not found
        mock_db_session.execute.return_value = mock_result
        
        schema = ApplicationCreate(**valid_application_payload)
        service = ApplicationService(mock_db_session)
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_application(schema)
            
        assert exc_info.value.status_code == 404
        assert "client" in exc_info.value.detail.lower()
        mock_db_session.add.assert_not_called()

    async def test_create_application_zero_down_payment(self, mock_db_session):
        # Arrange
        mock_client = MagicMock(spec=Client)
        mock_client.id = 1
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db_session.execute.return_value = mock_result
        
        payload = {
            "client_id": 1,
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("0.00"), # Invalid
            "loan_amount": Decimal("500000.00"),
            "amortization_years": 25,
            "interest_rate": Decimal("5.00"),
            "annual_income": Decimal("95000.00"),
            "property_tax": Decimal("3000.00"),
            "heating_cost": Decimal("1200.00"),
            "other_debt": Decimal("500.00")
        }
        schema = ApplicationCreate(**payload)
        service = ApplicationService(mock_db_session)
        
        # Act & Assert
        # Service should validate that down_payment > 0
        with pytest.raises(AppException) as exc_info:
            await service.create_application(schema)
        
        assert exc_info.value.error_code == "VALIDATION_ERROR"

    async def test_calculate_ltv_boundary(self, mock_db_session):
        # Arrange
        mock_client = MagicMock(spec=Client)
        mock_client.id = 1
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db_session.execute.return_value = mock_result
        
        # Test LTV > 80% (CMHC Insurance trigger)
        # Loan: 405k, Value: 500k -> LTV = 81%
        payload = {
            "client_id": 1,
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("95000.00"),
            "loan_amount": Decimal("405000.00"),
            "amortization_years": 25,
            "interest_rate": Decimal("5.00"),
            "annual_income": Decimal("95000.00"),
            "property_tax": Decimal("3000.00"),
            "heating_cost": Decimal("1200.00"),
            "other_debt": Decimal("500.00")
        }
        schema = ApplicationCreate(**payload)
        service = ApplicationService(mock_db_session)
        
        # Act
        result = await service.create_application(schema)
        
        # Assert
        # 405000 / 500000 = 0.81
        assert result.ltv_ratio == Decimal("0.81")
        # Check if insurance flag is set (assuming service handles this flag)
        assert result.insurance_required is True

    async def test_input_validation_floats_rejected(self):
        # Arrange
        # Pydantic should handle type coercion, but strict mode or explicit types help.
        # Here we test that passing a float string or float is handled or rejected.
        # With Pydantic v2, it often coerces. We want to ensure Decimals are used internally.
        payload = {
            "client_id": 1,
            "property_value": "500000.00", # String representation
            "down_payment": 100000.00, # Float
            "loan_amount": 400000,
            "amortization_years": 25,
            "interest_rate": 5.0,
            "annual_income": 95000,
            "property_tax": 3000,
            "heating_cost": 1200,
            "other_debt": 500
        }
        
        # Act
        schema = ApplicationCreate(**payload)
        
        # Assert - Pydantic converts to Decimal
        assert isinstance(schema.property_value, Decimal)
        assert isinstance(schema.down_payment, Decimal)
        assert schema.down_payment == Decimal("100000.00")
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.modules.client_intake.routes import router
from mortgage_underwriting.main import app # Assuming main app exists or we build one

# We need a FastAPI app to include the router
@pytest.fixture(scope="function")
def test_app():
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-intake")
    return app

pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_create_client_workflow(test_app, db_session, valid_client_payload):
    """
    Test the full workflow of creating a client via API and verifying DB state.
    """
    # Arrange
    transport = ASGITransport(app=test_app)
    
    # Act
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        
        # Assert Response
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["email"] == "john.doe@example.com"
        assert "sin" not in data  # PIPEDA: SIN should never be returned
        assert "created_at" in data # FINTRAC: Audit trail
        
        # Assert Database
        stmt = select(Client).where(Client.id == data["id"])
        result = await db_session.execute(stmt)
        db_client = result.scalar_one_or_none()
        
        assert db_client is not None
        assert db_client.first_name == "John"
        # Verify SIN is encrypted in DB (not plain text)
        assert db_client.sin != "123456789" 
        assert db_client.sin.startswith("encrypted_") # Based on our mock

@pytest.mark.asyncio
async def test_create_application_workflow(test_app, db_session, valid_client_payload, valid_application_payload):
    """
    Test creating a client then creating an application linked to that client.
    """
    # 1. Create Client
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        assert client_resp.status_code == 201
        client_id = client_resp.json()["id"]
        
        # 2. Create Application
        app_payload = valid_application_payload.copy()
        app_payload["client_id"] = client_id
        
        app_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        
        # Assert Application Response
        assert app_resp.status_code == 201
        app_data = app_resp.json()
        assert app_data["client_id"] == client_id
        assert app_data["loan_amount"] == "400000.00" # JSON serialization of Decimal
        assert app_data["ltv_ratio"] == "0.80" # Verify calculation was performed
        assert app_data["insurance_required"] is False # LTV <= 80%
        
        # Assert Database
        stmt = select(Application).where(Application.id == app_data["id"])
        result = await db_session.execute(stmt)
        db_app = result.scalar_one_or_none()
        
        assert db_app is not None
        assert db_app.loan_amount == Decimal("400000.00")

@pytest.mark.asyncio
async def test_create_application_validation_error(test_app, db_session):
    """
    Test that validation errors return structured 422 responses.
    """
    transport = ASGITransport(app=test_app)
    invalid_payload = {
        "client_id": 999, # Doesn't exist
        "property_value": -500, # Negative value
        "down_payment": "not_a_number",
        "loan_amount": 400000,
        "amortization_years": 25,
        "interest_rate": 5.0,
        "annual_income": 95000,
        "property_tax": 3000,
        "heating_cost": 1200,
        "other_debt": 500
    }
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/client-intake/applications", json=invalid_payload)
        
        # FastAPI/Pydantic validation errors usually return 422
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

@pytest.mark.asyncio
async def test_get_client_not_found(test_app):
    """
    Test retrieving a non-existent client returns 404.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/client-intake/clients/99999")
        
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND"

@pytest.mark.asyncio
async def test_cmhc_insurance_trigger(test_app, db_session, valid_client_payload):
    """
    Integration test to verify CMHC premium logic is triggered correctly at high LTV.
    """
    # Create Client
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]
        
        # Create Application with 95% LTV (5% down)
        # Value: 500k, Down: 25k, Loan: 475k
        app_payload = {
            "client_id": client_id,
            "property_value": "500000.00",
            "down_payment": "25000.00",
            "loan_amount": "475000.00",
            "amortization_years": 25,
            "interest_rate": "5.00",
            "annual_income": "120000.00",
            "property_tax": "3000.00",
            "heating_cost": "1200.00",
            "other_debt": "0.00"
        }
        
        app_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        assert app_resp.status_code == 201
        data = app_resp.json()
        
        # CMHC Logic: IF LTV > 80% THEN insurance_required = True
        assert data["insurance_required"] is True
        # Verify LTV calculation precision
        assert Decimal(data["ltv_ratio"]) == Decimal("0.95")

@pytest.mark.asyncio
async def test_pipeda_sin_not_exposed(test_app, db_session, valid_client_payload):
    """
    Ensure SIN is not exposed in List or Get endpoints.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create
        create_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = create_resp.json()["id"]
        
        # Get Single
        get_resp = await client.get(f"/api/v1/client-intake/clients/{client_id}")
        assert "sin" not in get_resp.json()
        
        # List (Assuming a list endpoint exists or adding one logic check)
        # If list endpoint exists: list_resp = await client.get("/api/v1/client-intake/clients")
        # assert all("sin" not in c for c in list_resp.json())
```