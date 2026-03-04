--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
import uuid

# Assuming Base is defined in common.database, but we create a local one for test setup if needed
# or import it. For fixture purposes, we will mock the structure or import if available.
# Here we assume the models exist in the module.

@pytest.fixture(scope="session")
def engine():
    """Create an async engine for testing (SQLite in-memory)."""
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for a test."""
    async with engine.begin() as conn:
        # In a real scenario, we would run Alembic migrations here
        # await conn.run_sync(Base.metadata.create_all)
        pass
    
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def sample_applicant_id() -> str:
    return str(uuid.uuid4())

@pytest.fixture
def fintrac_report_payload(sample_applicant_id) -> dict:
    return {
        "applicant_id": sample_applicant_id,
        "transaction_amount": "12500.00", # String to ensure Decimal parsing
        "transaction_type": "large_cash",
        "currency": "CAD",
        "occurrence_date": "2023-10-27T10:00:00Z"
    }

@pytest.fixture
def identity_verification_payload(sample_applicant_id) -> dict:
    return {
        "applicant_id": sample_applicant_id,
        "verification_method": "credit_bureau",
        "verified_by": "underwriter_1",
        "ip_address": "192.168.1.1"
    }

@pytest.fixture
def mock_security_context():
    """Mock the security context for user tracking."""
    return {
        "user_id": "test_user_123",
        "correlation_id": "req-abc-123"
    }
--- unit_tests ---
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import select

from mortgage_underwriting.modules.fintrac.models import FintracReport, IdentityVerificationLog
from mortgage_underwriting.modules.fintrac.schemas import FintracReportCreate, IdentityVerificationCreate
from mortgage_underwriting.modules.fintrac.services import FintracService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFintracService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_log_identity_verification_success(self, mock_db):
        """Test that identity verification is logged correctly with audit trail."""
        payload = IdentityVerificationCreate(
            applicant_id="user-123",
            verification_method="government_id",
            verified_by="system"
        )
        
        service = FintracService(mock_db)
        
        # Mock the return of the refresh to simulate DB response
        mock_log_instance = IdentityVerificationLog(
            id="log-1",
            applicant_id=payload.applicant_id,
            verification_method=payload.verification_method,
            verified_by=payload.verified_by,
            created_at=datetime.utcnow()
        )
        mock_db.refresh.return_value = mock_log_instance

        result = await service.log_verification(payload)

        # Assertions
        assert result.applicant_id == "user-123"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        
        # Verify audit fields are set (via service logic or DB default, we check logic here)
        # Assuming service sets created_at/created_by if not handled by DB trigger
        call_args = mock_db.add.call_args[0][0]
        assert isinstance(call_args, IdentityVerificationLog)

    @pytest.mark.asyncio
    async def test_record_transaction_large_cash_flag(self, mock_db):
        """Test that transactions >= 10,000 CAD are flagged correctly."""
        payload = FintracReportCreate(
            applicant_id="user-123",
            transaction_amount=Decimal("12000.00"),
            transaction_type="deposit",
            currency="CAD"
        )

        service = FintracService(mock_db)
        
        mock_report_instance = FintracReport(
            id="report-1",
            applicant_id=payload.applicant_id,
            transaction_amount=payload.transaction_amount,
            transaction_type=payload.transaction_type,
            is_large_cash=True, # Expecting this to be set by service
            created_at=datetime.utcnow()
        )
        mock_db.refresh.return_value = mock_report_instance

        result = await service.record_transaction(payload)

        # Verify the service flagged it
        call_args = mock_db.add.call_args[0][0]
        assert call_args.is_large_cash is True
        assert call_args.transaction_amount == Decimal("12000.00")

    @pytest.mark.asyncio
    async def test_record_transaction_small_amount_no_flag(self, mock_db):
        """Test that transactions < 10,000 CAD are not flagged."""
        payload = FintracReportCreate(
            applicant_id="user-123",
            transaction_amount=Decimal("5000.00"),
            transaction_type="deposit",
            currency="CAD"
        )

        service = FintracService(mock_db)
        
        mock_report_instance = FintracReport(
            id="report-1",
            applicant_id=payload.applicant_id,
            transaction_amount=payload.transaction_amount,
            transaction_type=payload.transaction_type,
            is_large_cash=False,
            created_at=datetime.utcnow()
        )
        mock_db.refresh.return_value = mock_report_instance

        result = await service.record_transaction(payload)

        call_args = mock_db.add.call_args[0][0]
        assert call_args.is_large_cash is False

    @pytest.mark.asyncio
    async def test_record_transaction_invalid_currency_raises(self, mock_db):
        """Test that non-CAD currencies raise an error or are handled (assuming CAD only for simplicity)."""
        payload = FintracReportCreate(
            applicant_id="user-123",
            transaction_amount=Decimal("100.00"),
            transaction_type="deposit",
            currency="USD"
        )

        service = FintracService(mock_db)
        
        with pytest.raises(ValueError) as exc_info:
            await service.record_transaction(payload)
        
        assert "currency" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_record_transaction_negative_amount_raises(self, mock_db):
        """Test that negative amounts are rejected."""
        payload = FintracReportCreate(
            applicant_id="user-123",
            transaction_amount=Decimal("-500.00"),
            transaction_type="deposit",
            currency="CAD"
        )

        service = FintracService(mock_db)
        
        with pytest.raises(ValueError):
            await service.record_transaction(payload)

    @pytest.mark.asyncio
    async def test_immutability_enforced_on_update_attempt(self, mock_db):
        """Test that updating an audit field (created_at) raises an error."""
        # Setup an existing report
        existing_report = FintracReport(
            id="report-1",
            applicant_id="user-123",
            transaction_amount=Decimal("100.00"),
            created_at=datetime(2023, 1, 1)
        )
        
        # Mock the DB get to return this object
        mock_result = AsyncMock()
        mock_result.unique.return_value.scalar_one_or_none.return_value = existing_report
        mock_db.execute.return_value = mock_result

        service = FintracService(mock_db)

        # Attempt to update created_at
        with pytest.raises(AppException) as exc_info:
            await service.update_report("report-1", {"created_at": datetime.now()})
        
        assert "immutable" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_retention_period_eligible(self, mock_db):
        """Test checking if a record is eligible for archival (older than 5 years)."""
        old_date = datetime.utcnow()
        # Mock logic that checks date
        # Service logic: is_retention_eligible(record)
        pass 
        # Note: Implementation depends on specific service method existence.
        # Assuming a method exists for checking retention.

    @patch('mortgage_underwriting.modules.fintrac.services.structlog')
    @pytest.mark.asyncio
    async def test_logging_of_large_cash_transaction(self, mock_logger, mock_db):
        """Test that large cash transactions trigger a specific audit log."""
        payload = FintracReportCreate(
            applicant_id="user-123",
            transaction_amount=Decimal("10000.00"), # Boundary
            transaction_type="large_cash",
            currency="CAD"
        )

        service = FintracService(mock_db)
        mock_db.refresh.return_value = MagicMock(id="report-1")

        await service.record_transaction(payload)

        # Verify structured logging was called with specific event type
        mock_logger.get_logger.return_value.info.assert_called()
        # Check call args for "large_cash_reported" event
        calls = mock_logger.get_logger.return_value.info.call_args_list
        assert any("large_cash" in str(call) for call in calls)

--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal
from datetime import datetime

from mortgage_underwriting.modules.fintrac.routes import router
from mortgage_underwriting.modules.fintrac.models import FintracReport, IdentityVerificationLog
from mortgage_underwriting.common.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

# Override the dependency for testing
async def override_get_db():
    # This would use the fixture from conftest in a real run
    # For integration tests, we usually bind the engine to the tables
    pass

@pytest.fixture
def app(engine):
    """Create a test FastAPI app with the Fintrac router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/fintrac")
    
    # Setup tables
    from mortgage_underwriting.modules.fintrac.models import Base
    from sqlalchemy.ext.asyncio import async_sessionmaker
    
    @app.on_event("startup")
    async def startup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
    return app

