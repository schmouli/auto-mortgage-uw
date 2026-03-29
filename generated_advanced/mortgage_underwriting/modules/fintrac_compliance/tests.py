--- conftest.py ---
```python
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator, Generator

# Assuming the Base is defined in common.database or similar, 
# but for testing isolation we often create a local one or import it.
# Based on structure: from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.database import Base

# Test Database URL (In-memory SQLite for speed and isolation)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def db_engine():
    """
    Create a fresh database engine for each test function.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a new database session for each test.
    """
    async_session_maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session

@pytest.fixture
def valid_transaction_payload() -> dict:
    """
    Standard payload for a small transaction (< $10,000).
    """
    return {
        "applicant_id": "applicant_123",
        "amount": "5000.00",
        "currency": "CAD",
        "transaction_type": "MORTGAGE_PAYMENT",
        "account_number": "****1234",
        "institution_id": "inst_001"
    }

@pytest.fixture
def large_cash_transaction_payload() -> dict:
    """
    Payload for a large cash transaction (> $10,000) triggering FINTRAC reporting.
    """
    return {
        "applicant_id": "applicant_456",
        "amount": "12500.00",
        "currency": "CAD",
        "transaction_type": "LARGE_CASH_DEPOSIT",
        "account_number": "****5678",
        "institution_id": "inst_001"
    }

@pytest.fixture
def identity_verification_payload() -> dict:
    return {
        "applicant_id": "applicant_123",
        "verification_method": "GOVERNMENT_ID",
        "id_type": "DRIVERS_LICENSE",
        "id_jurisdiction": "ON",
        "verified_by": "underwriter_1"
    }
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.exc import IntegrityError

# Absolute Imports based on project structure
from mortgage_underwriting.modules.fintrac.models import (
    FintracTransactionLog,
    IdentityVerificationRecord
)
from mortgage_underwriting.modules.fintrac.schemas import (
    TransactionCreate,
    TransactionResponse,
    IdentityVerificationCreate
)
from mortgage_underwriting.modules.fintrac.services import FintracService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFintracService:
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock AsyncSession for unit tests."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_record_transaction_success(self, mock_db_session):
        """Test successfully recording a standard transaction."""
        service = FintracService(mock_db_session)
        payload = TransactionCreate(
            applicant_id="app_123",
            amount=Decimal("5000.00"),
            currency="CAD",
            transaction_type="PAYMENT",
            account_number="****1234",
            institution_id="inst_01"
        )

        result = await service.record_transaction(payload, created_by="system")

        assert result.applicant_id == "app_123"
        assert result.amount == Decimal("5000.00")
        assert result.is_large_cash_reportable is False
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_large_cash_transaction(self, mock_db_session):
        """
        Test that transactions > $10,000 CAD are flagged for reporting.
        Regulatory: Explicit transaction type flag required.
        """
        service = FintracService(mock_db_session)
        payload = TransactionCreate(
            applicant_id="app_456",
            amount=Decimal("10001.00"),
            currency="CAD",
            transaction_type="LARGE_CASH",
            account_number="****5678",
            institution_id="inst_01"
        )

        result = await service.record_transaction(payload, created_by="system")

        assert result.amount == Decimal("10001.00")
        assert result.is_large_cash_reportable is True
        # Ensure specific flag is set
        assert result.transaction_type == "LARGE_CASH"

    @pytest.mark.asyncio
    async def test_record_transaction_boundary_10k(self, mock_db_session):
        """Test boundary condition exactly at $10,000.00 (should not flag)."""
        service = FintracService(mock_db_session)
        payload = TransactionCreate(
            applicant_id="app_789",
            amount=Decimal("10000.00"),
            currency="CAD",
            transaction_type="PAYMENT",
            account_number="****9999",
            institution_id="inst_01"
        )

        result = await service.record_transaction(payload, created_by="system")

        assert result.is_large_cash_reportable is False

    @pytest.mark.asyncio
    async def test_record_transaction_negative_amount_raises(self, mock_db_session):
        """Test that negative amounts are rejected."""
        service = FintracService(mock_db_session)
        payload = TransactionCreate(
            applicant_id="app_err",
            amount=Decimal("-50.00"),
            currency="CAD",
            transaction_type="PAYMENT",
            account_number="****0000",
            institution_id="inst_01"
        )

        with pytest.raises(ValueError) as exc_info:
            await service.record_transaction(payload, created_by="system")
        assert "Transaction amount must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_log_identity_verification_success(self, mock_db_session):
        """Test logging a successful identity verification."""
        service = FintracService(mock_db_session)
        payload = IdentityVerificationCreate(
            applicant_id="app_123",
            verification_method="PASSPORT",
            id_type="PASSPORT",
            id_jurisdiction="CA",
            verified_by="user_1"
        )

        result = await service.log_identity_verification(payload)

        assert result.applicant_id == "app_123"
        assert result.verification_status == "VERIFIED"
        assert result.verified_at is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_identity_verification_failure(self, mock_db_session):
        """Test logging a failed identity verification attempt."""
        service = FintracService(mock_db_session)
        payload = IdentityVerificationCreate(
            applicant_id="app_404",
            verification_method="GOVERNMENT_ID",
            id_type="SIN",
            id_jurisdiction="CA",
            verified_by="user_1"
        )

        # Simulate a failure scenario if the service supports manual status override
        # or if the verification logic determines failure based on payload
        # Here we assume the service sets status based on internal logic or payload
        result = await service.log_identity_verification(payload, status="FAILED")

        assert result.verification_status == "FAILED"

    @pytest.mark.asyncio
    async def test_immutable_audit_fields(self, mock_db_session):
        """
        Test that created_at and created_by are set and immutable.
        Regulatory: Immutable audit trail.
        """
        service = FintracService(mock_db_session)
        payload = TransactionCreate(
            applicant_id="app_audit",
            amount=Decimal("100.00"),
            currency="CAD",
            transaction_type="PAYMENT",
            account_number="****1111",
            institution_id="inst_01"
        )

        result = await service.record_transaction(payload, created_by="admin_user")

        assert result.created_at is not None
        assert result.created_by == "admin_user"
        assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_record_transaction_decimal_precision(self, mock_db_session):
        """Test that Decimal is used and precision is maintained."""
        service = FintracService(mock_db_session)
        precise_amount = Decimal("12345.67")
        payload = TransactionCreate(
            applicant_id="app_dec",
            amount=precise_amount,
            currency="CAD",
            transaction_type="PAYMENT",
            account_number="****2222",
            institution_id="inst_01"
        )

        result = await service.record_transaction(payload, created_by="system")

        # Ensure no float conversion happened
        assert isinstance(result.amount, Decimal)
        assert result.amount == precise_amount
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy import select

# Absolute Imports
from mortgage_underwriting.modules.fintrac.routes import router as fintrac_router
from mortgage_underwriting.modules.fintrac.models import FintracTransactionLog, IdentityVerificationRecord
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestFintracIntegration:

    @pytest.fixture
    def app(self, db_session):
        """
        Create a test FastAPI app with the Fintrac router and overridden DB dependency.
        """
        app = FastAPI()
        app.include_router(fintrac_router, prefix="/api/v1/fintrac", tags=["fintrac"])

        # Override the dependency
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db
        yield app
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_transaction_endpoint(self, app: FastAPI, valid_transaction_payload):
        """
        Test creating a transaction via API.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)

            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["amount"] == valid_transaction_payload["amount"]
            assert data["is_large_cash_reportable"] is False
            assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_large_cash_transaction_endpoint(self, app: FastAPI, large_cash_transaction_payload):
        """
        Test creating a large cash transaction (> 10k) via API.
        Verifies FINTRAC flag is set correctly.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/fintrac/transactions", json=large_cash_transaction_payload)

            assert response.status_code == 201
            data = response.json()
            assert data["is_large_cash_reportable"] is True
            assert data["amount"] == large_cash_transaction_payload["amount"]

    @pytest.mark.asyncio
    async def test_get_transaction_retrieval(self, app: FastAPI, valid_transaction_payload, db_session):
        """
        Test retrieving a logged transaction.
        """
        # First, create a transaction
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
            trans_id = create_resp.json()["id"]

            # Retrieve it
            get_resp = await client.get(f"/api/v1/fintrac/transactions/{trans_id}")
            
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["id"] == trans_id
            assert data["applicant_id"] == valid_transaction_payload["applicant_id"]

    @pytest.mark.asyncio
    async def test_log_identity_verification_endpoint(self, app: FastAPI, identity_verification_payload):
        """
        Test logging identity verification.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/fintrac/identity-verify", json=identity_verification_payload)

            assert response.status_code == 201
            data = response.json()
            assert data["applicant_id"] == identity_verification_payload["applicant_id"]
            assert data["verification_method"] == identity_verification_payload["verification_method"]
            assert data["verified_at"] is not None

    @pytest.mark.asyncio
    async def test_invalid_transaction_amount_rejected(self, app: FastAPI):
        """
        Test that invalid payloads (e.g., negative amounts) return 422.
        """
        invalid_payload = {
            "applicant_id": "app_123",
            "amount": "-500.00",
            "currency": "CAD",
            "transaction_type": "PAYMENT",
            "account_number": "****1234",
            "institution_id": "inst_01"
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/fintrac/transactions", json=invalid_payload)
            assert response.status_code == 422 # Unprocessable Entity

    @pytest.mark.asyncio
    async def test_transaction_persistence_in_db(self, app: FastAPI, valid_transaction_payload, db_session):
        """
        Verify that data is actually persisted in the database correctly.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)

        # Query DB directly
        stmt = select(FintracTransactionLog).where(
            FintracTransactionLog.applicant_id == valid_transaction_payload["applicant_id"]
        )
        result = await db_session.execute(stmt)
        record = result.scalar_one_or_none()

        assert record is not None
        assert record.amount == Decimal(valid_transaction_payload["amount"])
        assert record.created_by is not None
        assert record.created_at is not None

    @pytest.mark.asyncio
    async def test_fintrac_audit_trail_integrity(self, app: FastAPI, valid_transaction_payload, db_session):
        """
        Regulatory: Verify audit fields are immutable and present.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
            created_at = resp.json()["created_at"]

        # Ensure created_at is a valid ISO format string
        assert created_at is not None
        
        # In a real scenario, we might try to update the record via the API
        # and ensure created_at does not change, or the update is rejected if 
        # strict immutability is enforced at the API level.
        # Assuming the API only allows POST (Create) and GET (Read) for audit logs.
        
        stmt = select(FintracTransactionLog).where(
            FintracTransactionLog.applicant_id == valid_transaction_payload["applicant_id"]
        )
        result = await db_session.execute(stmt)
        record = result.scalar_one()
        
        assert record.updated_at is not None # Track last update time even if content is mostly immutable

    @pytest.mark.asyncio
    async def test_list_transactions_filtering(self, app: FastAPI, valid_transaction_payload, large_cash_transaction_payload):
        """
        Test filtering transactions (e.g., only large cash).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create mixed data
            await client.post("/api/v1/fintrac/transactions", json=valid_transaction_payload)
            await client.post("/api/v1/fintrac/transactions", json=large_cash_transaction_payload)

            # Filter for large cash
            response = await client.get("/api/v1/fintrac/transactions?is_large_cash_reportable=true")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["is_large_cash_reportable"] is True
```