--- conftest.py ---
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.modules.authentication.routes import router
from fastapi import FastAPI

# Database URL for in-memory SQLite (lightweight for testing)
# Note: Project uses PG 15, but SQLite is standard for isolated unit/integration tests
# unless a specific PG container is mandated.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/auth", tags=["Authentication"])
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

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
async def seeded_user(db_session: AsyncSession):
    # Helper to create a user directly in DB for login tests
    from mortgage_underwriting.common.security import hash_password
    
    user = User(
        username="existing_user",
        email="existing@example.com",
        hashed_password=hash_password("ExistingPass123!"),
        role="underwriter"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

--- unit_tests ---
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.authentication.services import UserService, AuthService
from mortgage_underwriting.modules.authentication.schemas import UserCreate, UserLogin, UserResponse
from mortgage_underwriting.modules.authentication.exceptions import DuplicateUserError, InvalidCredentialsError
from mortgage_underwriting.common.security import hash_password

@pytest.mark.unit
class TestAuthService:

    def test_hash_password_security(self):
        plain_password = "SuperSecret123!"
        hashed = hash_password(plain_password)
        
        assert hashed != plain_password
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$")  # Bcrypt identifier

    def test_verify_password_valid(self):
        plain = "UserPass123!"
        hashed = hash_password(plain)
        
        # In a real scenario, this is often inside the service or a utility
        # Assuming service method exists or we verify via bcrypt directly if service wraps it
        # Here we test the logic flow
        from bcrypt import checkpw
        assert checkpw(plain.encode('utf-8'), hashed.encode('utf-8')) is True

    def test_verify_password_invalid(self):
        plain = "UserPass123!"
        wrong = "WrongPass123!"
        hashed = hash_password(plain)
        
        from bcrypt import checkpw
        assert checkpw(wrong.encode('utf-8'), hashed.encode('utf-8')) is False

    @patch("mortgage_underwriting.modules.authentication.services.jwt")
    def test_create_token_success(self, mock_jwt):
        mock_jwt.encode.return_value = "encoded_token_string"
        
        payload = {"sub": "user_id", "role": "admin"}
        token = AuthService.create_token(payload)
        
        assert token == "encoded_token_string"
        mock_jwt.encode.assert_called_once()

    @patch("mortgage_underwriting.modules.authentication.services.jwt")
    def test_decode_token_success(self, mock_jwt):
        mock_jwt.decode.return_value = {"sub": "user_id", "role": "admin"}
        
        token = "dummy_token"
        decoded = AuthService.decode_token(token)
        
        assert decoded["sub"] == "user_id"
        mock_jwt.decode.assert_called_once()

@pytest.mark.unit
class TestUserService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_db):
        payload = UserCreate(
            username="new_user",
            email="new@example.com",
            password="Password123!",
            role="underwriter"
        )
        
        # Mock the flush/commit behavior
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Simulate returning a user object after refresh
        # We can't easily mock the model instance creation inside the service 
        # without access to the model, but we can verify DB calls.
        
        service = UserService(mock_db)
        result = await service.create_user(payload)
        
        # Assertions
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        
        # Verify PIPEDA compliance: Password should not be stored in plain text
        # The added object should have hashed_password, not password
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.hashed_password is not None
        assert added_obj.hashed_password != "Password123!"

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, mock_db):
        payload = UserCreate(
            username="dupe_user",
            email="dupe@example.com",
            password="Password123!",
            role="underwriter"
        )
        
        # Simulate IntegrityError from DB (Unique constraint violation)
        mock_db.flush = AsyncMock(side_effect=IntegrityError("duplicate", {}, None))
        
        service = UserService(mock_db)
        
        with pytest.raises(DuplicateUserError):
            await service.create_user(payload)
            
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_username_found(self, mock_db):
        # Mock the result of execute.scalar
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "found_user"
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        service = UserService(mock_db)
        result = await service.get_by_username("found_user")
        
        assert result is not None
        assert result.username == "found_user"

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db):
        # Setup: User exists and password matches
        plain_pass = "CorrectPass123!"
        hashed = hash_password(plain_pass)
        
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "valid_user"
        mock_user.hashed_password = hashed
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        payload = UserLogin(username="valid_user", password=plain_pass)
        
        service = UserService(mock_db)
        user = await service.authenticate(payload)
        
        assert user is not None
        assert user.username == "valid_user"

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db):
        # Setup: User exists but password is wrong
        hashed = hash_password("CorrectPass123!")
        
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "valid_user"
        mock_user.hashed_password = hashed
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        payload = UserLogin(username="valid_user", password="WrongPass123!")
        
        service = UserService(mock_db)
        
        with pytest.raises(InvalidCredentialsError):
            await service.authenticate(payload)

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        payload = UserLogin(username="ghost", password="DoesntMatter")
        
        service = UserService(mock_db)
        
        with pytest.raises(InvalidCredentialsError):
            await service.authenticate(payload)

