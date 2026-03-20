import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.infrastructure.services import InfrastructureService
from mortgage_underwriting.modules.infrastructure.models import SystemHealth, DeploymentRecord
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestInfrastructureService:
    
    @pytest.fixture
    def service(self):
        # Service doesn't hold state usually, but instantiated per test for clarity
        return InfrastructureService()

    @pytest.mark.asyncio
    async def test_check_database_health_success(self, service):
        """
        Test that database health check returns True when connection is successful.
        """
        mock_db = AsyncMock()
        # Mock the execute call to return a result
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result

        result = await service.check_database_health(mock_db)
        
        assert result is True
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_database_health_failure(self, service):
        """
        Test that database health check returns False when connection fails.
        """
        mock_db = AsyncMock()
        mock_db.execute.side_effect = SQLAlchemyError("Connection failed")

        result = await service.check_database_health(mock_db)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_record_deployment_success(self, service, mock_deployment_data):
        """
        Test successful recording of a deployment event.
        Ensures audit fields are populated.
        """
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock the refresh to populate the object
        def mock_refresh(obj):
            obj.id = 1
            obj.created_at = datetime.utcnow()
        
        mock_db.refresh.side_effect = mock_refresh

        result = await service.record_deployment(mock_db, mock_deployment_data)

        assert isinstance(result, DeploymentRecord)
        assert result.version == mock_deployment_data["version"]
        assert result.environment == mock_deployment_data["environment"]
        assert result.resource_cost == mock_deployment_data["resource_cost"]
        assert result.id is not None
        assert result.created_at is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_deployment_invalid_cost(self, service, mock_deployment_data):
        """
        Test that recording deployment with negative cost raises ValueError.
        Financial validation: Cost cannot be negative.
        """
        mock_db = AsyncMock()
        invalid_data = mock_deployment_data.copy()
        invalid_data["resource_cost"] = Decimal("-50.00")

        with pytest.raises(ValueError) as excinfo:
            await service.record_deployment(mock_db, invalid_data)
        
        assert "Resource cost cannot be negative" in str(excinfo.value)
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_deployment_missing_version(self, service, mock_deployment_data):
        """
        Test that missing version raises appropriate error.
        """
        mock_db = AsyncMock()
        invalid_data = mock_deployment_data.copy()
        del invalid_data["version"]

        with pytest.raises(KeyError):
            await service.record_deployment(mock_db, invalid_data)

    @pytest.mark.asyncio
    async def test_get_system_status_aggregates_correctly(self, service):
        """
        Test that get_system_status aggregates multiple health checks.
        """
        mock_db = AsyncMock()
        
        # Mock the service methods
        with patch.object(service, 'check_database_health', return_value=True), \
             patch.object(service, 'check_external_api_health', return_value=True):
            
            status = await service.get_system_status(mock_db)
            
            assert status["overall_status"] == "healthy"
            assert status["database"] is True
            assert status["external_api"] is True

    @pytest.mark.asyncio
    async def test_get_system_status_degraded_if_one_fails(self, service):
        """
        Test that overall status is 'degraded' if one component fails.
        """
        mock_db = AsyncMock()
        
        with patch.object(service, 'check_database_health', return_value=True), \
             patch.object(service, 'check_external_api_health', return_value=False):
            
            status = await service.get_system_status(mock_db)
            
            assert status["overall_status"] == "degraded"
            assert "database" in status

    @pytest.mark.asyncio
    async def test_log_infrastructure_event_sanitizes_secrets(self, service):
        """
        Test that logging infrastructure events does not leak secrets.
        """
        mock_db = AsyncMock()
        mock_logger = MagicMock()
        
        # Payload containing a fake secret
        payload = {
            "event": "config_update",
            "details": {"api_key": "super_secret_key_123"}
        }

        await service.log_infrastructure_event(mock_db, payload, logger=mock_logger)
        
        # Verify the logger was called
        mock_logger.info.assert_called_once()
        
        # Verify the secret is NOT in the logged message
        call_args = mock_logger.info.call_args[0][0]
        assert "super_secret_key_123" not in call_args
        assert "REDACTED" in call_args or "api_key" not in call_args