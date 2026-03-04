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