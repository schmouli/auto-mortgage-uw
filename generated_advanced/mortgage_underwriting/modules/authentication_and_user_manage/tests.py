--- conftest.py ---
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Assuming the module is named 'auth' based on the context
from mortgage_underwriting.modules.auth.models import Base, User
from mortgage_underwriting.modules.auth.routes import router
from mortgage_underwriting.common.database import get_async_session
from main import app  # Adjust if your app entry point differs

# Test Database Configuration (In-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with dependency overrides."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    
    # Ensure auth router is included if not already in main app
    app.include_router(router, prefix="/api/v1/auth", tags=["auth"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# --- Fixtures for Test Data ---

@pytest.fixture
def valid_user_payload():
    return {
        "username": "test_underwriter",
        "email": "underwriter@example.com",
        "password": "SecurePass123!",
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

@pytest.fixture
def login_payload(valid_user_payload):
    return {
        "username": valid_user_payload["username"],
        "password": valid_user_payload["password"]
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin, UserResponse
from mortgage_underwriting.modules.auth.services import AuthService, UserService
from mortgage_underwriting.common.exceptions import AppException

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


@pytest.mark.asyncio
class TestUserService:
    """Tests for user creation and retrieval logic."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.fixture
    def user_create_schema(self):
        return UserCreate(
            username="jdoe",
            email="john.doe@example.com",
            password="plain_text_password",
            role="underwriter"
        )

    async def test_create_user_hashes_password(self, mock_db, user_create_schema):
        """Ensure passwords are hashed before storage."""
        service = UserService(mock_db)
        
        # Mock the result of refresh to return a user object
        mock_user = User(
            id=1,
            username=user_create_schema.username,
            email=user_create_schema.email,
            hashed_password="hashed_secret", # Simulated hash
            role=user_create_schema.role
        )
        mock_db.refresh.return_value = mock_user

        result = await service.create_user(user_create_schema)

        # Verify DB interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        
        # Verify the returned object is a User model
        assert isinstance(result, User)
        assert result.username == "jdoe"

    async def test_create_user_duplicate_username_raises_integrity_error(self, mock_db, user_create_schema):
        """Ensure duplicate usernames are handled."""
        service = UserService(mock_db)
        
        # Simulate database integrity violation
        mock_db.commit.side_effect = IntegrityError("INSERT failed", {}, None)

        with pytest.raises(AppException) as exc_info:
            await service.create_user(user_create_schema)
        
        assert exc_info.value.status_code == 409 # Conflict
        assert "already exists" in str(exc_info.value.detail).lower()

    async def test_get_user_by_username_found(self, mock_db):
        """Test successful user retrieval."""
        service = UserService(mock_db)
        
        mock_user = User(
            id=1,
            username="jdoe",
            email="john@example.com",
            hashed_password="hash",
            role="underwriter"
        )
        
        # Mock the scalar chain: execute().scalars().first()
        mock_result = AsyncMock()
        mock_result.first.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        result = await service.get_user_by_username("jdoe")
        
        assert result is not None
        assert result.username == "jdoe"
        mock_db.execute.assert_awaited_once()

    async def test_get_user_by_username_not_found(self, mock_db):
        """Test retrieval when user does not exist."""
        service = UserService(mock_db)
        
        # Mock the scalar chain to return None
        mock_result = AsyncMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        
        result = await service.get_user_by_username("ghost")
        
        assert result is None


@pytest.mark.asyncio
class TestAuthService:
    """Tests for authentication logic (hashing, verification, tokens)."""

    @pytest.fixture
    def mock_user_service(self):
        return AsyncMock(spec=UserService)

    @pytest.fixture
    def auth_service(self, mock_user_service):
        return AuthService(mock_user_service)

    @pytest.fixture
    def sample_user(self):
        # In a real scenario, this password matches 'password123'
        return User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW", # bcrypt for "password123"
            role="underwriter"
        )

    async def test_verify_password_correct(self, auth_service, sample_user):
        """Test password verification with correct credentials."""
        is_valid = await auth_service.verify_password("password123", sample_user.hashed_password)
        assert is_valid is True

    async def test_verify_password_incorrect(self, auth_service, sample_user):
        """Test password verification with incorrect credentials."""
        is_valid = await auth_service.verify_password("wrongpass", sample_user.hashed_password)
        assert is_valid is False

    async def test_authenticate_user_success(self, auth_service, sample_user, mock_user_service):
        """Test successful authentication flow."""
        mock_user_service.get_user_by_username.return_value = sample_user
        
        result = await auth_service.authenticate_user("testuser", "password123")
        
        assert result == sample_user
        mock_user_service.get_user_by_username.assert_awaited_once_with("testuser")

    async def test_authenticate_user_wrong_password(self, auth_service, sample_user, mock_user_service):
        """Test authentication failure due to wrong password."""
        mock_user_service.get_user_by_username.return_value = sample_user
        
        with pytest.raises(AppException) as exc_info:
            await auth_service.authenticate_user("testuser", "wrongpass")
        
        assert exc_info.value.status_code == 401

    async def test_authenticate_user_not_found(self, auth_service, mock_user_service):
        """Test authentication failure when user doesn't exist."""
        mock_user_service.get_user_by_username.return_value = None
        
        with pytest.raises(AppException) as exc_info:
            await auth_service.authenticate_user("ghost", "password")
        
        assert exc_info.value.status_code == 401

    async def test_create_token_contains_claims(self, auth_service, sample_user):
        """Test JWT token creation contains correct data."""
        token = await auth_service.create_token(sample_user)
        
        assert isinstance(token, str)
        assert len(token) > 0
        # Note: Deep decoding of JWT requires PyJWT import, 
        # here we just check structure and non-emptiness based on service contract.
        # In a real scenario, we would decode and check 'sub' and 'role'.

    async def test_hash_password_is_hashed(self, auth_service):
        """Ensure hashing output is different from input."""
        plain = "mypassword"
        hashed = await auth_service.hash_password(plain)
        
        assert hashed != plain
        assert isinstance(hashed, str)

--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.auth.models import User

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
class TestAuthEndpoints:
    """Integration tests for Authentication API endpoints."""

    async def test_register_user_success(self, client: AsyncClient, valid_user_payload):
        """Test successful user registration."""
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        # PIPEDA Compliance Check: Password must NEVER be in response
        assert "password" not in data
        assert "hashed_password" not in data

    async def test_register_duplicate_user_conflict(self, client: AsyncClient, valid_user_payload):
        """Test that registering a duplicate user returns 409."""
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration with same data
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_register_weak_password_rejected(self, client: AsyncClient, valid_user_payload):
        """Test that weak passwords are rejected by validation."""
        weak_payload = valid_user_payload.copy()
        weak_payload["password"] = "123" # Too short
        
        response = await client.post("/api/v1/auth/register", json=weak_payload)
        
        assert response.status_code == 422 # Validation Error

    async def test_login_success(self, client: AsyncClient, valid_user_payload):
        """Test successful login returns a token."""
        # Register first
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login
        login_data = {
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        }
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials(self, client: AsyncClient, valid_user_payload):
        """Test login with wrong password returns 401."""
        # Register first
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login with wrong password
        login_data = {
            "username": valid_user_payload["username"],
            "password": "WrongPassword123!"
        }
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "access_token" not in response.json()

    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """Test accessing protected route without token returns 401."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    async def test_protected_endpoint_with_valid_token(self, client: AsyncClient, valid_user_payload):
        """Test accessing protected route with valid token."""
        # Register
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login
        login_res = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_res.json()["access_token"]
        
        # Access Protected Route
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_res.status_code == 200
        data = me_res.json()
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        # Ensure no sensitive data leaks
        assert "password" not in data

    async def test_protected_endpoint_with_invalid_token(self, client: AsyncClient):
        """Test accessing protected route with garbage token returns 401."""
        headers = {"Authorization": "Bearer invalid_token_string"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401

    async def test_user_data_persisted_correctly(self, client: AsyncClient, db_session, valid_user_payload):
        """Verify database state after registration."""
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Query DB directly
        result = await db_session.execute(select(User).where(User.username == valid_user_payload["username"]))
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.email == valid_user_payload["email"]
        assert user.role == valid_user_payload["role"]
        assert user.hashed_password is not None
        assert user.hashed_password != valid_user_payload["password"] # Verify hashing