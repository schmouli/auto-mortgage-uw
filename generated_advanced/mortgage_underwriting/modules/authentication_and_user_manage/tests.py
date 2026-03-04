--- conftest.py ---
```python
import pytest
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from decimal import Decimal

from mortgage_underwriting.common.database import Base, get_async_session
from mortgage_underwriting.main import app  # Assuming main.py exists to bootstrap the app
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.common.security import hash_password

# Use an in-memory SQLite database for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates a FastAPI AsyncClient with a dependency override for the database session.
    """
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def valid_user_payload() -> dict:
    """
    Returns a valid payload for user registration including financial data.
    Uses Decimal for financial values as per project conventions.
    """
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "sin": "123456789",  # PII: Should be encrypted
        "dob": "1990-01-01", # PII: Should be encrypted
        "annual_income": str(Decimal("85000.00")) # Financial: Must be Decimal/string
    }


@pytest.fixture
def existing_user(db_session: AsyncSession) -> User:
    """
    Creates an existing user in the database for testing login/conflicts.
    """
    import asyncio
    user = User(
        username="existinguser",
        email="existing@example.com",
        hashed_password=hash_password("Password123!"),
        sin_encrypted="encrypted_sin_placeholder", # Mocked encrypted value
        dob_encrypted="encrypted_dob_placeholder", # Mocked encrypted value
        role="applicant"
    )
    
    async def create_user():
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user
    
    # Run sync wrapper to make the fixture usable in both sync/async contexts if needed, 
    # though here primarily for integration tests which are async.
    # However, pytest fixtures are sync by default unless marked.
    # We will handle the async creation in the integration test or use a sync wrapper if strictly needed.
    # For this fixture, we'll return the coroutine or use the event loop if strictly synchronous.
    # Given the complexity, we will just return the object and let the test handle the commit 
    # OR make this fixture async.
    
    # Correct approach for pytest-asyncio fixtures:
    return user

# Async fixture version of existing_user
@pytest.fixture
async def async_existing_user(db_session: AsyncSession) -> User:
    user = User(
        username="existinguser",
        email="existing@example.com",
        hashed_password=hash_password("Password123!"),
        sin_encrypted="encrypted_sin_placeholder",
        dob_encrypted="encrypted_dob_placeholder",
        role="applicant"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.authentication.services import (
    UserService, 
    AuthService
)
from mortgage_underwriting.modules.authentication.schemas import (
    UserCreate, 
    UserLogin
)
from mortgage_underwriting.modules.authentication.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError
)
from mortgage_underwriting.common.exceptions import AppException

# Import paths strictly enforced
# from mortgage_underwriting.modules.authentication.models import User # Implicitly used via service

@pytest.mark.unit
class TestUserService:

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
    async def test_create_user_success_hashes_password_and_encrypts_pii(self, mock_db):
        """
        Unit test to ensure password hashing and PII encryption are called.
        """
        payload = UserCreate(
            username="jdoe",
            email="jdoe@example.com",
            password="plain_password",
            sin="123456789",
            dob="1985-05-20",
            annual_income=Decimal("60000.00")
        )

        # We need to patch the security functions used inside the service
        with patch("mortgage_underwriting.modules.authentication.services.hash_password") as mock_hash, \
             patch("mortgage_underwriting.modules.authentication.services.encrypt_pii") as mock_encrypt:
            
            mock_hash.return_value = "hashed_secret"
            mock_encrypt.return_value = "encrypted_blob"

            service = UserService(mock_db)
            result = await service.create_user(payload)

            # Assertions
            mock_hash.assert_called_once_with("plain_password")
            assert mock_encrypt.call_count == 2 # Once for SIN, once for DOB
            
            # Verify DB Add was called with a model instance
            mock_db.add.assert_called_once()
            added_user = mock_db.add.call_args[0][0]
            
            assert added_user.hashed_password == "hashed_secret"
            assert added_user.sin_encrypted == "encrypted_blob"
            assert added_user.dob_encrypted == "encrypted_blob"
            
            # Ensure raw PII is NOT stored
            assert not hasattr(added_user, 'sin') or getattr(added_user, 'sin', None) is None
            assert not hasattr(added_user, 'dob') or getattr(added_user, 'dob', None) is None

            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username_raises_exception(self, mock_db):
        """
        Test that IntegrityError from DB is mapped to UserAlreadyExistsError.
        """
        payload = UserCreate(
            username="jdoe",
            email="jdoe@example.com",
            password="plain_password",
            sin="123456789",
            dob="1985-05-20",
            annual_income=Decimal("60000.00")
        )

        # Simulate DB constraint violation
        mock_db.commit.side_effect = IntegrityError("INSERT failed", {}, None)

        with patch("mortgage_underwriting.modules.authentication.services.hash_password") as mock_hash, \
             patch("mortgage_underwriting.modules.authentication.services.encrypt_pii") as mock_encrypt:
            
            mock_hash.return_value = "hashed"
            mock_encrypt.return_value = "encrypted"

            service = UserService(mock_db)
            
            with pytest.raises(UserAlreadyExistsError):
                await service.create_user(payload)

    @pytest.mark.asyncio
    async def test_get_user_by_username_found(self, mock_db):
        """
        Test successful retrieval of a user by username.
        """
        # Mock the User model response
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.role = "applicant"
        
        # Mock the scalar query to return the user
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = result_mock

        service = UserService(mock_db)
        user = await service.get_user_by_username("testuser")

        assert user is not None
        assert user.username == "testuser"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_by_username_not_found(self, mock_db):
        """
        Test retrieval when user does not exist.
        """
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        service = UserService(mock_db)
        user = await service.get_user_by_username("ghost")

        assert user is None


@pytest.mark.unit
class TestAuthService:

    @pytest.fixture
    def mock_user_service(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_user_service):
        """
        Test valid credentials return a user object.
        """
        # Setup
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.hashed_password = "hashed_correct_password"
        
        mock_user_service.get_user_by_username.return_value = mock_user
        
        with patch("mortgage_underwriting.modules.authentication.services.verify_password") as mock_verify:
            mock_verify.return_value = True
            
            service = AuthService(mock_user_service)
            result = await service.authenticate_user("testuser", "raw_password")

            assert result == mock_user
            mock_verify.assert_called_once_with("raw_password", "hashed_correct_password")

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_user_service):
        """
        Test invalid password raises InvalidCredentialsError.
        """
        mock_user = MagicMock()
        mock_user.hashed_password = "hashed_correct_password"
        mock_user_service.get_user_by_username.return_value = mock_user

        with patch("mortgage_underwriting.modules.authentication.services.verify_password") as mock_verify:
            mock_verify.return_value = False
            
            service = AuthService(mock_user_service)
            
            with pytest.raises(InvalidCredentialsError):
                await service.authenticate_user("testuser", "wrong_password")

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_user_service):
        """
        Test non-existent user raises InvalidCredentialsError.
        """
        mock_user_service.get_user_by_username.return_value = None
        
        service = AuthService(mock_user_service)
        
        with pytest.raises(InvalidCredentialsError):
            await service.authenticate_user("ghost", "password")

    @pytest.mark.asyncio
    async def test_create_token_returns_jwt(self, mock_user_service):
        """
        Test token generation contains correct subject.
        """
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        
        with patch("mortgage_underwriting.modules.authentication.services.create_access_token") as mock_create_token:
            mock_create_token.return_value = "fake_jwt_token"
            
            service = AuthService(mock_user_service)
            token = await service.create_token(mock_user)
            
            assert token == "fake_jwt_token"
            mock_create_token.assert_called_once_with(data={"sub": str(mock_user.id), "role": mock_user.role})
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.authentication.models import User

@pytest.mark.integration
class TestAuthenticationRoutes:

    @pytest.mark.asyncio
    async def test_register_user_creates_encrypted_record(self, client: AsyncClient, db_session):
        """
        Test registration endpoint ensures data is stored and PII is encrypted.
        """
        payload = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "ComplexPass123!",
            "sin": "987654321",
            "dob": "1992-12-12",
            "annual_income": "95000.00" # String representation of Decimal
        }

        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert "id" in data
        # PIPEDA Check: Ensure SIN and DOB are NOT in the response
        assert "sin" not in data
        assert "dob" not in data
        assert "hashed_password" not in data

        # Verify Database State
        result = await db_session.execute(
            f"SELECT sin_encrypted, dob_encrypted, hashed_password FROM users WHERE username = 'newuser'"
        )
        db_record = result.one()

        # Verify encryption happened (value is not the raw input)
        assert db_record.sin_encrypted != "987654321"
        assert db_record.dob_encrypted != "1992-12-12"
        # Verify password hashing happened
        assert db_record.hashed_password != "ComplexPass123!"
        assert db_record.hashed_password.startswith("$2b$") # Bcrypt hash prefix

    @pytest.mark.asyncio
    async def test_register_duplicate_username_returns_400(self, client: AsyncClient, async_existing_user: User):
        """
        Test that registering a duplicate username returns a structured error.
        """
        payload = {
            "username": "existinguser", # Duplicate
            "email": "another@example.com",
            "password": "ComplexPass123!",
            "sin": "111111111",
            "dob": "1990-01-01",
            "annual_income": "50000.00"
        }

        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 400
        # Check structured error response
        assert "detail" in response.json()
        assert "error_code" in response.json()

    @pytest.mark.asyncio
    async def test_login_success_returns_token(self, client: AsyncClient, async_existing_user: User):
        """
        Test login with valid credentials returns a JWT token.
        """
        payload = {
            "username": "existinguser",
            "password": "Password123!"
        }

        response = await client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_returns_401(self, client: AsyncClient, async_existing_user: User):
        """
        Test login with wrong password returns 401.
        """
        payload = {
            "username": "existinguser",
            "password": "WrongPassword"
        }

        response = await client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 401
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_get_me_returns_user_without_pii(self, client: AsyncClient, async_existing_user: User):
        """
        Test retrieving the current user profile.
        1. Login to get token.
        2. Use token to hit /me.
        3. Verify PII is absent from response.
        """
        # Step 1: Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "existinguser",
            "password": "Password123!"
        })
        token = login_resp.json()["access_token"]

        # Step 2: Get /me
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)

        assert me_resp.status_code == 200
        user_data = me_resp.json()
        
        assert user_data["username"] == "existinguser"
        
        # PIPEDA Compliance: Strict check that sensitive fields are never exposed
        assert "sin" not in user_data
        assert "dob" not in user_data
        assert "sin_encrypted" not in user_data
        assert "dob_encrypted" not in user_data
        assert "hashed_password" not in user_data

    @pytest.mark.asyncio
    async def test_get_me_without_token_returns_401(self, client: AsyncClient):
        """
        Test that accessing protected endpoint without token fails.
        """
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        # FastAPI default detail for unauthorized
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_invalid_income_format_returns_422(self, client: AsyncClient):
        """
        Test validation of financial fields (Decimal requirement).
        Sending a float or garbage string should trigger validation error.
        """
        payload = {
            "username": "moneyuser",
            "email": "money@example.com",
            "password": "Pass123!",
            "sin": "123456789",
            "dob": "1990-01-01",
            "annual_income": "not_a_decimal" # Invalid format
        }

        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 422 # Unprocessable Entity
```