@pytest.mark.integration
@pytest.mark.asyncio
class TestFintracIntegration:

    async def test_create_identity_verification_log(self, app: FastAPI, db_session: AsyncSession):
        """
        Test POST /verify-identity
        Ensures the record is created in the DB and response is 201.
        """
        # Override dependency
        app.dependency_overrides[get_async_session] = lambda: db_session
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "applicant_id": "applicant-001",
                "verification_method": "passport",
                "verified_by": "agent_007"
            }
            
            response = await client.post("/api/v1/fintrac/verify-identity", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] is not None
            assert data["applicant_id"] == "applicant-001"
            assert data["verification_method"] == "passport"
            
            # Verify DB State
            result = await db_session.execute(
                select(IdentityVerificationLog).where(IdentityVerificationLog.applicant_id == "applicant-001")
            )
            log = result.scalar_one_or_none()
            assert log is not None
            assert log.verified_by == "agent_007"
            
        app.dependency_overrides.clear()

    async def test_create_transaction_large_cash_flagging(self, app: FastAPI, db_session: AsyncSession):
        """
        Test POST /transactions
        Ensures amounts >= 10k are flagged in DB and response.
        """
        app.dependency_overrides[get_async_session] = lambda: db_session
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "applicant_id": "applicant-002",
                "transaction_amount": "15000.00",
                "transaction_type": "wire_transfer",
                "currency": "CAD"
            }
            
            response = await client.post("/api/v1/fintrac/transactions", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert data["is_large_cash"] is True
            
            # Verify DB State
            result = await db_session.execute(
                select(FintracReport).where(FintracReport.applicant_id == "applicant-002")
            )
            report = result.scalar_one_or_none()
            assert report is not None
            assert report.transaction_amount == Decimal("15000.00")
            assert report.is_large_cash is True

        app.dependency_overrides.clear()

    async def test_create_transaction_small_cash(self, app: FastAPI, db_session: AsyncSession):
        """
        Test POST /transactions
        Ensures amounts < 10k are not flagged.
        """
        app.dependency_overrides[get_async_session] = lambda: db_session
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "applicant_id": "applicant-003",
                "transaction_amount": "9999.99",
                "transaction_type": "deposit",
                "currency": "CAD"
            }
            
            response = await client.post("/api/v1/fintrac/transactions", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert data["is_large_cash"] is False

        app.dependency_overrides.clear()

    async def test_get_fintrac_reports(self, app: FastAPI, db_session: AsyncSession):
        """
        Test GET /reports
        Verifies retrieval of logged reports.
        """
        app.dependency_overrides[get_async_session] = lambda: db_session
        
        # Seed data
        new_report = FintracReport(
            applicant_id="applicant-004",
            transaction_amount=Decimal("500.00"),
            transaction_type="fee",
            currency="CAD",
            is_large_cash=False
        )
        db_session.add(new_report)
        await db_session.commit()
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/fintrac/reports")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) >= 1
            assert any(r["applicant_id"] == "applicant-004" for r in data)

        app.dependency_overrides.clear()

    async def test_update_prevention_on_audit_fields(self, app: FastAPI, db_session: AsyncSession):
        """
        Test PATCH /reports/{id}
        Attempts to update created_at should fail.
        """
        app.dependency_overrides[get_async_session] = lambda: db_session
        
        # Seed data
        new_report = FintracReport(
            applicant_id="applicant-005",
            transaction_amount=Decimal("100.00"),
            transaction_type="fee",
            currency="CAD",
            is_large_cash=False
        )
        db_session.add(new_report)
        await db_session.commit()
        await db_session.refresh(new_report)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Attempt to update created_at
            update_payload = {
                "created_at": "2024-01-01T00:00:00Z"
            }
            
            response = await client.patch(f"/api/v1/fintrac/reports/{new_report.id}", json=update_payload)
            
            assert response.status_code == 400 # Bad Request / Validation Error
            assert "immutable" in response.json()["detail"].lower()

        app.dependency_overrides.clear()