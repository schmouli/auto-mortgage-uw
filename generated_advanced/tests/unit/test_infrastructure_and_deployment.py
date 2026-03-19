import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

# Assuming the module structure exists based on project conventions
from mortgage_underwriting.modules.infrastructure.services import InfrastructureService
from mortgage_underwriting.modules.infrastructure.exceptions import (
    InfrastructureException,
    DatabaseConnectionError
)
from mortgage_underwriting.modules.infrastructure.schemas import (
    HealthCheckResponse,
    DeploymentEventCreate,
    DeploymentEventResponse
)

@pytest.mark.unit
class TestInfrastructureService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return InfrastructureService(mock_db)

    @pytest.mark.asyncio
    async def test_check_health_success(self, service, mock_db):
        # Arrange
        mock_db.scalar.return_value = 1  # Simulate successful DB ping

        # Act
        result = await service.check_health()

        # Assert
        assert isinstance(result, HealthCheckResponse)
        assert result.status == "healthy"
        assert result.database_status == "connected"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_health_database_failure(self, service, mock_db):
        # Arrange
        mock_db.scalar.side_effect = SQLAlchemyError("Connection failed")

        # Act
        result = await service.check_health()

        # Assert
        assert isinstance(result, HealthCheckResponse)
        assert result.status == "unhealthy"
        assert result.database_status == "disconnected"
        assert "Connection failed" in result.details.get("database_error", "")

    @pytest.mark.asyncio
    async def test_record_deployment_success(self, service, mock_db):
        # Arrange
        payload = DeploymentEventCreate(
            version="v1.0.1",
            environment="staging",
            status="success",
            resource_cost=Decimal("50.00"),
            created_by="deploy_user"
        )

        # Act
        result = await service.record_deployment(payload)

        # Assert
        assert result is not None
        assert isinstance(result, DeploymentEventResponse)
        assert result.version == "v1.0.1"
        assert result.resource_cost == Decimal("50.00")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_deployment_invalid_cost_negative(self, service):
        # Arrange
        # Pydantic validation should catch this, but testing service logic if it bypasses schema
        # or if schema allows it but service rejects it (business rule)
        payload = DeploymentEventCreate(
            version="v1.0.1",
            environment="staging",
            status="success",
            resource_cost=Decimal("-10.00"), # Invalid business rule
            created_by="deploy_user"
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.record_deployment(payload)
        assert "Resource cost cannot be negative" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_record_deployment_db_error(self, service, mock_db):
        # Arrange
        payload = DeploymentEventCreate(
            version="v1.0.1",
            environment="staging",
            status="success",
            resource_cost=Decimal("50.00"),
            created_by="deploy_user"
        )
        mock_db.commit.side_effect = SQLAlchemyError("Deadlock")

        # Act & Assert
        with pytest.raises(InfrastructureException) as exc_info:
            await service.record_deployment(payload)
        assert exc_info.value.error_code == "DEPLOYMENT_DB_ERROR"
        assert "Deadlock" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_deployment_history_empty(self, service, mock_db):
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        # Act
        history = await service.get_deployment_history(limit=10)

        # Assert
        assert history == []
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_deployment_history_populated(self, service, mock_db):
        # Arrange
        # Mocking the ORM result object
        mock_event = MagicMock(spec=DeploymentEventResponse)
        mock_event.id = 1
        mock_event.version = "v1.0.0"
        mock_event.environment = "production"
        mock_event.status = "success"
        mock_event.resource_cost = Decimal("100.00")
        mock_event.created_at = datetime.now(timezone.utc)
        mock_event.created_by = "admin"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]
        mock_db.execute.return_value = mock_result

        # Act
        history = await service.get_deployment_history(limit=10)

        # Assert
        assert len(history) == 1
        assert history[0].version == "v1.0.0"
        assert history[0].resource_cost == Decimal("100.00")

    def test_validate_environment_valid(self, service):
        # Act & Assert
        assert service._validate_environment("production") is True
        assert service._validate_environment("staging") is True
        assert service._validate_environment("development") is True

    def test_validate_environment_invalid(self, service):
        # Act & Assert
        with pytest.raises(ValueError):
            service._validate_environment("invalid_env")