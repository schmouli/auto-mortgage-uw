import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.admin_panel.models import AdminUser, AuditLog, SystemConfig
from mortgage_underwriting.modules.admin_panel.schemas import AdminUserCreate, SystemConfigUpdate
from mortgage_underwriting.modules.admin_panel.services import AdminService
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.unit
class TestAdminService:
    """
    Unit tests for AdminPanel business logic.
    Focuses on user management, audit log retrieval, and system configuration.
    """

    @pytest.mark.asyncio
    async def test_create_admin_user_success(self, mock_db_session, valid_admin_user_dict):
        # Arrange
        payload = AdminUserCreate(**valid_admin_user_dict)
        
        # Mock the result of a potential duplicate check (return None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = AdminService(mock_db_session)

        # Act
        result = await service.create_user(payload)

        # Assert
        assert result.username == payload.username
        assert result.email == payload.email
        assert result.role == payload.role
        # Ensure password is not returned in plain text (PIPEDA compliance)
        assert "password" not in result.model_dump(mode="json")
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_admin_user_duplicate_email(self, mock_db_session, valid_admin_user_dict):
        # Arrange
        payload = AdminUserCreate(**valid_admin_user_dict)
        
        # Mock existing user found
        existing_user = AdminUser(id=1, username="existing", email=payload.email, role="admin")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute.return_value = mock_result

        service = AdminService(mock_db_session)

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_user(payload)
        
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_system_config_rate_validation(self, mock_db_session):
        # Arrange
        config_key = "qualifying_rate_floor"
        new_value = Decimal("5.50")
        
        # Mock fetching existing config
        mock_config = SystemConfig(id=1, key=config_key, value="5.25")
        mock_db_session.scalar.return_value = mock_config

        service = AdminService(mock_db_session)

        # Act
        updated_config = await service.update_config(config_key, str(new_value))

        # Assert
        assert updated_config.value == str(new_value)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_system_config_invalid_rate_type(self, mock_db_session):
        # Arrange
        config_key = "qualifying_rate_floor"
        invalid_value = "not_a_number"

        service = AdminService(mock_db_session)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.update_config(config_key, invalid_value)
        
        assert "Invalid value type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_audit_logs_paginated(self, mock_db_session):
        # Arrange
        page = 1
        limit = 10
        
        # Mock the scalars().all() chain
        mock_scalars = AsyncMock()
        mock_scalars.all.return_value = [
            AuditLog(id=1, action="CREATE_USER", actor_id=1, details="user_123"),
            AuditLog(id=2, action="UPDATE_RATE", actor_id=1, details="rate_5.5")
        ]
        
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_execute_result

        service = AdminService(mock_db_session)

        # Act
        logs = await service.get_audit_logs(page=page, limit=limit)

        # Assert
        assert len(logs) == 2
        assert logs[0].action == "CREATE_USER"
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_audit_entry_success(self, mock_db_session):
        # Arrange
        action = "LOGIN"
        actor_id = 1
        details = {"ip": "127.0.0.1"}

        service = AdminService(mock_db_session)

        # Act
        await service.log_action(action, actor_id, details)

        # Assert
        mock_db_session.add.assert_called_once()
        # Verify the object passed to add is an AuditLog
        call_args = mock_db_session.add.call_args[0][0]
        assert isinstance(call_args, AuditLog)
        assert call_args.action == action
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_user_cascade_soft_delete(self, mock_db_session):
        # Arrange
        user_id = 1
        mock_user = AdminUser(id=user_id, username="old_admin", email="old@test.com", role="admin")
        mock_db_session.scalar.return_value = mock_user

        service = AdminService(mock_db_session)

        # Act
        await service.delete_user(user_id)

        # Assert
        # Assuming soft delete is implemented via is_active flag or similar
        # If hard delete:
        mock_db_session.delete.assert_called_once_with(mock_user)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_financial_summary_decimals(self, mock_db_session):
        # Arrange
        # Mocking a hypothetical summary function that aggregates financial data
        mock_result = MagicMock()
        mock_result.one.return_value = (Decimal("1000000.00"), Decimal("500000.00"))
        mock_db_session.execute.return_value = mock_result

        service = AdminService(mock_db_session)

        # Act
        total_loans, total_value = await service.get_portfolio_summary()

        # Assert
        assert isinstance(total_loans, Decimal)
        assert total_loans == Decimal("1000000.00")
        # Ensure no float conversion occurred
        assert type(total_loans) is Decimal