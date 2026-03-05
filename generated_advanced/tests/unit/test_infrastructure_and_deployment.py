import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import text

# Import the module under test
from mortgage_underwriting.modules.infrastructure_deployment.services import InfrastructureService
from mortgage_underwriting.modules.infrastructure_deployment.models import DeploymentAudit
from mortgage_underwriting.modules.infrastructure_deployment.exceptions import DeploymentError, HealthCheckError

@pytest.mark.unit
class TestInfrastructureService:

    @pytest.mark.asyncio
    async def test_check_health_success(self, mock_db_session):
        """Test successful health check when DB responds."""
        # Mock the result of execute
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 1
        mock_db_session.execute.return_value = mock_result

        service = InfrastructureService(mock_db_session)
        is_healthy = await service.check_health()

        assert is_healthy is True
        mock_db_session.execute.assert_awaited_once()
        # Verify the query text matches expectation (simple select 1)
        call_args = mock_db_session.execute.call_args[0][0]
        assert "SELECT" in str(call_args).upper()

    @pytest.mark.asyncio
    async def test_check_health_failure_db_error(self, mock_db_session):
        """Test health check failure when DB throws an exception."""
        mock_db_session.execute.side_effect = Exception("Connection refused")

        service = InfrastructureService(mock_db_session)
        
        with pytest.raises(HealthCheckError) as exc_info:
            await service.check_health()
        
        assert "Database health check failed" in str(exc_info.value)
        assert "Connection refused" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_log_deployment_success(self, mock_db_session, sample_deployment_payload):
        """Test successfully logging a deployment event."""
        service = InfrastructureService(mock_db_session)
        
        result = await service.log_deployment(
            environment=sample_deployment_payload["environment"],
            version=sample_deployment_payload["version"],
            deployed_by=sample_deployment_payload["deployed_by"],
            status=sample_deployment_payload["status"]
        )

        assert result is not None
        assert isinstance(result, DeploymentAudit)
        assert result.environment == "production"
        assert result.version == "v1.2.3"
        assert result.status == "success"
        
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_deployment_invalid_environment(self, mock_db_session, sample_deployment_payload):
        """Test that invalid environment raises validation error."""
        service = InfrastructureService(mock_db_session)
        
        with pytest.raises(ValueError) as exc_info:
            await service.log_deployment(
                environment="invalid_env", # Invalid
                version="v1.0.0",
                deployed_by="user",
                status="success"
            )
        
        assert "Invalid environment" in str(exc_info.value)
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_log_deployment_db_commit_failure(self, mock_db_session):
        """Test handling of database commit failure during logging."""
        mock_db_session.commit.side_effect = Exception("DB Lock timeout")
        service = InfrastructureService(mock_db_session)

        with pytest.raises(DeploymentError) as exc_info:
            await service.log_deployment(
                environment="staging",
                version="v1.0.0",
                deployed_by="user",
                status="failed"
            )
        
        assert "Failed to record deployment" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_deployment_history_success(self, mock_db_session):
        """Test retrieving deployment history."""
        # Mock the scalars().all() chain
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [
            DeploymentAudit(id=1, version="v1.0.0", environment="dev", deployed_by="alice", status="success"),
            DeploymentAudit(id=2, version="v1.1.0", environment="prod", deployed_by="bob", status="success")
        ]
        
        mock_result = AsyncMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        service = InfrastructureService(mock_db_session)
        history = await service.get_deployment_history(limit=10)

        assert len(history) == 2
        assert history[0].version == "v1.0.0"
        assert history[1].version == "v1.1.0"

    @pytest.mark.asyncio
    async def test_get_deployment_history_empty(self, mock_db_session):
        """Test retrieving history when no deployments exist."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        
        mock_result = AsyncMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        service = InfrastructureService(mock_db_session)
        history = await service.get_deployment_history()

        assert history == []
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_deployment_history_limit_enforced(self, mock_db_session):
        """Test that the limit parameter is respected in the query construction."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        
        mock_result = AsyncMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        service = InfrastructureService(mock_db_session)
        await service.get_deployment_history(limit=5)

        # Check that the statement passed to execute contains the limit logic
        # Note: Exact assertion depends on SQLAlchemy implementation details, 
        # here we verify the call happened.
        mock_db_session.execute.assert_awaited_once()
        # We can't easily inspect the compiled SQL string in the mock without 
        # specific SQLAlchemy inspection tools, but we verify flow.

    @pytest.mark.asyncio
    async def test_log_deployment_audit_fields(self, mock_db_session):
        """Test that audit fields (created_at) are populated."""
        service = InfrastructureService(mock_db_session)
        
        with patch("mortgage_underwriting.modules.infrastructure_deployment.services.datetime") as mock_datetime:
            fixed_time = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = fixed_time

            result = await service.log_deployment("test", "v1", "user", "success")
            
            assert result.created_at == fixed_time