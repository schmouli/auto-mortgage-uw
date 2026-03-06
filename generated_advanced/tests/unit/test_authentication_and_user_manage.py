import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError
from mortgage_underwriting.modules.authentication.services import UserService, AuthService
from mortgage_underwriting.modules.authentication.schemas import UserCreate, UserLogin
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.modules.authentication.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    UserNotFoundError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestUserService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def user_create_schema(self, valid_user_payload):
        return UserCreate(**valid_user_payload)

    @pytest.mark.asyncio
    async def test_create_user_success_hashes_password(self, mock_db, user_create_schema):
        """
        Test that user creation hashes the password and encrypts PII (SIN/DOB).
        """
        # Mock the security functions
        with patch('mortgage_underwriting.modules.authentication.services.hash_password') as mock_hash, \
             patch('mortgage_underwriting.modules.authentication.services.encrypt_pii') as mock_encrypt:
            
            mock_hash.return_value = "hashed_secret"
            mock_encrypt.side_effect = lambda x: f"enc_{x}"

            service = UserService(mock_db)
            user = await service.create(user_create_schema)

            # Verify password was hashed
            assert user.hashed_password == "hashed_secret"
            mock_hash.assert_called_once_with("SecurePass123!")

            # Verify PII was encrypted (PIPEDA Compliance)
            assert user.sin_encrypted == "enc_123456789"
            assert user.dob_encrypted == "enc_1980-01-01"
            assert mock_encrypt.call_count == 2

            # Verify DB interaction
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once_with(user)

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username_raises_error(self, mock_db, user_create_schema):
        """
        Test that creating a duplicate user raises UserAlreadyExistsError.
        """
        # Simulate database integrity error (e.g., unique constraint violation)
        mock_db.commit.side_effect = IntegrityError("INSERT failed", {}, None)

        service = UserService(mock_db)
        
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await service.create(user_create_schema)
        
        assert "already exists" in str(exc_info.value).lower()
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, mock_db):
        """
        Test retrieving a user by ID.
        """
        # Mock the result of the scalar query
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.username = "test_user"
        
        # Setup the mock execution chain for SQLAlchemy 2.0 style select
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        service = UserService(mock_db)
        result = await service.get_by_id(1)

        assert result is not None
        assert result.username == "test_user"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, mock_db):
        """
        Test retrieving a non-existent user raises UserNotFoundError.
        """
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = UserService(mock_db)

        with pytest.raises(UserNotFoundError):
            await service.get_by_id(999)


@pytest.mark.unit
class TestAuthService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.username = "jdoe"
        user.hashed_password = "hashed_correct_password"
        user.is_active = True
        return user

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db, mock_user):
        """
        Test successful authentication with correct credentials.
        """
        # Mock User Service dependency
        with patch('mortgage_underwriting.modules.authentication.services.UserService') as MockUserService:
            user_service_instance = MockUserService.return_value
            user_service_instance.get_by_username = AsyncMock(return_value=mock_user)

            with patch('mortgage_underwriting.modules.authentication.services.verify_password') as mock_verify:
                mock_verify.return_value = True

                auth_service = AuthService(mock_db)
                result = await auth_service.authenticate("jdoe", "correct_password")

                assert result == mock_user
                mock_verify.assert_called_once_with("correct_password", "hashed_correct_password")

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db, mock_user):
        """
        Test authentication fails with wrong password.
        """
        with patch('mortgage_underwriting.modules.authentication.services.UserService') as MockUserService:
            user_service_instance = MockUserService.return_value
            user_service_instance.get_by_username = AsyncMock(return_value=mock_user)

            with patch('mortgage_underwriting.modules.authentication.services.verify_password') as mock_verify:
                mock_verify.return_value = False

                auth_service = AuthService(mock_db)
                
                with pytest.raises(InvalidCredentialsError):
                    await auth_service.authenticate("jdoe", "wrong_password")

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        """
        Test authentication fails when user does not exist.
        """
        with patch('mortgage_underwriting.modules.authentication.services.UserService') as MockUserService:
            user_service_instance = MockUserService.return_value
            user_service_instance.get_by_username = AsyncMock(side_effect=UserNotFoundError())

            auth_service = AuthService(mock_db)

            with pytest.raises(InvalidCredentialsError):
                await auth_service.authenticate("ghost", "password")

    @pytest.mark.asyncio
    async def test_create_token_generates_jwt(self, mock_user):
        """
        Test that a JWT token is generated successfully.
        """
        auth_service = AuthService(AsyncMock())
        
        # Mock the token creation logic if external, otherwise just test structure
        with patch('mortgage_underwriting.modules.authentication.services.create_access_token') as mock_create_token:
            mock_create_token.return_value = "fake_jwt_token"
            
            token = auth_service.create_token(mock_user)
            
            assert token == "fake_jwt_token"
            # Ensure data includes user ID and role for authorization
            mock_create_token.assert_called_once_with(data={"sub": str(mock_user.id), "role": mock_user.role})