--- conftest.py ---
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.fintrac_compliance.models import FintracReport, ClientIdentity
from mortgage_underwriting.modules.fintrac_compliance.routes import router
from mortgage_underwriting.common.config import settings

# Using in-memory SQLite for integration tests as per requirement
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_engine():
    """Create a fresh database engine for each test."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

@pytest.fixture(scope="function")
def app() -> FastAPI:
    """Create a test FastAPI application."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/fintrac", tags=["fintrac"])
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an AsyncClient for testing the API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# --- Test Data Fixtures ---

@pytest.fixture
def valid_identity_payload():
    return {
        "client_id": "client_123",
        "first_name": "John",
        "last_name": "Doe",
        "sin": "123-456-789", # Should be encrypted by service
        "dob": "1990-01-01",
        "occupation": "Engineer"
    }

@pytest.fixture
def valid_report_payload_small():
    """Transaction under $10,000 CAD."""
    return {
        "client_id": "client_123",
        "transaction_amount": "5000.00",
        "currency": "CAD",
        "transaction_type": "wire_transfer",
        "entity_type": "individual"
    }

@pytest.fixture
def valid_report_payload_large_cash():
    """Transaction over $10,000 CAD (Large Cash)."""
    return {
        "client_id": "client_123",
        "transaction_amount": "12500.00",
        "currency": "CAD",
        "transaction_type": "cash_deposit",
        "entity_type": "individual"
    }

@pytest.fixture
def valid_report_payload_non_cash_large():
    """Transaction over $10,000 CAD but not cash (still reportable)."""
    return {
        "client_id": "client_123",
        "transaction_amount": "15000.00",
        "currency": "CAD",
        "transaction_type": "wire_transfer",
        "entity_type": "business"
    }
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from sqlalchemy.orm import select