--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.authentication.models import User

@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthenticationFlow:

    async def test_register_user_creates_record(self, client: AsyncClient, db_session: AsyncSession, valid_user_payload):
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert "id" in data
        
        # PIPEDA Check: Ensure password is NOT in response
        assert "password" not in data
        assert "hashed_password" not in data
        
        # Verify Database State
        stmt = select(User).where(User.username == valid_user_payload["username"])
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.email == valid_user_payload["email"]
        assert user.hashed_password is not None
        assert user.hashed_password != valid_user_payload["password"]
        
        # FINTRAC/OSFI: Audit fields exist
        assert user.created_at is not None

    async def test_register_duplicate_fails_409(self, client: AsyncClient, valid_user_payload):
        # First request
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Duplicate request
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 409
        assert "detail" in response.json()

    async def test_login_success_returns_token(self, client: AsyncClient, seeded_user):
        login_payload = {
            "username": seeded_user.username,
            "password": "ExistingPass123!"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials_401(self, client: AsyncClient, seeded_user):
        login_payload = {
            "username": seeded_user.username,
            "password": "WrongPassword"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 401
        # Ensure error structure matches standard
        assert "detail" in response.json()

    async def test_protected_endpoint_with_valid_token(self, client: AsyncClient, seeded_user):
        # 1. Login to get token
        login_res = await client.post("/api/v1/auth/login", json={
            "username": seeded_user.username,
            "password": "ExistingPass123!"
        })
        token = login_res.json()["access_token"]
        
        # 2. Access protected endpoint (e.g., /users/me)
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/users/me", headers=headers)
        
        assert me_res.status_code == 200
        data = me_res.json()
        assert data["username"] == seeded_user.username
        assert "id" in data
        # PIPEDA: No sensitive audit logs or hashes in response
        assert "hashed_password" not in data

    async def test_protected_endpoint_without_token_401(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/users/me")
        
        assert response.status_code == 401

    async def test_protected_endpoint_with_invalid_token_401(self, client: AsyncClient):
        headers = {"Authorization": "Bearer invalid_token_string"}
        response = await client.get("/api/v1/auth/users/me", headers=headers)
        
        assert response.status_code == 401

    async def test_user_role_assignment(self, client: AsyncClient, admin_user_payload, db_session: AsyncSession):
        # Create an admin user
        res = await client.post("/api/v1/auth/register", json=admin_user_payload)
        assert res.status_code == 201
        
        # Verify role in DB
        stmt = select(User).where(User.username == admin_user_payload["username"])
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()
        
        assert user.role == admin_user_payload["role"]

    async def test_input_validation_missing_fields(self, client: AsyncClient):
        # Missing password
        payload = {
            "username": "incomplete",
            "email": "incomplete@example.com"
        }
        
        response = await client.post("/api/v1/auth/register", json=payload)
        
        assert response.status_code == 422  # Validation Error
        
    async def test_weak_password_rejection(self, client: AsyncClient):
        # Assuming the schema enforces strong passwords (length, complexity)
        # If not handled by Pydantic, this might pass, but let's test the contract
        payload = {
            "username": "weak_user",
            "email": "weak@example.com",
            "password": "123" # Too short/weak
        }
        
        response = await client.post("/api/v1/auth/register", json=payload)
        
        # If Pydantic regex is set in schemas.py, this is 422
        # If handled by service logic, might be 400
        # We expect validation to catch this
        assert response.status_code == 422