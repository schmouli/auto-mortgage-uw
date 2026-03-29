```python
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.deployment.services import (
    DeploymentService,
    HealthService
)
from mortgage_underwriting.modules.deployment.schemas import (
    DeploymentCreate,
    HealthCheckResponse
)
from mortgage_underwriting.modules.deployment.exceptions import (
    DeploymentRecordError,
    HealthCheckError
)

@pytest.mark.unit
class TestDeploymentService:
    
    @pytest.mark.asyncio
    async def test_record_deployment_success(self, db_session):
        """
        Test recording a successful deployment creates an audit trail (FINTRAC compliance).
        """
        service = DeploymentService(db_session)
        payload = DeploymentCreate(
            version="v1.0.0",
            deployed_by="admin",
            environment="production",
            notes="Initial release"
        )

        result = await service.record_deployment(payload)

        assert result.id is not None
        assert result.version == "v1.0.0"
        assert result.status == "success"
        assert result.created_at is not None
        # Verify immutability logic (simulated by lack of update methods in service)
        # and audit fields presence
        assert result.deployed_by == "admin"

    @pytest.mark.asyncio
    async def test_record_deployment_db_failure(self, db_session):
        """
        Test that database errors during deployment recording are handled gracefully.
        """
        # Mock the session to raise an error on commit
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock(side_effect=SQLAlchemyError("DB Connection Lost"))
        
        service = DeploymentService(mock_session)
        payload = DeploymentCreate(
            version="v1.0.1",
            deployed_by="admin",
            environment="production"
        )

        with pytest.raises(DeploymentRecordError) as exc_info:
            await service.record_deployment(payload)
        
        assert "Failed to record deployment" in str(exc_info.value)
        mock_session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_deployment_minimal_data(self, db_session):
        """
        Test recording with minimal required fields (Data Minimization).
        """
        service = DeploymentService(db_session)
        payload = DeploymentCreate(
            version="v2.0.0",
            deployed_by="ci_bot",
            environment="testing"
        )

        result = await service.record_deployment(payload)
        
        assert result.version == "v2.0.0"
        assert result.notes is None  # Ensure optional fields are handled

@pytest.mark.unit
class TestHealthService:

    @pytest.mark.asyncio
    async def test_health_check_all_systems_go(self, db_session, mock_redis):
        """
        Test health check returns healthy when DB and Redis are responsive.
        """
        service = HealthService(db_session)
        
        # Mock DB execution
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        
        health = await service.check_system_health(mock_session)
        
        assert health.status == "healthy"
        assert health.database == "connected"
        assert health.cache == "connected"

    @pytest.mark.asyncio
    async def test_health_check_database_down(self, mock_redis):
        """
        Test health check handles database connection failure.
        """
        # Mock a failing DB session
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Connection refused"))
        
        service = HealthService(mock_session)
        
        health = await service.check_system_health(mock_session)
        
        assert health.status == "unhealthy"
        assert health.database == "disconnected"
        assert "Connection refused" in health.details.get("database_error", "")

    @pytest.mark.asyncio
    async def test_health_check_redis_down(self, db_session):
        """
        Test health check handles Redis connection failure.
        """
        with patch("mortgage_underwriting.modules.deployment.services.redis_client") as bad_redis:
            bad_redis.ping = AsyncMock(side_effect=ConnectionError("Redis timeout"))
            
            service = HealthService(db_session)
            health = await service.check_system_health(db_session)
            
            assert health.status == "degraded" # DB is up, cache is down
            assert health.cache == "disconnected"

    @pytest.mark.asyncio
    async def test_health_check_unexpected_error(self, db_session):
        """
        Test that unexpected errors during health checks are caught.
        """
        service = HealthService(db_session)
        
        # Force an unexpected error
        with patch.object(service, '_check_db', side_effect=Exception("Unexpected crash")):
            with pytest.raises(HealthCheckError) as exc_info:
                await service.check_system_health(db_session)
            
            assert "Health check failed" in str(exc_info.value)

@pytest.mark.unit
class TestDeploymentModels:
    """
    Unit tests for model logic (e.g., string representation, defaults).
    """
    def test_deployment_audit_repr(self):
        from mortgage_underwriting.modules.deployment.models import DeploymentAudit
        
        audit = DeploymentAudit(
            id=1,
            version="v1.0.0",
            deployed_by="user",
            environment="prod",
            status="success",
            created_at=datetime.utcnow()
        )
        
        repr_str = repr(audit)
        assert "DeploymentAudit" in repr_str
        assert "v1.0.0" in repr_str
        # Ensure PII is not in repr (though deployed_by is an internal user ID here, not PII)
        assert "user" in repr_str
```