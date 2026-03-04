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