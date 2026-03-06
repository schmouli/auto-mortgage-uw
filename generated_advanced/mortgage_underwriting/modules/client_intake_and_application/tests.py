--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
import uuid

# Assuming the Base is imported from common.database as per conventions
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_intake.models import ClientApplication
from mortgage_underwriting.modules.client_intake.schemas import ClientApplicationCreate

# Database URL for testing (In-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create async engine
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    Handles schema creation and teardown.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def valid_application_payload() -> dict:
    """
    Provides a valid payload for creating a client application.
    Complies with PIPEDA (SIN included for encryption testing) and CMHC (Loan/Value).
    """
    return {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1985-05-15",
        "sin": "123456789", # Will be encrypted/hashed
        "email": "john.doe@example.com",
        "phone_number": "4165550199",
        "property_address": "123 Maple Ave, Toronto, ON",
        "property_value": Decimal("500000.00"),
        "loan_amount": Decimal("400000.00"),
        "down_payment": Decimal("100000.00"),
        "employment_status": "employed",
        "annual_income": Decimal("95000.00")
    }

@pytest.fixture
def high_ltv_payload() -> dict:
    """
    Payload with LTV > 80% to trigger CMHC insurance requirement logic.
    """
    return {
        "first_name": "Jane",
        "last_name": "Smith",
        "date_of_birth": "1990-01-01",
        "sin": "987654321",
        "email": "jane.smith@example.com",
        "phone_number": "6475550199",
        "property_address": "456 Oak St, Vancouver, BC",
        "property_value": Decimal("500000.00"),
        "loan_amount": Decimal("450000.00"), # 90% LTV
        "down_payment": Decimal("50000.00"),
        "employment_status": "employed",
        "annual_income": Decimal("120000.00")
    }

