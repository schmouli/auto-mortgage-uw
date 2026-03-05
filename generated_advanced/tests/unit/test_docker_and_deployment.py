import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from mortgage_underwriting.modules.docker_deployment.services import (
    HealthService,
    DeploymentService,
    ConfigService
)
from mortgage_underwriting.modules.docker_deployment.models import DeploymentLog
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.unit
class TestHealthService:
    @pytest.mark.asyncio
    async def test_check_database_healthy(self):
        """Test that health check returns True when DB connection succeeds."""
        mock_db = AsyncMock()
        # Simulate successful execution
        mock_db.execute.return_value = AsyncMock(scalar=AsyncMock(return_value=1))

        service = HealthService()
        is_healthy = await service.check_database(mock_db)

        assert is_healthy is True
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_database_unhealthy_on_exception(self):
        """Test that health check returns False when DB connection fails."""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("Connection refused")

        service = HealthService()
        is_healthy = await service.check_database(mock_db)

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_get_system_status_healthy(self):
        """Test aggregate system status when all components are up."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = AsyncMock(scalar=AsyncMock(return_value=1))

        service = HealthService()
        status = await service.get_system_status(mock_db)

        assert status["status"] == "healthy"
        assert status["database"] == "up"
        assert "timestamp" in status


@pytest.mark.unit
class TestDeploymentService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_log_deployment_success(self, mock_db, mock_deployment_payload):
        """Test successful logging of a deployment event."""
        service = DeploymentService(mock_db)
        
        result = await service.log_deployment_event(mock_deployment_payload)

        assert isinstance(result, DeploymentLog)
        assert result.version == mock_deployment_payload["version"]
        assert result.git_commit_sha == mock_deployment_payload["git_commit_sha"]
        assert result.status == mock_deployment_payload["status"]
        
        # Verify Audit fields
        assert result.created_at is not None
        assert result.id is not None

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_log_deployment_missing_version_raises(self, mock_db):
        """Test that missing required version field raises validation error."""
        invalid_payload = {
            "environment": "test",
            "deployed_by": "user"
        }
        service = DeploymentService(mock_db)

        with pytest.raises(ValueError) as excinfo:
            await service.log_deployment_event(invalid_payload)
        
        assert "version" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_log_deployment_persistence_failure(self, mock_db, mock_deployment_payload):
        """Test handling of database commit failure during deployment logging."""
        mock_db.commit.side_effect = Exception("Database write failed")
        service = DeploymentService(mock_db)

        with pytest.raises(AppException) as excinfo:
            await service.log_deployment_event(mock_deployment_payload)
        
        assert excinfo.value.error_code == "DEPLOYMENT_LOG_FAILED"
        mock_db.add.assert_called_once()


@pytest.mark.unit
class TestConfigService:
    @pytest.mark.asyncio
    async def test_validate_config_success(self, mock_env_vars):
        """Test configuration validation when all env vars are present."""
        service = ConfigService()
        # Mocking os.environ access indirectly via the service logic
        with patch.dict('os.environ', {
            'DATABASE_URL': 'sqlite://', 
            'SECRET_KEY': 'secret', 
            'ENVIRONMENT': 'test'
        }):
            is_valid = await service.validate_environment()
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_config_missing_secret(self, mock_env_vars):
        """Test configuration validation fails if SECRET_KEY is missing."""
        service = ConfigService()
        with patch.dict('os.environ', {
            'DATABASE_URL': 'sqlite://',
            'ENVIRONMENT': 'test'
        }, clear=True):
            is_valid = await service.validate_environment()
            assert is_valid is False

    @pytest.mark.asyncio
    async def test_get_financial_config_defaults(self, mock_env_vars):
        """Test retrieval of financial configuration with default fallbacks."""
        service = ConfigService()
        with patch.dict('os.environ', {
            'QUALIFYING_RATE_BUFFER': '2.0'
        }):
            config = await service.get_financial_config()
            # Ensure we return Decimal for financial values
            assert config["qualifying_rate_buffer"] == Decimal("2.0")