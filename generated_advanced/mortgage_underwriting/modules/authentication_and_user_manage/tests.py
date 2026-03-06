--- conftest.py ---
```python
import pytest
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Assuming common database structure exists
from mortgage_underwriting.common.database import Base, get_async_session
from mortgage_underwriting.modules.auth_user.models import User
from mortgage_underwriting.modules.auth_user.schemas import UserRegister, UserLogin

# Pytest fixtures for shared test data

@pytest.fixture
def user_payload():
    """Valid payload for user registration."""
    return {
        "email": "underwriter@example.com",
        "password": "SecurePass123!",
        "first_name": "John",
        "last_name": "Doe",
        "sin": "123456789",  # PII - must be encrypted
        "dob": "1980-01-01",
        "role": "underwriter"
    }

@pytest.fixture
def login_payload():
    """Valid payload for login."""
    return {
        "email": "underwriter@example.com",
        "password": "SecurePass123!"
    }

@pytest.fixture
def mock_user_model(user_payload):
    """A mock User model instance."""
    # In a real scenario, SIN would be encrypted here
    return User(
        id=1,
        email=user_payload["email"],
        hashed_password="hashed_SecurePass123!",
        first_name=user_payload["first_name"],
        last_name=user_payload["last_name"],
        encrypted_sin="encrypted_hash_123", 
        dob=user_payload["dob"],
        role=user_payload["role"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

@pytest.fixture
def mock_db_session():
    """Mock AsyncSession for unit tests."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session

# Security Mocks

@pytest.fixture
def mock_security_utils():
    """Mock common security functions."""
    with pytest.mock.patch("mortgage_underwriting.modules.auth_user.services.encrypt_pii") as mock_enc, \
         pytest.mock.patch("mortgage_underwriting.modules.auth_user.services.hash_password") as mock_hash, \
         pytest.mock.patch("mortgage_underwriting.modules.auth_user.services.verify_password") as mock_verify, \
         pytest.mock.patch("mortgage_underwriting.modules.auth_user.services.create_access_token") as mock_token:
        
        mock_enc.return_value = "encrypted_hash"
        mock_hash.return_value = "hashed_password"
        mock_verify.return_value = True
        mock_token.return_value = "mock_jwt_token"
        
        yield {
            "encrypt": mock_enc,
            "hash": mock_hash,
            "verify": mock_verify,
            "token": mock_token
        }

# Integration Test Database Setup (In-Memory SQLite)

@pytest.fixture(scope="function")
async def test_engine():
    """Create an async engine for integration tests."""
    # Using SQLite for speed in tests, though project uses Postgres
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for a test."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
```

