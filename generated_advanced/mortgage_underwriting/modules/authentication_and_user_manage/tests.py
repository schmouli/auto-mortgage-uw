--- conftest.py ---
import pytest
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, Numeric
from datetime import datetime
from decimal import Decimal

from fastapi import FastAPI
from common.config import settings

# Import the module under test
from mortgage_underwriting.modules.authentication.routes import router as auth_router
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.common.database import get_async_session

# Using an in-memory SQLite database for testing isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

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
    Creates a fresh database session for each test.
    Applies schema creation for the User model.
    """
    async with engine.begin() as conn:
        await conn.run_sync(User.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates a test client that overrides the database dependency.
    """
    def override_get_db():
        yield db_session

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
    app.dependency_overrides[get_async_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

@pytest.fixture
def valid_user_payload():
    """
    Returns a valid payload for user registration.
    Uses Decimal for financial fields as per project rules.
    """
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test User",
        "sin": "123456789", # Will be encrypted
        "date_of_birth": "1990-01-01",
        "annual_income": "85000.00" # String representation for Decimal
    }

@pytest.fixture
def valid_login_payload():
    return {
        "username": "testuser",
        "password": "SecurePassword123!"
    }

@pytest.fixture
def admin_user_payload():
    return {
        "username": "admin",
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "role": "underwriter"
    }

@pytest.fixture
def mock_security_context():
    """Context manager to mock security functions if needed in unit tests."""
    from unittest.mock import patch
    with patch("mortgage_underwriting.common.security.encrypt_pii", return_value="encrypted_sin"), \
         patch("mortgage_underwriting.common.security.hash_password", return_value="hashed_password"):
        yield
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.authentication.services import AuthService
from mortgage_underwriting.modules.authentication.schemas import UserCreate, UserLogin, UserResponse
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestAuthService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_hash_password(self):
        """Test that password hashing returns a string different from input."""
        plain_password = "mypassword"
        hashed = await AuthService._hash_password(plain_password)
        
        assert isinstance(hashed, str)
        assert hashed != plain_password
        # Bcrypt hashes usually start with $2b$
        assert hashed.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_verify_password_success(self):
        """Test successful password verification."""
        plain = "mypassword"
        hashed = await AuthService._hash_password(plain)
        result = await AuthService._verify_password(plain, hashed)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_password_failure(self):
        """Test password verification failure."""
        plain = "mypassword"
        wrong = "wrongpassword"
        hashed = await AuthService._hash_password(plain)
        result = await AuthService._verify_password(wrong, hashed)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_db, valid_user_payload):
        """Test successful user creation with encryption and hashing."""
        # Mock the return value of a potential duplicate check
        mock_db.scalar.return_value = None

        service = AuthService(mock_db)
        user_schema = UserCreate(**valid_user_payload)

        # Mock the encryption function
        with patch("mortgage_underwriting.modules.authentication.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "encrypted_sin_value"
            
            result = await service.create_user(user_schema)

            # Verify DB interactions
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once()

            # Verify PII was encrypted
            mock_encrypt.assert_called_once_with(valid_user_payload["sin"])

            # Verify Password was hashed (check result object)
            # Note: In a real unit test we might inspect the object passed to db.add
            # Here we assume the result returned is the DB object
            assert result.sin == "encrypted_sin_value"
            assert result.hashed_password != "SecurePassword123!"

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, mock_db, valid_user_payload):
        """Test that creating a user with an existing username raises an error."""
        # Simulate existing user
        mock_db.scalar.return_value = MagicMock() # Truthy value indicates exists

        service = AuthService(mock_db)
        user_schema = UserCreate(**valid_user_payload)

        with pytest.raises(AppException) as exc_info:
            await service.create_user(user_schema)

        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail).lower()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db):
        """Test successful authentication returning a user."""
        # Mock user found in DB
        fake_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password=await AuthService._hash_password("password123"),
            role="applicant"
        )
        mock_db.scalar.return_value = fake_user

        service = AuthService(mock_db)
        credentials = UserLogin(username="testuser", password="password123")

        result = await service.authenticate_user(credentials)

        assert result is not None
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        """Test authentication failure when user does not exist."""
        mock_db.scalar.return_value = None

        service = AuthService(mock_db)
        credentials = UserLogin(username="ghost", password="password123")

        with pytest.raises(AppException) as exc_info:
            await service.authenticate_user(credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db):
        """Test authentication failure with wrong password."""
        fake_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password=await AuthService._hash_password("correct_password"),
            role="applicant"
        )
        mock_db.scalar.return_value = fake_user

        service = AuthService(mock_db)
        credentials = UserLogin(username="testuser", password="wrong_password")

        with pytest.raises(AppException) as exc_info:
            await service.authenticate_user(credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_create_token(self):
        """Test JWT token generation."""
        fake_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="hash",
            role="applicant"
        )
        
        token = await AuthService.create_token(fake_user)
        
        assert isinstance(token, str)
        assert len(token) > 20 # Basic sanity check for JWT length
        # Decode and check subject (optional, but good for coverage)
        # Skipping deep decode to avoid importing jwt in unit test unless necessary

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mock_db):
        """Test retrieving a user by ID."""
        fake_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="hash",
            sin="encrypted",
            annual_income=Decimal("50000.00"),
            role="applicant"
        )
        mock_db.get.return_value = fake_user

        service = AuthService(mock_db)
        result = await service.get_user_by_id(1)

        assert result.username == "testuser"
        # Ensure we aren't returning the hashed password in a generic get
        # (Depends on service implementation, usually we use schemas for output)
