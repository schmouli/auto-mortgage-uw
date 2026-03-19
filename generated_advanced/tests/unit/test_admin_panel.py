import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from mortgage_underwriting.modules.admin_panel.services import AdminService
from mortgage_underwriting.modules.admin_panel.exceptions import (
    AdminConfigurationError,
    InvalidRateError,
)
from mortgage_underwriting.common.exceptions import AppException

# Import paths assumed based on project structure
# from mortgage_underwriting.modules.admin_panel.models import SystemConfig, AuditLog
# from mortgage_underwriting.modules.admin_panel.schemas import ConfigUpdate, DashboardStats


@pytest.mark.unit
class TestAdminService:
    """
    Unit tests for AdminService business logic.
    Focuses on regulatory compliance (OSFI B-20) and data integrity.
    """

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.scalar_one_or_none = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_success(self, mock_db):
        """
        Test retrieving dashboard statistics.
        Ensures counts are returned correctly.
        """
        # Mock return values for aggregate queries
        mock_db.scalar.side_effect = [150, 100, 50]  # total, approved, pending

        service = AdminService(mock_db)
        stats = await service.get_dashboard_stats()

        assert stats.total_applications == 150
        assert stats.approved_applications == 100
        assert stats.pending_applications == 50
        assert mock_db.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_update_system_config_osfi_compliance(self, mock_db):
        """
        Test updating system configuration.
        Validates OSFI B-20 rule: qualifying rate >= 5.25%.
        """
        # Mock existing config
        mock_config = MagicMock()
        mock_config.min_stress_test_rate = Decimal("5.25")
        mock_db.scalar_one_or_none.return_value = mock_config

        service = AdminService(mock_db)
        
        # Valid update
        payload = {
            "min_stress_test_rate": Decimal("5.50"),
            "max_gds_ratio": Decimal("39.0"),
            "max_tds_ratio": Decimal("44.0")
        }
        
        result = await service.update_system_config(config_id=1, payload=payload)
        
        assert result.min_stress_test_rate == Decimal("5.50")
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_system_config_rate_too_low_raises_osfi_error(self, mock_db):
        """
        Test that updating the stress test rate below OSFI minimum (5.25%) raises an error.
        """
        mock_config = MagicMock()
        mock_config.min_stress_test_rate = Decimal("5.25")
        mock_db.scalar_one_or_none.return_value = mock_config

        service = AdminService(mock_db)
        
        # Invalid update (Rate < 5.25%)
        payload = {
            "min_stress_test_rate": Decimal("4.00"), # Violates OSFI B-20
            "max_gds_ratio": Decimal("39.0"),
            "max_tds_ratio": Decimal("44.0")
        }

        with pytest.raises(InvalidRateError) as exc_info:
            await service.update_system_config(config_id=1, payload=payload)
        
        assert "qualifying rate" in str(exc_info.value).lower()
        assert "5.25" in str(exc_info.value)
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_system_config_gds_exceeds_limit(self, mock_db):
        """
        Test that GDS limit cannot exceed OSFI hard limit of 39%.
        """
        mock_config = MagicMock()
        mock_config.max_gds_ratio = Decimal("39.0")
        mock_db.scalar_one_or_none.return_value = mock_config

        service = AdminService(mock_db)
        
        payload = {
            "min_stress_test_rate": Decimal("5.25"),
            "max_gds_ratio": Decimal("45.00"), # Violates OSFI limit (39%)
            "max_tds_ratio": Decimal("44.0")
        }

        with pytest.raises(AdminConfigurationError) as exc_info:
            await service.update_system_config(config_id=1, payload=payload)
        
        assert "GDS" in str(exc_info.value)
        assert "39%" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_audit_logs_pii_redaction(self, mock_db):
        """
        Test retrieving audit logs.
        Ensures PII (SIN, DOB) is not included in the response (PIPEDA).
        """
        # Mock a log entry that might contain sensitive data in the DB
        mock_log_entry = MagicMock()
        mock_log_entry.id = 1
        mock_log_entry.action = "LOGIN"
        mock_log_entry.actor = "user_123"
        mock_log_entry.details = {"ip": "127.0.0.1"}
        # Simulate that 'sin' field exists on model but service should not return it
        mock_log_entry.sin_hash = "hashed_sin_value" 

        # Setup mock execution result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log_entry]
        mock_db.execute.return_value = mock_result

        service = AdminService(mock_db)
        logs = await service.get_audit_logs(limit=10)

        assert len(logs) == 1
        assert hasattr(logs[0], 'action')
        # Verify the raw model attribute is not exposed in the response schema
        # (Assuming the service maps model to response schema)
        response_dict = logs[0].model_dump() if hasattr(logs[0], 'model_dump') else logs[0].__dict__
        assert 'sin_hash' not in response_dict
        assert 'sin' not in response_dict

    @pytest.mark.asyncio
    async def test_create_admin_user_missing_fields(self, mock_db):
        """
        Test validation when creating an admin user with missing required fields.
        """
        service = AdminService(mock_db)
        
        incomplete_payload = {
            "username": "new_admin",
            # Missing email and role
        }

        with pytest.raises(AppException) as exc_info:
            await service.create_admin_user(incomplete_payload)
        
        assert "validation" in str(exc_info.value).lower()
        mock_db.add.assert_not_called()