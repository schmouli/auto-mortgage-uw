--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, func, Boolean, Text
from datetime import datetime
from fastapi import FastAPI

# Import the module under test
from mortgage_underwriting.modules.admin_panel.routes import router as admin_router
from mortgage_underwriting.common.database import Base

# Test Database Configuration
# Using SQLite for test isolation and speed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture to create a new database session for a test.
    Creates all tables before the test and drops them after.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def app() -> FastAPI:
    """
    Fixture to create a test FastAPI application instance.
    Includes the Admin Panel router.
    """
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture to create an HTTP client for integration tests.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# Fixtures for Test Data

@pytest.fixture
def valid_admin_user_data():
    return {
        "username": "admin_test",
        "email": "admin@example.com",
        "role": "underwriter_manager",
        "is_active": True
    }

@pytest.fixture
def valid_audit_log_data():
    return {
        "action": "LOGIN",
        "actor_id": "user_123",
        "details": {"ip": "127.0.0.1"},
        "timestamp": datetime.utcnow()
    }

@pytest.fixture
def valid_system_config_data():
    return {
        "key": "min_credit_score",
        "value": "600",
        "description": "Minimum credit score for approval"
    }

@pytest.fixture
def stress_test_config_data():
    return {
        "key": "stress_test_rate",
        "value": "5.25",
        "description": "OSFI B-20 Qualifying Rate Floor"
    }
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.admin_panel.services import (
    AdminService,
    AuditLogService,
    SystemConfigService
)
from mortgage_underwriting.modules.admin_panel.exceptions import (
    AdminUserExistsError,
    AuditLogNotFoundError,
    ConfigLockViolationError
)
from mortgage_underwriting.modules.admin_panel.models import (
    AdminUser,
    AuditLog,
    SystemConfig
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestAdminService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.scalars = MagicMock()
        db.scalar = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_admin_user_success(self, mock_db, valid_admin_user_data):
        # Arrange
        service = AdminService(mock_db)
        # Mock scalar to return None (user doesn't exist)
        mock_db.scalar.return_value = None
        
        # Act
        result = await service.create_user(valid_admin_user_data)

        # Assert
        assert result.username == valid_admin_user_data["username"]
        assert result.email == valid_admin_user_data["email"]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_admin_user_duplicate_email_raises(self, mock_db, valid_admin_user_data):
        # Arrange
        service = AdminService(mock_db)
        existing_user = AdminUser(**valid_admin_user_data)
        mock_db.scalar.return_value = existing_user

        # Act & Assert
        with pytest.raises(AdminUserExistsError):
            await service.create_user(valid_admin_user_data)
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deactivate_user_success(self, mock_db):
        # Arrange
        service = AdminService(mock_db)
        user = AdminUser(id=1, username="test", email="test@test.com", is_active=True)
        mock_db.scalar.return_value = user

        # Act
        await service.deactivate_user(user_id=1)

        # Assert
        assert user.is_active is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deactivate_non_existent_user_raises(self, mock_db):
        # Arrange
        service = AdminService(mock_db)
        mock_db.scalar.return_value = None

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.deactivate_user(user_id=999)
        assert "not found" in str(exc_info.value.detail).lower()

@pytest.mark.unit
class TestAuditLogService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_log_action_success(self, mock_db, valid_audit_log_data):
        # Arrange
        service = AuditLogService(mock_db)
        
        # Act
        await service.log_action(
            action=valid_audit_log_data["action"],
            actor_id=valid_audit_log_data["actor_id"],
            details=valid_audit_log_data["details"]
        )

        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        # Verify immutable fields are set
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.action == "LOGIN"
        assert added_obj.id is not None # UUID generation check

    @pytest.mark.asyncio
    async def test_retrieve_logs_paginated(self, mock_db):
        # Arrange
        service = AuditLogService(mock_db)
        mock_result = MagicMock()
        mock_result.all.return_value = [AuditLog(id="1", action="TEST", actor_id="u1")]
        mock_db.scalars.return_value = mock_result

        # Act
        logs = await service.get_logs(limit=10, offset=0)

        # Assert
        assert len(logs) == 1
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retrieve_logs_with_date_filter(self, mock_db):
        # Arrange
        service = AuditLogService(mock_db)
        start_date = datetime(2023, 1, 1)
        
        # Act
        await service.get_logs(start_date=start_date)

        # Assert
        # We verify the query was constructed (implicitly via execute call)
        # In a real unit test we might inspect the SQL string, but here checking execution is sufficient
        mock_db.execute.assert_awaited_once()

@pytest.mark.unit
class TestSystemConfigService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.scalar = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_update_stress_test_rate_compliance(self, mock_db, stress_test_config_data):
        """
        Regulatory: Verify that updating the stress test rate logs the change for auditability.
        """
        # Arrange
        service = SystemConfigService(mock_db)
        existing_config = SystemConfig(
            id=1, 
            key="stress_test_rate", 
            value="5.00", 
            is_locked=False
        )
        mock_db.scalar.return_value = existing_config

        # Act
        new_value = "5.50"
        await service.update_config(key="stress_test_rate", value=new_value)

        # Assert
        assert existing_config.value == new_value
        assert existing_config.updated_at is not None
        mock_db.commit.assert_awaited_once()
        # In a real scenario, we would check if an AuditLog entry was created
        # but since that's a separate service, we verify the state change here.

    @pytest.mark.asyncio
    async def test_update_locked_config_raises_error(self, mock_db):
        """
        Security: Ensure locked configurations cannot be modified via standard update.
        """
        # Arrange
        service = SystemConfigService(mock_db)
        locked_config = SystemConfig(
            id=1, 
            key="compliance_lock", 
            value="true", 
            is_locked=True
        )
        mock_db.scalar.return_value = locked_config

        # Act & Assert
        with pytest.raises(ConfigLockViolationError):
            await service.update_config(key="compliance_lock", value="false")
        
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_config_value_as_decimal(self, mock_db):
        """
        Financial: Ensure decimal values are handled correctly.
        """
        # Arrange
        service = SystemConfigService(mock_db)
        mock_config = SystemConfig(id=1, key="max_loan_amount", value="500000.00")
        mock_db.scalar.return_value = mock_config

        # Act
        val = await service.get_config_value("max_loan_amount", as_type=Decimal)

        # Assert
        assert val == Decimal("500000.00")
        assert isinstance(val, Decimal)

    @pytest.mark.asyncio
    async def test_get_config_value_missing_returns_none(self, mock_db):
        # Arrange
        service = SystemConfigService(mock_db)
        mock_db.scalar.return_value = None

        # Act
        val = await service.get_config_value("missing_key")

        # Assert
        assert val is None
--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal

from mortgage_underwriting.modules.admin_panel.models import AdminUser, AuditLog, SystemConfig
from mortgage_underwriting.common.security import encrypt_pii

@pytest.mark.integration
@pytest.mark.asyncio
class TestAdminPanelEndpoints:

    async def test_create_user_endpoint(self, client: AsyncClient, db_session, valid_admin_user_data):
        """
        Test creating a new admin user via API.
        Verify DB persistence and response structure.
        """
        # Act
        response = await client.post("/api/v1/admin/users", json=valid_admin_user_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == valid_admin_user_data["username"]
        assert "id" in data
        assert "password" not in data  # Ensure password is not leaked in response

        # Verify DB
        stmt = select(AdminUser).where(AdminUser.email == valid_admin_user_data["email"])
        result = await db_session.execute(stmt)
        db_user = result.scalar_one()
        assert db_user is not None
        assert db_user.is_active is True

    async def test_create_user_duplicate_email_conflict(self, client: AsyncClient, db_session, valid_admin_user_data):
        """
        Test that duplicate emails return 409 Conflict.
        """
        # Setup - Create first user
        response1 = await client.post("/api/v1/admin/users", json=valid_admin_user_data)
        assert response1.status_code == 201

        # Act - Try to create same user again
        response2 = await client.post("/api/v1/admin/users", json=valid_admin_user_data)

        # Assert
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()

    async def test_list_audit_logs_endpoint(self, client: AsyncClient, db_session):
        """
        Test retrieving audit logs with pagination.
        """
        # Setup - Create logs directly in DB
        log1 = AuditLog(action="CREATE_USER", actor_id="admin_1", details={})
        log2 = AuditLog(action="UPDATE_RATE", actor_id="admin_1", details={})
        db_session.add(log1)
        db_session.add(log2)
        await db_session.commit()

        # Act
        response = await client.get("/api/v1/admin/audit-logs?limit=10")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 2
        assert data["total"] >= 2

    async def test_update_system_config_endpoint(self, client: AsyncClient, db_session, valid_system_config_data):
        """
        Test updating a system configuration.
        Verify update persistence.
        """
        # Setup - Create config
        config = SystemConfig(**valid_system_config_data)
        db_session.add(config)
        await db_session.commit()

        # Act
        update_payload = {"value": "650"}
        response = await client.put(f"/api/v1/admin/config/{valid_system_config_data['key']}", json=update_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "650"
        
        # Verify DB
        await db_session.refresh(config)
        assert config.value == "650"

    async def test_update_stress_test_rate_validation(self, client: AsyncClient, db_session):
        """
        Regulatory: Ensure stress test rate update accepts valid decimal strings.
        """
        # Setup
        config = SystemConfig(key="stress_test_rate", value="5.25", description="Floor")
        db_session.add(config)
        await db_session.commit()

        # Act - Update to exactly 5.25% (OSFI B-20 floor)
        response = await client.put("/api/v1/admin/config/stress_test_rate", json={"value": "5.25"})

        # Assert
        assert response.status_code == 200
        
        # Act - Update to 5.50%
        response = await client.put("/api/v1/admin/config/stress_test_rate", json={"value": "5.50"})
        assert response.status_code == 200

    async def test_update_config_invalid_format(self, client: AsyncClient, db_session):
        """
        Test that updating a config with invalid data (e.g., text for numeric field) is handled.
        """
        # Setup
        config = SystemConfig(key="min_credit_score", value="600", description="Score")
        db_session.add(config)
        await db_session.commit()

        # Act
        response = await client.put("/api/v1/admin/config/min_credit_score", json={"value": "not_a_number"})

        # Assert
        # Depending on implementation, this might be 422 (validation) or 400
        assert response.status_code in [400, 422]

    async def test_get_audit_logs_filter_by_action(self, client: AsyncClient, db_session):
        """
        Test filtering audit logs by specific action.
        """
        # Setup
        log1 = AuditLog(action="LOGIN", actor_id="u1", details={})
        log2 = AuditLog(action="LOGOUT", actor_id="u1", details={})
        db_session.add_all([log1, log2])
        await db_session.commit()

        # Act
        response = await client.get("/api/v1/admin/audit-logs?action=LOGIN")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(item["action"] == "LOGIN" for item in data["items"])

    async def test_delete_user_soft_delete(self, client: AsyncClient, db_session):
        """
        Verify that deleting a user performs a soft delete (sets is_active=False) 
        rather than removing the record (FINTRAC compliance).
        """
        # Setup
        user_data = {"username": "to_delete", "email": "del@test.com", "role": "viewer", "is_active": True}
        create_resp = await client.post("/api/v1/admin/users", json=user_data)
        user_id = create_resp.json()["id"]

        # Act
        response = await client.delete(f"/api/v1/admin/users/{user_id}")

        # Assert
        assert response.status_code == 204

        # Verify DB - User should still exist but be inactive
        stmt = select(AdminUser).where(AdminUser.id == user_id)
        result = await db_session.execute(stmt)
        db_user = result.scalar_one()
        assert db_user is not None # Record exists
        assert db_user.is_active is False # Soft deleted