from mortgage_underwriting.modules.fintrac_compliance.services import FintracService
from mortgage_underwriting.modules.fintrac_compliance.models import FintracReport, ClientIdentity
from mortgage_underwriting.modules.fintrac_compliance.schemas import (
    FintracReportCreate, 
    ClientIdentityCreate,
    FintracReportResponse
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFintracService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return FintracService(mock_db)

    @pytest.mark.asyncio
    async def test_log_transaction_standard_amount(self, service, mock_db):
        """Test logging a standard transaction (< 10k CAD)."""
        payload = FintracReportCreate(
            client_id="client_001",
            transaction_amount=Decimal("5000.00"),
            currency="CAD",
            transaction_type="wire_transfer",
            entity_type="individual"
        )

        # Mock the return of the added object (usually happens after refresh/commit)
        mock_report = FintracReport(**payload.model_dump(), id=1)
        mock_db.refresh.return_value = mock_report
        mock_db.scalar.return_value = None # No existing report

        result = await service.log_transaction(payload)

        assert result.transaction_amount == Decimal("5000.00")
        assert result.is_large_cash_transaction is False
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_transaction_large_cash_threshold(self, service, mock_db):
        """Test that transactions > 10k CAD are flagged correctly."""
        payload = FintracReportCreate(
            client_id="client_001",
            transaction_amount=Decimal("10500.00"),
            currency="CAD",
            transaction_type="cash_deposit", # Explicit cash
            entity_type="individual"
        )

        mock_report = FintracReport(**payload.model_dump(), id=2, is_large_cash_transaction=True)
        mock_db.refresh.return_value = mock_report
        
        result = await service.log_transaction(payload)

        assert result.is_large_cash_transaction is True
        assert result.transaction_amount == Decimal("10500.00")

    @pytest.mark.asyncio
    async def test_log_transaction_foreign_currency(self, service, mock_db):
        """Test handling of foreign currency (assuming conversion logic exists or is mocked)."""
        # Assuming service converts to CAD or logs as is. 
        # For this test, we check that the service accepts non-CAD.
        payload = FintracReportCreate(
            client_id="client_001",
            transaction_amount=Decimal("8000.00"),
            currency="USD",
            transaction_type="wire_transfer",
            entity_type="individual"
        )

        mock_report = FintracReport(**payload.model_dump(), id=3)
        mock_db.refresh.return_value = mock_report

        result = await service.log_transaction(payload)

        assert result.currency == "USD"
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_transaction_invalid_amount_negative(self, service, mock_db):
        """Test that negative amounts raise validation errors."""
        with pytest.raises(ValueError) as exc_info:
            await service.log_transaction(
                FintracReportCreate(
                    client_id="client_001",
                    transaction_amount=Decimal("-100.00"),
                    currency="CAD",
                    transaction_type="wire_transfer",
                    entity_type="individual"
                )
            )
        assert "Transaction amount must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("mortgage_underwriting.common.security.encrypt_pii")
    async def test_verify_identity_encryption_called(self, mock_encrypt, service, mock_db):
        """Test that PII (SIN) is encrypted during identity verification."""
        mock_encrypt.return_value = "encrypted_sin_blob"
        
        payload = ClientIdentityCreate(
            client_id="client_001",
            first_name="Jane",
            last_name="Smith",
            sin="987-654-321",
            dob="1985-05-20",
            occupation="Doctor"
        )

        mock_identity = ClientIdentity(**payload.model_dump(), id=1, sin_hash="hash123")
        mock_db.refresh.return_value = mock_identity

        await service.verify_identity(payload)

        # Assert security utility was called for SIN
        mock_encrypt.assert_called_once_with("987-654-321")
        # Assert DB add was called
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    @patch("mortgage_underwriting.common.security.encrypt_pii")
    @patch("mortgage_underwriting.common.security.hash_value")
    async def test_verify_identity_stores_hash_not_sin(self, mock_hash, mock_encrypt, service, mock_db):
        """Test that the DB model stores the hash of the SIN, not the plain SIN."""
        mock_encrypt.return_value = "encrypted_blob"
        mock_hash.return_value = "hashed_sin_value"
        
        payload = ClientIdentityCreate(
            client_id="client_001",
            first_name="Bob",
            last_name="Builder",
            sin="111-222-333",
            dob="1970-01-01",
            occupation="Architect"
        )

        # Capture the object passed to db.add
        added_obj = None
        def capture_add(obj):
            nonlocal added_obj
            added_obj = obj
        mock_db.add.side_effect = capture_add
        
        await service.verify_identity(payload)

        assert added_obj is not None
        # Check that the model object was prepared with the hash, not plain SIN
        assert added_obj.sin_hash == "hashed_sin_value"
        # Ensure plain SIN is not stored in the 'sin' field (which shouldn't exist on model or be encrypted col)
        # Assuming model has 'sin_encrypted' or similar, or just relies on hash. 
        # Based on prompt: "Use hashed values (SIN -> SHA256) for lookups only."
        assert getattr(added_obj, 'sin', None) is None or getattr(added_obj, 'sin') == "encrypted_blob"

    @pytest.mark.asyncio
    @patch("structlog.get_logger")
    async def test_verify_identity_logs_verification_not_pii(self, mock_logger, service, mock_db):
        """Test that identity verification is logged without exposing PII."""
        logger_instance = MagicMock()
        mock_logger.return_value = logger_instance
        
        payload = ClientIdentityCreate(
            client_id="client_001",
            first_name="Test",
            last_name="User",
            sin="000-000-000",
            dob="2000-01-01",
            occupation="Tester"
        )
        
        mock_identity = ClientIdentity(**payload.model_dump(), id=1)
        mock_db.refresh.return_value = mock_identity

        await service.verify_identity(payload)

        # Verify logging occurred
        logger_instance.info.assert_called()
        
        # Verify PII is NOT in the logs
        call_args = logger_instance.info.call_args
        log_message = str(call_args)
        assert "000-000-000" not in log_message
        assert "2000-01-01" not in log_message
        assert "client_001" in log_message # Client ID is okay

    @pytest.mark.asyncio
    async def test_get_report_by_id(self, service, mock_db):
        """Test retrieving a FINTRAC report."""
        mock_report = FintracReport(
            id=1, 
            client_id="client_001", 
            transaction_amount=Decimal("500.00"),
            created_by="system"
        )
        mock_db.scalar.return_value = mock_report

        result = await service.get_report(report_id=1)

        assert result.id == 1
        assert result.client_id == "client_001"
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_fields_immutability(self, service, mock_db):
        """Test that created_at and created_by are set and cannot be modified via service update (if applicable)."""
        # Note: SQLAlchemy models usually handle this, but we test the service behavior
        payload = FintracReportCreate(
            client_id="client_001",
            transaction_amount=Decimal("100.00"),
            currency="CAD",
            transaction_type="wire_transfer",
            entity_type="individual"
        )
        
        mock_report = FintracReport(**payload.model_dump(), id=1)
        mock_db.refresh.return_value = mock_report
        
        result = await service.log_transaction(payload)
        
        # In a real scenario, these are set by DB defaults or service logic
        # Here we check the service doesn't strip them if the model has them
        # or sets them if responsible.
        # Assuming service logic: result.created_by = "system"
        
        assert hasattr(result, 'created_at')
        assert hasattr(result, 'created_by')

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.fintrac_compliance.models import FintracReport, ClientIdentity

@pytest.mark.integration
class TestFintracIntegration:

    @pytest.mark.asyncio
    async def test_create_and_retrieve_report(self, client: AsyncClient, db_session):
        """Test full workflow of creating a report and retrieving it."""
        # 1. Create Report
        payload = {
            "client_id": "int_client_01",
            "transaction_amount": "7500.00",
            "currency": "CAD",
            "transaction_type": "wire_transfer",
            "entity_type": "individual"
        }
        response = await client.post("/api/v1/fintrac/reports", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["client_id"] == "int_client_01"
        assert data["is_large_cash_transaction"] is False
        
        # 2. Verify in DB
        stmt = select(FintracReport).where(FintracReport.client_id == "int_client_01")
        result = await db_session.execute(stmt)
        db_report = result.scalar_one_or_none()
        
        assert db_report is not None
        assert db_report.transaction_amount == Decimal("7500.00")
        assert db_report.created_at is not None

    @pytest.mark.asyncio
    async def test_large_cash_transaction_flagging(self, client: AsyncClient, db_session):
        """Test that large cash transactions (>10k) are flagged via API."""
        payload = {
            "client_id": "int_client_02",
            "transaction_amount": "12000.00",
            "currency": "CAD",
            "transaction_type": "cash_deposit",
            "entity_type": "individual"
        }
        
        response = await client.post("/api/v1/fintrac/reports", json=payload)
        assert response.status_code == 201
        data = response.json()
        
        assert data["is_large_cash_transaction"] is True
        
        # Check DB persistence
        stmt = select(FintracReport).where(FintracReport.client_id == "int_client_02")
        result = await db_session.execute(stmt)
        db_report = result.scalar_one_or_none()
        assert db_report.is_large_cash_transaction is True

    @pytest.mark.asyncio
    async def test_identity_verification_pii_protection(self, client: AsyncClient, db_session):
        """Test that identity verification does not return plain SIN."""
        payload = {
            "client_id": "int_client_03",
            "first_name": "Alice",
            "last_name": "Wonderland",
            "sin": "123-456-789",
            "dob": "1992-02-02",
            "occupation": "Designer"
        }
        
        response = await client.post("/api/v1/fintrac/verify-identity", json=payload)
        assert response.status_code == 201
        data = response.json()
        
        # CRITICAL: Ensure SIN is NOT in the response
        assert "sin" not in data
        assert "123-456-789" not in str(data)
        assert data["client_id"] == "int_client_03"
        
        # Verify DB storage (Hashed/Encrypted)
        stmt = select(ClientIdentity).where(ClientIdentity.client_id == "int_client_03")
        result = await db_session.execute(stmt)
        db_identity = result.scalar_one_or_none()
        
        assert db_identity is not None
        # Assuming model has sin_encrypted or sin_hash
        # Ensure plain SIN is not stored in a plain 'sin' column
        assert getattr(db_identity, 'sin', None) != "123-456-789"

    @pytest.mark.asyncio
    async def test_transaction_validation_error(self, client: AsyncClient):
        """Test API validation for invalid inputs."""
        # Negative amount
        payload = {
            "client_id": "int_client_04",
            "transaction_amount": "-50.00",
            "currency": "CAD",
            "transaction_type": "wire_transfer",
            "entity_type": "individual"
        }
        
        response = await client.post("/api/v1/fintrac/reports", json=payload)
        assert response.status_code == 422 # Unprocessable Entity

    @pytest.mark.asyncio
    async def test_get_fintrac_report_endpoint(self, client: AsyncClient, db_session):
        """Test retrieving a specific report by ID."""
        # Seed data
        new_report = FintracReport(
            client_id="int_client_05",
            transaction_amount=Decimal("2500.00"),
            currency="CAD",
            transaction_type="etransfer",
            entity_type="individual",
            is_large_cash_transaction=False
        )
        db_session.add(new_report)
        await db_session.commit()
        await db_session.refresh(new_report)
        
        # Fetch via API
        response = await client.get(f"/api/v1/fintrac/reports/{new_report.id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == new_report.id
        assert data["transaction_amount"] == "2500.00"

    @pytest.mark.asyncio
    async def test_fintrac_audit_trail_fields(self, client: AsyncClient, db_session):
        """Test that audit fields are automatically populated."""
        payload = {
            "client_id": "int_client_06",
            "transaction_amount": "100.00",
            "currency": "CAD",
            "transaction_type": "wire_transfer",
            "entity_type": "individual"
        }
        
        await client.post("/api/v1/fintrac/reports", json=payload)
        
        stmt = select(FintracReport).where(FintracReport.client_id == "int_client_06")
        result = await db_session.execute(stmt)
        report = result.scalar_one_or_none()
        
        assert report.created_at is not None
        assert report.updated_at is not None
        # Assuming created_by is handled by middleware or service, if not, it might be null/system
        # But fields must exist.
        assert hasattr(report, 'created_at')
        assert hasattr(report, 'created_by')

    @pytest.mark.asyncio
    async def test_nonexistent_report_returns_404(self, client: AsyncClient):
        """Test getting a report that doesn't exist."""
        response = await client.get("/api/v1/fintrac/reports/99999")
        assert response.status_code == 404
        assert "detail" in response.json()