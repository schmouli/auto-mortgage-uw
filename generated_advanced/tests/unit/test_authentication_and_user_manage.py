```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext

from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin, UserResponse
from mortgage_underwriting.modules.auth.services import UserService, AuthService
from mortgage_underwriting.modules.auth.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    InactiveUserError
)

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.scalar = AsyncMock()
    return db

@pytest.fixture
def pwd_context():
    # Real context used for logic verification, but mocked in service tests where appropriate
    return CryptContext(schemes=["bcrypt"], deprecated="auto")

class TestUserService:

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_db, valid_user_payload):
        # Arrange
        user_create = UserCreate(**valid_user_payload)
        service = UserService(mock_db)
        
        # Mock the refresh to return a user object with ID
        mock_user = User(id=1, **user_create.model_dump())
        # Password hashing happens inside service, we just verify the call
        
        # Act
        result = await service.create_user(user_create)

        # Assert
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        
        # Verify password was hashed before storage (logic check)
        # In a real scenario, we check the object passed to add
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.hashed_password != user_create.password
        assert added_obj.username == user_create.username
        assert added_obj.email == user_create.email
        assert added_obj.is_active is True  # Default status

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email_raises_exception(self, mock_db, valid_user_payload):
        # Arrange
        user_create = UserCreate(**valid_user_payload)
        mock_db.commit.side_effect = IntegrityError("INSERT", {}, Exception())
        service = UserService(mock_db)

        # Act & Assert
        with pytest.raises(UserAlreadyExistsError):
            await service.create_user(user_create)
        
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, mock_db):
        # Arrange
        user_id = 1
        expected_user = User(id=user_id, username="test", email="test@test.com", hashed_password="hash")
        mock_db.scalar.return_value = expected_user
        service = UserService(mock_db)

        # Act
        result = await service.get_user_by_id(user_id)

        # Assert
        assert result.id == user_id
        mock_db.scalar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_by_email_success(self, mock_db):
        # Arrange
        email = "test@example.com"
        expected_user = User(id=1, username="test", email=email, hashed_password="hash")
        mock_db.scalar.return_value = expected_user
        service = UserService(mock_db)

        # Act
        result = await service.get_user_by_email(email)

        # Assert
        assert result.email == email
        mock_db.scalar.assert_awaited_once()

class TestAuthService:

    @pytest.mark.asyncio
    async def test_verify_password_success(self, pwd_context):
        # Arrange
        plain_password = "SecretPass123"
        hashed_password = pwd_context.hash(plain_password)
        service = AuthService(AsyncMock()) # DB not needed for pure crypto logic

        # Act
        is_valid = service.verify_password(plain_password, hashed_password)

        # Assert
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_password_failure(self, pwd_context):
        # Arrange
        plain_password = "SecretPass123"
        hashed_password = pwd_context.hash("WrongPass123")
        service = AuthService(AsyncMock())

        # Act
        is_valid = service.verify_password(plain_password, hashed_password)

        # Assert
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db):
        # Arrange
        login_data = UserLogin(email="test@example.com", password="password123")
        user = User(
            id=1, 
            username="test", 
            email=login_data.email, 
            hashed_password=AuthService(AsyncMock()).hash_password(login_data.password),
            is_active=True
        )
        
        # Mock UserService dependency injection or mock the DB call directly
        # Here we mock the DB scalar call which the service uses internally
        mock_db.scalar.return_value = user
        service = AuthService(mock_db)

        # Act
        result = await service.authenticate_user(login_data.email, login_data.password)

        # Assert
        assert result.email == login_data.email
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password_raises(self, mock_db):
        # Arrange
        login_data = UserLogin(email="test@example.com", password="wrongpassword")
        user = User(
            id=1, 
            username="test", 
            email=login_data.email, 
            hashed_password=AuthService(AsyncMock()).hash_password("correctpassword"),
            is_active=True
        )
        mock_db.scalar.return_value = user
        service = AuthService(mock_db)

        # Act & Assert
        with pytest.raises(InvalidCredentialsError):
            await service.authenticate_user(login_data.email, login_data.password)

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found_raises(self, mock_db):
        # Arrange
        mock_db.scalar.return_value = None
        service = AuthService(mock_db)

        # Act & Assert
        with pytest.raises(InvalidCredentialsError):
            await service.authenticate_user("missing@example.com", "password")

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive_raises(self, mock_db):
        # Arrange
        login_data = UserLogin(email="test@example.com", password="password123")
        user = User(
            id=1, 
            username="test", 
            email=login_data.email, 
            hashed_password=AuthService(AsyncMock()).hash_password(login_data.password),
            is_active=False
        )
        mock_db.scalar.return_value = user
        service = AuthService(mock_db)

        # Act & Assert
        with pytest.raises(InvalidCredentialsError): # Or InactiveUserError depending on policy
            await service.authenticate_user(login_data.email, login_data.password)

    @pytest.mark.asyncio
    async def test_create_token_structure(self):
        # Arrange
        user = User(id=1, email="test@test.com", username="test")
        service = AuthService(AsyncMock())

        # Act
        token = service.create_access_token(data={"sub": user.email, "id": user.id})

        # Assert
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # JWT structure: header.payload.signature
```