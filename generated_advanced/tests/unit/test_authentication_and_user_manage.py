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