--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from fastapi import FastAPI

from mortgage_underwriting.common.database import Base, get_async_session
from mortgage_underwriting.modules.docker_deployment.routes import router as deployment_router
from mortgage_underwriting.modules.docker_deployment.models import DeploymentLog

# Use in-memory SQLite for testing isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates a test client that overrides the database dependency.
    """
    app = FastAPI()
    app.include_router(deployment_router, prefix="/api/v1/deployment", tags=["deployment"])

    # Dependency Override
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_deployment_payload():
    return {
        "version": "1.0.5",
        "environment": "test",
        "deployed_by": "ci_cd_pipeline",
        "git_commit_sha": "a1b2c3d4",
        "status": "success"
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for config validation tests."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("SECRET_KEY", "test_secret_key")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("QUALIFYING_RATE_BUFFER", "2.0")

--- unit_tests ---
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

--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from mortgage_underwriting.modules.docker_deployment.models import DeploymentLog


@pytest.mark.integration
class TestDeploymentRoutes:
    @pytest.mark.asyncio
    async def test_create_deployment_log(self, client: AsyncClient, mock_deployment_payload):
        """Test creating a deployment log via API."""
        response = await client.post("/api/v1/deployment/logs", json=mock_deployment_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["version"] == mock_deployment_payload["version"]
        assert data["id"] is not None
        assert data["created_at"] is not None

    @pytest.mark.asyncio
    async def test_create_deployment_log_invalid_payload(self, client: AsyncClient):
        """Test API validation with missing fields."""
        incomplete_payload = {"environment": "prod"}
        response = await client.post("/api/v1/deployment/logs", json=incomplete_payload)

        assert response.status_code == 422  # Validation Error

    @pytest.mark.asyncio
    async def test_get_deployment_logs(self, client: AsyncClient, db_session, mock_deployment_payload):
        """Test retrieving list of deployment logs."""
        # Seed data
        log1 = DeploymentLog(**mock_deployment_payload)
        log2 = DeploymentLog(**{**mock_deployment_payload, "version": "1.0.6"})
        db_session.add(log1)
        db_session.add(log2)
        await db_session.commit()
        await db_session.refresh(log1)
        await db_session.refresh(log2)

        response = await client.get("/api/v1/deployment/logs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 2
        # Verify newest is first (assuming ordering)
        assert data["items"][0]["version"] == "1.0.6"

    @pytest.mark.asyncio
    async def test_get_deployment_log_by_id(self, client: AsyncClient, db_session, mock_deployment_payload):
        """Test retrieving a specific deployment log."""
        log = DeploymentLog(**mock_deployment_payload)
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        response = await client.get(f"/api/v1/deployment/logs/{log.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == log.id
        assert data["git_commit_sha"] == mock_deployment_payload["git_commit_sha"]


@pytest.mark.integration
class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, client: AsyncClient):
        """Test the liveness/readiness probe endpoint."""
        response = await client.get("/api/v1/deployment/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_version_endpoint(self, client: AsyncClient):
        """Test the version endpoint."""
        response = await client.get("/api/v1/deployment/version")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        # Check format (e.g., 1.0.0)
        assert isinstance(data["version"], str)


@pytest.mark.integration
class TestDeploymentAuditTrail:
    @pytest.mark.asyncio
    async def test_deployment_log_immutability_audit_fields(self, client: AsyncClient, db_session, mock_deployment_payload):
        """
        Test that deployment logs are created with correct audit fields
        and represent an immutable event log.
        """
        response = await client.post("/api/v1/deployment/logs", json=mock_deployment_payload)
        assert response.status_code == 201
        
        log_id = response.json()["id"]
        
        # Verify in DB
        result = await db_session.execute(select(DeploymentLog).where(DeploymentLog.id == log_id))
        log = result.scalar_one()
        
        assert log.created_at is not None
        assert log.updated_at is not None # Usually set by base model
        
        # Attempting to update via API should fail or be restricted depending on implementation
        # Assuming updates are not allowed for audit logs
        update_payload = {"status": "failed"}
        response = await client.patch(f"/api/v1/deployment/logs/{log_id}", json=update_payload)
        
        # Expect 405 Method Not Allowed or 403 Forbidden if strictly immutable
        assert response.status_code in [405, 403, 404] # 404 if endpoint doesn't exist