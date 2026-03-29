```python
# conftest.py
import pytest
from collections.abc import AsyncGenerator, Generator
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from fastapi import FastAPI
from mortgage_underwriting.modules.auth.routes import router as auth_router
from mortgage_underwriting.common.config import settings

# Use an in-memory SQLite database for testing isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}, echo=False
)
AsyncTestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    Handles schema creation and teardown.
    """
    # Import models here to ensure they are registered with SQLAlchemy metadata
    from mortgage_underwriting.modules.auth.models import User
    from mortgage_underwriting.modules.audit.models import AuditLog

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncTestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def app() -> FastAPI:
    """
    Creates a test FastAPI application instance.
    """
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
    return app


@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates an AsyncClient for testing FastAPI endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def valid_user_payload() -> dict:
    return {
        "username": "test_underwriter",
        "email": "underwriter@example.com",
        "password": "SecurePass123!",
        "role": "underwriter"
    }

@pytest.fixture
def admin_user_payload() -> dict:
    return {
        "username": "admin_user",
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "role": "admin"
    }
```

```python
# unit_tests
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext

from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin, UserResponse
from mortgage_underwriting.modules.auth.services import AuthService, UserService
from mortgage_underwriting.common.exceptions import AppException

# Mocking the security utilities to avoid real crypto overhead in unit tests
mock_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@pytest.mark.unit
class TestUserService:
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, mock_db):
        # Arrange
        user_id = 1
        mock_user = User(id=user_id, username="testuser", email="test@example.com", role="user")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        # Act
        user = await UserService.get_by_id(mock_db, user_id)

        # Assert
        assert user is not None
        assert user.id == user_id
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, mock_db):
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        user = await UserService.get_by_id(mock_db, 999)

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_username_success(self, mock_db):
        # Arrange
        username = "testuser"
        mock_user = User(id=1, username=username, email="test@example.com", role="user")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        # Act
        user = await UserService.get_by_username(mock_db, username)

        # Assert
        assert user is not None
        assert user.username == username


@pytest.mark.unit
class TestAuthService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def user_payload(self):
        return UserCreate(
            username="newuser",
            email="new@example.com",
            password="plain_password",
            role="underwriter"
        )

    @pytest.mark.asyncio
    async def test_register_user_success(self, mock_db, user_payload):
        # Arrange
        # Mock the hash function to return a fixed value for predictability
        with patch('mortgage_underwriting.common.security.hash_password', return_value="hashed_secret"):
            # Act
            user = await AuthService.register(mock_db, user_payload)

            # Assert
            assert user.username == "newuser"
            assert user.email == "new@example.com"
            assert user.password_hash == "hashed_secret" # Ensure hashing was called
            assert user.role == "underwriter"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once_with(user)

    @pytest.mark.asyncio
    async def test_register_user_duplicate_username_raises_exception(self, mock_db, user_payload):
        # Arrange
        mock_db.commit.side_effect = IntegrityError("INSERT conflict", None, None)

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await AuthService.register(mock_db, user_payload)
        
        assert exc_info.value.status_code == 409
        assert "already exists" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db):
        # Arrange
        username = "testuser"
        password = "correct_password"
        hashed_pw = "hashed_correct_password"
        
        mock_user = User(id=1, username=username, email="test@example.com", password_hash=hashed_pw, role="user")
        
        # Mock DB to return user
        with patch.object(UserService, 'get_by_username', return_value=mock_user) as mock_get:
            # Mock password verification
            with patch('mortgage_underwriting.common.security.verify_password', return_value=True) as mock_verify:
                # Act
                authenticated_user = await AuthService.authenticate(mock_db, username, password)

                # Assert
                assert authenticated_user is not None
                assert authenticated_user.username == username
                mock_get.assert_awaited_once_with(mock_db, username)
                mock_verify.assert_called_once_with(password, hashed_pw)

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db):
        # Arrange
        username = "testuser"
        password = "wrong_password"
        hashed_pw = "hashed_correct_password"
        
        mock_user = User(id=1, username=username, email="test@example.com", password_hash=hashed_pw, role="user")

        with patch.object(UserService, 'get_by_username', return_value=mock_user):
            with patch('mortgage_underwriting.common.security.verify_password', return_value=False):
                # Act & Assert
                with pytest.raises(AppException) as exc_info:
                    await AuthService.authenticate(mock_db, username, password)
                
                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        # Arrange
        with patch.object(UserService, 'get_by_username', return_value=None):
            # Act & Assert
            with pytest.raises(AppException) as exc_info:
                await AuthService.authenticate(mock_db, "ghost", "pass")
            
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_create_token(self):
        # Arrange
        user = User(id=1, username="test", email="test@example.com", role="admin")
        
        # Act
        with patch('mortgage_underwriting.common.security.create_access_token', return_value="mock_jwt_token") as mock_create:
            token_data = AuthService.create_token(user)
            
            # Assert
            assert token_data.access_token == "mock_jwt_token"
            assert token_data.token_type == "bearer"
            mock_create.assert_called_once_with(data={"sub": user.username, "role": user.role})

    def test_password_not_stored_in_plaintext_in_model(self):
        # This test ensures the User model structure compliance
        # Arrange & Act
        user = User(username="test", email="test@example.com", password_hash="hashed")
        
        # Assert
        assert hasattr(user, 'password_hash')
        # Ensure there is no 'password' field on the ORM model that exposes plain text
        assert not hasattr(user, 'password')
```

