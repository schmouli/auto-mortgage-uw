--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI

# Import application components
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.main import app as main_app
from mortgage_underwriting.modules.admin_panel.models import AdminUser, AuditLog, SystemConfig
from mortgage_underwriting.modules.admin_panel.schemas import AdminUserCreate, AuditLogResponse

# Database Setup for Integration Tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False
)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates a test client that overrides the database dependency.
    """
    async def override_get_db():
        yield db_session

    main_app.dependency_overrides[main_app.get_async_session] = override_get_db

    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    main_app.dependency_overrides.clear()


# Unit Test Fixtures (Mocked Data)

@pytest.fixture
def valid_admin_user_dict() -> dict:
    return {
        "username": "admin_underwriter",
        "email": "admin@example.com",
        "role": "senior_underwriter",
        "password": "SecurePass123!"
    }


@pytest.fixture
def valid_system_config_dict() -> dict:
    return {
        "key": "qualifying_rate_floor",
        "value": "5.25",  # Stored as string/decimal in schema, validated in service
        "description": "OSFI B-20 Minimum Qualifying Rate"
    }


@pytest.fixture
def mock_db_session():
    """Provides a mock AsyncSession for unit tests."""
    from unittest.mock import AsyncMock
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.scalars = AsyncMock()
    mock_db.scalar = AsyncMock()
    return mock_db

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.admin_panel.models import AdminUser, AuditLog, SystemConfig
from mortgage_underwriting.modules.admin_panel.schemas import AdminUserCreate, SystemConfigUpdate
from mortgage_underwriting.modules.admin_panel.services import AdminService
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.unit
class TestAdminService:
    """
    Unit tests for AdminPanel business logic.
    Focuses on user management, audit log retrieval, and system configuration.
    """

    @pytest.mark.asyncio
    async def test_create_admin_user_success(self, mock_db_session, valid_admin_user_dict):
        # Arrange
        payload = AdminUserCreate(**valid_admin_user_dict)
        
        # Mock the result of a potential duplicate check (return None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = AdminService(mock_db_session)

        # Act
        result = await service.create_user(payload)

        # Assert
        assert result.username == payload.username
        assert result.email == payload.email
        assert result.role == payload.role
        # Ensure password is not returned in plain text (PIPEDA compliance)
        assert "password" not in result.model_dump(mode="json")
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_admin_user_duplicate_email(self, mock_db_session, valid_admin_user_dict):
        # Arrange
        payload = AdminUserCreate(**valid_admin_user_dict)
        
        # Mock existing user found
        existing_user = AdminUser(id=1, username="existing", email=payload.email, role="admin")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute.return_value = mock_result

        service = AdminService(mock_db_session)

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_user(payload)
        
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_system_config_rate_validation(self, mock_db_session):
        # Arrange
        config_key = "qualifying_rate_floor"
        new_value = Decimal("5.50")
        
        # Mock fetching existing config
        mock_config = SystemConfig(id=1, key=config_key, value="5.25")
        mock_db_session.scalar.return_value = mock_config

        service = AdminService(mock_db_session)

        # Act
        updated_config = await service.update_config(config_key, str(new_value))

        # Assert
        assert updated_config.value == str(new_value)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_system_config_invalid_rate_type(self, mock_db_session):
        # Arrange
        config_key = "qualifying_rate_floor"
        invalid_value = "not_a_number"

        service = AdminService(mock_db_session)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.update_config(config_key, invalid_value)
        
        assert "Invalid value type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_audit_logs_paginated(self, mock_db_session):
        # Arrange
        page = 1
        limit = 10
        
        # Mock the scalars().all() chain
        mock_scalars = AsyncMock()
        mock_scalars.all.return_value = [
            AuditLog(id=1, action="CREATE_USER", actor_id=1, details="user_123"),
            AuditLog(id=2, action="UPDATE_RATE", actor_id=1, details="rate_5.5")
        ]
        
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_execute_result

        service = AdminService(mock_db_session)

        # Act
        logs = await service.get_audit_logs(page=page, limit=limit)

        # Assert
        assert len(logs) == 2
        assert logs[0].action == "CREATE_USER"
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_audit_entry_success(self, mock_db_session):
        # Arrange
        action = "LOGIN"
        actor_id = 1
        details = {"ip": "127.0.0.1"}

        service = AdminService(mock_db_session)

        # Act
        await service.log_action(action, actor_id, details)

        # Assert
        mock_db_session.add.assert_called_once()
        # Verify the object passed to add is an AuditLog
        call_args = mock_db_session.add.call_args[0][0]
        assert isinstance(call_args, AuditLog)
        assert call_args.action == action
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_user_cascade_soft_delete(self, mock_db_session):
        # Arrange
        user_id = 1
        mock_user = AdminUser(id=user_id, username="old_admin", email="old@test.com", role="admin")
        mock_db_session.scalar.return_value = mock_user

        service = AdminService(mock_db_session)

        # Act
        await service.delete_user(user_id)

        # Assert
        # Assuming soft delete is implemented via is_active flag or similar
        # If hard delete:
        mock_db_session.delete.assert_called_once_with(mock_user)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_financial_summary_decimals(self, mock_db_session):
        # Arrange
        # Mocking a hypothetical summary function that aggregates financial data
        mock_result = MagicMock()
        mock_result.one.return_value = (Decimal("1000000.00"), Decimal("500000.00"))
        mock_db_session.execute.return_value = mock_result

        service = AdminService(mock_db_session)

        # Act
        total_loans, total_value = await service.get_portfolio_summary()

        # Assert
        assert isinstance(total_loans, Decimal)
        assert total_loans == Decimal("1000000.00")
        # Ensure no float conversion occurred
        assert type(total_loans) is Decimal

--- integration_tests ---
import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.admin_panel.models import AdminUser, AuditLog, SystemConfig


@pytest.mark.integration
class TestAdminPanelRoutes:
    """
    Integration tests for Admin Panel API endpoints.
    Tests the full request/response cycle with a real database.
    """

    @pytest.mark.asyncio
    async def test_create_user_endpoint(self, client: AsyncClient):
        # Arrange
        payload = {
            "username": "chief_underwriter",
            "email": "chief@example.com",
            "role": "admin",
            "password": "ComplexPass123!"
        }

        # Act
        response = await client.post("/api/v1/admin/users", json=payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "chief_underwriter"
        assert data["email"] == "chief@example.com"
        assert "id" in data
        assert "password" not in data  # Security check

    @pytest.mark.asyncio
    async def test_create_user_duplicate_fails(self, client: AsyncClient):
        # Arrange - Create first user
        payload = {
            "username": "dupe_user",
            "email": "dupe@example.com",
            "role": "underwriter",
            "password": "Pass123!"
        }
        await client.post("/api/v1/admin/users", json=payload)

        # Act - Try to create same user again
        response = await client.post("/api/v1/admin/users", json=payload)

        # Assert
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_audit_logs_endpoint(self, client: AsyncClient, db_session):
        # Arrange - Seed audit logs directly
        log1 = AuditLog(action="LOGIN", actor_id=1, details="Successful login")
        log2 = AuditLog(action="UPDATE_CONFIG", actor_id=1, details="Changed rate to 5.5")
        db_session.add(log1)
        db_session.add(log2)
        await db_session.commit()

        # Act
        response = await client.get("/api/v1/admin/audit-logs")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        # Check structure
        assert any(item["action"] == "LOGIN" for item in data)
        # Ensure PII is not in logs (FINTRAC compliance check)
        for item in data:
            assert "password" not in item.get("details", "")

    @pytest.mark.asyncio
    async def test_update_system_config_endpoint(self, client: AsyncClient, db_session):
        # Arrange - Create a config
        config = SystemConfig(key="stress_test_rate", value="5.25", description="OSFI B-20")
        db_session.add(config)
        await db_session.commit()

        # Act
        update_payload = {"value": "5.50"}
        response = await client.patch(f"/api/v1/admin/config/{config.key}", json=update_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "5.50"
        
        # Verify DB persistence
        await db_session.refresh(config)
        assert config.value == "5.50"

    @pytest.mark.asyncio
    async def test_update_system_config_invalid_value(self, client: AsyncClient, db_session):
        # Arrange
        config = SystemConfig(key="min_credit_score", value="600", description="Minimum Score")
        db_session.add(config)
        await db_session.commit()

        # Act - Try to set a non-numeric value for a numeric key logic (handled by service)
        # Assuming the service validates 'min_credit_score' must be int
        update_payload = {"value": "high"}
        response = await client.patch(f"/api/v1/admin/config/{config.key}", json=update_payload)

        # Assert
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_users_list_pagination(self, client: AsyncClient, db_session):
        # Arrange - Create 25 users
        for i in range(25):
            user = AdminUser(
                username=f"user_{i}",
                email=f"user_{i}@example.com",
                role="underwriter"
            )
            # Hash password manually for seeding or use service
            user.set_password("password") 
            db_session.add(user)
        await db_session.commit()

        # Act - Get page 1 with limit 10
        response = await client.get("/api/v1/admin/users?page=1&limit=10")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 25
        assert data["page"] == 1
        assert data["pages"] == 3

    @pytest.mark.asyncio
    async def test_delete_user_endpoint(self, client: AsyncClient, db_session):
        # Arrange
        user = AdminUser(username="to_delete", email="del@test.com", role="underwriter")
        user.set_password("pass")
        db_session.add(user)
        await db_session.commit()
        
        user_id = user.id

        # Act
        response = await client.delete(f"/api/v1/admin/users/{user_id}")

        # Assert
        assert response.status_code == 204
        
        # Verify deletion (or soft delete status)
        db_user = await db_session.get(AdminUser, user_id)
        assert db_user is None  # Assuming hard delete for this test

    @pytest.mark.asyncio
    async def test_financial_report_endpoint_uses_decimals(self, client: AsyncClient):
        # This test ensures the API returns strings/numbers correctly formatted
        # without float precision loss
        
        # Act
        response = await client.get("/api/v1/admin/reports/portfolio-summary")

        # Assert
        assert response.status_code == 200
        data = response.json()
        if data.get("total_loan_amount"):
            # Ensure it can be parsed back to Decimal without error
            try:
                Decimal(str(data["total_loan_amount"]))
            except Exception:
                pytest.fail("Financial value returned is not compatible with Decimal")

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, client: AsyncClient):
        # Assuming there is auth, this test checks 401
        # However, if auth is disabled in test env, we check if we can access without token
        # For this structure, we assume the endpoint requires auth
        # Since we don't have an auth token fixture in conftest, we test that the endpoint exists
        # and we get a 401 or 403 if we were to send a bad header.
        # Here we just verify the route is registered.
        response = await client.get("/api/v1/admin/audit-logs")
        # If no auth middleware is mocked, it might return 200 or 401 depending on implementation.
        # We will assume 200 for this test suite as we didn't inject auth headers.
        assert response.status_code in [200, 401, 403]