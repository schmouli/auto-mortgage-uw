--- conftest.py ---
import pytest
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

# Assuming Base is imported from common.database
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.authentication.routes import router as auth_router
from mortgage_underwriting.common.config import settings

# Use an in-memory SQLite database for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def app() -> FastAPI:
    """
    Create a test application instance including the authentication router.
    """
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
    return app

@pytest.fixture(scope="function")
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
        "username": "jdoe",
        "email": "john.doe@example.com",
        "password": "SecurePass123!",
        "full_name": "John Doe",
        "role": "underwriter",
        "sin": "123456789", # PII - must be encrypted
        "dob": "1980-01-01" # PII - must be encrypted
    }

@pytest.fixture
def login_payload():
    return {
        "username": "jdoe",
        "password": "SecurePass123!"
    }

--- unit_tests ---
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError
from mortgage_underwriting.modules.authentication.services import UserService, AuthService
from mortgage_underwriting.modules.authentication.schemas import UserCreate, UserLogin
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.modules.authentication.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    UserNotFoundError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestUserService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def user_create_schema(self, valid_user_payload):
        return UserCreate(**valid_user_payload)

    @pytest.mark.asyncio
    async def test_create_user_success_hashes_password(self, mock_db, user_create_schema):
        """
        Test that user creation hashes the password and encrypts PII (SIN/DOB).
        """
        # Mock the security functions
        with patch('mortgage_underwriting.modules.authentication.services.hash_password') as mock_hash, \
             patch('mortgage_underwriting.modules.authentication.services.encrypt_pii') as mock_encrypt:
            
            mock_hash.return_value = "hashed_secret"
            mock_encrypt.side_effect = lambda x: f"enc_{x}"

            service = UserService(mock_db)
            user = await service.create(user_create_schema)

            # Verify password was hashed
            assert user.hashed_password == "hashed_secret"
            mock_hash.assert_called_once_with("SecurePass123!")

            # Verify PII was encrypted (PIPEDA Compliance)
            assert user.sin_encrypted == "enc_123456789"
            assert user.dob_encrypted == "enc_1980-01-01"
            assert mock_encrypt.call_count == 2

            # Verify DB interaction
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once_with(user)

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username_raises_error(self, mock_db, user_create_schema):
        """
        Test that creating a duplicate user raises UserAlreadyExistsError.
        """
        # Simulate database integrity error (e.g., unique constraint violation)
        mock_db.commit.side_effect = IntegrityError("INSERT failed", {}, None)

        service = UserService(mock_db)
        
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await service.create(user_create_schema)
        
        assert "already exists" in str(exc_info.value).lower()
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, mock_db):
        """
        Test retrieving a user by ID.
        """
        # Mock the result of the scalar query
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.username = "test_user"
        
        # Setup the mock execution chain for SQLAlchemy 2.0 style select
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        service = UserService(mock_db)
        result = await service.get_by_id(1)

        assert result is not None
        assert result.username == "test_user"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, mock_db):
        """
        Test retrieving a non-existent user raises UserNotFoundError.
        """
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = UserService(mock_db)

        with pytest.raises(UserNotFoundError):
            await service.get_by_id(999)


@pytest.mark.unit
class TestAuthService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.username = "jdoe"
        user.hashed_password = "hashed_correct_password"
        user.is_active = True
        return user

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db, mock_user):
        """
        Test successful authentication with correct credentials.
        """
        # Mock User Service dependency
        with patch('mortgage_underwriting.modules.authentication.services.UserService') as MockUserService:
            user_service_instance = MockUserService.return_value
            user_service_instance.get_by_username = AsyncMock(return_value=mock_user)

            with patch('mortgage_underwriting.modules.authentication.services.verify_password') as mock_verify:
                mock_verify.return_value = True

                auth_service = AuthService(mock_db)
                result = await auth_service.authenticate("jdoe", "correct_password")

                assert result == mock_user
                mock_verify.assert_called_once_with("correct_password", "hashed_correct_password")

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db, mock_user):
        """
        Test authentication fails with wrong password.
        """
        with patch('mortgage_underwriting.modules.authentication.services.UserService') as MockUserService:
            user_service_instance = MockUserService.return_value
            user_service_instance.get_by_username = AsyncMock(return_value=mock_user)

            with patch('mortgage_underwriting.modules.authentication.services.verify_password') as mock_verify:
                mock_verify.return_value = False

                auth_service = AuthService(mock_db)
                
                with pytest.raises(InvalidCredentialsError):
                    await auth_service.authenticate("jdoe", "wrong_password")

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        """
        Test authentication fails when user does not exist.
        """
        with patch('mortgage_underwriting.modules.authentication.services.UserService') as MockUserService:
            user_service_instance = MockUserService.return_value
            user_service_instance.get_by_username = AsyncMock(side_effect=UserNotFoundError())

            auth_service = AuthService(mock_db)

            with pytest.raises(InvalidCredentialsError):
                await auth_service.authenticate("ghost", "password")

    @pytest.mark.asyncio
    async def test_create_token_generates_jwt(self, mock_user):
        """
        Test that a JWT token is generated successfully.
        """
        auth_service = AuthService(AsyncMock())
        
        # Mock the token creation logic if external, otherwise just test structure
        with patch('mortgage_underwriting.modules.authentication.services.create_access_token') as mock_create_token:
            mock_create_token.return_value = "fake_jwt_token"
            
            token = auth_service.create_token(mock_user)
            
            assert token == "fake_jwt_token"
            # Ensure data includes user ID and role for authorization
            mock_create_token.assert_called_once_with(data={"sub": str(mock_user.id), "role": mock_user.role})

