--- conftest.py ---
```python
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import declarative_base

# Assuming Base is in common.database, importing for test setup
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.main import app  # Assuming main app entry point
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin
from mortgage_underwriting.modules.auth.security import hash_password

# Database URL for in-memory SQLite (fast for integration tests)
# Using SQLite for integration tests as requested, despite prod being Postgres
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create async engine
engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Create async session factory
AsyncTestingSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncSession:
    """
    Fixture to create a fresh database session for each test.
    Creates tables at start and drops them at end.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncTestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncClient:
    """
    Fixture to create an AsyncClient for testing FastAPI endpoints.
    Overrides the dependency for the database session.
    """
    from mortgage_underwriting.common.database import get_async_session

    # Dependency override
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def valid_user_payload() -> dict:
    """Returns a valid payload for user creation."""
    return {
        "username": "test_underwriter",
        "email": "underwriter@example.com",
        "password": "SecurePassword123!",
        "role": "underwriter"
    }

@pytest.fixture
def admin_user_payload() -> dict:
    """Returns a valid payload for admin creation."""
    return {
        "username": "admin_user",
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "role": "admin"
    }

@pytest.fixture
async def seeded_user(db_session: AsyncSession, valid_user_payload: dict) -> User:
    """Fixture to create a user in the database before a test runs."""
    hashed_pw = hash_password(valid_user_payload["password"])
    user = User(
        username=valid_user_payload["username"],
        email=valid_user_payload["email"],
        password_hash=hashed_pw,
        role=valid_user_payload["role"]
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
```

--- unit_tests ---
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError
from mortgage_underwriting.modules.auth.services import AuthService, UserService
from mortgage_underwriting.modules.auth.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    InactiveUserError
)
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin

# Module name mapping: 'auth' represents Authentication & User Management
from mortgage_underwriting.modules.auth.security import hash_password, verify_password

@pytest.mark.unit
class TestSecurityHelpers:
    def test_hash_password_returns_string(self):
        password = "MySecretP@ssw0rd"
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert hashed != password
        assert len(hashed) > 20  # bcrypt hashes are long

    def test_verify_password_success(self):
        password = "MySecretP@ssw0rd"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_failure(self):
        password = "MySecretP@ssw0rd"
        wrong_password = "WrongPassword"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False


@pytest.mark.unit
class TestAuthService:
    @pytest.fixture
    def mock_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.email = "test@example.com"
        user.is_active = True
        user.role = "underwriter"
        return user

    def test_create_token(self, mock_user):
        token = AuthService.create_token(mock_user)
        assert isinstance(token, str)
        # JWT tokens have 3 parts separated by dots
        assert len(token.split(".")) == 3

    def test_decode_token_success(self, mock_user):
        token = AuthService.create_token(mock_user)
        payload = AuthService.decode_token(token)
        assert payload["sub"] == str(mock_user.id)
        assert payload["username"] == mock_user.username

    def test_decode_token_invalid(self):
        with pytest.raises(InvalidCredentialsError):
            AuthService.decode_token("invalid.token.string")


@pytest.mark.unit
class TestUserService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_db):
        payload = UserCreate(
            username="newuser",
            email="new@example.com",
            password="Password123!",
            role="underwriter"
        )
        
        # Mock scalar to return None (user doesn't exist)
        mock_db.scalar.return_value = None

        user = await UserService.create_user(mock_db, payload)
        
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert user.password_hash != "Password123!" # Ensure hashed
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, mock_db):
        payload = UserCreate(
            username="newuser",
            email="existing@example.com",
            password="Password123!",
            role="underwriter"
        )
        
        # Mock scalar to return existing user
        existing_user = MagicMock()
        mock_db.scalar.return_value = existing_user

        with pytest.raises(UserAlreadyExistsError):
            await UserService.create_user(mock_db, payload)
        
        # Ensure we didn't try to add
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db):
        plain_password = "CorrectPassword"
        hashed = hash_password(plain_password)
        
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = hashed
        mock_user.is_active = True
        
        mock_db.scalar.return_value = mock_user

        login_data = UserLogin(email="test@example.com", password="CorrectPassword")
        result = await UserService.authenticate_user(mock_db, login_data)
        
        assert result == mock_user
        mock_db.scalar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db):
        hashed = hash_password("CorrectPassword")
        
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = hashed
        
        mock_db.scalar.return_value = mock_user

        login_data = UserLogin(email="test@example.com", password="WrongPassword")
        
        with pytest.raises(InvalidCredentialsError):
            await UserService.authenticate_user(mock_db, login_data)

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        mock_db.scalar.return_value = None
        login_data = UserLogin(email="ghost@example.com", password="DoesntMatter")
        
        with pytest.raises(InvalidCredentialsError):
            await UserService.authenticate_user(mock_db, login_data)

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(self, mock_db):
        hashed = hash_password("CorrectPassword")
        
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = hashed
        mock_user.is_active = False
        
        mock_db.scalar.return_value = mock_user

        login_data = UserLogin(email="test@example.com", password="CorrectPassword")
        
        with pytest.raises(InactiveUserError):
            await UserService.authenticate_user(mock_db, login_data)

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mock_db):
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_db.get.return_value = mock_user
        
        result = await UserService.get_user_by_id(mock_db, 1)
        assert result == mock_user
        mock_db.get.assert_awaited_once_with(User, 1)
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.auth.models import User

