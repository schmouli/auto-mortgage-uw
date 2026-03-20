--- conftest.py ---
```python
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, func
from datetime import datetime

# Assuming the module name is 'auth' based on the context
from mortgage_underwriting.modules.auth.routes import router
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings

# Use an in-memory SQLite database for fast integration tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
async def app(db_session: AsyncSession):
    """
    Create a test FastAPI app that overrides the dependency for the database session.
    """
    from fastapi import FastAPI
    from mortgage_underwriting.common.database import get_async_session
    
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/auth", tags=["Auth"])
    
    # Override the dependency
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for testing endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_user_payload():
    return {
        "username": "test_user",
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "role": "underwriter"
    }

@pytest.fixture
def admin_user_payload():
    return {
        "username": "admin_user",
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "role": "admin"
    }
```
--- unit_tests ---
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from passlib.context import CryptContext
from jose import jwt, JWTError

from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin, UserResponse
from mortgage_underwriting.modules.auth.services import AuthService, UserService
from mortgage_underwriting.common.exceptions import AppException

# Mock settings for JWT
SECRET_KEY = "test_secret_key"
ALGORITHM = "HS256"

@pytest.mark.unit
class TestAuthService:
    
    @pytest.fixture
    def pwd_context(self):
        return CryptContext(schemes=["bcrypt"], deprecated="auto")

    @pytest.mark.asyncio
    async def test_hash_password(self, pwd_context):
        """Test that password hashing works and returns a different string."""
        plain_password = "my_plain_password"
        hashed = AuthService.hash_password(plain_password)
        
        assert hashed is not None
        assert hashed != plain_password
        assert pwd_context.verify(plain_password, hashed)

    @pytest.mark.asyncio
    async def test_verify_password_success(self, pwd_context):
        """Test successful password verification."""
        plain_password = "my_plain_password"
        hashed = pwd_context.hash(plain_password)
        
        is_valid = AuthService.verify_password(plain_password, hashed)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_password_failure(self, pwd_context):
        """Test password verification failure with wrong password."""
        plain_password = "my_plain_password"
        wrong_password = "wrong_password"
        hashed = pwd_context.hash(plain_password)
        
        is_valid = AuthService.verify_password(wrong_password, hashed)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_create_token(self):
        """Test JWT token creation contains correct data."""
        data = {"sub": "test_user", "role": "underwriter"}
        token = AuthService.create_token(data)
        
        assert isinstance(token, str)
        # Decode to verify structure
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "test_user"
        assert decoded["role"] == "underwriter"
        assert "exp" in decoded

    @pytest.mark.asyncio
    async def test_decode_token_success(self):
        """Test decoding a valid token."""
        data = {"sub": "test_user", "role": "underwriter"}
        token = AuthService.create_token(data)
        
        payload = AuthService.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "test_user"

    @pytest.mark.asyncio
    async def test_decode_token_invalid(self):
        """Test decoding an invalid/expired token raises exception."""
        invalid_token = "invalid.token.string"
        
        with pytest.raises(AppException) as exc_info:
            AuthService.decode_token(invalid_token)
        assert exc_info.value.status_code == 401
        assert "invalid" in str(exc_info.value.detail).lower()

