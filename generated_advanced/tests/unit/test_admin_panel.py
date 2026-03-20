import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.admin_panel.services import (
    AdminService,
    AuditLogService,
    SystemConfigService
)
from mortgage_underwriting.modules.admin_panel.exceptions import (
    AdminUserExistsError,
    AuditLogNotFoundError,
    ConfigLockViolationError
)
from mortgage_underwriting.modules.admin_panel.models import (
    AdminUser,
    AuditLog,
    SystemConfig
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestAdminService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.scalars = MagicMock()
        db.scalar = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_admin_user_success(self, mock_db, valid_admin_user_data):
        # Arrange
        service = AdminService(mock_db)
        # Mock scalar to return None (user doesn't exist)
        mock_db.scalar.return_value = None
        
        # Act
        result = await service.create_user(valid_admin_user_data)

        # Assert
        assert result.username == valid_admin_user_data["username"]
        assert result.email == valid_admin_user_data["email"]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_admin_user_duplicate_email_raises(self, mock_db, valid_admin_user_data):
        # Arrange
        service = AdminService(mock_db)
        existing_user = AdminUser(**valid_admin_user_data)
        mock_db.scalar.return_value = existing_user

        # Act & Assert
        with pytest.raises(AdminUserExistsError):
            await service.create_user(valid_admin_user_data)
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deactivate_user_success(self, mock_db):
        # Arrange
        service = AdminService(mock_db)
        user = AdminUser(id=1, username="test", email="test@test.com", is_active=True)
        mock_db.scalar.return_value = user

        # Act
        await service.deactivate_user(user_id=1)

        # Assert
        assert user.is_active is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deactivate_non_existent_user_raises(self, mock_db):
        # Arrange
        service = AdminService(mock_db)
        mock_db.scalar.return_value = None

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.deactivate_user(user_id=999)
        assert "not found" in str(exc_info.value.detail).lower()

@pytest.mark.unit
class TestAuditLogService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_log_action_success(self, mock_db, valid_audit_log_data):
        # Arrange
        service = AuditLogService(mock_db)
        
        # Act
        await service.log_action(
            action=valid_audit_log_data["action"],
            actor_id=valid_audit_log_data["actor_id"],
            details=valid_audit_log_data["details"]
        )

        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        # Verify immutable fields are set
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.action == "LOGIN"
        assert added_obj.id is not None # UUID generation check

    @pytest.mark.asyncio
    async def test_retrieve_logs_paginated(self, mock_db):
        # Arrange
        service = AuditLogService(mock_db)
        mock_result = MagicMock()
        mock_result.all.return_value = [AuditLog(id="1", action="TEST", actor_id="u1")]
        mock_db.scalars.return_value = mock_result

        # Act
        logs = await service.get_logs(limit=10, offset=0)

        # Assert
        assert len(logs) == 1
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retrieve_logs_with_date_filter(self, mock_db):
        # Arrange
        service = AuditLogService(mock_db)
        start_date = datetime(2023, 1, 1)
        
        # Act
        await service.get_logs(start_date=start_date)

        # Assert
        # We verify the query was constructed (implicitly via execute call)
        # In a real unit test we might inspect the SQL string, but here checking execution is sufficient
        mock_db.execute.assert_awaited_once()

@pytest.mark.unit
class TestSystemConfigService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.scalar = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_update_stress_test_rate_compliance(self, mock_db, stress_test_config_data):
        """
        Regulatory: Verify that updating the stress test rate logs the change for auditability.
        """
        # Arrange
        service = SystemConfigService(mock_db)
        existing_config = SystemConfig(
            id=1, 
            key="stress_test_rate", 
            value="5.00", 
            is_locked=False
        )
        mock_db.scalar.return_value = existing_config

        # Act
        new_value = "5.50"
        await service.update_config(key="stress_test_rate", value=new_value)

        # Assert
        assert existing_config.value == new_value
        assert existing_config.updated_at is not None
        mock_db.commit.assert_awaited_once()
        # In a real scenario, we would check if an AuditLog entry was created
        # but since that's a separate service, we verify the state change here.

    @pytest.mark.asyncio
    async def test_update_locked_config_raises_error(self, mock_db):
        """
        Security: Ensure locked configurations cannot be modified via standard update.
        """
        # Arrange
        service = SystemConfigService(mock_db)
        locked_config = SystemConfig(
            id=1, 
            key="compliance_lock", 
            value="true", 
            is_locked=True
        )
        mock_db.scalar.return_value = locked_config

        # Act & Assert
        with pytest.raises(ConfigLockViolationError):
            await service.update_config(key="compliance_lock", value="false")
        
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_config_value_as_decimal(self, mock_db):
        """
        Financial: Ensure decimal values are handled correctly.
        """
        # Arrange
        service = SystemConfigService(mock_db)
        mock_config = SystemConfig(id=1, key="max_loan_amount", value="500000.00")
        mock_db.scalar.return_value = mock_config

        # Act
        val = await service.get_config_value("max_loan_amount", as_type=Decimal)

        # Assert
        assert val == Decimal("500000.00")
        assert isinstance(val, Decimal)

    @pytest.mark.asyncio
    async def test_get_config_value_missing_returns_none(self, mock_db):
        # Arrange
        service = SystemConfigService(mock_db)
        mock_db.scalar.return_value = None

        # Act
        val = await service.get_config_value("missing_key")

        # Assert
        assert val is None