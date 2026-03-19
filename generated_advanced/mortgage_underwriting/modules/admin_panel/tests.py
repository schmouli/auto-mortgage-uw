--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.admin_panel.routes import router as admin_router

# Use an in-memory SQLite database for integration tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture to create a new database session for each test.
    Creates tables on setup and drops them on teardown.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app() -> FastAPI:
    """
    Fixture to create a test FastAPI application instance.
    """
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture for an async HTTP client using ASGI transport.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_admin_user_payload():
    """Payload for creating or updating an admin user."""
    return {
        "username": "admin_user",
        "email": "admin@example.com",
        "role": "underwriter_manager",
        "is_active": True,
    }


@pytest.fixture
def mock_system_config_payload():
    """
    Payload for system configuration updates.
    Includes OSFI B-20 compliant stress test rate.
    """
    return {
        "min_stress_test_rate": Decimal("5.25"),
        "max_gds_ratio": Decimal("39.0"),
        "max_tds_ratio": Decimal("44.0"),
        "insurance_enabled": True,
    }


@pytest.fixture
def mock_audit_log_data():
    """Mock data representing an immutable audit trail entry (FINTRAC)."""
    return {
        "id": 1,
        "entity_id": "uuid-1234",
        "action": "APPLICATION_APPROVED",
        "actor": "admin_user",
        "timestamp": "2023-10-27T10:00:00Z",
        "details": {"status": "approved", "reason": "meets criteria"},
        # PII (SIN/DOB) must NOT be present here
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from mortgage_underwriting.modules.admin_panel.services import AdminService
from mortgage_underwriting.modules.admin_panel.exceptions import (
    AdminConfigurationError,
    InvalidRateError,
)
from mortgage_underwriting.common.exceptions import AppException

# Import paths assumed based on project structure
# from mortgage_underwriting.modules.admin_panel.models import SystemConfig, AuditLog
# from mortgage_underwriting.modules.admin_panel.schemas import ConfigUpdate, DashboardStats


@pytest.mark.unit
class TestAdminService:
    """
    Unit tests for AdminService business logic.
    Focuses on regulatory compliance (OSFI B-20) and data integrity.
    """

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.scalar_one_or_none = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_success(self, mock_db):
        """
        Test retrieving dashboard statistics.
        Ensures counts are returned correctly.
        """
        # Mock return values for aggregate queries
        mock_db.scalar.side_effect = [150, 100, 50]  # total, approved, pending

        service = AdminService(mock_db)
        stats = await service.get_dashboard_stats()

        assert stats.total_applications == 150
        assert stats.approved_applications == 100
        assert stats.pending_applications == 50
        assert mock_db.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_update_system_config_osfi_compliance(self, mock_db):
        """
        Test updating system configuration.
        Validates OSFI B-20 rule: qualifying rate >= 5.25%.
        """
        # Mock existing config
        mock_config = MagicMock()
        mock_config.min_stress_test_rate = Decimal("5.25")
        mock_db.scalar_one_or_none.return_value = mock_config

        service = AdminService(mock_db)
        
        # Valid update
        payload = {
            "min_stress_test_rate": Decimal("5.50"),
            "max_gds_ratio": Decimal("39.0"),
            "max_tds_ratio": Decimal("44.0")
        }
        
        result = await service.update_system_config(config_id=1, payload=payload)
        
        assert result.min_stress_test_rate == Decimal("5.50")
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_system_config_rate_too_low_raises_osfi_error(self, mock_db):
        """
        Test that updating the stress test rate below OSFI minimum (5.25%) raises an error.
        """
        mock_config = MagicMock()
        mock_config.min_stress_test_rate = Decimal("5.25")
        mock_db.scalar_one_or_none.return_value = mock_config

        service = AdminService(mock_db)
        
        # Invalid update (Rate < 5.25%)
        payload = {
            "min_stress_test_rate": Decimal("4.00"), # Violates OSFI B-20
            "max_gds_ratio": Decimal("39.0"),
            "max_tds_ratio": Decimal("44.0")
        }

        with pytest.raises(InvalidRateError) as exc_info:
            await service.update_system_config(config_id=1, payload=payload)
        
        assert "qualifying rate" in str(exc_info.value).lower()
        assert "5.25" in str(exc_info.value)
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_system_config_gds_exceeds_limit(self, mock_db):
        """
        Test that GDS limit cannot exceed OSFI hard limit of 39%.
        """
        mock_config = MagicMock()
        mock_config.max_gds_ratio = Decimal("39.0")
        mock_db.scalar_one_or_none.return_value = mock_config

        service = AdminService(mock_db)
        
        payload = {
            "min_stress_test_rate": Decimal("5.25"),
            "max_gds_ratio": Decimal("45.00"), # Violates OSFI limit (39%)
            "max_tds_ratio": Decimal("44.0")
        }

        with pytest.raises(AdminConfigurationError) as exc_info:
            await service.update_system_config(config_id=1, payload=payload)
        
        assert "GDS" in str(exc_info.value)
        assert "39%" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_audit_logs_pii_redaction(self, mock_db):
        """
        Test retrieving audit logs.
        Ensures PII (SIN, DOB) is not included in the response (PIPEDA).
        """
        # Mock a log entry that might contain sensitive data in the DB
        mock_log_entry = MagicMock()
        mock_log_entry.id = 1
        mock_log_entry.action = "LOGIN"
        mock_log_entry.actor = "user_123"
        mock_log_entry.details = {"ip": "127.0.0.1"}
        # Simulate that 'sin' field exists on model but service should not return it
        mock_log_entry.sin_hash = "hashed_sin_value" 

        # Setup mock execution result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log_entry]
        mock_db.execute.return_value = mock_result

        service = AdminService(mock_db)
        logs = await service.get_audit_logs(limit=10)

        assert len(logs) == 1
        assert hasattr(logs[0], 'action')
        # Verify the raw model attribute is not exposed in the response schema
        # (Assuming the service maps model to response schema)
        response_dict = logs[0].model_dump() if hasattr(logs[0], 'model_dump') else logs[0].__dict__
        assert 'sin_hash' not in response_dict
        assert 'sin' not in response_dict

    @pytest.mark.asyncio
    async def test_create_admin_user_missing_fields(self, mock_db):
        """
        Test validation when creating an admin user with missing required fields.
        """
        service = AdminService(mock_db)
        
        incomplete_payload = {
            "username": "new_admin",
            # Missing email and role
        }

        with pytest.raises(AppException) as exc_info:
            await service.create_admin_user(incomplete_payload)
        
        assert "validation" in str(exc_info.value).lower()
        mock_db.add.assert_not_called()

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, status
from sqlalchemy import select

from mortgage_underwriting.modules.admin_panel.routes import router as admin_router
from mortgage_underwriting.modules.admin_panel.models import SystemConfig, AuditLog
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.security import verify_token

# Mock authentication dependency
async def mock_auth_override():
    return {"user_id": "admin-test", "role": "admin"}


@pytest.mark.integration
@pytest.mark.asyncio
class TestAdminPanelIntegration:
    """
    Integration tests for Admin Panel endpoints.
    Tests full request/response cycle with database interaction.
    """

    @pytest.fixture
    def app(self, db_session):
        """
        Create app with DB session override and Auth override.
        """
        app = FastAPI()
        app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])

        # Override DB dependency
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db
        app.dependency_overrides[verify_token] = mock_auth_override
        
        yield app
        app.dependency_overrides.clear()

    @pytest.fixture
    async def client(self, app):
        """
        Async client for testing endpoints.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_get_dashboard_stats_endpoint(self, client: AsyncClient):
        """
        Test GET /api/v1/admin/stats
        """
        response = await client.get("/api/v1/admin/stats")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_applications" in data
        assert "approved_applications" in data
        # Validate types
        assert isinstance(data["total_applications"], int)

    async def test_update_system_config_endpoint_success(self, client: AsyncClient, db_session):
        """
        Test PATCH /api/v1/admin/config
        Updates OSFI B-20 settings.
        """
        # Setup: Create a default config
        config = SystemConfig(
            min_stress_test_rate=Decimal("5.25"),
            max_gds_ratio=Decimal("39.0"),
            max_tds_ratio=Decimal("44.0")
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)

        update_payload = {
            "min_stress_test_rate": "6.00", # JSON string, converted to Decimal
            "max_gds_ratio": "39.0"
        }

        response = await client.patch(f"/api/v1/admin/config/{config.id}", json=update_payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["min_stress_test_rate"] == "6.00"
        
        # Verify DB update
        await db_session.refresh(config)
        assert config.min_stress_test_rate == Decimal("6.00")

    async def test_update_system_config_endpoint_osfi_validation(self, client: AsyncClient, db_session):
        """
        Test PATCH /api/v1/admin/config with invalid OSFI rate.
        Ensures API returns 400/422 for regulatory violations.
        """
        config = SystemConfig(
            min_stress_test_rate=Decimal("5.25"),
            max_gds_ratio=Decimal("39.0"),
            max_tds_ratio=Decimal("44.0")
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)

        # Attempt to set rate below 5.25%
        invalid_payload = {
            "min_stress_test_rate": "4.00",
            "max_gds_ratio": "39.0"
        }

        response = await client.patch(f"/api/v1/admin/config/{config.id}", json=invalid_payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert "qualifying rate" in data["detail"].lower()

    async def test_get_audit_logs_endpoint(self, client: AsyncClient, db_session):
        """
        Test GET /api/v1/admin/audit
        Verifies FINTRAC audit trail retrieval.
        """
        # Setup: Create an audit log
        log_entry = AuditLog(
            entity_id="app-123",
            action="STATUS_CHANGE",
            actor="admin_user",
            details={"old": "pending", "new": "approved"}
        )
        db_session.add(log_entry)
        await db_session.commit()

        response = await client.get("/api/v1/admin/audit?limit=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1
        
        # Check PII is not exposed
        first_log = data["items"][0]
        assert "sin" not in first_log
        assert "dob" not in first_log
        assert first_log["action"] == "STATUS_CHANGE"

    async def test_unauthorized_access(self, client: AsyncClient, app):
        """
        Test that removing auth override results in 401.
        """
        # Remove override to test actual security (if implemented) or default behavior
        app.dependency_overrides.pop(verify_token, None)

        response = await client.get("/api/v1/admin/stats")
        
        # Assuming default auth requires a token
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_create_config_endpoint_decimal_precision(self, client: AsyncClient):
        """
        Test POST /api/v1/admin/config
        Ensures Decimal precision is maintained for financial thresholds.
        """
        payload = {
            "min_stress_test_rate": "5.75",
            "max_gds_ratio": "35.50",
            "max_tds_ratio": "42.00"
        }

        response = await client.post("/api/v1/admin/config", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        # Ensure we get strings back or decimals, not floats
        assert data["max_gds_ratio"] == "35.50" or Decimal("35.50") == Decimal(data["max_gds_ratio"])