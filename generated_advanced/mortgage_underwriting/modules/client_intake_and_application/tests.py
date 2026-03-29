--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Assuming the project structure allows these imports
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_intake.routes import router
from mortgage_underwriting.modules.client_intake.models import Application

# Use in-memory SQLite for fast integration testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def engine() -> AsyncGenerator:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest.fixture(scope="function")
def app() -> FastAPI:
    """Create a test FastAPI app including the client intake router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-intake", tags=["Client Intake"])
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_application_payload() -> dict:
    """Standard valid payload for creating an application."""
    return {
        "borrower_first_name": "John",
        "borrower_last_name": "Doe",
        "borrower_email": "john.doe@example.com",
        "borrower_phone": "4165550199",
        "borrower_sin": "123456789", # Will be hashed
        "borrower_dob": "1985-05-15", # Will be encrypted
        "property_address": "123 Maple St, Toronto, ON",
        "property_value": "750000.00",
        "down_payment": "150000.00",
        "loan_amount": "600000.00",
        "income_annual": "120000.00",
        "employment_status": "employed",
        "credit_score": 750
    }

@pytest.fixture
def invalid_application_payload_missing_sin() -> dict:
    payload = {
        "borrower_first_name": "Jane",
        "borrower_last_name": "Smith",
        "borrower_email": "jane@example.com",
        "property_address": "456 Oak Ave, Vancouver, BC",
        "property_value": "500000.00",
        "down_payment": "100000.00",
        "loan_amount": "400000.00",
        "income_annual": "90000.00",
        "employment_status": "employed",
        "credit_score": 680
    }
    return payload

@pytest.fixture
def invalid_application_payload_negative_income() -> dict:
    payload = {
        "borrower_first_name": "Bob",
        "borrower_last_name": "Jones",
        "borrower_email": "bob@example.com",
        "borrower_sin": "987654321",
        "borrower_dob": "1990-01-01",
        "property_address": "789 Pine Rd, Montreal, QC",
        "property_value": "300000.00",
        "down_payment": "60000.00",
        "loan_amount": "240000.00",
        "income_annual": "-50000.00", # Invalid
        "employment_status": "employed",
        "credit_score": 700
    }
    return payload
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientIntakeService
from mortgage_underwriting.modules.client_intake.models import Application
from mortgage_underwriting.modules.client_intake.schemas import ApplicationCreate
from mortgage_underwriting.common.exceptions import AppException

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

@pytest.mark.asyncio
class TestClientIntakeService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def valid_payload_dict(self):
        return {
            "borrower_first_name": "Test",
            "borrower_last_name": "User",
            "borrower_email": "test@example.com",
            "borrower_sin": "123456789",
            "borrower_dob": "1990-01-01",
            "property_address": "1 Test St",
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("100000.00"),
            "loan_amount": Decimal("400000.00"),
            "income_annual": Decimal("80000.00"),
            "employment_status": "employed",
            "credit_score": 720
        }

    @pytest.fixture
    def application_create_schema(self, valid_payload_dict):
        return ApplicationCreate(**valid_payload_dict)

    async def test_create_application_success(self, mock_db, application_create_schema):
        """Test successful creation of an application."""
        # Mock the return value of refresh
        mock_app_instance = Application(id=1, status="DRAFT")
        mock_db.refresh.return_value = None
        mock_db.add.side_effect = lambda x: setattr(x, 'id', 1) # Simulate ID assignment

        service = ClientIntakeService(mock_db)
        
        result = await service.create_application(application_create_schema)

        # Verify DB interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        
        # Verify result
        assert result is not None
        assert result.borrower_first_name == "Test"
        assert result.status == "DRAFT"

    @patch('mortgage_underwriting.modules.client_intake.services.encrypt_pii')
    @patch('mortgage_underwriting.modules.client_intake.services.hash_value')
    async def test_create_application_sanitizes_pii(self, mock_hash, mock_encrypt, mock_db, application_create_schema):
        """Test that PII (SIN, DOB) is processed by security functions."""
        mock_hash.return_value = "hashed_sin_123"
        mock_encrypt.return_value = "encrypted_dob_456"
        
        service = ClientIntakeService(mock_db)
        await service.create_application(application_create_schema)

        # Verify security helpers were called
        mock_hash.assert_called_once_with("123456789")
        mock_encrypt.assert_called_once_with("1990-01-01")

    async def test_create_application_missing_sin_raises_validation_error(self, mock_db):
        """Test that missing SIN raises a validation error."""
        invalid_payload = {
            "borrower_first_name": "No",
            "borrower_last_name": "Sin",
            "borrower_email": "nosin@example.com",
            "property_address": "1 No Sin St",
            "property_value": Decimal("100000.00"),
            "down_payment": Decimal("20000.00"),
            "loan_amount": Decimal("80000.00"),
            "income_annual": Decimal("50000.00"),
            "employment_status": "employed",
            "credit_score": 700
        }
        
        # Pydantic validation should fail before service logic
        with pytest.raises(ValueError): # Or Pydantic ValidationError
            ApplicationCreate(**invalid_payload)

    async def test_create_application_negative_income_raises_error(self, mock_db):
        """Test that negative income is rejected."""
        invalid_payload = {
            "borrower_first_name": "Poor",
            "borrower_last_name": "User",
            "borrower_email": "poor@example.com",
            "borrower_sin": "111111111",
            "borrower_dob": "2000-01-01",
            "property_address": "2 Poor St",
            "property_value": Decimal("100000.00"),
            "down_payment": Decimal("20000.00"),
            "loan_amount": Decimal("80000.00"),
            "income_annual": Decimal("-5000.00"), # Invalid
            "employment_status": "employed",
            "credit_score": 600
        }

        with pytest.raises(ValueError):
             ApplicationCreate(**invalid_payload)

    async def test_get_application_by_id_success(self, mock_db):
        """Test retrieving an application by ID."""
        # Mock the result
        mock_app = Application(
            id=1, 
            borrower_first_name="Get", 
            borrower_last_name="Me",
            status="DRAFT"
        )
        
        # Setup mock execute result
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = mock_app
        mock_db.execute.return_value = result_mock

        service = ClientIntakeService(mock_db)
        result = await service.get_application_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.borrower_first_name == "Get"

    async def test_get_application_by_id_not_found(self, mock_db):
        """Test retrieving a non-existent application returns None."""
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        service = ClientIntakeService(mock_db)
        result = await service.get_application_by_id(999)

        assert result is None

    async def test_update_application_status_success(self, mock_db):
        """Test updating application status (e.g., Draft -> Submitted)."""
        mock_app = Application(id=1, status="DRAFT")
        
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = mock_app
        mock_db.execute.return_value = result_mock

        service = ClientIntakeService(mock_db)
        updated_app = await service.update_application_status(1, "SUBMITTED")

        assert updated_app.status == "SUBMITTED"
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    async def test_update_application_status_invalid_transition(self, mock_db):
        """Test that invalid status transitions are handled."""
        # Start with APPROVED (final state)
        mock_app = Application(id=1, status="APPROVED")
        
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = mock_app
        mock_db.execute.return_value = result_mock

        service = ClientIntakeService(mock_db)
        
        with pytest.raises(AppException) as exc_info:
            await service.update_application_status(1, "DRAFT")
        
        assert "Invalid status transition" in str(exc_info.value.detail)

    async def test_calculate_ltv_boundary_checks(self, mock_db):
        """Test LTV calculation logic within service if applicable (or helper)."""
        # Assuming service has a helper or logic to check LTV during creation
        payload = {
            "borrower_first_name": "LTV",
            "borrower_last_name": "Check",
            "borrower_email": "ltv@example.com",
            "borrower_sin": "555555555",
            "borrower_dob": "1985-05-05",
            "property_address": "3 LTV Ln",
            "property_value": Decimal("100000.00"),
            "down_payment": Decimal("5000.00"), # 95% LTV
            "loan_amount": Decimal("95000.00"),
            "income_annual": Decimal("100000.00"),
            "employment_status": "employed",
            "credit_score": 800
        }
        
        schema = ApplicationCreate(**payload)
        
        # If service validates max LTV (e.g., 95%)
        # This test assumes validation logic exists in service
        service = ClientIntakeService(mock_db)
        
        # Expect success at boundary
        mock_db.add.side_effect = lambda x: setattr(x, 'id', 1)
        result = await service.create_application(schema)
        assert result is not None

    async def test_high_risk_ltv_rejection(self, mock_db):
        """Test rejection of LTV > 95%."""
        payload = {
            "borrower_first_name": "High",
            "borrower_last_name": "Risk",
            "borrower_email": "high@example.com",
            "borrower_sin": "666666666",
            "borrower_dob": "1990-10-10",
            "property_address": "4 Risk Rd",
            "property_value": Decimal("100000.00"),
            "down_payment": Decimal("4000.00"), # 96% LTV
            "loan_amount": Decimal("96000.00"),
            "income_annual": Decimal("100000.00"),
            "employment_status": "employed",
            "credit_score": 800
        }
        
        schema = ApplicationCreate(**payload)
        service = ClientIntakeService(mock_db)
        
        with pytest.raises(AppException) as exc_info:
            await service.create_application(schema)
        
        assert "LTV exceeds maximum" in str(exc_info.value.detail)

    async def test_database_integrity_error_handling(self, mock_db, application_create_schema):
        """Test handling of DB integrity errors (e.g., duplicate SIN)."""
        # Simulate IntegrityError from DB
        mock_db.commit.side_effect = IntegrityError("INSERT INTO application", {}, Exception())
        
        service = ClientIntakeService(mock_db)
        
        with pytest.raises(AppException) as exc_info:
            await service.create_application(application_create_schema)
        
        assert exc_info.value.status_code == 409 # Conflict
        mock_db.rollback.assert_awaited_once()
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_create_application_endpoint_success(client: AsyncClient, valid_application_payload: dict):
    """Test full workflow of creating an application via API."""
    response = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert "id" in data
    assert data["status"] == "DRAFT"
    assert data["borrower_first_name"] == "John"
    assert data["borrower_last_name"] == "Doe"
    
    # PII Checks (PIPEDA Compliance)
    # SIN must NOT be returned in plain text
    assert "borrower_sin" not in data
    # DOB must NOT be returned in plain text
    assert "borrower_dob" not in data
    
    # Financial checks
    assert Decimal(data["property_value"]) == Decimal("750000.00")
    assert Decimal(data["loan_amount"]) == Decimal("600000.00")

@pytest.mark.asyncio
async def test_create_application_endpoint_validation_error(client: AsyncClient, invalid_application_payload_missing_sin: dict):
    """Test API validation when required fields are missing."""
    response = await client.post("/api/v1/client-intake/applications", json=invalid_application_payload_missing_sin)
    
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data

@pytest.mark.asyncio
async def test_create_application_endpoint_negative_income(client: AsyncClient, invalid_application_payload_negative_income: dict):
    """Test API validation for negative income."""
    response = await client.post("/api/v1/client-intake/applications", json=invalid_application_payload_negative_income)
    
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_get_application_endpoint_success(client: AsyncClient, valid_application_payload: dict):
    """Test retrieving an application after creation."""
    # 1. Create
    create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    app_id = create_resp.json()["id"]
    
    # 2. Retrieve
    get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
    
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == app_id
    assert data["borrower_email"] == "john.doe@example.com"
    
    # Verify PII is still masked on GET
    assert "borrower_sin" not in data

@pytest.mark.asyncio
async def test_get_application_not_found(client: AsyncClient):
    """Test retrieving a non-existent application."""
    response = await client.get("/api/v1/client-intake/applications/99999")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_submit_application_workflow(client: AsyncClient, valid_application_payload: dict):
    """Test the workflow of creating and then submitting an application."""
    # 1. Create Application
    create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "DRAFT"
    
    # 2. Submit Application
    submit_payload = {"status": "SUBMITTED"}
    submit_resp = await client.patch(f"/api/v1/client-intake/applications/{app_id}", json=submit_payload)
    
    assert submit_resp.status_code == 200
    data = submit_resp.json()
    assert data["status"] == "SUBMITTED"
    
    # 3. Verify status persistence
    get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
    assert get_resp.json()["status"] == "SUBMITTED"

@pytest.mark.asyncio
async def test_update_property_value(client: AsyncClient, valid_application_payload: dict):
    """Test updating financial details (property value)."""
    # 1. Create
    create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    app_id = create_resp.json()["id"]
    
    # 2. Update Property Value
    update_payload = {
        "property_value": "800000.00",
        "down_payment": "160000.00",
        "loan_amount": "640000.00"
    }
    update_resp = await client.patch(f"/api/v1/client-intake/applications/{app_id}", json=update_payload)
    
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert Decimal(data["property_value"]) == Decimal("800000.00")
    assert Decimal(data["loan_amount"]) == Decimal("640000.00")

@pytest.mark.asyncio
async def test_list_applications(client: AsyncClient, valid_application_payload: dict):
    """Test listing multiple applications."""
    # Create two apps
    await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    payload_2 = valid_application_payload.copy()
    payload_2["borrower_email"] = "second@example.com"
    await client.post("/api/v1/client-intake/applications", json=payload_2)
    
    # List
    list_resp = await client.get("/api/v1/client-intake/applications")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) >= 2
    
    # Ensure PII is not in list view
    for app in data:
        assert "borrower_sin" not in app

@pytest.mark.asyncio
async def test_duplicate_sin_prevention(client: AsyncClient, valid_application_payload: dict):
    """Test that submitting an application with an existing SIN is handled (FINTRAC/Audit)."""
    # 1. Create first app
    resp1 = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    assert resp1.status_code == 201
    
    # 2. Try to create second app with same SIN
    # Assuming business logic or DB constraint prevents this
    # If unique constraint on hashed_sin exists:
    resp2 = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    
    # Expecting 409 Conflict or 400 Bad Request depending on implementation
    assert resp2.status_code in [409, 400]

@pytest.mark.asyncio
async def test_invalid_status_transition(client: AsyncClient, valid_application_payload: dict):
    """Test API guard against invalid status changes."""
    # Create
    create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    app_id = create_resp.json()["id"]
    
    # Try to jump directly to APPROVED (skipping underwriting)
    invalid_payload = {"status": "APPROVED"}
    resp = await client.patch(f"/api/v1/client-intake/applications/{app_id}", json=invalid_payload)
    
    # Should fail validation or business rule
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_decimal_precision_preservation(client: AsyncClient, valid_application_payload: dict):
    """Test that financial values retain precision (no float conversion)."""
    # Use high precision values
    precise_payload = valid_application_payload.copy()
    precise_payload["property_value"] = "1234567.89"
    precise_payload["down_payment"] = "234567.88"
    
    resp = await client.post("/api/v1/client-intake/applications", json=precise_payload)
    assert resp.status_code == 201
    
    data = resp.json()
    # Verify exact string match or Decimal equality
    assert data["property_value"] == "1234567.89"
    assert data["down_payment"] == "234567.88"
```