```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError
from mortgage_underwriting.modules.auth.services import AuthService, UserService
from mortgage_underwriting.modules.auth.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    InactiveUserError
)
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin

# Module name mapping: 'auth' represents Authentication & User Management
from mortgage_underwriting.modules.auth.security import hash_password, verify_password

@pytest.mark.unit
class TestSecurityHelpers:
    def test_hash_password_returns_string(self):
        password = "MySecretP@ssw0rd"
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert hashed != password
        assert len(hashed) > 20  # bcrypt hashes are long

    def test_verify_password_success(self):
        password = "MySecretP@ssw0rd"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_failure(self):
        password = "MySecretP@ssw0rd"
        wrong_password = "WrongPassword"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False


@pytest.mark.unit
class TestAuthService:
    @pytest.fixture
    def mock_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.email = "test@example.com"
        user.is_active = True
        user.role = "underwriter"
        return user

    def test_create_token(self, mock_user):
        token = AuthService.create_token(mock_user)
        assert isinstance(token, str)
        # JWT tokens have 3 parts separated by dots
        assert len(token.split(".")) == 3

    def test_decode_token_success(self, mock_user):
        token = AuthService.create_token(mock_user)
        payload = AuthService.decode_token(token)
        assert payload["sub"] == str(mock_user.id)
        assert payload["username"] == mock_user.username

    def test_decode_token_invalid(self):
        with pytest.raises(InvalidCredentialsError):
            AuthService.decode_token("invalid.token.string")


@pytest.mark.unit
class TestUserService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_db):
        payload = UserCreate(
            username="newuser",
            email="new@example.com",
            password="Password123!",
            role="underwriter"
        )
        
        # Mock scalar to return None (user doesn't exist)
        mock_db.scalar.return_value = None

        user = await UserService.create_user(mock_db, payload)
        
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert user.password_hash != "Password123!" # Ensure hashed
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, mock_db):
        payload = UserCreate(
            username="newuser",
            email="existing@example.com",
            password="Password123!",
            role="underwriter"
        )
        
        # Mock scalar to return existing user
        existing_user = MagicMock()
        mock_db.scalar.return_value = existing_user

        with pytest.raises(UserAlreadyExistsError):
            await UserService.create_user(mock_db, payload)
        
        # Ensure we didn't try to add
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db):
        plain_password = "CorrectPassword"
        hashed = hash_password(plain_password)
        
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = hashed
        mock_user.is_active = True
        
        mock_db.scalar.return_value = mock_user

        login_data = UserLogin(email="test@example.com", password="CorrectPassword")
        result = await UserService.authenticate_user(mock_db, login_data)
        
        assert result == mock_user
        mock_db.scalar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db):
        hashed = hash_password("CorrectPassword")
        
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = hashed
        
        mock_db.scalar.return_value = mock_user

        login_data = UserLogin(email="test@example.com", password="WrongPassword")
        
        with pytest.raises(InvalidCredentialsError):
            await UserService.authenticate_user(mock_db, login_data)

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        mock_db.scalar.return_value = None
        login_data = UserLogin(email="ghost@example.com", password="DoesntMatter")
        
        with pytest.raises(InvalidCredentialsError):
            await UserService.authenticate_user(mock_db, login_data)

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(self, mock_db):
        hashed = hash_password("CorrectPassword")
        
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = hashed
        mock_user.is_active = False
        
        mock_db.scalar.return_value = mock_user

        login_data = UserLogin(email="test@example.com", password="CorrectPassword")
        
        with pytest.raises(InactiveUserError):
            await UserService.authenticate_user(mock_db, login_data)

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mock_db):
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_db.get.return_value = mock_user
        
        result = await UserService.get_user_by_id(mock_db, 1)
        assert result == mock_user
        mock_db.get.assert_awaited_once_with(User, 1)
```