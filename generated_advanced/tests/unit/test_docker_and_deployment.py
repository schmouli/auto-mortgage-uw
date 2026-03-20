import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

# Module imports based on project structure
from mortgage_underwriting.modules.deployment.services import DeploymentService
from mortgage_underwriting.modules.deployment.schemas import HealthCheckResponse, DeploymentEventCreate
from mortgage_underwriting.modules.deployment.exceptions import DatabaseConnectionError, ConfigurationError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDeploymentServiceHealth:
    """
    Unit tests for the DeploymentService health check functionality.
    Ensures the service correctly reports status based on DB and external dependencies.
    """

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self):
        return DeploymentService()

    @pytest.mark.asyncio
    async def test_check_health_success(self, service, mock_db):
        """Test successful health check when DB is responsive."""
        # Mock the execution of a simple query (e.g., SELECT 1)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        mock_db.execute.return_value = mock_result

        result = await service.check_health(mock_db)

        assert result.status == "healthy"
        assert result.database_status == "connected"
        assert result.timestamp is not None
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_health_db_failure(self, service, mock_db):
        """Test health check failure when DB is unreachable."""
        mock_db.execute.side_effect = SQLAlchemyError("Connection failed")

        with pytest.raises(DatabaseConnectionError) as exc_info:
            await service.check_health(mock_db)

        assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_health_unexpected_error(self, service, mock_db):
        """Test health check handles unexpected errors gracefully."""
        mock_db.execute.side_effect = Exception("Unexpected crash")

        with pytest.raises(AppException) as exc_info:
            await service.check_health(mock_db)
        
        assert exc_info.value.status_code == 500

@pytest.mark.unit
class TestDeploymentServiceConfig:
    """
    Unit tests for configuration validation and retrieval.
    """

    @pytest.fixture
    def service(self):
        return DeploymentService()

    def test_get_app_version(self, service, monkeypatch):
        """Test retrieving application version."""
        monkeypatch.setenv("APP_VERSION", "2.4.1")
        # Reload settings or mock the config object directly
        with patch("mortgage_underwriting.modules.deployment.services.settings") as mock_settings:
            mock_settings.APP_VERSION = "2.4.1"
            version = service.get_version()
            assert version == "2.4.1"

    def test_validate_environment_success(self, service, monkeypatch):
        """Test environment validation with all required variables set."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://...")
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        
        with patch("mortgage_underwriting.modules.deployment.services.settings") as mock_settings:
            mock_settings.DATABASE_URL = "postgresql://..."
            mock_settings.SECRET_KEY = "test-secret"
            
            # Should not raise
            service.validate_environment()

    def test_validate_environment_missing_secret(self, service, monkeypatch):
        """Test environment validation raises error if SECRET_KEY is missing."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        
        with patch("mortgage_underwriting.modules.deployment.services.settings") as mock_settings:
            mock_settings.SECRET_KEY = None
            
            with pytest.raises(ConfigurationError) as exc_info:
                service.validate_environment()
            
            assert "SECRET_KEY" in str(exc_info.value)

@pytest.mark.unit
class TestDeploymentServiceAudit:
    """
    Unit tests for deployment event logging (FINTRAC compliance).
    """

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self):
        return DeploymentService()

    @pytest.mark.asyncio
    async def test_log_deployment_event_success(self, service, mock_db):
        """Test successful logging of a deployment event."""
        payload = DeploymentEventCreate(
            event_type="MIGRATION",
            description="Applied migration 001_initial.up.sql",
            initiated_by="system"
        )

        result = await service.log_event(mock_db, payload)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        assert result.event_type == "MIGRATION"
        # Verify audit fields are present (simulated)
        assert hasattr(result, "created_at")

    @pytest.mark.asyncio
    async def test_log_deployment_event_db_error(self, service, mock_db):
        """Test logging event handles DB errors."""
        payload = DeploymentEventCreate(
            event_type="SCALE_UP",
            description="Increased replica count",
            initiated_by="admin"
        )
        mock_db.commit.side_effect = SQLAlchemyError("Lock timeout")

        with pytest.raises(AppException):
            await service.log_event(mock_db, payload)

@pytest.mark.unit
class TestDeploymentUtilities:
    """Tests for helper functions within the module."""

    def test_format_uptime(self):
        from mortgage_underwriting.modules.deployment.services import format_uptime
        # Test seconds
        assert format_uptime(45) == "45s"
        # Test minutes
        assert format_uptime(120) == "2m 0s"
        # Test hours
        assert format_uptime(3661) == "1h 1m 1s"

    def test_mask_sensitive_config(self):
        from mortgage_underwriting.modules.deployment.services import mask_sensitive_config
        config_data = {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "DEBUG": "True",
            "API_KEY": "secret-key-123"
        }
        masked = mask_sensitive_config(config_data)
        
        assert "pass" not in masked["DATABASE_URL"]
        assert "secret" not in masked["API_KEY"]
        assert masked["DEBUG"] == "True"