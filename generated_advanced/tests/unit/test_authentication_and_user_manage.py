import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.authentication.services import AuthService
from mortgage_underwriting.modules.authentication.schemas import UserCreate, UserLogin, UserResponse
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestAuthService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_hash_password(self):
        """Test that password hashing returns a string different from input."""
        plain_password = "mypassword"
        hashed = await AuthService._hash_password(plain_password)
        
        assert isinstance(hashed, str)
        assert hashed != plain_password
        # Bcrypt hashes usually start with $2b$
        assert hashed.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_verify_password_success(self):
        """Test successful password verification."""
        plain = "mypassword"
        hashed = await AuthService._hash_password(plain)
        result = await AuthService._verify_password(plain, hashed)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_password_failure(self):
        """Test password verification failure."""
        plain = "mypassword"
        wrong = "wrongpassword"
        hashed = await AuthService._hash_password(plain)
        result = await AuthService._verify_password(wrong, hashed)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_db, valid_user_payload):
        """Test successful user creation with encryption and hashing."""
        # Mock the return value of a potential duplicate check
        mock_db.scalar.return_value = None

        service = AuthService(mock_db)
        user_schema = UserCreate(**valid_user_payload)

        # Mock the encryption function
        with patch("mortgage_underwriting.modules.authentication.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "encrypted_sin_value"
            
            result = await service.create_user(user_schema)

            # Verify DB interactions
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once()

            # Verify PII was encrypted
            mock_encrypt.assert_called_once_with(valid_user_payload["sin"])

            # Verify Password was hashed (check result object)
            # Note: In a real unit test we might inspect the object passed to db.add
            # Here we assume the result returned is the DB object
            assert result.sin == "encrypted_sin_value"
            assert result.hashed_password != "SecurePassword123!"

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, mock_db, valid_user_payload):
        """Test that creating a user with an existing username raises an error."""
        # Simulate existing user
        mock_db.scalar.return_value = MagicMock() # Truthy value indicates exists

        service = AuthService(mock_db)
        user_schema = UserCreate(**valid_user_payload)

        with pytest.raises(AppException) as exc_info:
            await service.create_user(user_schema)

        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail).lower()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db):
        """Test successful authentication returning a user."""
        # Mock user found in DB
        fake_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password=await AuthService._hash_password("password123"),
            role="applicant"
        )
        mock_db.scalar.return_value = fake_user

        service = AuthService(mock_db)
        credentials = UserLogin(username="testuser", password="password123")

        result = await service.authenticate_user(credentials)

        assert result is not None
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        """Test authentication failure when user does not exist."""
        mock_db.scalar.return_value = None

        service = AuthService(mock_db)
        credentials = UserLogin(username="ghost", password="password123")

        with pytest.raises(AppException) as exc_info:
            await service.authenticate_user(credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db):
        """Test authentication failure with wrong password."""
        fake_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password=await AuthService._hash_password("correct_password"),
            role="applicant"
        )
        mock_db.scalar.return_value = fake_user

        service = AuthService(mock_db)
        credentials = UserLogin(username="testuser", password="wrong_password")

        with pytest.raises(AppException) as exc_info:
            await service.authenticate_user(credentials)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_create_token(self):
        """Test JWT token generation."""
        fake_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="hash",
            role="applicant"
        )
        
        token = await AuthService.create_token(fake_user)
        
        assert isinstance(token, str)
        assert len(token) > 20 # Basic sanity check for JWT length
        # Decode and check subject (optional, but good for coverage)
        # Skipping deep decode to avoid importing jwt in unit test unless necessary

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mock_db):
        """Test retrieving a user by ID."""
        fake_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="hash",
            sin="encrypted",
            annual_income=Decimal("50000.00"),
            role="applicant"
        )
        mock_db.get.return_value = fake_user

        service = AuthService(mock_db)
        result = await service.get_user_by_id(1)

        assert result.username == "testuser"
        # Ensure we aren't returning the hashed password in a generic get
        # (Depends on service implementation, usually we use schemas for output)