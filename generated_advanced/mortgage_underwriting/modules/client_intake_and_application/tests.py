--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import AsyncMock, MagicMock

# Assuming module name is 'client_intake'
from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_intake.schemas import (
    ClientCreate,
    ApplicationCreate,
    EmploymentInfo,
    AssetInfo
)

# Pytest Async Configuration
pytest_plugins = ('pytest_asyncio',)

# --- Test Data Fixtures ---

@pytest.fixture
def client_payload_dict() -> dict:
    """Valid payload for creating a client."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone_number": "+1-416-555-0199",
        "date_of_birth": "1985-05-20",
        "sin": "123456789",  # Should be encrypted before storage
        "address": {
            "street": "123 Maple Ave",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M4W1E5"
        }
    }

@pytest.fixture
def application_payload_dict(client_payload_dict: dict) -> dict:
    """Valid payload for creating a mortgage application."""
    return {
        "client_id": 1, # Placeholder, will be replaced in tests
        "property_address": "123 Maple Ave",
        "property_value": Decimal("750000.00"),
        "down_payment": Decimal("150000.00"),
        "loan_amount": Decimal("600000.00"),
        "employment": [
            {
                "employer_name": "Tech Corp",
                "position": "Senior Developer",
                "years_employed": 5,
                "annual_income": Decimal("120000.00")
            }
        ],
        "assets": [
            {
                "type": "Vehicle",
                "value": Decimal("25000.00"),
                "description": "2020 Honda Civic"
            }
        ]
    }

# --- Unit Test Mocks ---

@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock AsyncSession for unit tests."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session

@pytest.fixture
def mock_encryption_service():
    """Mock the security encryption functions."""
    with pytest.mock.patch('mortgage_underwriting.common.security.encrypt_pii') as mock_enc, \
         pytest.mock.patch('mortgage_underwriting.common.security.hash_value') as mock_hash:
        # Setup return values
        mock_enc.return_value = "encrypted_string_blob"
        mock_hash.return_value = "hashed_sin_value"
        yield mock_enc, mock_hash

# --- Integration Test Database ---

@pytest.fixture(scope="function")
async def test_engine():
    """Create an in-memory SQLite engine for integration tests."""
    # Using SQLite for speed in tests, though production is Postgres
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    yield engine
    await engine.dispose()

@pytest.fixture(scope="function")
async def test_db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session and create tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        # Cleanup is handled by engine disposal dropping the in-memory db

@pytest.fixture
def app():
    """Fixture to setup the FastAPI app for integration testing."""
    from fastapi import FastAPI
    from mortgage_underwriting.modules.client_intake.routes import router
    
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-intake", tags=["Client Intake"])
    return app

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.modules.client_intake.schemas import ClientCreate, ApplicationCreate
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientService:

    @pytest.mark.asyncio
    async def test_create_client_success(self, mock_db_session, mock_encryption_service, client_payload_dict):
        # Arrange
        mock_enc, mock_hash = mock_encryption_service
        payload = ClientCreate(**client_payload_dict)
        service = ClientService(mock_db_session)
        
        # Mock the DB refresh to return an object with an ID
        def mock_refresh(obj):
            obj.id = 1
            obj.created_at = "2023-01-01T00:00:00"
            
        mock_db_session.refresh.side_effect = mock_refresh

        # Act
        result = await service.create_client(payload)

        # Assert
        assert result.id == 1
        assert result.first_name == "John"
        assert result.email == "john.doe@example.com"
        # Ensure SIN was encrypted, not stored plain
        mock_enc.assert_called_once_with("123456789")
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_client_duplicate_email_raises(self, mock_db_session, mock_encryption_service, client_payload_dict):
        # Arrange
        payload = ClientCreate(**client_payload_dict)
        service = ClientService(mock_db_session)
        
        # Simulate DB integrity error (e.g., unique constraint violation)
        mock_db_session.commit.side_effect = IntegrityError("INSERT", {}, Exception())

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_client(payload)
        
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_client_by_id_success(self, mock_db_session):
        # Arrange
        service = ClientService(mock_db_session)
        mock_client = Client(
            id=1,
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            encrypted_sin="enc...",
            hashed_sin="hash...",
            date_of_birth="1990-01-01"
        )
        mock_db_session.scalar.return_value = mock_client

        # Act
        result = await service.get_client(1)

        # Assert
        assert result.first_name == "Jane"
        assert result.id == 1
        mock_db_session.scalar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_client_not_found_raises(self, mock_db_session):
        # Arrange
        service = ClientService(mock_db_session)
        mock_db_session.scalar.return_value = None

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_client(999)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

@pytest.mark.unit
class TestApplicationService:

    @pytest.mark.asyncio
    async def test_create_application_success(self, mock_db_session, application_payload_dict):
        # Arrange
        payload = ApplicationCreate(**application_payload_dict)
        service = ApplicationService(mock_db_session)
        
        # Mock Client existence check
        mock_client = Client(id=1, first_name="John", last_name="Doe", email="john@example.com", encrypted_sin="x", hashed_sin="y")
        mock_db_session.scalar.return_value = mock_client

        def mock_refresh(obj):
            obj.id = 101
            obj.created_at = "2023-01-01T00:00:00"
            
        mock_db_session.refresh.side_effect = mock_refresh

        # Act
        result = await service.create_application(payload)

        # Assert
        assert result.id == 101
        assert result.loan_amount == Decimal("600000.00")
        assert result.property_value == Decimal("750000.00")
        # Check Decimal precision is maintained
        assert result.down_payment == Decimal("150000.00")
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_client_not_found(self, mock_db_session, application_payload_dict):
        # Arrange
        payload = ApplicationCreate(**application_payload_dict)
        service = ApplicationService(mock_db_session)
        
        # Mock client not found
        mock_db_session.scalar.return_value = None

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_application(payload)
        
        assert exc_info.value.status_code == 404
        assert "client" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_application_invalid_ltv_logic(self, mock_db_session, application_payload_dict):
        # Arrange
        # Modify payload to make Down Payment > Property Value (Impossible LTV)
        invalid_payload = application_payload_dict.copy()
        invalid_payload['down_payment'] = Decimal("800000.00") # Higher than property value
        invalid_payload['loan_amount'] = Decimal("-50000.00") # Negative loan
        
        payload = ApplicationCreate(**invalid_payload)
        service = ApplicationService(mock_db_session)
        
        # Mock client exists
        mock_client = Client(id=1, first_name="John", last_name="Doe", email="john@example.com", encrypted_sin="x", hashed_sin="y")
        mock_db_session.scalar.return_value = mock_client

        # Act & Assert
        # The service should validate that Loan Amount + Down Payment = Property Value (approx) or basic logic
        # For this test, we assume validation happens in Pydantic or Service
        with pytest.raises(ValueError) as exc_info:
            await service.create_application(payload)
        
        assert "invalid financials" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_update_application_status(self, mock_db_session):
        # Arrange
        service = ApplicationService(mock_db_session)
        mock_app = Application(
            id=1,
            client_id=1,
            status="submitted",
            loan_amount=Decimal("100000.00"),
            property_value=Decimal("100000.00")
        )
        mock_db_session.scalar.return_value = mock_app

        # Act
        result = await service.update_status(application_id=1, new_status="under_review")

        # Assert
        assert result.status == "under_review"
        mock_db_session.commit.assert_awaited_once()

--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from decimal import Decimal

from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.common.database import get_async_session

# Helper to override DB dependency in tests
async def override_get_db(session):
    yield session

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_and_retrieve_client_workflow(self, app: FastAPI, test_db_session: AsyncSession):
        # Setup Override
        app.dependency_overrides[get_async_session] = lambda: override_get_db(test_db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 1: Create Client
            payload = {
                "first_name": "Alice",
                "last_name": "Wonderland",
                "email": "alice@test.com",
                "phone_number": "4165551234",
                "date_of_birth": "1992-02-02",
                "sin": "987654321",
                "address": {
                    "street": "456 Wonderland Rd",
                    "city": "Mississauga",
                    "province": "ON",
                    "postal_code": "L5B1C2"
                }
            }
            
            response = await client.post("/api/v1/client-intake/clients", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["email"] == "alice@test.com"
            assert data["created_at"] is not None
            # PIPEDA Compliance: SIN must NOT be in response
            assert "sin" not in data
            assert "987654321" not in str(data)
            
            client_id = data["id"]

            # Step 2: Retrieve Client
            response = await client.get(f"/api/v1/client-intake/clients/{client_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["first_name"] == "Alice"
            assert "sin" not in data # PIPEDA check again

        # Cleanup
        app.dependency_overrides.clear()

    async def test_create_application_workflow(self, app: FastAPI, test_db_session: AsyncSession):
        app.dependency_overrides[get_async_session] = lambda: override_get_db(test_db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Seed a client manually (or via endpoint, let's do endpoint for realism)
            client_payload = {
                "first_name": "Bob", "last_name": "Builder", "email": "bob@test.com",
                "phone_number": "9055559876", "date_of_birth": "1980-03-03", "sin": "111222333",
                "address": {"street": "789 Construction Way", "city": "Brampton", "province": "ON", "postal_code": "L6Y0E1"}
            }
            create_resp = await client.post("/api/v1/client-intake/clients", json=client_payload)
            client_id = create_resp.json()["id"]

            # 2. Create Application
            app_payload = {
                "client_id": client_id,
                "property_address": "789 Construction Way",
                "property_value": "500000.00",
                "down_payment": "100000.00",
                "loan_amount": "400000.00",
                "employment": [
                    {
                        "employer_name": "Self Employed",
                        "position": "Contractor",
                        "years_employed": 10,
                        "annual_income": "95000.00"
                    }
                ],
                "assets": []
            }
            
            response = await client.post("/api/v1/client-intake/applications", json=app_payload)
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["status"] == "submitted" # Default status
            assert Decimal(data["loan_amount"]) == Decimal("400000.00")
            assert data["created_at"] is not None # FINTRAC Audit trail

            # 3. Verify Application Retrieval
            app_id = data["id"]
            get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
            assert get_resp.status_code == 200
            app_data = get_resp.json()
            assert app_data["client_id"] == client_id

        app.dependency_overrides.clear()

    async def test_create_application_invalid_client_id(self, app: FastAPI, test_db_session: AsyncSession):
        app.dependency_overrides[get_async_session] = lambda: override_get_db(test_db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            app_payload = {
                "client_id": 9999, # Non-existent
                "property_address": "Nowhere",
                "property_value": "100.00",
                "down_payment": "10.00",
                "loan_amount": "90.00",
                "employment": [],
                "assets": []
            }
            
            response = await client.post("/api/v1/client-intake/applications", json=app_payload)
            
            assert response.status_code == 404
            assert "client" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    async def test_validation_error_missing_fields(self, app: FastAPI, test_db_session: AsyncSession):
        app.dependency_overrides[get_async_session] = lambda: override_get_db(test_db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing email and sin
            payload = {
                "first_name": "Incomplete",
                "last_name": "Data"
            }
            
            response = await client.post("/api/v1/client-intake/clients", json=payload)
            
            assert response.status_code == 422 # Validation Error
            
            errors = response.json()["detail"]
            error_fields = [e["loc"][1] for e in errors]
            assert "email" in error_fields
            assert "sin" in error_fields

        app.dependency_overrides.clear()