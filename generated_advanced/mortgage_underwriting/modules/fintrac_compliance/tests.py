--- conftest.py ---
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Numeric, Boolean, DateTime

from fastapi import FastAPI
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.fintrac_compliance.routes import router as fintrac_router

# Test Database Setup (SQLite in-memory for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_test_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

# Minimal Model for testing DB interactions if actual models aren't imported
# In a real scenario, we import from mortgage_underwriting.modules.fintrac_compliance.models
class FintracReport(Base):
    __tablename__ = "fintrac_reports"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_high_value: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_test_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def app(db_session: AsyncSession) -> FastAPI:
    """
    Create a test application with overridden dependencies.
    """
    app = FastAPI()
    app.include_router(fintrac_router, prefix="/api/v1/fintrac", tags=["fintrac"])

    # Override the dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async client for integration testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# Unit Test Fixtures
@pytest.fixture
def mock_db_session():
    from unittest.mock import AsyncMock
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session

@pytest.fixture
def valid_report_payload():
    return {
        "amount": "5000.00",
        "transaction_type": "eft",
        "created_by": "system_user"
    }

@pytest.fixture
def high_value_report_payload():
    return {
        "amount": "12500.00",
        "transaction_type": "wire",
        "created_by": "system_user"
    }

@pytest.fixture
def invalid_report_payload():
    return {
        "amount": "-100.00",
        "transaction_type": "cash",
        "created_by": "system_user"
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.fintrac_compliance.services import FintracService
from mortgage_underwriting.modules.fintrac_compliance.schemas import FintracReportCreate
from mortgage_underwriting.modules.fintrac_compliance.exceptions import FintracValidationError

# Import models for type hinting/mocking
from mortgage_underwriting.modules.fintrac_compliance.models import FintracReport

@pytest.mark.unit
class TestFintracService:

    @pytest.mark.asyncio
    async def test_create_report_success(self, mock_db_session):
        """Test successful creation of a standard FINTRAC report."""
        service = FintracService(mock_db_session)
        payload = FintracReportCreate(
            amount=Decimal("5000.00"),
            transaction_type="deposit",
            created_by="underwriter_1"
        )

        # Mock the return of refresh
        mock_report = FintracReport(
            id=1,
            amount=payload.amount,
            transaction_type=payload.transaction_type,
            is_high_value=False,
            created_by=payload.created_by
        )
        mock_db_session.refresh.return_value = mock_report

        result = await service.create_report(payload)

        assert result.amount == Decimal("5000.00")
        assert result.is_high_value is False
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_report_high_value_threshold(self, mock_db_session):
        """Test that transactions > 10,000 CAD are flagged as high value."""
        service = FintracService(mock_db_session)
        
        # Boundary test: Exactly 10,000
        payload_boundary = FintracReportCreate(
            amount=Decimal("10000.00"),
            transaction_type="wire",
            created_by="system"
        )
        mock_report_boundary = FintracReport(
            id=1, amount=payload_boundary.amount, 
            transaction_type=payload_boundary.transaction_type, 
            is_high_value=False, created_by="system"
        )
        mock_db_session.refresh.return_value = mock_report_boundary
        
        result_boundary = await service.create_report(payload_boundary)
        assert result_boundary.is_high_value is False

        # Boundary test: 10,000.01 (Should be True)
        payload_over = FintracReportCreate(
            amount=Decimal("10000.01"),
            transaction_type="wire",
            created_by="system"
        )
        mock_report_over = FintracReport(
            id=2, amount=payload_over.amount, 
            transaction_type=payload_over.transaction_type, 
            is_high_value=True, created_by="system"
        )
        mock_db_session.refresh.return_value = mock_report_over

        result_over = await service.create_report(payload_over)
        assert result_over.is_high_value is True

    @pytest.mark.asyncio
    async def test_create_report_negative_amount_raises(self, mock_db_session):
        """Test validation error for negative financial values."""
        service = FintracService(mock_db_session)
        
        with pytest.raises(FintracValidationError) as exc_info:
            await service.create_report(
                FintracReportCreate(
                    amount=Decimal("-50.00"),
                    transaction_type="cash",
                    created_by="user"
                )
            )
        
        assert "Amount must be positive" in str(exc_info.value)
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_report_missing_created_by_raises(self, mock_db_session):
        """Test validation error if audit field created_by is missing."""
        service = FintracService(mock_db_session)
        
        with pytest.raises(FintracValidationError) as exc_info:
            await service.create_report(
                FintracReportCreate(
                    amount=Decimal("100.00"),
                    transaction_type="cash",
                    created_by="" # Empty string
                )
            )
        
        assert "created_by is required for audit trail" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_log_identity_verification_success(self, mock_db_session, caplog):
        """Test logging of identity verification attempts."""
        service = FintracService(mock_db_session)
        
        # Assuming a method log_verification exists
        # We check that the service logic handles the logging requirement
        with caplog.at_level("INFO"):
            service.log_identity_verification(
                user_id="user_123", 
                method="passport", 
                status="verified"
            )
        
        assert any("Identity verification" in record.message for record in caplog.records)
        assert "user_123" in caplog.text

    @pytest.mark.asyncio
    async def test_get_report_by_id(self, mock_db_session):
        """Test retrieving a report."""
        service = FintracService(mock_db_session)
        
        mock_report = FintracReport(
            id=1,
            amount=Decimal("500.00"),
            transaction_type="cash",
            is_high_value=False,
            created_by="admin"
        )
        
        # Mock the scalar/where logic
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_report
        mock_db_session.execute.return_value = mock_result

        result = await service.get_report(1)
        
        assert result is not None
        assert result.id == 1
        assert result.amount == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, mock_db_session):
        """Test retrieving a non-existent report returns None."""
        service = FintracService(mock_db_session)
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await service.get_report(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_retention_period(self):
        """Test that 5-year retention logic is correctly calculated."""
        service = FintracService(AsyncMock())
        
        created_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        retention_date = service.calculate_retention_expiry(created_date)
        
        expected_year = created_date.year + 5
        assert retention_date.year == expected_year
        assert retention_date.month == created_date.month
        assert retention_date.day == created_date.day

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.fintrac_compliance.models import FintracReport

@pytest.mark.integration
@pytest.mark.asyncio
class TestFintracRoutes:

    async def test_create_report_endpoint_success(self, client: AsyncClient, valid_report_payload):
        """Test creating a report via API and verifying DB state."""
        response = await client.post("/api/v1/fintrac/reports", json=valid_report_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["amount"] == "5000.00"
        assert data["is_high_value"] is False
        assert "created_at" in data

    async def test_create_high_value_report_flag(self, client: AsyncClient, high_value_report_payload):
        """Test that high value transactions are flagged automatically by the API."""
        response = await client.post("/api/v1/fintrac/reports", json=high_value_report_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["is_high_value"] is True
        assert data["amount"] == "12500.00"

    async def test_create_report_invalid_amount(self, client: AsyncClient, invalid_report_payload):
        """Test API rejection of invalid (negative) amounts."""
        response = await client.post("/api/v1/fintrac/reports", json=invalid_report_payload)
        
        assert response.status_code == 422 # Validation error

    async def test_get_report_endpoint(self, client: AsyncClient, valid_report_payload, db_session):
        """Test retrieving a created report."""
        # Create a report first
        create_resp = await client.post("/api/v1/fintrac/reports", json=valid_report_payload)
        report_id = create_resp.json()["id"]

        # Retrieve it
        get_resp = await client.get(f"/api/v1/fintrac/reports/{report_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == report_id
        assert data["transaction_type"] == "eft"

    async def test_get_report_not_found(self, client: AsyncClient):
        """Test retrieving a non-existent report."""
        response = await client.get("/api/v1/fintrac/reports/99999")
        assert response.status_code == 404

    async def test_list_reports_pagination(self, client: AsyncClient, valid_report_payload):
        """Test listing reports with pagination."""
        # Create 3 reports
        for _ in range(3):
            await client.post("/api/v1/fintrac/reports", json=valid_report_payload)

        response = await client.get("/api/v1/fintrac/reports?limit=2&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1

    async def test_audit_trail_immutability(self, client: AsyncClient, valid_report_payload, db_session):
        """
        Test that created_at and created_by are populated and cannot be updated via standard update endpoint 
        (or that update logic preserves them).
        """
        # Create
        create_resp = await client.post("/api/v1/fintrac/reports", json=valid_report_payload)
        report_id = create_resp.json()["id"]
        original_created_at = create_resp.json()["created_at"]
        
        # Verify DB state
        stmt = select(FintracReport).where(FintracReport.id == report_id)
        result = await db_session.execute(stmt)
        db_obj = result.scalar_one_or_none()
        
        assert db_obj is not None
        assert db_obj.created_by == "system_user"
        assert db_obj.created_at is not None

        # Attempt Update (if endpoint exists)
        # Assuming a PUT/PATCH endpoint exists for amount/status but NOT audit fields
        update_payload = {"amount": "6000.00"}
        update_resp = await client.patch(f"/api/v1/fintrac/reports/{report_id}", json=update_payload)
        
        if update_resp.status_code == 200:
            # Fetch again to ensure audit fields didn't change
            await db_session.refresh(db_obj)
            assert db_obj.amount == Decimal("6000.00")
            assert db_obj.created_by == "system_user" # Should remain unchanged
            assert str(db_obj.created_at) == original_created_at

    async def test_financial_precision_integrity(self, client: AsyncClient, db_session):
        """Test that decimal precision is maintained through the API and DB."""
        precise_payload = {
            "amount": "12345.6789", # High precision
            "transaction_type": "wire",
            "created_by": "precision_test"
        }
        
        response = await client.post("/api/v1/fintrac/reports", json=precise_payload)
        assert response.status_code == 201
        
        report_id = response.json()["id"]
        stmt = select(FintracReport).where(FintracReport.id == report_id)
        result = await db_session.execute(stmt)
        db_obj = result.scalar_one_or_none()
        
        # Verify strict Decimal equality
        assert db_obj.amount == Decimal("12345.6789")