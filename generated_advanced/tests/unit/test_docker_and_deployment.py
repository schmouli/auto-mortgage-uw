import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError
from mortgage_underwriting.modules.deployment.services import DeploymentService
from mortgage_underwriting.modules.deployment.schemas import HealthCheckResponse, SystemInfoResponse

@pytest.mark.unit
class TestDeploymentService:

    @pytest.fixture
    def service(self):
        return DeploymentService()

    @pytest.mark.asyncio
    async def test_check_database_health_success(self, service):
        """
        Test that database health check returns True when connection succeeds.
        """
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: 1)

        result = await service.check_database_health(mock_db)
        
        assert result is True
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_database_health_failure(self, service):
        """
        Test that database health check returns False on SQLAlchemy error.
        """
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=SQLAlchemyError("Connection failed"))

        result = await service.check_database_health(mock_db)
        
        assert result is False
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_database_health_unexpected_error(self, service):
        """
        Test that database health check returns False on generic Exception.
        """
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=RuntimeError("Unexpected crash"))

        result = await service.check_database_health(mock_db)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_get_system_status_healthy(self, service):
        """
        Test system status aggregation when all components are healthy.
        """
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: 1))

        with patch.object(service, 'check_database_health', return_value=True):
            status = await service.get_system_status(mock_db)

        assert status.status == "healthy"
        assert status.database is True
        assert status.dependencies == {}

    @pytest.mark.asyncio
    async def test_get_system_status_unhealthy_db(self, service):
        """
        Test system status aggregation when database is down.
        """
        mock_db = AsyncMock()
        
        with patch.object(service, 'check_database_health', return_value=False):
            status = await service.get_system_status(mock_db)

        assert status.status == "unhealthy"
        assert status.database is False

    @pytest.mark.asyncio
    async def test_get_system_info(self, service):
        """
        Test retrieval of system information (version, environment).
        """
        with patch('mortgage_underwriting.modules.deployment.services.settings') as mock_settings:
            mock_settings.app_name = "MortgageUnderwriting"
            mock_settings.version = "1.0.0"
            mock_settings.environment = "test"
            
            info = await service.get_system_info()

        assert info.app_name == "MortgageUnderwriting"
        assert info.version == "1.0.0"
        assert info.environment == "test"

    def test_validate_environment_variables_present(self, service):
        """
        Test that environment validation passes when required vars are set.
        """
        # Assuming the service checks for specific keys like 'DATABASE_URL', 'SECRET_KEY'
        env_vars = {
            "DATABASE_URL": "postgresql://...",
            "SECRET_KEY": "secret",
            "ALGORITHM": "HS256"
        }
        
        # Mock os.environ
        with patch.dict('os.environ', env_vars, clear=True):
            result = service.validate_environment()
            
        assert result is True

    def test_validate_environment_variables_missing(self, service):
        """
        Test that environment validation fails when required vars are missing.
        """
        env_vars = {
            "DATABASE_URL": "postgresql://..."
            # Missing SECRET_KEY
        }
        
        with patch.dict('os.environ', env_vars, clear=True):
            result = service.validate_environment()
            
        assert result is False

    @pytest.mark.asyncio
    async def test_readiness_check_true(self, service):
        """
        Test readiness check returns True if DB is accessible.
        """
        mock_db = AsyncMock()
        
        with patch.object(service, 'check_database_health', return_value=True):
            is_ready = await service.readiness_check(mock_db)
            
        assert is_ready is True

    @pytest.mark.asyncio
    async def test_readiness_check_false(self, service):
        """
        Test readiness check returns False if DB is inaccessible.
        """
        mock_db = AsyncMock()
        
        with patch.object(service, 'check_database_health', return_value=False):
            is_ready = await service.readiness_check(mock_db)
            
        assert is_ready is False

    @pytest.mark.asyncio
    async def test_liveness_check(self, service):
        """
        Test liveness check. In a simple app, this is often just a return True 
        unless we check for thread deadlocks or memory. We assume simple success.
        """
        is_alive = await service.liveness_check()
        assert is_alive is True

    def test_get_uptime(self, service):
        """
        Test uptime calculation.
        """
        with patch('time.time', return_value=1000):
            service.start_time = 900
            uptime = service.get_uptime()
            
        assert uptime == 100

    def test_get_uptime_not_started(self, service):
        """
        Test uptime when start_time is not set (should handle gracefully).
        """
        service.start_time = None
        uptime = service.get_uptime()
        assert uptime == 0