```python
# integration_tests
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.audit.models import AuditLog

@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthEndpoints:

    async def test_register_user_creates_record_and_audit_log(self, client: AsyncClient, db_session: AsyncSession, valid_user_payload: dict):
        # Act
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)

        # Assert - Response
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert "id" in data
        assert "password" not in data # Security: PIPEDA compliance check

        # Assert - Database
        result = await db_session.execute(select(User).where(User.username == valid_user_payload["username"]))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email == valid_user_payload["email"]
        assert user.password_hash != valid_user_payload["password"] # Ensure hashed

        # Assert - Audit Log (FINTRAC/Regulatory)
        audit_result = await db_session.execute(select(AuditLog).where(AuditLog.entity_id == user.id))
        audit_log = audit_result.scalar_one_or_none()
        assert audit_log is not None
        assert audit_log.action == "USER_CREATED"
        assert audit_log.created_by == "system" # Assuming system context for self-registration

    async def test_register_duplicate_username_returns_409(self, client: AsyncClient, valid_user_payload: dict):
        # Arrange - Create first user
        await client.post("/api/v1/auth/register", json=valid_user_payload)

        # Act - Try to create same user again
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)

        # Assert
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        # Arrange
        invalid_payload = {
            "username": "test",
            "email": "not-an-email",
            "password": "ValidPass123!",
            "role": "underwriter"
        }

        # Act
        response = await client.post("/api/v1/auth/register", json=invalid_payload)

        # Assert
        assert response.status_code == 422

    async def test_login_success_returns_token(self, client: AsyncClient, valid_user_payload: dict):
        # Arrange - Register user first
        await client.post("/api/v1/auth/register", json=valid_user_payload)

        # Act
        login_payload = {
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20

    async def test_login_wrong_password_returns_401(self, client: AsyncClient, valid_user_payload: dict):
        # Arrange
        await client.post("/api/v1/auth/register", json=valid_user_payload)

        # Act
        login_payload = {
            "username": valid_user_payload["username"],
            "password": "WrongPassword123!"
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)

        # Assert
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    async def test_protected_endpoint_requires_auth(self, client: AsyncClient):
        # Act
        response = await client.get("/api/v1/auth/me")

        # Assert
        assert response.status_code == 401

    async def test_protected_endpoint_returns_user_data(self, client: AsyncClient, valid_user_payload: dict):
        # Arrange - Register and Login
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        login_res = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Act
        response = await client.get("/api/v1/auth/me", headers=headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        # Ensure sensitive fields are not exposed
        assert "password" not in data
        assert "password_hash" not in data
        assert "sin" not in data # Context: PIPEDA check if SIN is part of user profile

    async def test_logout_deactivates_token(self, client: AsyncClient, valid_user_payload: dict):
        # Arrange
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        login_res = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Act - Logout
        logout_res = await client.post("/api/v1/auth/logout", headers=headers)
        assert logout_res.status_code == 200

        # Act - Try to use token again
        me_res = await client.get("/api/v1/auth/me", headers=headers)

        # Assert - Token should be invalid (depending on implementation, might be 401 or 403)
        # Assuming blacklist or revocation logic exists
        assert me_res.status_code == 401

    async def test_password_change_flow(self, client: AsyncClient, valid_user_payload: dict):
        # Arrange
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        login_res = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Act - Change Password
        new_pass = "NewSecurePass456!"
        change_res = await client.post("/api/v1/auth/change-password", headers=headers, json={
            "old_password": valid_user_payload["password"],
            "new_password": new_pass
        })

        # Assert
        assert change_res.status_code == 200

        # Verify login with old password fails
        fail_login = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        assert fail_login.status_code == 401

        # Verify login with new password succeeds
        success_login = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": new_pass
        })
        assert success_login.status_code == 200
```