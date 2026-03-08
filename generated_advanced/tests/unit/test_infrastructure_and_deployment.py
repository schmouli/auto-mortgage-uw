import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from sqlalchemy.exc import SQLAlchemyError

# Import the module under test
from mortgage_underwriting.modules.infrastructure_deployment.services import (
    HealthService,
    ConfigService,
    DeploymentService
)
from mortgage_underwriting.modules.infrastructure_deployment.exceptions import (
    InfrastructureUnavailableError,
    ConfigurationError
)

@pytest.mark.unit
class TestHealthService:
    """
    Unit tests for HealthService logic.
    Verifies system status checks without actual I/O.
    """

    @pytest.mark.asyncio
    async def test_check_database_health_success(self, mock_db_session):
        """
        Test that database health check returns True when DB is responsive.
        """
        # Mock the execution of a simple query (SELECT 1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        mock_db_session.execute.return_value = mock_result

        service = HealthService(mock_db_session)
        is_healthy = await service.check_database_health()

        assert is_healthy is True
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_database_health_failure(self, mock_db_session):
        """
        Test that database health check returns False on connection error.
        """
        mock_db_session.execute.side_effect = SQLAlchemyError("Connection failed")

        service = HealthService(mock_db_session)
        is_healthy = await service.check_database_health()

        assert is_healthy is False
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_redis_health_success(self, mock_redis_client):
        """
        Test that Redis health check returns True when Redis is responsive.
        """
        service = HealthService(mock_db_session, redis_client=mock_redis_client)
        is_healthy = await service.check_redis_health()

        assert is_healthy is True
        mock_redis_client.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_redis_health_failure(self, mock_redis_client):
        """
        Test that Redis health check returns False on error.
        """
        mock_redis_client.ping.side_effect = Exception("Redis timeout")

        service = HealthService(mock_db_session, redis_client=mock_redis_client)
        is_healthy = await service.check_redis_health()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_get_system_status_healthy(self, mock_db_session, mock_redis_client):
        """
        Test aggregation of system status when all components are healthy.
        """
        # Setup mocks
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        mock_db_session.execute.return_value = mock_result

        service = HealthService(mock_db_session, redis_client=mock_redis_client)
        status = await service.get_system_status()

        assert status["status"] == "healthy"
        assert status["components"]["database"] == "up"
        assert status["components"]["redis"] == "up"

    @pytest.mark.asyncio
    async def test_get_system_status_unhealthy_db(self, mock_db_session, mock_redis_client):
        """
        Test aggregation of system status when DB is down.
        """
        mock_db_session.execute.side_effect = SQLAlchemyError("Down")

        service = HealthService(mock_db_session, redis_client=mock_redis_client)
        status = await service.get_system_status()

        assert status["status"] == "unhealthy"
        assert status["components"]["database"] == "down"
        assert status["components"]["redis"] == "up"


@pytest.mark.unit
class TestConfigService:
    """
    Unit tests for ConfigService logic.
    Verifies configuration loading and validation.
    """

    def test_get_required_setting_exists(self, mock_settings):
        """
        Test retrieving a required setting that exists.
        """
        service = ConfigService()
        value = service.get_setting("SECRET_KEY")
        assert value == "test-secret-key"

    def test_get_required_setting_missing_raises(self, mock_settings):
        """
        Test that retrieving a missing required setting raises ConfigurationError.
        """
        service = ConfigService()
        # Delete the attribute to simulate missing env var
        delattr(mock_settings, "SECRET_KEY")
        
        with pytest.raises(ConfigurationError) as exc_info:
            service.get_setting("SECRET_KEY")
        
        assert "Missing required configuration" in str(exc_info.value)

    def test_validate_financial_precision_config(self, mock_settings):
        """
        Test validation of financial precision configuration.
        Ensures Decimal precision is set correctly for monetary values.
        """
        with patch.object(mock_settings, "DECIMAL_PRECISION", "28") as mock_prec:
            service = ConfigService()
            precision = service.get_decimal_precision()
            
            assert isinstance(precision, int)
            assert precision == 28

    def test_mask_sensitive_data_in_logs(self):
        """
        Test PIPEDA compliance: ensuring sensitive keys are masked.
        """
        service = ConfigService()
        log_data = {
            "username": "admin",
            "password": "supersecret123",  # Should be masked
            "api_key": "key-xyz",          # Should be masked
            "timestamp": "2023-01-01"
        }

        masked = service.mask_sensitive_data(log_data)
        
        assert masked["password"] == "*****"
        assert masked["api_key"] == "*****"
        assert masked["username"] == "admin"
        assert masked["timestamp"] == "2023-01-01"


@pytest.mark.unit
class TestDeploymentService:
    """
    Unit tests for DeploymentService logic.
    Verifies migration status and versioning.
    """

    @pytest.mark.asyncio
    async def test_check_migrations_success(self):
        """
        Test successful migration status check.
        """
        mock_alembic = AsyncMock()
        mock_alembic.get_current_head.return_value = "12345"
        mock_alembic.get_current_revision.return_value = "12345"

        service = DeploymentService(alembic_util=mock_alembic)
        is_synced = await service.check_migrations()

        assert is_synced is True

    @pytest.mark.asyncio
    async def test_check_migrations_out_of_sync(self):
        """
        Test migration status check when DB is behind code.
        """
        mock_alembic = AsyncMock()
        mock_alembic.get_current_head.return_value = "67890"
        mock_alembic.get_current_revision.return_value = "12345"

        service = DeploymentService(alembic_util=mock_alembic)
        is_synced = await service.check_migrations()

        assert is_synced is False

    @pytest.mark.asyncio
    async def test_get_application_version(self):
        """
        Test retrieval of application version info.
        """
        service = DeploymentService()
        version = service.get_version()

        assert "version" in version
        assert "build_date" in version
        # Check format validity (basic)
        assert isinstance(version["version"], str)

    @pytest.mark.asyncio
    async def test_register_deployment_event(self, mock_db_session):
        """
        Test logging a deployment event to the database for audit trail.
        """
        service = DeploymentService()
        
        # Mock the model creation
        mock_deployment_log = MagicMock()
        mock_deployment_log.id = 1
        
        with patch("mortgage_underwriting.modules.infrastructure_deployment.services.DeploymentLog", return_value=mock_deployment_log):
            await service.log_deployment(mock_db_session, version="1.0.0", status="success")
            
            mock_db_session.add.assert_called_once_with(mock_deployment_log)
            mock_db_session.commit.assert_awaited_once()