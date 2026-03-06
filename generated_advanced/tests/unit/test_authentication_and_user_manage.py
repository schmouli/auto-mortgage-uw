```python
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from mortgage_underwriting.modules.auth_user.models import User
from mortgage_underwriting.modules.auth_user.schemas import UserRegister, UserLogin, UserResponse
from mortgage_underwriting.modules.auth_user.services import AuthService
from mortgage_underwriting.common.exceptions import AppException

# Import the module under test
from mortgage_underwriting.modules.auth_user.services import AuthService

@pytest.mark.unit
class TestAuthService:

    @pytest.mark.asyncio
    async def test_register_user_success(self, mock_db_session, user_payload, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        schema = UserRegister(**user_payload)

        # Act
        result = await service.register_user(schema)

        # Assert
        assert isinstance(result, User)
        assert result.email == user_payload["email"]
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_security_utils["hash"].assert_called_once_with(user_payload["password"])
        
        # PIPEDA Compliance: Ensure SIN is encrypted, not stored in plain text
        mock_security_utils["encrypt"].assert_called_once_with(user_payload["sin"])
        assert result.encrypted_sin == "encrypted_hash"

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, mock_db_session, user_payload, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        schema = UserRegister(**user_payload)
        
        # Mock DB returning an existing user (simulating unique constraint violation)
        mock_db_session.scalar.return_value = User(id=1, email=user_payload["email"])

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.register_user(schema)
        
        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db_session, mock_user_model, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        mock_db_session.scalar.return_value = mock_user_model
        
        login_schema = UserLogin(email="underwriter@example.com", password="SecurePass123!")

        # Act
        token = await service.authenticate_user(login_schema)

        # Assert
        assert token == "mock_jwt_token"
        mock_security_utils["verify"].assert_called_once_with("SecurePass123!", "hashed_SecurePass123!")

    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_password(self, mock_db_session, mock_user_model, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        mock_db_session.scalar.return_value = mock_user_model
        mock_security_utils["verify"].return_value = False # Wrong password
        
        login_schema = UserLogin(email="underwriter@example.com", password="WrongPass")

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.authenticate_user(login_schema)
        
        assert exc_info.value.status_code == 401
        assert "invalid credentials" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db_session, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        mock_db_session.scalar.return_value = None # User not found
        
        login_schema = UserLogin(email="ghost@example.com", password="DoesntMatter")

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.authenticate_user(login_schema)
        
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mock_db_session, mock_user_model):
        # Arrange
        service = AuthService(mock_db_session)
        mock_db_session.get.return_value = mock_user_model

        # Act
        user = await service.get_user_by_id(1)

        # Assert
        assert user is not None
        assert user.email == mock_user_model.email
        mock_db_session.get.assert_called_once_with(User, 1)

    @pytest.mark.asyncio
    async def test_pii_data_minimization(self, mock_db_session, user_payload, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        schema = UserRegister(**user_payload)

        # Act
        user = await service.register_user(schema)

        # Assert - PIPEDA: Ensure raw SIN is NOT on the model
        assert not hasattr(user, 'sin') or getattr(user, 'sin', None) is None
        assert hasattr(user, 'encrypted_sin')
        # Ensure raw password is NOT on the model
        assert not hasattr(user, 'password')
        assert hasattr(user, 'hashed_password')

    @pytest.mark.asyncio
    async def test_fintrac_audit_fields(self, mock_db_session, user_payload, mock_security_utils):
        # Arrange
        service = AuthService(mock_db_session)
        schema = UserRegister(**user_payload)

        # Act
        user = await service.register_user(schema)

        # Assert - FINTRAC: Audit trails must exist
        # Note: In a real scenario, these are often defaults in the DB or model __init__
        # Here we check the service logic handles or preserves them
        assert hasattr(user, 'created_at')
        assert hasattr(user, 'updated_at')
```