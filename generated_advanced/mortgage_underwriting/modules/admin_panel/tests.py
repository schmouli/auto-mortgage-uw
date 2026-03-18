--- conftest.py ---
```python
import asyncio
import pytest
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool

# Assuming the module name is 'admin_panel' based on the user request
# Adjust imports based on actual file structure if necessary
from mortgage_underwriting.modules.admin_panel.routes import router
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.admin_panel.models import User, AuditLog
from mortgage_underwriting.modules.admin_panel.schemas import UserCreate, UserResponse

# Use SQLite for integration tests for speed and isolation
# In a real CI/CD pipeline, this might point to a test Postgres instance
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
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
async def app():
    """Fixture for the FastAPI application."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin", tags=["admin"])
    return app

@pytest.fixture(scope="function")
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async client for testing endpoints."""
    # Override security dependency to bypass auth for testing
    from mortgage_underwriting.common.security import verify_token
    from fastapi import Depends
    
    # Mock the dependency
    async def mock_verify_token():
        return {"user_id": "test-admin-001", "role": "admin"}
    
    app.dependency_overrides[verify_token] = mock_verify_token
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture
def valid_user_payload():
    return {
        "username": "jdoe",
        "email": "john.doe@example.com",
        "full_name": "John Doe",
        "role": "underwriter",
        "sin": "123456789", # Should be encrypted/hashed
        "password": "SecurePassword123!"
    }

@pytest.fixture
def sample_user(db_session):
    """Create a sample user in the database for tests that need existing data."""
    # Note: In a real scenario, password hashing happens in the service/model
    # Here we just simulate the DB entry state
    user = User(
        username="existing_user",
        email="existing@example.com",
        full_name="Existing User",
        role="admin",
        sin_hash="hashed_sin_value",
        password_hash="hashed_password"
    )
    return user
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.admin_panel.services import AdminService
from mortgage_underwriting.modules.admin_panel.models import User, AuditLog
from mortgage_underwriting.modules.admin_panel.exceptions import (
    UserAlreadyExistsError,
    AuditLogImmutableError,
    InvalidRoleError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestAdminService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return AdminService(mock_db)

    @pytest.mark.asyncio
    async def test_create_user_success(self, service, mock_db):
        """Test successful user creation with password hashing."""
        payload = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123",
            "role": "underwriter",
            "sin": "987654321"
        }
        
        # Mock DB checks: user doesn't exist
        mock_db.scalar.return_value = None
        
        result = await service.create_user(payload)
        
        assert result.username == "newuser"
        assert result.email == "new@example.com"
        assert result.role == "underwriter"
        # Verify PIPEDA compliance: SIN is hashed, not stored in plain text
        assert result.sin_hash != "987654321" 
        assert "987654321" not in str(result.sin_hash)
        # Verify password is hashed
        assert result.password_hash != "password123"
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email_raises(self, service, mock_db):
        """Test that creating a user with an existing email raises an error."""
        payload = {
            "username": "newuser",
            "email": "existing@example.com",
            "password": "password123",
            "role": "underwriter",
            "sin": "987654321"
        }
        
        # Simulate existing user found
        existing_user = User(id=1, username="old", email="existing@example.com")
        mock_db.scalar.return_value = existing_user
        
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await service.create_user(payload)
        
        assert "email" in str(exc_info.value).lower()
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_user_invalid_role_raises(self, service, mock_db):
        """Test that creating a user with an invalid role raises ValueError."""
        payload = {
            "username": "hacker",
            "email": "hacker@example.com",
            "password": "password123",
            "role": "super_admin", # Invalid role
            "sin": "000000000"
        }
        
        mock_db.scalar.return_value = None
        
        with pytest.raises(InvalidRoleError):
            await service.create_user(payload)

    @pytest.mark.asyncio
    async def test_get_audit_logs_success(self, service, mock_db):
        """Test retrieving audit logs with pagination."""
        # Mock the result of scalars().all()
        mock_log = AuditLog(
            id=1,
            action="USER_LOGIN",
            entity_type="User",
            entity_id="user-123",
            details={"ip": "127.0.0.1"}
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        mock_db.execute.return_value = mock_result
        
        logs = await service.get_audit_logs(limit=10, offset=0)
        
        assert len(logs) == 1
        assert logs[0].action == "USER_LOGIN"
        assert logs[0].entity_id == "user-123"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_audit_log_fails_immutability(self, service, mock_db):
        """Test FINTRAC compliance: Audit logs cannot be deleted."""
        log_id = 1
        
        # Mock fetching the log
        mock_log = AuditLog(id=log_id, action="TEST", entity_type="Test")
        mock_db.get.return_value = mock_log
        
        with pytest.raises(AuditLogImmutableError) as exc_info:
            await service.delete_audit_log(log_id)
        
        assert "immutable" in str(exc_info.value).lower()
        # Ensure delete was never called on the session
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_user_role_success(self, service, mock_db):
        """Test updating a user's role."""
        user_id = 1
        new_role = "senior_underwriter"
        
        mock_user = User(id=user_id, username="user1", role="underwriter")
        mock_db.get.return_value = mock_user
        
        updated_user = await service.update_user_role(user_id, new_role)
        
        assert updated_user.role == new_role
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(mock_user)

    @pytest.mark.asyncio
    async def test_update_user_role_not_found(self, service, mock_db):
        """Test updating a user that does not exist."""
        mock_db.get.return_value = None
        
        with pytest.raises(AppException) as exc_info:
            await service.update_user_role(999, "admin")
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_user_sin_hashing_algorithm(self, service, mock_db):
        """Verify specific hashing algorithm (SHA256) is used for SIN."""
        payload = {
            "username": "hashcheck",
            "email": "hash@example.com",
            "password": "pass",
            "role": "underwriter",
            "sin": "123456789"
        }
        mock_db.scalar.return_value = None
        
        with patch('mortgage_underwriting.modules.admin_panel.services.hashlib.sha256') as mock_sha:
            # Setup mock return value for the hexdigest
            mock_sha.return_value.hexdigest.return_value = "hashed_sin_123"
            
            await service.create_user(payload)
            
            # Verify sha256 was called with the SIN encoded as bytes
            mock_sha.assert_called_once_with(b"123456789")

    @pytest.mark.asyncio
    async def test_log_action_creates_audit_entry(self, service, mock_db):
        """Test that logging an action creates a record in the DB."""
        await service.log_action(
            user_id="admin-1",
            action="UPDATE_RATE",
            entity_type="Configuration",
            entity_id="rate-1",
            details={"old_rate": "5.0", "new_rate": "5.25"}
        )
        
        mock_db.add.assert_called_once()
        # Verify the object added is an AuditLog
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, AuditLog)
        assert added_obj.action == "UPDATE_RATE"
        mock_db.commit.assert_awaited_once()
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.admin_panel.models import User, AuditLog
from mortgage_underwriting.modules.admin_panel.schemas import UserRole

@pytest.mark.integration
@pytest.mark.asyncio
class TestAdminPanelEndpoints:

    async def test_create_user_endpoint(self, client: AsyncClient, db_session):
        """Test creating a new user via API."""
        payload = {
            "username": "jdoe_integration",
            "email": "jdoe@example.com",
            "full_name": "John Doe",
            "role": "underwriter",
            "sin": "123456789",
            "password": "StrongPass123!"
        }
        
        response = await client.post("/api/v1/admin/users", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "jdoe_integration"
        assert data["email"] == "jdoe@example.com"
        assert data["role"] == "underwriter"
        assert "id" in data
        assert "password" not in data  # Ensure password is not in response
        assert "sin" not in data      # Ensure SIN is not in response (PIPEDA)
        assert "sin_hash" not in data # Ensure hash is not leaked

        # Verify DB state
        stmt = select(User).where(User.username == "jdoe_integration")
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.sin_hash is not None
        assert user.sin_hash != "123456789"

    async def test_create_user_duplicate_email_conflict(self, client: AsyncClient, db_session):
        """Test that duplicate email returns 409 Conflict."""
        payload = {
            "username": "user1",
            "email": "duplicate@example.com",
            "full_name": "User One",
            "role": "underwriter",
            "sin": "111111111",
            "password": "Pass123!"
        }
        
        # Create first user
        await client.post("/api/v1/admin/users", json=payload)
        
        # Try to create second user with same email but different username
        payload["username"] = "user2"
        response = await client.post("/api/v1/admin/users", json=payload)
        
        assert response.status_code == 409
        assert "detail" in response.json()

    async def test_get_users_list(self, client: AsyncClient, db_session):
        """Test retrieving a list of users."""
        # Seed data directly into DB
        user1 = User(
            username="admin_user", 
            email="admin@test.com", 
            role="admin",
            sin_hash="hash1",
            password_hash="pass1"
        )
        user2 = User(
            username="underwriter_user", 
            email="uw@test.com", 
            role="underwriter",
            sin_hash="hash2",
            password_hash="pass2"
        )
        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()
        
        response = await client.get("/api/v1/admin/users")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        # Verify PII protection
        for user in data["items"]:
            assert "sin" not in user
            assert "password" not in user

    async def test_get_audit_logs_endpoint(self, client: AsyncClient, db_session):
        """Test retrieving audit logs."""
        # Seed audit log
        log = AuditLog(
            action="USER_CREATED",
            entity_type="User",
            entity_id="user-123",
            performed_by="admin-1",
            details={"username": "new_user"}
        )
        db_session.add(log)
        await db_session.commit()
        
        response = await client.get("/api/v1/admin/audit-logs")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["action"] == "USER_CREATED"
        assert data[0]["performed_by"] == "admin-1"

    async def test_update_user_role_endpoint(self, client: AsyncClient, db_session):
        """Test updating a user's role via API."""
        # Create user
        create_payload = {
            "username": "promote_me",
            "email": "promote@test.com",
            "full_name": "Promote Me",
            "role": "underwriter",
            "sin": "999999999",
            "password": "Pass123!"
        }
        create_resp = await client.post("/api/v1/admin/users", json=create_payload)
        user_id = create_resp.json()["id"]
        
        # Update role
        update_payload = {"role": "admin"}
        update_resp = await client.patch(f"/api/v1/admin/users/{user_id}", json=update_payload)
        
        assert update_resp.status_code == 200
        assert update_resp.json()["role"] == "admin"
        
        # Verify Audit Log was created for this action
        stmt = select(AuditLog).where(AuditLog.action == "ROLE_UPDATED")
        result = await db_session.execute(stmt)
        audit_log = result.scalar_one_or_none()
        assert audit_log is not None
        assert audit_log.entity_id == str(user_id)

    async def test_get_user_by_id(self, client: AsyncClient, db_session):
        """Test retrieving a specific user by ID."""
        payload = {
            "username": "single_user",
            "email": "single@test.com",
            "full_name": "Single User",
            "role": "underwriter",
            "sin": "555555555",
            "password": "Pass123!"
        }
        create_resp = await client.post("/api/v1/admin/users", json=payload)
        user_id = create_resp.json()["id"]
        
        response = await client.get(f"/api/v1/admin/users/{user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["username"] == "single_user"

    async def test_invalid_role_payload(self, client: AsyncClient):
        """Test validation error for invalid role during creation."""
        payload = {
            "username": "bad_role",
            "email": "bad@test.com",
            "full_name": "Bad Role",
            "role": "hacker", # Invalid
            "sin": "000000000",
            "password": "Pass123!"
        }
        
        response = await client.post("/api/v1/admin/users", json=payload)
        
        assert response.status_code == 422 # Unprocessable Entity

    async def test_delete_user_forbidden(self, client: AsyncClient, db_session):
        """Test that deleting a user is handled correctly (e.g., soft delete or forbidden)."""
        # Assuming system policy prevents deletion of users for audit trail purposes
        # Or if deletion is allowed, it should be a soft delete.
        # Here we test if the endpoint exists and handles the request appropriately.
        # Based on FINTRAC, usually we don't delete, we deactivate.
        
        payload = {
            "username": "delete_me",
            "email": "delete@test.com",
            "full_name": "Delete Me",
            "role": "underwriter",
            "sin": "123123123",
            "password": "Pass123!"
        }
        create_resp = await client.post("/api/v1/admin/users", json=payload)
        user_id = create_resp.json()["id"]
        
        # Attempt delete
        response = await client.delete(f"/api/v1/admin/users/{user_id}")
        
        # Expect 405 Method Not Allowed or 403 Forbidden depending on implementation
        # Assuming it is not allowed to maintain audit trail
        assert response.status_code in [405, 403]

    async def test_health_check(self, client: AsyncClient):
        """Test the health check endpoint for the admin module."""
        response = await client.get("/api/v1/admin/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
```