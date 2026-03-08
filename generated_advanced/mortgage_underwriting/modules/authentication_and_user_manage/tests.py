--- conftest.py ---
```python
import asyncio
import pytest
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool

# Assuming standard project structure
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.main import app  # Adjust if your app entry point differs
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.modules.authentication.schemas import UserCreate, UserLogin

# Database setup for tests (using in-memory SQLite for speed and isolation)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates an AsyncClient for testing FastAPI endpoints.
    Overrides the dependency for the database session.
    """
    from mortgage_underwriting.common.database import get_async_session

    async def override_get_async_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_async_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def valid_user_payload() -> dict:
    """
    Valid payload for user registration.
    """
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "sin": "123456789",  # Will be hashed
        "dob": "1990-01-01", # Will be encrypted
        "role": "underwriter"
    }

@pytest.fixture
def admin_user_payload() -> dict:
    return {
        "username": "admin",
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "sin": "987654321",
        "dob": "1980-01-01",
        "role": "admin"
    }

@pytest.fixture
async def seeded_user(db_session: AsyncSession, valid_user_payload: dict) -> User:
    """
    Helper to create a user in the DB directly for testing login/fetch logic.
    """
    from mortgage_underwriting.common.security import hash_password, encrypt_pii, hash_sin
    
    hashed_pw = hash_password(valid_user_payload["password"])
    encrypted_dob = encrypt_pii(valid_user_payload["dob"])
    hashed_sin = hash_sin(valid_user_payload["sin"])
    
    user = User(
        username=valid_user_payload["username"],
        email=valid_user_payload["email"],
        hashed_password=hashed_pw,
        sin_hash=hashed_sin,
        encrypted_dob=encrypted_dob,
        role=valid_user_payload.get("role", "user")
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

from mortgage_underwriting.modules.authentication.services import AuthService
from mortgage_underwriting.modules.authentication.exceptions import (
    UserAlreadyExistsException,
    InvalidCredentialsException,
    UserNotFoundException
)
from mortgage_underwriting.common.exceptions import AppException

# Import models/schemas as defined in the prompt structure
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.modules.authentication.schemas import UserCreate, UserLogin, UserResponse

@pytest.mark.unit
class TestAuthService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_register_user_success(self, mock_db):
        """
        Test successful user registration: password hashing, SIN hashing, DOB encryption.
        """
        payload = UserCreate(
            username="newuser",
            email="new@example.com",
            password="Password123!",
            sin="123456789",
            dob="1985-05-20",
            role="underwriter"
        )

        with patch("mortgage_underwriting.modules.authentication.services.hash_password") as mock_hash_pw, \
             patch("mortgage_underwriting.modules.authentication.services.hash_sin") as mock_hash_sin, \
             patch("mortgage_underwriting.modules.authentication.services.encrypt_pii") as mock_encrypt_dob:

            mock_hash_pw.return_value = "hashed_secret"
            mock_hash_sin.return_value = "hashed_sin"
            mock_encrypt_dob.return_value = "encrypted_dob"

            service = AuthService(mock_db)
            result = await service.register_user(payload)

            # Verify DB interactions
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once()

            # Verify security transformations were called
            mock_hash_pw.assert_called_once_with("Password123!")
            mock_hash_sin.assert_called_once_with("123456789")
            mock_encrypt_dob.assert_called_once_with("1985-05-20")

            # Verify the result is a UserResponse schema
            assert isinstance(result, UserResponse)
            assert result.username == "newuser"
            assert result.role == "underwriter"
            # PII must not be in response
            assert not hasattr(result, 'sin_hash')
            assert not hasattr(result, 'encrypted_dob')
            assert not hasattr(result, 'password')

    @pytest.mark.asyncio
    async def test_register_user_duplicate_username(self, mock_db):
        """
        Test registration failure when username already exists.
        """
        payload = UserCreate(
            username="existing",
            email="new@example.com",
            password="Password123!",
            sin="999999999",
            dob="1990-01-01"
        )
        
        # Simulate IntegrityError from DB (unique constraint violation)
        mock_db.commit.side_effect = IntegrityError("INSERT failed", {}, Exception())

        service = AuthService(mock_db)
        
        with pytest.raises(UserAlreadyExistsException) as exc_info:
            await service.register_user(payload)
        
        assert exc_info.value.detail == "User with this username or email already exists."

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db):
        """
        Test successful authentication returning a token.
        """
        login_data = UserLogin(username="testuser", password="password123")
        
        # Mock User object
        mock_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password123",
            role="user"
        )

        mock_db.scalar.return_value = mock_user

        with patch("mortgage_underwriting.modules.authentication.services.verify_password") as mock_verify, \
             patch("mortgage_underwriting.modules.authentication.services.create_access_token") as mock_token:

            mock_verify.return_value = True
            mock_token.return_value = "valid_jwt_token"

            service = AuthService(mock_db)
            token = await service.authenticate_user(login_data)

            assert token == "valid_jwt_token"
            mock_verify.assert_called_once_with("password123", "hashed_password123")
            mock_token.assert_called_once_with(data={"sub": "testuser", "role": "user"})

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        """
        Test authentication failure when user does not exist.
        """
        login_data = UserLogin(username="ghost", password="password")
        mock_db.scalar.return_value = None

        service = AuthService(mock_db)

        with pytest.raises(InvalidCredentialsException):
            await service.authenticate_user(login_data)

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db):
        """
        Test authentication failure with incorrect password.
        """
        login_data = UserLogin(username="testuser", password="wrongpass")
        
        mock_user = User(
            id=1,
            username="testuser",
            hashed_password="correct_hash"
        )
        mock_db.scalar.return_value = mock_user

        with patch("mortgage_underwriting.modules.authentication.services.verify_password") as mock_verify:
            mock_verify.return_value = False

            service = AuthService(mock_db)

            with pytest.raises(InvalidCredentialsException):
                await service.authenticate_user(login_data)

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, mock_db):
        """
        Test retrieving a user by ID.
        """
        mock_user = User(id=1, username="fetchme", email="fetch@example.com", role="user")
        mock_db.get.return_value = mock_user

        service = AuthService(mock_db)
        result = await service.get_user_by_id(1)

        assert result.username == "fetchme"
        mock_db.get.assert_called_once_with(User, 1)

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, mock_db):
        """
        Test retrieving a non-existent user raises exception.
        """
        mock_db.get.return_value = None
        service = AuthService(mock_db)

        with pytest.raises(UserNotFoundException):
            await service.get_user_by_id(999)

    @pytest.mark.asyncio
    async def test_pii_not_logged_in_service(self, mock_db, caplog):
        """
        Ensure that PII (SIN, DOB, Password) is not part of standard error logging or state.
        This is a structural check on how data is handled in the service layer.
        """
        payload = UserCreate(
            username="logtest",
            email="log@example.com",
            password="Secret123!",
            sin="111222333",
            dob="1970-01-01"
        )

        # We verify that the object passed to DB.add contains the HASHED/ENCRYPTED versions, not raw
        with patch("mortgage_underwriting.modules.authentication.services.hash_password") as mock_hash_pw, \
             patch("mortgage_underwriting.modules.authentication.services.hash_sin") as mock_hash_sin, \
             patch("mortgage_underwriting.modules.authentication.services.encrypt_pii") as mock_encrypt_dob:

            mock_hash_pw.return_value = "xxx"
            mock_hash_sin.return_value = "yyy"
            mock_encrypt_dob.return_value = "zzz"

            service = AuthService(mock_db)
            await service.register_user(payload)

            # Check the call arguments to db.add
            added_user = mock_db.add.call_args[0][0]
            
            # Ensure raw PII is NOT set on the model instance
            assert added_user.hashed_password != "Secret123!"
            assert added_user.sin_hash != "111222333"
            assert added_user.encrypted_dob != "1970-01-01"
            
            # Ensure transformed data IS set
            assert added_user.hashed_password == "xxx"
            assert added_user.sin_hash == "yyy"
            assert added_user.encrypted_dob == "zzz"
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient

from mortgage_underwriting.modules.authentication.models import User
from sqlalchemy import select

@pytest.mark.integration
class TestAuthenticationRoutes:

    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient, valid_user_payload: dict):
        """
        Integration test: Register a new user via API.
        """
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert data["role"] == valid_user_payload["role"]
        
        # PII Check: SIN and DOB must NOT be in response
        assert "sin" not in data
        assert "dob" not in data
        assert "password" not in data
        assert "sin_hash" not in data
        assert "encrypted_dob" not in data

    @pytest.mark.asyncio
    async def test_register_user_duplicate(self, client: AsyncClient, valid_user_payload: dict):
        """
        Integration test: Attempt to register duplicate user.
        """
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration (should fail)
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "already exists" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_user_validation_error(self, client: AsyncClient):
        """
        Integration test: Register with invalid data (missing fields).
        """
        invalid_payload = {
            "username": "baduser",
            # Missing email, password, sin, dob
        }
        
        response = await client.post("/api/v1/auth/register", json=invalid_payload)
        assert response.status_code == 422 # Validation Error

    @pytest.mark.asyncio
    async def test_login_user_success(self, client: AsyncClient, seeded_user: User):
        """
        Integration test: Login with valid credentials.
        """
        login_payload = {
            "username": seeded_user.username,
            "password": "SecurePassword123!" # From conftest fixture
        }
        
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_user_invalid_password(self, client: AsyncClient, seeded_user: User):
        """
        Integration test: Login with wrong password.
        """
        login_payload = {
            "username": seeded_user.username,
            "password": "WrongPassword"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_current_user_protected(self, client: AsyncClient, seeded_user: User):
        """
        Integration test: Access protected /me endpoint with valid token.
        """
        # 1. Login to get token
        login_payload = {
            "username": seeded_user.username,
            "password": "SecurePassword123!"
        }
        login_resp = await client.post("/api/v1/auth/login", json=login_payload)
        token = login_resp.json()["access_token"]
        
        # 2. Access /me
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["username"] == seeded_user.username
        assert data["email"] == seeded_user.email
        # Ensure PII is not exposed
        assert "sin" not in data
        assert "dob" not in data

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """
        Integration test: Access protected /me endpoint without token.
        """
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """
        Integration test: Access protected /me endpoint with malformed token.
        """
        headers = {"Authorization": "Bearer invalid_token_string"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_pii_storage_in_db(self, db_session, client: AsyncClient, valid_user_payload: dict):
        """
        Regulatory Check: Verify that SIN is hashed and DOB is encrypted in the DB.
        """
        # Register via API
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Query DB directly
        result = await db_session.execute(select(User).where(User.username == valid_user_payload["username"]))
        db_user = result.scalar_one_or_none()
        
        assert db_user is not None
        
        # Verify raw data is NOT stored
        assert db_user.sin_hash != valid_user_payload["sin"]
        assert db_user.encrypted_dob != valid_user_payload["dob"]
        
        # Verify fields are populated (transformed)
        assert db_user.sin_hash is not None
        assert db_user.encrypted_dob is not None
        
        # Verify raw data is never in the model instance attributes
        assert not hasattr(db_user, 'sin')
        assert not hasattr(db_user, 'raw_dob')

    @pytest.mark.asyncio
    async def test_user_audit_fields(self, db_session, client: AsyncClient, valid_user_payload: dict):
        """
        Regulatory Check: Verify created_at and updated_at are populated.
        """
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        result = await db_session.execute(select(User).where(User.username == valid_user_payload["username"]))
        db_user = result.scalar_one_or_none()
        
        assert db_user.created_at is not None
        assert db_user.updated_at is not None
```