@pytest.mark.unit
class TestUserService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def user_payload(self):
        return UserCreate(
            username="jdoe",
            email="john@example.com",
            password="Password123!",
            role="underwriter"
        )

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_db, user_payload):
        """Test successful user creation."""
        # Mock the scalar to return None (user doesn't exist)
        mock_db.scalar.return_value = None
        
        service = UserService(mock_db)
        user = await service.create_user(user_payload)
        
        assert user is not None
        assert user.username == "jdoe"
        assert user.email == "john@example.com"
        assert user.role == "underwriter"
        # Ensure password is hashed, not plain
        assert user.hashed_password != "Password123!"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, mock_db, user_payload):
        """Test that creating a user with duplicate email raises error."""
        # Mock existing user
        mock_user = MagicMock()
        mock_user.email = "john@example.com"
        mock_db.scalar.return_value = mock_user
        
        service = UserService(mock_db)
        
        with pytest.raises(AppException) as exc_info:
            await service.create_user(user_payload)
        
        assert exc_info.value.status_code == 400
        assert "already registered" in str(exc_info.value.detail).lower()
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db, user_payload):
        """Test successful authentication with correct credentials."""
        # Create a mock user instance with a hashed password
        hashed_pw = AuthService.hash_password("Password123!")
        mock_user = User(
            id=1,
            username="jdoe",
            email="john@example.com",
            hashed_password=hashed_pw,
            role="underwriter",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_db.scalar.return_value = mock_user
        
        service = UserService(mock_db)
        login_data = UserLogin(email="john@example.com", password="Password123!")
        result = await service.authenticate_user(login_data)
        
        assert result == mock_user
        assert result.username == "jdoe"

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db, user_payload):
        """Test authentication failure with wrong password."""
        hashed_pw = AuthService.hash_password("Password123!")
        mock_user = User(
            id=1,
            username="jdoe",
            email="john@example.com",
            hashed_password=hashed_pw,
            role="underwriter",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_db.scalar.return_value = mock_user
        
        service = UserService(mock_db)
        login_data = UserLogin(email="john@example.com", password="WrongPassword!")
        
        with pytest.raises(AppException) as exc_info:
            await service.authenticate_user(login_data)
        
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        """Test authentication failure when user doesn't exist."""
        mock_db.scalar.return_value = None
        
        service = UserService(mock_db)
        login_data = UserLogin(email="ghost@example.com", password="DoesNotMatter")
        
        with pytest.raises(AppException) as exc_info:
            await service.authenticate_user(login_data)
        
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mock_db):
        """Test retrieving a user by ID."""
        mock_user = User(
            id=99,
            username="fetcher",
            email="fetch@example.com",
            hashed_password="hash",
            role="admin",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        # Simulate DB get
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        service = UserService(mock_db)
        result = await service.get_user_by_id(99)
        
        assert result is not None
        assert result.username == "fetcher"
        mock_db.execute.assert_awaited_once()
```
--- integration_tests ---
```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from datetime import datetime

from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.common.security import verify_token

@pytest.mark.integration
class TestAuthEndpoints:

    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient, valid_user_payload):
        """Test user registration endpoint returns 201 and creates user."""
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "test_user"
        assert data["email"] == "test@example.com"
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, valid_user_payload):
        """Test that registering the same email twice returns 400."""
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient, valid_user_payload):
        """Test registration validation with bad email."""
        payload = valid_user_payload.copy()
        payload["email"] = "not-an-email"
        
        response = await client.post("/api/v1/auth/register", json=payload)
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, valid_user_payload):
        """Test login returns valid access token."""
        # Register user first
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

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, valid_user_payload):
        """Test login with wrong password returns 401."""
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        login_payload = {
            "email": valid_user_payload["email"],
            "password": "WrongPassword!"
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, valid_user_payload):
        """Test retrieving current user profile with valid token."""
        # Register
        reg_res = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_res.json()["id"]
        
        # Login
        login_res = await client.post("/api/v1/auth/login", json={
            "email": valid_user_payload["email"],
            "password": valid_user_payload["password"]
        })
        token = login_res.json()["access_token"]
        
        # Get Me
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_res.status_code == 200
        data = me_res.json()
        assert data["id"] == user_id
        assert data["email"] == valid_user_payload["email"]
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test accessing protected endpoint without token returns 401."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test accessing protected endpoint with bad token returns 401."""
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_user_persistence_in_db(self, client: AsyncClient, db_session, valid_user_payload):
        """Test that user data is correctly persisted in the database."""
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Query DB directly
        result = await db_session.execute(select(User).where(User.email == valid_user_payload["email"]))
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.username == "test_user"
        assert user.email == "test@example.com"
        assert user.role == "underwriter"
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_password_is_hashed_in_db(self, client: AsyncClient, db_session, valid_user_payload):
        """Test that password is never stored in plain text."""
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        result = await db_session.execute(select(User).where(User.email == valid_user_payload["email"]))
        user = result.scalar_one_or_none()
        
        assert user.hashed_password != valid_user_payload["password"]
        # Bcrypt hashes usually start with $2b$
        assert user.hashed_password.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_update_last_login(self, client: AsyncClient, valid_user_payload):
        """
        Test that logging in updates user activity (simulated via audit logs or updated_at if applicable).
        Note: This assumes the service updates the user or logs a LoginHistory entry.
        Here we verify the token allows access, implying session validity.
        """
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        login_res = await client.post("/api/v1/auth/login", json={
            "email": valid_user_payload["email"],
            "password": valid_user_payload["password"]
        })
        
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        
        # Verify token is valid via protected endpoint
        me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
```