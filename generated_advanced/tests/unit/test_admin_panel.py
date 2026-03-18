```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.admin_panel.services import AdminService
from mortgage_underwriting.modules.admin_panel.models import User, AuditLog
from mortgage_underwriting.modules.admin_panel.exceptions import (
    UserAlreadyExistsError,
    AuditLogImmutableError,
    InvalidRoleError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestAdminService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return AdminService(mock_db)

    @pytest.mark.asyncio
    async def test_create_user_success(self, service, mock_db):
        """Test successful user creation with password hashing."""
        payload = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123",
            "role": "underwriter",
            "sin": "987654321"
        }
        
        # Mock DB checks: user doesn't exist
        mock_db.scalar.return_value = None
        
        result = await service.create_user(payload)
        
        assert result.username == "newuser"
        assert result.email == "new@example.com"
        assert result.role == "underwriter"
        # Verify PIPEDA compliance: SIN is hashed, not stored in plain text
        assert result.sin_hash != "987654321" 
        assert "987654321" not in str(result.sin_hash)
        # Verify password is hashed
        assert result.password_hash != "password123"
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email_raises(self, service, mock_db):
        """Test that creating a user with an existing email raises an error."""
        payload = {
            "username": "newuser",
            "email": "existing@example.com",
            "password": "password123",
            "role": "underwriter",
            "sin": "987654321"
        }
        
        # Simulate existing user found
        existing_user = User(id=1, username="old", email="existing@example.com")
        mock_db.scalar.return_value = existing_user
        
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await service.create_user(payload)
        
        assert "email" in str(exc_info.value).lower()
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_user_invalid_role_raises(self, service, mock_db):
        """Test that creating a user with an invalid role raises ValueError."""
        payload = {
            "username": "hacker",
            "email": "hacker@example.com",
            "password": "password123",
            "role": "super_admin", # Invalid role
            "sin": "000000000"
        }
        
        mock_db.scalar.return_value = None
        
        with pytest.raises(InvalidRoleError):
            await service.create_user(payload)

    @pytest.mark.asyncio
    async def test_get_audit_logs_success(self, service, mock_db):
        """Test retrieving audit logs with pagination."""
        # Mock the result of scalars().all()
        mock_log = AuditLog(
            id=1,
            action="USER_LOGIN",
            entity_type="User",
            entity_id="user-123",
            details={"ip": "127.0.0.1"}
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        mock_db.execute.return_value = mock_result
        
        logs = await service.get_audit_logs(limit=10, offset=0)
        
        assert len(logs) == 1
        assert logs[0].action == "USER_LOGIN"
        assert logs[0].entity_id == "user-123"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_audit_log_fails_immutability(self, service, mock_db):
        """Test FINTRAC compliance: Audit logs cannot be deleted."""
        log_id = 1
        
        # Mock fetching the log
        mock_log = AuditLog(id=log_id, action="TEST", entity_type="Test")
        mock_db.get.return_value = mock_log
        
        with pytest.raises(AuditLogImmutableError) as exc_info:
            await service.delete_audit_log(log_id)
        
        assert "immutable" in str(exc_info.value).lower()
        # Ensure delete was never called on the session
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_user_role_success(self, service, mock_db):
        """Test updating a user's role."""
        user_id = 1
        new_role = "senior_underwriter"
        
        mock_user = User(id=user_id, username="user1", role="underwriter")
        mock_db.get.return_value = mock_user
        
        updated_user = await service.update_user_role(user_id, new_role)
        
        assert updated_user.role == new_role
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(mock_user)

    @pytest.mark.asyncio
    async def test_update_user_role_not_found(self, service, mock_db):
        """Test updating a user that does not exist."""
        mock_db.get.return_value = None
        
        with pytest.raises(AppException) as exc_info:
            await service.update_user_role(999, "admin")
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_user_sin_hashing_algorithm(self, service, mock_db):
        """Verify specific hashing algorithm (SHA256) is used for SIN."""
        payload = {
            "username": "hashcheck",
            "email": "hash@example.com",
            "password": "pass",
            "role": "underwriter",
            "sin": "123456789"
        }
        mock_db.scalar.return_value = None
        
        with patch('mortgage_underwriting.modules.admin_panel.services.hashlib.sha256') as mock_sha:
            # Setup mock return value for the hexdigest
            mock_sha.return_value.hexdigest.return_value = "hashed_sin_123"
            
            await service.create_user(payload)
            
            # Verify sha256 was called with the SIN encoded as bytes
            mock_sha.assert_called_once_with(b"123456789")

    @pytest.mark.asyncio
    async def test_log_action_creates_audit_entry(self, service, mock_db):
        """Test that logging an action creates a record in the DB."""
        await service.log_action(
            user_id="admin-1",
            action="UPDATE_RATE",
            entity_type="Configuration",
            entity_id="rate-1",
            details={"old_rate": "5.0", "new_rate": "5.25"}
        )
        
        mock_db.add.assert_called_once()
        # Verify the object added is an AuditLog
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, AuditLog)
        assert added_obj.action == "UPDATE_RATE"
        mock_db.commit.assert_awaited_once()
```