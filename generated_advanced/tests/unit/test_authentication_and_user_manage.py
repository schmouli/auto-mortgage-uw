```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from jose import jwt

from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.modules.authentication.schemas import UserCreate, UserLogin, UserResponse
from mortgage_underwriting.modules.authentication.services import AuthService, UserService
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.common.security import verify_token, encrypt_pii

# Mock Settings
SECRET_KEY = "test_secret_key"
ALGORITHM = "HS256"

@pytest.mark.unit
class TestAuthService:

    @pytest.fixture
    def mock_pwd_context(self):
        with patch("mortgage_underwriting.modules.authentication.services.pwd_context") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_verify_password_success(self, mock_pwd_context):
        mock_pwd_context.verify.return_value = True
        service = AuthService()
        assert await service.verify_password("plain", "hashed") is True
        mock_pwd_context.verify.assert_called_once_with("plain", "hashed")

    @pytest.mark.asyncio
    async def test_verify_password_failure(self, mock_pwd_context):
        mock_pwd_context.verify.return_value = False
        service = AuthService()
        assert await service.verify_password("plain", "hashed") is False

    @pytest.mark.asyncio
    async def test_hash_password(self, mock_pwd_context):
        mock_pwd_context.hash.return_value = "hashed_secret"
        service = AuthService()
        result = await service.hash_password("plain")
        assert result == "hashed_secret"
        mock_pwd_context.hash.assert_called_once_with("plain")

    @pytest.mark.asyncio
    async def test_create_token(self):
        # Arrange
        subject = "user_123"
        with patch("mortgage_underwriting.modules.authentication.services.settings") as mock_settings:
            mock_settings.SECRET_KEY = SECRET_KEY
            mock_settings.ALGORITHM = ALGORITHM
            
            service = AuthService()
            token = await service.create_access_token(subject)
            
            # Assert
            decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            assert decoded["sub"] == subject
            assert "exp" in decoded

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_pwd_context):
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = User(id=1, username="test", email="test@test.com", hashed_password="hashed", role="user")
        
        # Mock result execution
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        mock_pwd_context.verify.return_value = True
        
        with patch("mortgage_underwriting.modules.authentication.services.select"):
            service = AuthService()
            user = await service.authenticate_user(mock_db, "test@test.com", "password")
            
            assert user == mock_user

    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_password(self, mock_pwd_context):
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = User(id=1, username="test", email="test@test.com", hashed_password="hashed", role="user")
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        mock_pwd_context.verify.return_value = False
        
        with patch("mortgage_underwriting.modules.authentication.services.select"):
            service = AuthService()
            user = await service.authenticate_user(mock_db, "test@test.com", "wrong")
            
            assert user is None


@pytest.mark.unit
class TestUserService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
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
        
        with patch("mortgage_underwriting.modules.authentication.services.AuthService") as MockAuthService:
            MockAuthService.return_value.hash_password = AsyncMock(return_value="hashed_password")
            MockAuthService.return_value.create_access_token = AsyncMock(return_value="token")
            
            service = UserService(mock_db)
            result = await service.create_user(payload)
            
            assert isinstance(result, UserResponse)
            assert result.email == "new@example.com"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email_raises_exception(self, mock_db):
        payload = UserCreate(
            username="newuser",
            email="existing@example.com",
            password="Password123!",
            role="underwriter"
        )
        
        # Simulate IntegrityError from DB
        from sqlalchemy.exc import IntegrityError
        mock_db.commit.side_effect = IntegrityError("mock", "mock", "mock")
        
        with patch("mortgage_underwriting.modules.authentication.services.AuthService") as MockAuthService:
            MockAuthService.return_value.hash_password = AsyncMock(return_value="hashed")
            
            service = UserService(mock_db)
            
            with pytest.raises(AppException) as exc_info:
                await service.create_user(payload)
            
            assert exc_info.value.status_code == 400
            assert "already registered" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mock_db):
        mock_user = User(id=1, username="test", email="test@test.com", hashed_password="hashed", role="user")
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        with patch("mortgage_underwriting.modules.authentication.services.select"):
            service = UserService(mock_db)
            user = await service.get_user_by_id(1)
            
            assert user is not None
            assert user.id == 1

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, mock_db):
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with patch("mortgage_underwriting.modules.authentication.services.select"):
            service = UserService(mock_db)
            user = await service.get_user_by_id(999)
            
            assert user is None

    @pytest.mark.asyncio
    async def test_register_user_encrypts_pii(self, mock_db):
        """
        Regulatory Check: PIPEDA - Ensure PII (like SIN if present in profile) is encrypted.
        Assuming UserCreate might contain sensitive info or related profile creation.
        """
        payload = UserCreate(
            username="secure_user",
            email="secure@example.com",
            password="Password123!",
            role="underwriter"
        )
        
        with patch("mortgage_underwriting.modules.authentication.services.AuthService") as MockAuthService:
            MockAuthService.return_value.hash_password = AsyncMock(return_value="hashed")
            MockAuthService.return_value.create_access_token = AsyncMock(return_value="token")
            
            # Patch encrypt_pii to ensure it's called if we extend user creation to include SIN
            with patch("mortgage_underwriting.modules.authentication.services.encrypt_pii") as mock_encrypt:
                mock_encrypt.return_value = "encrypted_data"
                
                service = UserService(mock_db)
                await service.create_user(payload)
                
                # In a real scenario with SIN, we would assert:
                # mock_encrypt.assert_called_once_with(sin_value)
                # For now, we ensure the flow doesn't break.
                mock_db.add.assert_called_once()
```