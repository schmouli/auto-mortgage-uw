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