--- unit_tests ---
```python
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from mortgage_underwriting.modules.auth_user.models import User
from mortgage_underwriting.modules.auth_user.schemas import UserRegister, UserLogin, UserResponse
from mortgage_underwriting.modules.auth_user.services import AuthService
from mortgage_underwriting.common.exceptions import AppException

# Import the module under test
from mortgage_underwriting.modules.auth_user.services import AuthService

@pytest.mark.unit
class TestAuthService:

    @pytest.mark.asyncio
    async def test_register_user_success(self, mock_db_session, user_payload, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        schema = UserRegister(**user_payload)

        # Act
        result = await service.register_user(schema)

        # Assert
        assert isinstance(result, User)
        assert result.email == user_payload["email"]
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_security_utils["hash"].assert_called_once_with(user_payload["password"])
        
        # PIPEDA Compliance: Ensure SIN is encrypted, not stored in plain text
        mock_security_utils["encrypt"].assert_called_once_with(user_payload["sin"])
        assert result.encrypted_sin == "encrypted_hash"

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, mock_db_session, user_payload, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        schema = UserRegister(**user_payload)
        
        # Mock DB returning an existing user (simulating unique constraint violation)
        mock_db_session.scalar.return_value = User(id=1, email=user_payload["email"])

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.register_user(schema)
        
        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db_session, mock_user_model, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        mock_db_session.scalar.return_value = mock_user_model
        
        login_schema = UserLogin(email="underwriter@example.com", password="SecurePass123!")

        # Act
        token = await service.authenticate_user(login_schema)

        # Assert
        assert token == "mock_jwt_token"
        mock_security_utils["verify"].assert_called_once_with("SecurePass123!", "hashed_SecurePass123!")

    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_password(self, mock_db_session, mock_user_model, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        mock_db_session.scalar.return_value = mock_user_model
        mock_security_utils["verify"].return_value = False # Wrong password
        
        login_schema = UserLogin(email="underwriter@example.com", password="WrongPass")

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.authenticate_user(login_schema)
        
        assert exc_info.value.status_code == 401
        assert "invalid credentials" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db_session, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        mock_db_session.scalar.return_value = None # User not found
        
        login_schema = UserLogin(email="ghost@example.com", password="DoesntMatter")

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.authenticate_user(login_schema)
        
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mock_db_session, mock_user_model):
        # Arrange
        service = AuthService(mock_db_session)
        mock_db_session.get.return_value = mock_user_model

        # Act
        user = await service.get_user_by_id(1)

        # Assert
        assert user is not None
        assert user.email == mock_user_model.email
        mock_db_session.get.assert_called_once_with(User, 1)

    @pytest.mark.asyncio
    async def test_pii_data_minimization(self, mock_db_session, user_payload, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        schema = UserRegister(**user_payload)

        # Act
        user = await service.register_user(schema)

        # Assert - PIPEDA: Ensure raw SIN is NOT on the model
        assert not hasattr(user, 'sin') or getattr(user, 'sin', None) is None
        assert hasattr(user, 'encrypted_sin')
        # Ensure raw password is NOT on the model
        assert not hasattr(user, 'password')
        assert hasattr(user, 'hashed_password')

    @pytest.mark.asyncio
    async def test_fintrac_audit_fields(self, mock_db_session, user_payload, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        schema = UserRegister(**user_payload)

        # Act
        user = await service.register_user(schema)

        # Assert - FINTRAC: Audit trails must exist
        # Note: In a real scenario, these are often defaults in the DB or model __init__
        # Here we check the service logic handles or preserves them
        assert hasattr(user, 'created_at')
        assert hasattr(user, 'updated_at')
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy import select

from mortgage_underwriting.modules.auth_user.models import User
from mortgage_underwriting.modules.auth_user.routes import router
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.security import get_password_hash

# Import test session fixture
from conftest import test_session

@pytest.fixture
def app(test_session):
    """Create a test FastAPI app with the auth router."""
    app = FastAPI()
    
    # Dependency override to use the test session
    async def override_get_async_session():
        yield test_session

    app.include_router(router, prefix="/api/v1/auth", tags=["auth"])
    app.dependency_overrides[get_async_session] = override_get_async_session
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_user_integration(app, user_payload):
    # Arrange
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Act
        response = await client.post("/api/v1/auth/register", json=user_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_payload["email"]
        assert "id" in data
        assert "password" not in data
        
        # PIPEDA Check: SIN must NOT be in the response
        assert "sin" not in data
        assert "encrypted_sin" not in data
        
        # Verify in DB
        # Note: We need the session from the fixture, but the fixture is in conftest.py
        # In a real setup, we would inject the session or query via a separate client.
        # Here we verify the response contract primarily.

@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_user_duplicate_email_integration(app, user_payload, test_session):
    # Arrange - Pre-seed DB
    existing_user = User(
        email=user_payload["email"],
        hashed_password="hash",
        first_name="Existing",
        last_name="User",
        encrypted_sin="hash",
        dob="1990-01-01",
        role="underwriter"
    )
    test_session.add(existing_user)
    await test_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Act
        response = await client.post("/api/v1/auth/register", json=user_payload)

        # Assert
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_user_integration(app, user_payload, test_session):
    # Arrange - Create user first
    # We manually hash to simulate what the registration endpoint would do
    hashed_pw = get_password_hash(user_payload["password"])
    new_user = User(
        email=user_payload["email"],
        hashed_password=hashed_pw,
        first_name=user_payload["first_name"],
        last_name=user_payload["last_name"],
        encrypted_sin="dummy_encrypted_sin",
        dob=user_payload["dob"],
        role=user_payload["role"]
    )
    test_session.add(new_user)
    await test_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Act
        login_data = {"email": user_payload["email"], "password": user_payload["password"]}
        response = await client.post("/api/v1/auth/login", json=login_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_user_wrong_password_integration(app, user_payload, test_session):
    # Arrange
    hashed_pw = get_password_hash(user_payload["password"])
    new_user = User(
        email=user_payload["email"],
        hashed_password=hashed_pw,
        first_name="Test",
        last_name="User",
        encrypted_sin="hash",
        dob="1980-01-01",
        role="underwriter"
    )
    test_session.add(new_user)
    await test_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Act
        login_data = {"email": user_payload["email"], "password": "WrongPassword"}
        response = await client.post("/api/v1/auth/login", json=login_data)

        # Assert
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_me_protected_route_integration(app, user_payload, test_session):
    # Arrange - Create User
    hashed_pw = get_password_hash(user_payload["password"])
    new_user = User(
        email=user_payload["email"],
        hashed_password=hashed_pw,
        first_name=user_payload["first_name"],
        last_name=user_payload["last_name"],
        encrypted_sin="hash",
        dob=user_payload["dob"],
        role=user_payload["role"]
    )
    test_session.add(new_user)
    await test_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login to get token
        login_resp = await client.post("/api/v1/auth/login", json={"email": user_payload["email"], "password": user_payload["password"]})
        token = login_resp.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}

        # Act - Access protected route
        # Assuming a /me endpoint exists in the auth router
        me_resp = await client.get("/api/v1/auth/me", headers=headers)

        # Assert
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["email"] == user_payload["email"]
        # PIPEDA Check: Ensure SIN is not exposed
        assert "sin" not in data
        assert "encrypted_sin" not in data

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_me_unauthorized_integration(app):
    # Arrange
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Act - Access protected route without token
        me_resp = await client.get("/api/v1/auth/me")

        # Assert
        assert me_resp.status_code == 401
```