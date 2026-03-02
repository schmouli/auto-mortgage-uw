--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from unittest.mock import AsyncMock, MagicMock

# Import paths based on project conventions
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings
from mortgage_underwriting.modules.auth.routes import router as auth_router

# Use in-memory SQLite for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    yield engine
    engine.sync_engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def app(db_session: AsyncSession) -> FastAPI:
    """
    Create a test application with the auth router.
    Override the dependency for the database session.
    """
    from mortgage_underwriting.common.database import get_async_session
    
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    
    # Dependency override
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async client for integration testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_user_payload():
    return {
        "username": "testuser",
        "password": "SecurePassword123!",
        "email": "test@example.com",
        "full_name": "Test User",
        "sin": "123456789", # PIPEDA: Must be encrypted
        "date_of_birth": "1990-01-01",
        "annual_income": "95000.00" # Decimal required for financial values
    }

@pytest.fixture
def mock_security_service():
    """Mock for security utility functions"""
    from mortgage_underwriting.common.security import encrypt_pii, verify_token, hash_password
    
    # We use patching in tests, but this fixture provides a consistent mock object if needed
    mock_sec = MagicMock()
    mock_sec.encrypt_pii = MagicMock(side_effect=lambda x: f"encrypted_{x}")
    mock_sec.hash_password = MagicMock(side_effect=lambda x: f"hashed_{x}")
    mock_sec.verify_password = MagicMock(return_value=True)
    return mock_sec

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

# Import paths based on project conventions
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin, UserResponse, TokenResponse
from mortgage_underwriting.modules.auth.services import AuthService
from mortgage_underwriting.modules.auth.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    PIPEDAComplianceException
)

@pytest.mark.unit
class TestAuthService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return AuthService(mock_db)

    @pytest.mark.asyncio
    async def test_hash_password(self, service):
        plain_password = "MySecretPass123"
        hashed = await service._hash_password(plain_password)
        
        assert hashed is not None
        assert hashed != plain_password
        # Verify bcrypt hash format (starts with $2b$)
        assert hashed.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_verify_password_success(self, service):
        plain = "MySecretPass123"
        hashed = await service._hash_password(plain)
        
        result = await service._verify_password(plain, hashed)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_password_failure(self, service):
        plain = "MySecretPass123"
        wrong = "WrongPassword"
        hashed = await service._hash_password(plain)
        
        result = await service._verify_password(wrong, hashed)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_user_success(self, service, mock_db, valid_user_payload):
        # Arrange
        user_schema = UserCreate(**valid_user_payload)
        
        # Mock DB behavior for unique check (user doesn't exist)
        mock_db.scalar.return_value = None
        
        # Act
        result = await service.create_user(user_schema)
        
        # Assert
        assert isinstance(result, User)
        assert result.username == user_schema.username
        assert result.sin_hash != user_schema.sin # PIPEDA: SIN must be hashed
        assert result.sin_hash.startswith("sha256:") or len(result.sin_hash) == 64 # Assuming SHA256 hash
        assert result.hashed_password.startswith("$2b$")
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, service, mock_db, valid_user_payload):
        # Arrange
        user_schema = UserCreate(**valid_user_payload)
        existing_user = User(id=1, username=user_schema.username)
        mock_db.scalar.return_value = existing_user
        
        # Act & Assert
        with pytest.raises(UserAlreadyExistsException):
            await service.create_user(user_schema)
        
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, service, mock_db, valid_user_payload):
        # Arrange
        username = valid_user_payload["username"]
        password = valid_user_payload["password"]
        
        # Create a fake user object in DB
        fake_user = User(
            id=1,
            username=username,
            hashed_password=await service._hash_password(password),
            sin_hash="hash",
            annual_income=Decimal("95000.00")
        )
        mock_db.scalar.return_value = fake_user
        
        # Act
        result = await service.authenticate_user(username, password)
        
        # Assert
        assert result == fake_user
        mock_db.scalar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, service, mock_db):
        # Arrange
        mock_db.scalar.return_value = None
        
        # Act & Assert
        with pytest.raises(InvalidCredentialsException):
            await service.authenticate_user("nonexistent", "password")

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, service, mock_db, valid_user_payload):
        # Arrange
        username = valid_user_payload["username"]
        fake_user = User(
            id=1,
            username=username,
            hashed_password=await service._hash_password("correct_pass"),
            sin_hash="hash"
        )
        mock_db.scalar.return_value = fake_user
        
        # Act & Assert
        with pytest.raises(InvalidCredentialsException):
            await service.authenticate_user(username, "wrong_pass")

    @pytest.mark.asyncio
    async def test_create_token(self, service):
        # Arrange
        user = User(id=1, username="testuser", sin_hash="hash")
        
        # Act
        token_data = await service.create_token(user)
        
        # Assert
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        # Decode and check sub (subject) claim matches username
        # Note: In a real test we might decode the JWT, here we check existence
        assert len(token_data["access_token"]) > 20

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, service, mock_db):
        # Arrange
        user = User(id=1, username="testuser", sin_hash="hash", annual_income=Decimal("50000.00"))
        token_data = await service.create_token(user)
        token = token_data["access_token"]
        
        mock_db.scalar.return_value = user
        
        # Act
        result = await service.get_current_user(token)
        
        # Assert
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, service):
        # Act & Assert
        with pytest.raises(InvalidCredentialsException):
            await service.get_current_user("invalid.token.here")

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient

# Import paths based on project conventions
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthEndpoints:

    async def test_register_user_success(self, client: AsyncClient, valid_user_payload):
        """
        Test user registration endpoint ensures:
        1. User is created in DB
        2. Response does not contain PII (SIN)
        3. Response contains audit fields
        """
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        # Validate Response Structure
        assert "id" in data
        assert "username" in data
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert "annual_income" in data
        assert Decimal(data["annual_income"]) == Decimal(valid_user_payload["annual_income"])
        
        # PIPEDA Compliance: SIN must NOT be in response
        assert "sin" not in data
        assert "password" not in data
        assert "hashed_password" not in data
        
        # Audit Fields (FINTRAC/General Audit)
        assert "created_at" in data
        assert "updated_at" in data

    async def test_register_user_duplicate(self, client: AsyncClient, valid_user_payload):
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration with same data
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 400
        assert "detail" in response.json()

    async def test_register_user_invalid_decimal(self, client: AsyncClient, valid_user_payload):
        """
        Test that float or non-decimal strings for financial fields are rejected
        """
        # Violation: Float provided instead of string/decimal
        invalid_payload = valid_user_payload.copy()
        invalid_payload["annual_income"] = 95000.00 
        
        response = await client.post("/api/v1/auth/register", json=invalid_payload)
        
        # Pydantic validation error (422)
        assert response.status_code == 422

    async def test_login_success(self, client: AsyncClient, valid_user_payload):
        # Register user first
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login
        login_payload = {
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials(self, client: AsyncClient, valid_user_payload):
        # Register user
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login with wrong password
        login_payload = {
            "username": valid_user_payload["username"],
            "password": "WrongPassword123!"
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 401
        assert "detail" in response.json()

    async def test_get_me_protected_route(self, client: AsyncClient, valid_user_payload):
        # 1. Register
        reg_resp = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_resp.json()["id"]

        # 2. Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_resp.json()["access_token"]

        # 3. Access Protected Route /me
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["id"] == user_id
        assert data["username"] == valid_user_payload["username"]
        
        # PIPEDA Compliance Check on /me endpoint
        assert "sin" not in data

    async def test_get_me_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_sin_encrypted_in_db(self, client: AsyncClient, valid_user_payload, db_session):
        """
        Direct DB check to ensure PIPEDA compliance:
        SIN is hashed and not stored in plain text.
        """
        plain_sin = valid_user_payload["sin"]
        
        # Register via API
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Query DB directly
        from sqlalchemy import select
        stmt = select(User).where(User.username == valid_user_payload["username"])
        result = await db_session.execute(stmt)
        user = result.scalar_one()
        
        assert user is not None
        # Assert SIN is NOT stored plainly
        assert user.sin != plain_sin 
        # Assert SIN hash is present
        assert user.sin_hash is not None
        # Assert hash is not the plain text
        assert user.sin_hash != plain_sin
        # Assert hash looks like a hash (length check for SHA256)
        assert len(user.sin_hash) == 64

    async def test_financial_data_precision(self, client: AsyncClient, valid_user_payload):
        """
        Ensure Decimal precision is maintained through the request/response cycle
        """
        # Specific high precision income
        valid_user_payload["annual_income"] = "123456.78"
        
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        assert response.status_code == 201
        
        data = response.json()
        # Verify precision is kept
        assert Decimal(data["annual_income"]) == Decimal("123456.78")