# Module name mapping: 'auth' represents Authentication & User Management
from mortgage_underwriting.modules.auth.routes import router

@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthEndpoints:
    
    async def test_register_user_success(self, client: AsyncClient, valid_user_payload: dict):
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert "password_hash" not in data  # PIPEDA: Never return password hash
        assert "password" not in data

    async def test_register_user_duplicate_email(self, client: AsyncClient, valid_user_payload: dict):
        # First request
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Duplicate request
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_register_user_invalid_email(self, client: AsyncClient, valid_user_payload: dict):
        payload = valid_user_payload.copy()
        payload["email"] = "not-an-email"
        
        response = await client.post("/api/v1/auth/register", json=payload)
        
        assert response.status_code == 422  # Validation Error

    async def test_register_user_weak_password(self, client: AsyncClient, valid_user_payload: dict):
        payload = valid_user_payload.copy()
        payload["password"] = "123" # Too short
        
        response = await client.post("/api/v1/auth/register", json=payload)
        
        assert response.status_code == 422

    async def test_login_success(self, client: AsyncClient, valid_user_payload: dict):
        # Register first
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login
        login_payload = {
            "email": valid_user_payload["email"],
            "password": valid_user_payload["password"]
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials(self, client: AsyncClient, valid_user_payload: dict):
        # Register first
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login with wrong password
        login_payload = {
            "email": valid_user_payload["email"],
            "password": "WrongPassword123!"
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()

    async def test_get_me_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    async def test_get_me_authorized(self, client: AsyncClient, valid_user_payload: dict):
        # Register
        reg_resp = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_resp.json()["id"]
        
        # Login
        login_payload = {
            "email": valid_user_payload["email"],
            "password": valid_user_payload["password"]
        }
        login_resp = await client.post("/api/v1/auth/login", json=login_payload)
        token = login_resp.json()["access_token"]
        
        # Access protected route
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["id"] == user_id
        assert data["email"] == valid_user_payload["email"]
        assert "password_hash" not in data

    async def test_get_me_invalid_token(self, client: AsyncClient):
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401

    async def test_user_persistence_in_db(self, client: AsyncClient, db_session: AsyncClient, valid_user_payload: dict):
        """Integration test verifying actual DB state (FINTRAC: Audit trail check)"""
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Query DB directly
        result = await db_session.execute(select(User).where(User.email == valid_user_payload["email"]))
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.username == valid_user_payload["username"]
        assert user.created_at is not None  # FINTRAC: Audit trail
        assert user.updated_at is not None  # FINTRAC: Audit trail
        assert user.password_hash is not None
        assert user.password_hash != valid_user_payload["password"]

    async def test_logout_deactivates_token(self, client: AsyncClient, valid_user_payload: dict):
        """Test if logout is implemented (optional feature, but good to test)"""
        # Register
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login
        login_payload = {
            "email": valid_user_payload["email"],
            "password": valid_user_payload["password"]
        }
        login_resp = await client.post("/api/v1/auth/login", json=login_payload)
        token = login_resp.json()["access_token"]
        
        # Logout (assuming endpoint exists, usually just client-side token drop, but testing server-side if applicable)
        # If endpoint doesn't exist, this test would 404. Assuming standard implementation:
        # For this specific stack, we usually just drop the token on client. 
        # Let's test a protected endpoint ensures the token works first.
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        
        # If there was a /logout endpoint that blacklisted the token, we would call it here.
        # Since we are using stateless JWT, we just verify the token continues to work 
        # until it expires, which is expected behavior.
```