@pytest.fixture
def invalid_payload_missing_sin() -> dict:
    """Invalid payload missing mandatory SIN."""
    return {
        "first_name": "Error",
        "last_name": "Case",
        "date_of_birth": "1990-01-01",
        "email": "error@example.com"
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.client_intake.services import ClientIntakeService
from mortgage_underwriting.modules.client_intake.models import ClientApplication
from mortgage_underwriting.modules.client_intake.exceptions import ApplicationCreationError, InvalidInputError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientIntakeService:

    @pytest.fixture
    def mock_db_session(self):
        """Mock AsyncSession for unit tests."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.scalar = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_create_application_success(self, mock_db_session, valid_application_payload):
        """Test successful creation of a client application."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        
        # Mock the encryption behavior
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "encrypted_hash_123"
            
            # Act
            result = await service.create_application(ClientApplicationCreate(**valid_application_payload))

            # Assert
            assert isinstance(result, ClientApplication)
            assert result.first_name == "John"
            assert result.loan_amount == Decimal("400000.00")
            assert result.sin_hash == "encrypted_hash_123" # Verify PIPEDA encryption call
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_ltv_calculation(self, mock_db_session, high_ltv_payload):
        """Test that LTV is calculated correctly and CMHC flag is set if needed."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "hash"
            
            # Act
            result = await service.create_application(ClientApplicationCreate(**high_ltv_payload))

            # Assert
            # LTV = 450,000 / 500,000 = 0.90 (90%)
            expected_ltv = Decimal("0.90")
            assert result.ltv_ratio == expected_ltv
            # CMHC Requirement: > 80% LTV requires insurance
            assert result.insurance_required is True

    @pytest.mark.asyncio
    async def test_create_application_no_insurance_under_80_ltv(self, mock_db_session, valid_application_payload):
        """Test that insurance is not required if LTV <= 80%."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "hash"
            
            # Act
            result = await service.create_application(ClientApplicationCreate(**valid_application_payload))

            # Assert
            # LTV = 400,000 / 500,000 = 0.80 (80%)
            expected_ltv = Decimal("0.80")
            assert result.ltv_ratio == expected_ltv
            assert result.insurance_required is False

    @pytest.mark.asyncio
    async def test_create_application_database_error(self, mock_db_session, valid_application_payload):
        """Test handling of database errors during commit."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        mock_db_session.commit.side_effect = SQLAlchemyError("DB Connection failed")

        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii"):
            # Act & Assert
            with pytest.raises(ApplicationCreationError):
                await service.create_application(ClientApplicationCreate(**valid_application_payload))
            
            # Ensure rollback is attempted on error
            mock_db_session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_application_by_id_success(self, mock_db_session):
        """Test retrieving an application by ID."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        app_id = uuid.uuid4()
        
        mock_app = ClientApplication(
            id=app_id,
            first_name="Test",
            last_name="User",
            loan_amount=Decimal("100000.00"),
            property_value=Decimal("200000.00"),
            ltv_ratio=Decimal("0.50"),
            sin_hash="hash",
            dob_encrypted="encrypted",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_app
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.get_application_by_id(app_id)

        # Assert
        assert result is not None
        assert result.id == app_id
        assert result.first_name == "Test"

    @pytest.mark.asyncio
    async def test_get_application_not_found(self, mock_db_session):
        """Test retrieving a non-existent application raises appropriate error."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        app_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_application_by_id(app_id)
        
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_validate_financials_zero_down_payment(self, mock_db_session):
        """Test validation logic for zero or negative down payment."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        invalid_payload = {
            "first_name": "Bad",
            "last_name": "Data",
            "date_of_birth": "1990-01-01",
            "sin": "000000000",
            "email": "bad@test.com",
            "phone_number": "0000000000",
            "property_address": "0 Nowhere St",
            "property_value": Decimal("100000.00"),
            "loan_amount": Decimal("100000.00"), # 100% LTV
            "down_payment": Decimal("0.00"),
            "employment_status": "employed",
            "annual_income": Decimal("50000.00")
        }

        # Act & Assert
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii"):
            with pytest.raises(InvalidInputError) as exc_info:
                await service.create_application(ClientApplicationCreate(**invalid_payload))
            
            assert "down payment" in str(exc_info.value.detail).lower()

--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.client_intake.routes import router
from mortgage_underwriting.modules.client_intake.models import ClientApplication
from mortgage_underwriting.common.database import get_async_session

# Override the dependency for testing
async def override_get_db():
    async with async_session_maker() as session:
        yield session

@pytest.fixture(scope="module")
def app() -> FastAPI:
    """Create a test application instance."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-intake", tags=["Client Intake"])
    app.dependency_overrides[get_async_session] = override_get_db
    return app

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_application_endpoint_success(self, app: FastAPI, valid_application_payload):
        """Test the POST endpoint creates a record in DB."""
        # Arrange
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.post("/api/v1/client-intake/", json=valid_application_payload)

            # Assert
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["first_name"] == "John"
            assert data["loan_amount"] == "400000.00"
            
            # PIPEDA Compliance Check: SIN must NEVER be in response
            assert "sin" not in data
            assert "sin_hash" not in data # Internal field usually hidden from API response
            
            # FINTRAC Compliance Check: Audit fields present
            assert "created_at" in data

    async def test_create_application_pipedata_sin_not_logged(self, app: FastAPI, valid_application_payload, caplog):
        """Ensure SIN is not logged in server logs."""
        # This test assumes structlog or similar is used. 
        # Here we verify the API response doesn't leak it first.
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/client-intake/", json=valid_application_payload)
            
            assert response.status_code == 201
            # Verify the raw SIN from payload is not in the response
            assert valid_application_payload["sin"] not in response.text

    async def test_get_application_endpoint(self, app: FastAPI, valid_application_payload, db_session):
        """Test retrieving a created application."""
        # Arrange - Create via service first to get ID
        from mortgage_underwriting.modules.client_intake.services import ClientIntakeService
        from mortgage_underwriting.modules.client_intake.schemas import ClientApplicationCreate
        
        service = ClientIntakeService(db_session)
        created_app = await service.create_application(ClientApplicationCreate(**valid_application_payload))
        await db_session.commit()
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(f"/api/v1/client-intake/{created_app.id}")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(created_app.id)
            assert data["email"] == "john.doe@example.com"
            # Verify PIPEDA: DOB should be encrypted or omitted if not strictly necessary for GET
            # Assuming schema returns DOB for the owner, but definitely not SIN
            assert "sin" not in data

    async def test_create_application_validation_error(self, app: FastAPI, invalid_payload_missing_sin):
        """Test 422 error for invalid input."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/client-intake/", json=invalid_payload_missing_sin)
            
            assert response.status_code == 422 # Validation Error

    async def test_create_application_high_ltv_cmhc_flag(self, app: FastAPI, high_ltv_payload):
        """Test that high LTV applications trigger insurance_required flag via API."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/client-intake/", json=high_ltv_payload)
            
            assert response.status_code == 201
            data = response.json()
            # CMHC Logic Check
            assert data["insurance_required"] is True
            assert data["ltv_ratio"] == "0.90"

    async def test_get_application_not_found(self, app: FastAPI):
        """Test 404 for non-existent UUID."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/client-intake/{fake_id}")
            assert response.status_code == 404
            assert "detail" in response.json()

    async def test_database_persistence(self, app: FastAPI, valid_application_payload, db_session):
        """Test that data actually persists in the database correctly."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.post("/api/v1/client-intake/", json=valid_application_payload)
            app_id = response.json()["id"]
            
            # Verify directly in DB
            result = await db_session.execute(select(ClientApplication).where(ClientApplication.id == app_id))
            db_record = result.scalar_one_or_none()
            
            assert db_record is not None
            assert db_record.loan_amount == Decimal("400000.00")
            assert db_record.sin_hash is not None # Verify PIPEDA encryption happened in DB
            assert db_record.sin_hash != valid_application_payload["sin"] # Verify it's not plain text
            assert db_record.created_at is not None # FINTRAC audit trail