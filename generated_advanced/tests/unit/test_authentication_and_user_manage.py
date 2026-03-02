import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

# Import paths based on project conventions
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin, UserResponse, TokenResponse
from mortgage_underwriting.modules.auth.services import AuthService
from mortgage_underwriting.modules.auth.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    PIPEDAComplianceException
)

@pytest.mark.unit
class TestAuthService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return AuthService(mock_db)

    @pytest.mark.asyncio
    async def test_hash_password(self, service):
        plain_password = "MySecretPass123"
        hashed = await service._hash_password(plain_password)
        
        assert hashed is not None
        assert hashed != plain_password
        # Verify bcrypt hash format (starts with $2b$)
        assert hashed.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_verify_password_success(self, service):
        plain = "MySecretPass123"
        hashed = await service._hash_password(plain)
        
        result = await service._verify_password(plain, hashed)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_password_failure(self, service):
        plain = "MySecretPass123"
        wrong = "WrongPassword"
        hashed = await service._hash_password(plain)
        
        result = await service._verify_password(wrong, hashed)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_user_success(self, service, mock_db, valid_user_payload):
        # Arrange
        user_schema = UserCreate(**valid_user_payload)
        
        # Mock DB behavior for unique check (user doesn't exist)
        mock_db.scalar.return_value = None
        
        # Act
        result = await service.create_user(user_schema)
        
        # Assert
        assert isinstance(result, User)
        assert result.username == user_schema.username
        assert result.sin_hash != user_schema.sin # PIPEDA: SIN must be hashed
        assert result.sin_hash.startswith("sha256:") or len(result.sin_hash) == 64 # Assuming SHA256 hash
        assert result.hashed_password.startswith("$2b$")
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, service, mock_db, valid_user_payload):
        # Arrange
        user_schema = UserCreate(**valid_user_payload)
        existing_user = User(id=1, username=user_schema.username)
        mock_db.scalar.return_value = existing_user
        
        # Act & Assert
        with pytest.raises(UserAlreadyExistsException):
            await service.create_user(user_schema)
        
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, service, mock_db, valid_user_payload):
        # Arrange
        username = valid_user_payload["username"]
        password = valid_user_payload["password"]
        
        # Create a fake user object in DB
        fake_user = User(
            id=1,
            username=username,
            hashed_password=await service._hash_password(password),
            sin_hash="hash",
            annual_income=Decimal("95000.00")
        )
        mock_db.scalar.return_value = fake_user
        
        # Act
        result = await service.authenticate_user(username, password)
        
        # Assert
        assert result == fake_user
        mock_db.scalar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, service, mock_db):
        # Arrange
        mock_db.scalar.return_value = None
        
        # Act & Assert
        with pytest.raises(InvalidCredentialsException):
            await service.authenticate_user("nonexistent", "password")

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, service, mock_db, valid_user_payload):
        # Arrange
        username = valid_user_payload["username"]
        fake_user = User(
            id=1,
            username=username,
            hashed_password=await service._hash_password("correct_pass"),
            sin_hash="hash"
        )
        mock_db.scalar.return_value = fake_user
        
        # Act & Assert
        with pytest.raises(InvalidCredentialsException):
            await service.authenticate_user(username, "wrong_pass")

    @pytest.mark.asyncio
    async def test_create_token(self, service):
        # Arrange
        user = User(id=1, username="testuser", sin_hash="hash")
        
        # Act
        token_data = await service.create_token(user)
        
        # Assert
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        # Decode and check sub (subject) claim matches username
        # Note: In a real test we might decode the JWT, here we check existence
        assert len(token_data["access_token"]) > 20

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, service, mock_db):
        # Arrange
        user = User(id=1, username="testuser", sin_hash="hash", annual_income=Decimal("50000.00"))
        token_data = await service.create_token(user)
        token = token_data["access_token"]
        
        mock_db.scalar.return_value = user
        
        # Act
        result = await service.get_current_user(token)
        
        # Assert
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, service):
        # Act & Assert
        with pytest.raises(InvalidCredentialsException):
            await service.get_current_user("invalid.token.here")