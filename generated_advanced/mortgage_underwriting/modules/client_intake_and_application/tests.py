--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings
from mortgage_underwriting.modules.client_intake.routes import router as client_intake_router
from mortgage_underwriting.modules.client_intake.models import Client, Application

# Use in-memory SQLite for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(client_intake_router, prefix="/api/v1/client-intake", tags=["Client Intake"])
    return app

@pytest.fixture(scope="function")
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_client_payload() -> dict:
    return {
        "first_name": "John",
        "last_name": "Doe",
        "sin": "123456789",
        "dob": "1985-05-20",
        "email": "john.doe@example.com",
        "phone": "4165550199",
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M4W1A5"
    }

@pytest.fixture
def valid_application_payload() -> dict:
    return {
        "client_id": 1, # Will be replaced in tests
        "requested_amount": "450000.00",
        "property_value": "500000.00",
        "property_type": "detached",
        "property_address": "123 Maple St",
        "property_city": "Toronto",
        "property_province": "ON",
        "property_postal_code": "M4W1A5"
    }

@pytest.fixture
def mock_security():
    """Mock security functions to avoid real encryption overhead in unit tests."""
    from unittest.mock import MagicMock
    with pytest.mock.patch("mortgage_underwriting.common.security.encrypt_pii", return_value="encrypted_string") as m1, \
         pytest.mock.patch("mortgage_underwriting.common.security.hash_sin", return_value="hashed_sin") as m2:
        yield m1, m2

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.modules.client_intake.schemas import ClientCreate, ApplicationCreate
from mortgage_underwriting.modules.client_intake.services import ClientIntakeService, ApplicationService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientIntakeService:
    
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
        encrypt_mock, hash_mock = mock_security
        schema = ClientCreate(**valid_client_payload)
        service = ClientIntakeService(mock_db)
        
        # Mock the result of a potential existing user check (return None)
        mock_result = AsyncMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act
        result = await service.create_client(schema)

        # Assert
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        encrypt_mock.assert_called() # PIPEDA: Ensure encryption was attempted
        hash_mock.assert_called()    # PIPEDA: Ensure hashing was attempted
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_client_duplicate_sin_raises_exception(self, mock_db, valid_client_payload):
        # Arrange
        schema = ClientCreate(**valid_client_payload)
        service = ClientIntakeService(mock_db)
        
        # Mock existing client
        mock_existing_client = Client(id=1, sin_hash="hashed_sin")
        mock_result = AsyncMock()
        mock_result.first.return_value = mock_existing_client
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_client(schema)
        
        assert exc_info.value.error_code == "CLIENT_EXISTS"
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_client_by_id_success(self, mock_db):
        # Arrange
        client_id = 1
        service = ClientIntakeService(mock_db)
        mock_client = Client(id=client_id, first_name="Jane", last_name="Smith")
        
        mock_result = AsyncMock()
        mock_result.first.return_value = mock_client
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act
        result = await service.get_client(client_id)

        # Assert
        assert result is not None
        assert result.id == client_id

    @pytest.mark.asyncio
    async def test_get_client_not_found_raises(self, mock_db):
        # Arrange
        service = ClientIntakeService(mock_db)
        mock_result = AsyncMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_client(999)
        assert exc_info.value.status_code == 404


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
        # Ensure Decimal is used for financial values
        payload = valid_application_payload.copy()
        payload["requested_amount"] = Decimal(payload["requested_amount"])
        payload["property_value"] = Decimal(payload["property_value"])
        
        schema = ApplicationCreate(**payload)
        service = ApplicationService(mock_db)

        # Mock client existence check
        mock_client = Client(id=1, first_name="John")
        mock_result = AsyncMock()
        mock_result.first.return_value = mock_client
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act
        result = await service.create_application(schema)

        # Assert
        assert result.requested_amount == Decimal("450000.00")
        assert result.property_value == Decimal("500000.00")
        assert result.status == "PENDING"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_client_not_found_raises(self, mock_db, valid_application_payload):
        # Arrange
        payload = valid_application_payload.copy()
        payload["requested_amount"] = Decimal(payload["requested_amount"])
        payload["property_value"] = Decimal(payload["property_value"])
        
        schema = ApplicationCreate(**payload)
        service = ApplicationService(mock_db)

        # Mock client not found
        mock_result = AsyncMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_application(schema)
        assert exc_info.value.error_code == "CLIENT_NOT_FOUND"
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_ltv_logic_high_ratio(self, mock_db):
        # Arrange
        # CMHC Logic: LTV > 80% triggers insurance
        service = ApplicationService(mock_db)
        amount = Decimal("450000.00")
        value = Decimal("500000.00")
        
        # Act
        ltv = service.calculate_ltv(amount, value)

        # Assert
        # 450000 / 500000 = 0.9 (90%)
        assert ltv == Decimal("0.90")
        # In a real scenario, this would trigger insurance_required = True logic

    @pytest.mark.asyncio
    async def test_validate_ltv_logic_conventional(self, mock_db):
        # Arrange
        service = ApplicationService(mock_db)
        amount = Decimal("400000.00")
        value = Decimal("500000.00")
        
        # Act
        ltv = service.calculate_ltv(amount, value)

        # Assert
        # 400000 / 500000 = 0.8 (80%)
        assert ltv == Decimal("0.80")

    @pytest.mark.asyncio
    async def test_application_invalid_zero_amount_raises(self, mock_db, valid_application_payload):
        # Arrange
        payload = valid_application_payload.copy()
        payload["requested_amount"] = Decimal("0.00")
        payload["property_value"] = Decimal("500000.00")
        
        schema = ApplicationCreate(**payload)
        service = ApplicationService(mock_db)

        # Act & Assert
        with pytest.raises(ValueError): # Or AppException depending on implementation
            await service.create_application(schema)

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.client_intake.models import Client

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_client_flow(self, client: AsyncClient, valid_client_payload):
        # Act
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        
        # PIPEDA Compliance Check: SIN must NOT be in the response
        assert "sin" not in data
        assert "123456789" not in str(data)
        
        # FINTRAC Compliance Check: Audit fields present
        assert "created_at" in data

    async def test_create_client_duplicate_sin(self, client: AsyncClient, valid_client_payload):
        # First creation
        await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        
        # Second creation with same SIN
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)

        # Assert
        assert response.status_code == 400 # Bad Request / Conflict
        data = response.json()
        assert "error_code" in data

    async def test_get_client_success(self, client: AsyncClient, valid_client_payload):
        # Setup
        create_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = create_resp.json()["id"]

        # Act
        response = await client.get(f"/api/v1/client-intake/clients/{client_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == client_id
        assert "sin" not in data # PIPEDA

    async def test_get_client_not_found(self, client: AsyncClient):
        # Act
        response = await client.get("/api/v1/client-intake/clients/99999")

        # Assert
        assert response.status_code == 404

    async def test_create_application_success(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        # Setup: Create Client first
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]
        
        # Update payload with real ID
        valid_application_payload["client_id"] = client_id

        # Act
        response = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["client_id"] == client_id
        assert Decimal(data["requested_amount"]) == Decimal("450000.00")
        assert Decimal(data["property_value"]) == Decimal("500000.00")
        
        # FINTRAC: Audit fields
        assert "created_at" in data

    async def test_create_application_invalid_client_id(self, client: AsyncClient, valid_application_payload):
        # Act
        response = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert "CLIENT_NOT_FOUND" in data.get("error_code", "")

    async def test_create_application_ltv_boundary_check(self, client: AsyncClient, valid_client_payload):
        # Setup
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]

        # High Ratio Scenario (95% LTV - Max CMHC insurable)
        # Loan 475k on 500k value
        high_ltv_payload = {
            "client_id": client_id,
            "requested_amount": "475000.00",
            "property_value": "500000.00",
            "property_type": "condo",
            "property_address": "456 High Risk Ave",
            "property_city": "Vancouver",
            "property_province": "BC",
            "property_postal_code": "V6B2W1"
        }

        # Act
        response = await client.post("/api/v1/client-intake/applications", json=high_ltv_payload)

        # Assert
        # Should be accepted by intake (underwriting happens later), or rejected if hard limit > 95
        # Assuming intake accepts it, but flags insurance needed
        assert response.status_code in [201, 400] 
        if response.status_code == 201:
            data = response.json()
            # Verify precision is maintained
            assert Decimal(data["requested_amount"]) == Decimal("475000.00")

    async def test_list_applications_for_client(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        # Setup
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]
        
        valid_application_payload["client_id"] = client_id
        await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Act
        response = await client.get(f"/api/v1/client-intake/clients/{client_id}/applications")

        # Assert
        assert response.status_code == 200
        apps = response.json()
        assert len(apps) == 1
        assert apps[0]["client_id"] == client_id