--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.authentication.models import User

@pytest.mark.integration
class TestAuthenticationEndpoints:

    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient, valid_user_payload):
        """Test successful user registration."""
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert "hashed_password" not in data # Security check
        assert "sin" not in data # PIPEDA check: SIN should not be in response
        assert "created_at" in data # FINTRAC check

    @pytest.mark.asyncio
    async def test_register_user_duplicate(self, client: AsyncClient, valid_user_payload):
        """Test registering a duplicate user returns 400."""
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 400
        assert "error_code" in response.json()

    @pytest.mark.asyncio
    async def test_register_user_invalid_income_type(self, client: AsyncClient, valid_user_payload):
        """Test that float income is rejected (must be Decimal/string)."""
        # This test validates Pydantic schema enforcement
        # Sending a float where a Decimal is expected usually results in 422 if strict types
        # However, Pydantic v2 coerces strings to Decimals. Let's test invalid format.
        payload = valid_user_payload.copy()
        payload["annual_income"] = "not_a_number"
        
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, valid_user_payload):
        """Test successful login and token generation."""
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

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with wrong password."""
        login_data = {"username": "nonexistent", "password": "wrong"}
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_current_user_profile(self, client: AsyncClient, valid_user_payload):
        """Test retrieving the current user profile (protected route)."""
        # 1. Register
        reg_resp = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_resp.json()["id"]
        
        # 2. Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_resp.json()["access_token"]
        
        # 3. Access Protected Route
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["id"] == user_id
        assert data["username"] == valid_user_payload["username"]
        assert "sin" not in data # Data minimization
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test accessing protected route without token."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test accessing protected route with garbage token."""
        headers = {"Authorization": "Bearer invalid_token_string"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_user_profile(self, client: AsyncClient, valid_user_payload):
        """Test updating user financial info (income)."""
        # 1. Register & Login
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Update Income
        update_payload = {"annual_income": "95000.00"}
        update_resp = await client.patch("/api/v1/auth/me", json=update_payload, headers=headers)
        
        assert update_resp.status_code == 200
        data = update_resp.json()
        # Ensure Decimal precision is maintained
        assert data["annual_income"] == "95000.00" 

    @pytest.mark.asyncio
    async def test_pipeda_sin_not_exposed_in_db_dump_simulation(self, client: AsyncClient, db_session, valid_user_payload):
        """
        Integration test to verify SIN is encrypted at rest.
        We query the DB directly to ensure the 'sin' column is not plain text.
        """
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Direct DB query
        result = await db_session.execute(
            f"SELECT sin FROM users WHERE username = '{valid_user_payload['username']}'"
        )
        db_sin = result.scalar_one_or_none()
        
        assert db_sin is not None
        assert db_sin != valid_user_payload["sin"]
        # Assuming encryption produces a longer string or specific format
        assert len(db_sin) > len(valid_user_payload["sin"]) or db_sin.startswith("encrypted:") or db_sin != "123456789"