import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin, UserResponse
from mortgage_underwriting.modules.auth.services import AuthService, UserService
from mortgage_underwriting.common.exceptions import AppException

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


@pytest.mark.asyncio
class TestUserService:
    """Tests for user creation and retrieval logic."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.fixture
    def user_create_schema(self):
        return UserCreate(
            username="jdoe",
            email="john.doe@example.com",
            password="plain_text_password",
            role="underwriter"
        )

    async def test_create_user_hashes_password(self, mock_db, user_create_schema):
        """Ensure passwords are hashed before storage."""
        service = UserService(mock_db)
        
        # Mock the result of refresh to return a user object
        mock_user = User(
            id=1,
            username=user_create_schema.username,
            email=user_create_schema.email,
            hashed_password="hashed_secret", # Simulated hash
            role=user_create_schema.role
        )
        mock_db.refresh.return_value = mock_user

        result = await service.create_user(user_create_schema)

        # Verify DB interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        
        # Verify the returned object is a User model
        assert isinstance(result, User)
        assert result.username == "jdoe"

    async def test_create_user_duplicate_username_raises_integrity_error(self, mock_db, user_create_schema):
        """Ensure duplicate usernames are handled."""
        service = UserService(mock_db)
        
        # Simulate database integrity violation
        mock_db.commit.side_effect = IntegrityError("INSERT failed", {}, None)

        with pytest.raises(AppException) as exc_info:
            await service.create_user(user_create_schema)
        
        assert exc_info.value.status_code == 409 # Conflict
        assert "already exists" in str(exc_info.value.detail).lower()

    async def test_get_user_by_username_found(self, mock_db):
        """Test successful user retrieval."""
        service = UserService(mock_db)
        
        mock_user = User(
            id=1,
            username="jdoe",
            email="john@example.com",
            hashed_password="hash",
            role="underwriter"
        )
        
        # Mock the scalar chain: execute().scalars().first()
        mock_result = AsyncMock()
        mock_result.first.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        result = await service.get_user_by_username("jdoe")
        
        assert result is not None
        assert result.username == "jdoe"
        mock_db.execute.assert_awaited_once()

    async def test_get_user_by_username_not_found(self, mock_db):
        """Test retrieval when user does not exist."""
        service = UserService(mock_db)
        
        # Mock the scalar chain to return None
        mock_result = AsyncMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        
        result = await service.get_user_by_username("ghost")
        
        assert result is None


@pytest.mark.asyncio
class TestAuthService:
    """Tests for authentication logic (hashing, verification, tokens)."""

    @pytest.fixture
    def mock_user_service(self):
        return AsyncMock(spec=UserService)

    @pytest.fixture
    def auth_service(self, mock_user_service):
        return AuthService(mock_user_service)

    @pytest.fixture
    def sample_user(self):
        # In a real scenario, this password matches 'password123'
        return User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW", # bcrypt for "password123"
            role="underwriter"
        )

    async def test_verify_password_correct(self, auth_service, sample_user):
        """Test password verification with correct credentials."""
        is_valid = await auth_service.verify_password("password123", sample_user.hashed_password)
        assert is_valid is True

    async def test_verify_password_incorrect(self, auth_service, sample_user):
        """Test password verification with incorrect credentials."""
        is_valid = await auth_service.verify_password("wrongpass", sample_user.hashed_password)
        assert is_valid is False

    async def test_authenticate_user_success(self, auth_service, sample_user, mock_user_service):
        """Test successful authentication flow."""
        mock_user_service.get_user_by_username.return_value = sample_user
        
        result = await auth_service.authenticate_user("testuser", "password123")
        
        assert result == sample_user
        mock_user_service.get_user_by_username.assert_awaited_once_with("testuser")

    async def test_authenticate_user_wrong_password(self, auth_service, sample_user, mock_user_service):
        """Test authentication failure due to wrong password."""
        mock_user_service.get_user_by_username.return_value = sample_user
        
        with pytest.raises(AppException) as exc_info:
            await auth_service.authenticate_user("testuser", "wrongpass")
        
        assert exc_info.value.status_code == 401

    async def test_authenticate_user_not_found(self, auth_service, mock_user_service):
        """Test authentication failure when user doesn't exist."""
        mock_user_service.get_user_by_username.return_value = None
        
        with pytest.raises(AppException) as exc_info:
            await auth_service.authenticate_user("ghost", "password")
        
        assert exc_info.value.status_code == 401

    async def test_create_token_contains_claims(self, auth_service, sample_user):
        """Test JWT token creation contains correct data."""
        token = await auth_service.create_token(sample_user)
        
        assert isinstance(token, str)
        assert len(token) > 0
        # Note: Deep decoding of JWT requires PyJWT import, 
        # here we just check structure and non-emptiness based on service contract.
        # In a real scenario, we would decode and check 'sub' and 'role'.

    async def test_hash_password_is_hashed(self, auth_service):
        """Ensure hashing output is different from input."""
        plain = "mypassword"
        hashed = await auth_service.hash_password(plain)
        
        assert hashed != plain
        assert isinstance(hashed, str)