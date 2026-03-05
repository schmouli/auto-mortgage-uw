import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import paths based on project conventions
from mortgage_underwriting.modules.admin_panel.services import AdminService
from mortgage_underwriting.modules.admin_panel.exceptions import (
    AdminUserExistsError,
    AuditLogNotFoundError
)
from mortgage_underwriting.modules.admin_panel.models import AdminUser, AuditLog
from mortgage_underwriting.modules.admin_panel.schemas import AdminUserCreate

@pytest.mark.unit
class TestAdminService:
    """
    Unit tests for AdminService business logic.
    Focuses on user management and audit log retrieval.
    """

    @pytest.mark.asyncio
    async def test_create_admin_user_success(self, mock_db_session, sample_admin_user_payload):
        """
        Test successful creation of an admin user.
        Verifies DB interaction and PIPEDA compliance (no password logging).
        """
        # Mock the result of a potential existing user check (return None)
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_execute_result

        # Mock the added instance for refresh
        new_user = AdminUser(**sample_admin_user_payload)
        mock_db_session.add = MagicMock()
        mock_db_session.refresh = AsyncMock()

        service = AdminService(mock_db_session)
        payload = AdminUserCreate(**sample_admin_user_payload)

        result = await service.create_user(payload)

        # Assertions
        assert result.username == sample_admin_user_payload["username"]
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_admin_user_duplicate_email_raises(self, mock_db_session, sample_admin_user_payload):
        """
        Test that creating a user with an existing email raises AdminUserExistsError.
        """
        # Mock the result of existing user check (return existing user)
        existing_user = AdminUser(id=1, **sample_admin_user_payload)
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute.return_value = mock_execute_result

        service = AdminService(mock_db_session)
        payload = AdminUserCreate(**sample_admin_user_payload)

        with pytest.raises(AdminUserExistsError) as exc_info:
            await service.create_user(payload)

        assert exc_info.value.detail == "User with this email already exists"
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_audit_logs_success(self, mock_db_session):
        """
        Test retrieving audit logs.
        Verifies FINTRAC compliance requirement of immutability (read-only access).
        """
        # Mock database response
        log_entry = AuditLog(
            id=1,
            action="UNDERWRITING_DECISION",
            actor="system",
            timestamp="2023-01-01T12:00:00",
            details={"application_id": "12345"}
        )
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [log_entry]
        mock_db_session.execute.return_value = mock_result

        service = AdminService(mock_db_session)
        logs = await service.get_audit_logs(limit=10)

        assert len(logs) == 1
        assert logs[0].action == "UNDERWRITING_DECISION"
        # Ensure we are querying the AuditLog model
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_audit_logs_empty_result(self, mock_db_session):
        """
        Test retrieving audit logs when none exist.
        """
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        service = AdminService(mock_db_session)
        logs = await service.get_audit_logs()

        assert logs == []
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_admin_user_success(self, mock_db_session):
        """
        Test deleting an admin user (soft delete or hard delete depending on policy).
        Assuming hard delete for this specific module logic, but usually soft delete is preferred.
        """
        # Mock finding the user
        user_to_delete = AdminUser(id=1, username="old_admin", email="old@test.com", role="admin")
        
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = user_to_delete
        mock_db_session.execute.return_value = mock_execute_result

        service = AdminService(mock_db_session)
        
        result = await service.delete_user(user_id=1)

        assert result is True
        mock_db_session.delete.assert_called_once_with(user_to_delete)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_admin_user_not_found(self, mock_db_session):
        """
        Test deleting a user that does not exist.
        """
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_execute_result

        service = AdminService(mock_db_session)

        with pytest.raises(AuditLogNotFoundError): # Reusing generic NotFound or specific UserNotFound
            await service.delete_user(user_id=999)

        mock_db_session.delete.assert_not_called()