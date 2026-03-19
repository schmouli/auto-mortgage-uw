import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.deployment.models import DeploymentLog
from mortgage_underwriting.modules.deployment.schemas import DeploymentCreate, DeploymentResponse
from mortgage_underwriting.modules.deployment.services import DeploymentService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDeploymentService:

    @pytest.fixture
    def mock_db(self):
        """Fixture for a mocked database session."""
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_log_deployment_success(self, mock_db, sample_deployment_payload):
        """
        Test that a deployment is logged successfully with audit fields.
        """
        service = DeploymentService(mock_db)
        payload = DeploymentCreate(**sample_deployment_payload)
        
        # Simulate the DB returning an object after refresh
        mock_log = DeploymentLog(
            id=1,
            environment=payload.environment,
            version=payload.version,
            commit_hash=payload.commit_hash,
            deployed_by=payload.deployed_by,
            status=payload.status,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_db.refresh.side_effect = lambda x: None # Mock refresh behavior
        
        result = await service.log_deployment(payload)
        
        assert isinstance(result, DeploymentResponse)
        assert result.environment == "production"
        assert result.version == "1.2.3"
        assert result.status == "success"
        
        # Verify Audit Trail (FINTRAC/General Compliance)
        assert result.created_at is not None
        assert result.updated_at is not None
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_deployment_db_failure(self, mock_db, sample_deployment_payload):
        """
        Test that AppException is raised on database error.
        """
        service = DeploymentService(mock_db)
        payload = DeploymentCreate(**sample_deployment_payload)
        
        mock_db.commit.side_effect = SQLAlchemyError("Connection failed")
        
        with pytest.raises(AppException) as exc_info:
            await service.log_deployment(payload)
        
        assert exc_info.value.status_code == 500
        assert "Database error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_latest_deployment_success(self, mock_db):
        """
        Test retrieving the latest deployment record.
        """
        service = DeploymentService(mock_db)
        
        mock_log = DeploymentLog(
            id=1,
            environment="production",
            version="1.2.3",
            commit_hash="abc123",
            deployed_by="admin",
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Mock the scalars().first() chain
        mock_scalar_result = AsyncMock()
        mock_scalar_result.first.return_value = mock_log
        mock_db.scalars.return_value = mock_scalar_result
        
        result = await service.get_latest_deployment("production")
        
        assert result is not None
        assert result.version == "1.2.3"
        assert result.environment == "production"

    @pytest.mark.asyncio
    async def test_get_latest_deployment_not_found(self, mock_db):
        """
        Test handling when no deployment exists for an environment.
        """
        service = DeploymentService(mock_db)
        
        # Mock returning None
        mock_scalar_result = AsyncMock()
        mock_scalar_result.first.return_value = None
        mock_db.scalars.return_value = mock_scalar_result
        
        with pytest.raises(AppException) as exc_info:
            await service.get_latest_deployment("staging")
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_validate_version_format_valid(self, mock_db):
        """
        Test validation logic for semantic versioning.
        """
        service = DeploymentService(mock_db)
        valid_versions = ["1.0.0", "2.3.4-beta", "10.20.30"]
        
        for version in valid_versions:
            is_valid = service._validate_version_format(version)
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_version_format_invalid(self, mock_db):
        """
        Test validation logic rejects invalid version strings.
        """
        service = DeploymentService(mock_db)
        invalid_versions = ["1.0", "v1.0.0", "latest", "abc"]
        
        for version in invalid_versions:
            is_valid = service._validate_version_format(version)
            assert is_valid is False

    @pytest.mark.asyncio
    async def test_log_deployment_invalid_version_raises(self, mock_db, sample_deployment_payload):
        """
        Test that logging with an invalid version raises a validation error.
        """
        service = DeploymentService(mock_db)
        sample_deployment_payload["version"] = "invalid-version-string"
        payload = DeploymentCreate(**sample_deployment_payload)
        
        with pytest.raises(AppException) as exc_info:
            await service.log_deployment(payload)
        
        assert exc_info.value.status_code == 400
        assert "Invalid version format" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_check_system_health_healthy(self, mock_db):
        """
        Test health check returns True when dependencies are responsive.
        """
        service = DeploymentService(mock_db)
        # Mock a successful DB ping
        mock_db.execute.return_value = AsyncMock()
        
        health_status = await service.check_system_health()
        
        assert health_status["status"] == "healthy"
        assert "database" in health_status["dependencies"]

    @pytest.mark.asyncio
    async def test_check_system_health_unhealthy(self, mock_db):
        """
        Test health check returns False when DB fails.
        """
        service = DeploymentService(mock_db)
        mock_db.execute.side_effect = SQLAlchemyError("Timeout")
        
        health_status = await service.check_system_health()
        
        assert health_status["status"] == "unhealthy"
        assert "database" in health_status["dependencies"]
        assert health_status["dependencies"]["database"] == "unreachable"