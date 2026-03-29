```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import DBAPIError, OperationalError

from mortgage_underwriting.modules.infrastructure.services import HealthService
from mortgage_underwriting.modules.infrastructure.exceptions import (
    InfrastructureException,
    SystemUnhealthyException,
)
from mortgage_underwriting.modules.infrastructure.schemas import HealthCheckResponse

@pytest.mark.unit
class TestHealthService:

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for unit tests."""
        session = AsyncMock()
        # Mock the execute() method to return a result with scalar()
        result_mock = MagicMock()
        result_mock.scalar.return_value = 1
        session.execute.return_value = result_mock
        return session

    @pytest.mark.asyncio
    async def test_check_database_connection_success(self, mock_db_session):
        """Test that DB health check returns True on successful query."""
        service = HealthService(mock_db_session)
        is_healthy = await service.check_database_connection()
        
        assert is_healthy is True
        mock_db_session.execute.assert_awaited_once()
        # Ensure we tried to execute a simple SELECT 1
        call_args = mock_db_session.execute.call_args
        assert "SELECT 1" in str(call_args).upper()

    @pytest.mark.asyncio
    async def test_check_database_connection_failure(self, mock_db_session):
        """Test that DB health check returns False on connection error."""
        # Simulate a database connection error
        mock_db_session.execute.side_effect = OperationalError("Connection failed", None, None)
        
        service = HealthService(mock_db_session)
        is_healthy = await service.check_database_connection()
        
        assert is_healthy is False
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_health_status_all_systems_go(self, mock_db_session):
        """Test health status returns healthy when all checks pass."""
        service = HealthService(mock_db_session)
        
        response = await service.get_health_status()
        
        assert isinstance(response, HealthCheckResponse)
        assert response.status == "healthy"
        assert response.database.status == "up"
        assert response.details["database"] == "Connection successful"

    @pytest.mark.asyncio
    async def test_get_health_status_database_down(self, mock_db_session):
        """Test health status returns degraded/unhealthy when DB fails."""
        mock_db_session.execute.side_effect = DBAPIError("Error", None, None)
        
        service = HealthService(mock_db_session)
        
        response = await service.get_health_status()
        
        assert response.status == "unhealthy"
        assert response.database.status == "down"
        assert "error" in response.database.message.lower()

    @pytest.mark.asyncio
    async def test_get_health_status_logs_details(self, mock_db_session, caplog):
        """Test that health check logs are generated for audit purposes."""
        service = HealthService(mock_db_session)
        
        with caplog.at_level("INFO"):
            await service.get_health_status()
        
        # Verify logs contain relevant info
        assert any("Health check performed" in record.message for record in caplog.records)
        assert any("database" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_check_external_service_timeout(self):
        """Test handling of external service timeouts (e.g.,征信局 API)."""
        service = HealthService(AsyncMock()) # DB not needed for this specific check logic
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = TimeoutError("Request timed out")
            
            is_healthy = await service.check_external_service("https://api.credit-bureau.com")
            
            assert is_healthy is False

    @pytest.mark.asyncio
    async def test_check_external_service_success(self):
        """Test handling of successful external service ping."""
        service = HealthService(AsyncMock())
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = mock_response
            
            is_healthy = await service.check_external_service("https://api.credit-bureau.com")
            
            assert is_healthy is True
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_version_info(self):
        """Test retrieval of application version information."""
        service = HealthService(AsyncMock())
        
        with patch("mortgage_underwriting.modules.infrastructure.services.settings") as mock_settings:
            mock_settings.APP_VERSION = "1.0.0"
            mock_settings.ENVIRONMENT = "test"
            
            version_info = await service.get_version_info()
            
            assert version_info["version"] == "1.0.0"
            assert version_info["environment"] == "test"

    @pytest.mark.asyncio
    async def test_unhealthy_exception_propagation(self, mock_db_session):
        """Test that specific exception is raised when critical systems fail."""
        mock_db_session.execute.side_effect = OperationalError("Critical DB failure", None, None)
        
        service = HealthService(mock_db_session)
        
        # Assuming the service has a method that enforces strict health checks
        with pytest.raises(SystemUnhealthyException) as exc_info:
            await service.verify_critical_systems()
            
        assert "database" in str(exc_info.value).lower()

@pytest.mark.unit
class TestConfigService:
    """Tests for configuration validation and loading logic within Infrastructure."""

    @pytest.mark.asyncio
    async def test_validate_encryption_key_present(self):
        """Test that configuration validation fails if encryption key is missing."""
        from mortgage_underwriting.modules.infrastructure.services import ConfigService
        from pydantic import ValidationError
        
        with patch.dict("os.environ", {}, clear=True):
            # Ensure key is missing
            if "ENCRYPTION_KEY" in patch.dict("os.environ"):
                del patch.dict("os.environ")["ENCRYPTION_KEY"]
                
            with pytest.raises(ValidationError) as exc_info:
                ConfigService.load_settings()
            
            # Check that the error mentions encryption key or similar required fields
            errors = exc_info.value.errors()
            assert any("encryption_key" in str(err.get("loc", "")).lower() for err in errors)

    @pytest.mark.asyncio
    async def test_get_masked_config(self):
        """Test that sensitive config values are masked in output."""
        from mortgage_underwriting.modules.infrastructure.services import ConfigService
        
        with patch("mortgage_underwriting.modules.infrastructure.services.settings") as mock_settings:
            mock_settings.DATABASE_URL = "postgresql://user:pass@localhost/db"
            mock_settings.SECRET_KEY = "super_secret_key"
            mock_settings.ENCRYPTION_KEY = "encryption_key_123"
            mock_settings.APP_NAME = "MortgageApp"
            
            config = ConfigService.get_public_config()
            
            assert config["database_url"] == "********"
            assert config["secret_key"] == "********"
            assert config["app_name"] == "MortgageApp" # Public info visible
```