--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.common.security import verify_password

@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthenticationEndpoints:

    async def test_register_user_creates_record_in_db(self, client: AsyncClient, db_session, valid_user_payload):
        """
        Test the registration endpoint creates a user record with encrypted PII and hashed password.
        """
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["username"] == "jdoe"
        assert data["email"] == "john.doe@example.com"
        
        # PIPEDA Compliance: PII must NOT be in the response
        assert "sin" not in data
        assert "dob" not in data
        assert "password" not in data
        assert "hashed_password" not in data

        # Verify Database State
        stmt = select(User).where(User.username == "jdoe")
        result = await db_session.execute(stmt)
        db_user = result.scalar_one_or_none()

        assert db_user is not None
        assert db_user.username == "jdoe"
        
        # Verify password hashing
        assert verify_password("SecurePass123!", db_user.hashed_password) is True
        
        # Verify PII is encrypted in DB (PIPEDA Compliance)
        assert db_user.sin_encrypted != "123456789"
        assert db_user.dob_encrypted != "1980-01-01"
        assert db_user.sin_encrypted is not None
        assert db_user.dob_encrypted is not None

        # FINTRAC Compliance: Audit fields exist
        assert db_user.created_at is not None
        assert db_user.updated_at is not None

    async def test_register_duplicate_user_returns_400(self, client: AsyncClient, valid_user_payload):
        """
        Test that registering a duplicate user returns a 400 error.
        """
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration (duplicate)
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    async def test_login_valid_credentials_returns_token(self, client: AsyncClient, valid_user_payload, login_payload):
        """
        Test logging in with valid credentials returns a JWT token.
        """
        # Setup: Register user first
        await client.post("/api/v1/auth/register", json=valid_user_payload)

        # Action: Login
        response = await client.post("/api/v1/auth/login", json=login_payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials_returns_401(self, client: AsyncClient, valid_user_payload):
        """
        Test logging in with invalid credentials returns 401 Unauthorized.
        """
        # Setup: Register user
        await client.post("/api/v1/auth/register", json=valid_user_payload)

        # Action: Login with wrong password
        response = await client.post("/api/v1/auth/login", json={
            "username": "jdoe",
            "password": "WrongPassword!"
        })

        assert response.status_code == 401
        # Ensure error code is present for structured error handling
        assert "error_code" in response.json()

    async def test_get_user_profile_returns_sanitized_data(self, client: AsyncClient, valid_user_payload, db_session):
        """
        Test retrieving a user profile via API excludes sensitive PII.
        """
        # Setup: Register user
        reg_resp = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_resp.json()["id"]

        # Login to get token
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "jdoe",
            "password": "SecurePass123!"
        })
        token = login_resp.json()["access_token"]

        # Action: Get User Profile
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get(f"/api/v1/auth/users/{user_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        
        # Verify non-sensitive fields
        assert data["id"] == user_id
        assert data["username"] == "jdoe"
        assert data["email"] == "john.doe@example.com"
        
        # PIPEDA Compliance: Strict check that PII is absent
        assert "sin" not in data
        assert "dob" not in data
        assert "hashed_password" not in data
        assert "sin_encrypted" not in data
        assert "dob_encrypted" not in data

    async def test_get_user_profile_unauthorized_without_token(self, client: AsyncClient, valid_user_payload):
        """
        Test accessing profile without token returns 401.
        """
        reg_resp = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_resp.json()["id"]

        response = await client.get(f"/api/v1/auth/users/{user_id}")
        assert response.status_code == 401

    async def test_update_user_last_login(self, client: AsyncClient, valid_user_payload, db_session):
        """
        Test that login updates the audit trail (last_login_at).
        """
        # Setup
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Check initial state
        stmt = select(User).where(User.username == "jdoe")
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()
        initial_last_login = user.last_login_at

        # Action
        await client.post("/api/v1/auth/login", json={
            "username": "jdoe",
            "password": "SecurePass123!"
        })

        # Verify update
        await db_session.refresh(user)
        # Assuming the service updates last_login_at on successful auth
        # If the field exists in model, it should be updated
        if hasattr(user, 'last_login_at'):
            assert user.last_login_at is not None
            if initial_last_login:
                assert user.last_login_at > initial_last_login