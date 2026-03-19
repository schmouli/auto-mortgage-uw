--- conftest.py ---
import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
import sys
import os

# Adjust path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Assuming the Base and database setup are in common.database
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.deployment.models import DeploymentLog

# Use SQLite for in-memory testing to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def app() -> FastAPI:
    """
    Fixture to create a test FastAPI app instance including the deployment router.
    """
    from mortgage_underwriting.modules.deployment.routes import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/deployment", tags=["deployment"])
    return app

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for testing endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def sample_deployment_payload():
    return {
        "environment": "production",
        "version": "1.2.3",
        "commit_hash": "a1b2c3d4",
        "deployed_by": "ci_cd_pipeline",
        "status": "success"
    }
--- unit_tests ---
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
--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from datetime import datetime

from mortgage_underwriting.modules.deployment.models import DeploymentLog

@pytest.mark.integration
@pytest.mark.asyncio
class TestDeploymentRoutes:

    async def test_create_deployment_log(self, client: AsyncClient, db_session, sample_deployment_payload):
        """
        Test the endpoint to create a deployment log.
        """
        response = await client.post("/api/v1/deployment/log", json=sample_deployment_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["environment"] == "production"
        assert data["version"] == "1.2.3"
        assert "id" in data
        assert "created_at" in data

        # Verify persistence in DB
        stmt = select(DeploymentLog).where(DeploymentLog.version == "1.2.3")
        result = await db_session.execute(stmt)
        log = result.scalar_one_or_none()
        
        assert log is not None
        assert log.commit_hash == "a1b2c3d4"
        assert log.status == "success"

    async def test_create_deployment_log_invalid_version(self, client: AsyncClient, sample_deployment_payload):
        """
        Test validation rejection for bad version format via API.
        """
        sample_deployment_payload["version"] = "bad_version"
        response = await client.post("/api/v1/deployment/log", json=sample_deployment_payload)
        
        assert response.status_code == 422  # Validation Error

    async def test_get_deployment_history(self, client: AsyncClient, db_session):
        """
        Test retrieving history of deployments for an environment.
        """
        # Seed data
        log1 = DeploymentLog(
            environment="production",
            version="1.0.0",
            commit_hash="hash1",
            deployed_by="user1",
            status="success",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        log2 = DeploymentLog(
            environment="production",
            version="1.0.1",
            commit_hash="hash2",
            deployed_by="user1",
            status="success",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(log1)
        db_session.add(log2)
        await db_session.commit()

        response = await client.get("/api/v1/deployment/history?environment=production")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        versions = [item["version"] for item in data]
        assert "1.0.0" in versions
        assert "1.0.1" in versions

    async def test_get_deployment_history_empty(self, client: AsyncClient):
        """
        Test retrieving history when no records exist.
        """
        response = await client.get("/api/v1/deployment/history?environment=staging")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    async def test_health_check_endpoint(self, client: AsyncClient):
        """
        Test the public health check endpoint.
        """
        response = await client.get("/api/v1/deployment/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        # Check structure matches expected health schema
        assert data["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_get_latest_deployment_endpoint(self, client: AsyncClient, db_session):
        """
        Test getting the single latest deployment record.
        """
        log = DeploymentLog(
            environment="production",
            version="2.0.0",
            commit_hash="latest_hash",
            deployed_by="admin",
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(log)
        await db_session.commit()

        response = await client.get("/api/v1/deployment/latest?environment=production")
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "2.0.0"
        assert data["commit_hash"] == "latest_hash"

    async def test_get_latest_deployment_not_found_endpoint(self, client: AsyncClient):
        """
        Test 404 when requesting latest for non-existent environment.
        """
        response = await client.get("/api/v1/deployment/latest?environment=nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    async def test_update_deployment_status(self, client: AsyncClient, db_session):
        """
        Test updating the status of a deployment (e.g., rollback).
        """
        # Create initial log
        log = DeploymentLog(
            environment="production",
            version="3.0.0",
            commit_hash="hash3",
            deployed_by="admin",
            status="deploying",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        # Update via API
        update_payload = {"status": "failed", "notes": "Health check failed"}
        response = await client.patch(f"/api/v1/deployment/{log.id}", json=update_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        
        # Verify DB update
        await db_session.refresh(log)
        assert log.status == "failed"
        assert log.updated_at > log.created_at

    async def test_security_no_secrets_in_response(self, client: AsyncClient, db_session):
        """
        Ensure sensitive fields (if any existed) are not leaked.
        Here we ensure internal IDs or tokens are not exposed unnecessarily.
        """
        log = DeploymentLog(
            environment="production",
            version="1.0.0",
            commit_hash="secret_hash",
            deployed_by="admin",
            status="success",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(log)
        await db_session.commit()

        response = await client.get("/api/v1/deployment/latest?environment=production")
        assert response.status_code == 200
        data = response.json()
        # Ensure response does not contain internal fields not defined in schema
        # (e.g. internal_notes if they existed in model but not schema)
        assert "deployed_by" in data # This is allowed
        # Verify no unexpected keys
        allowed_keys = {"id", "environment", "version", "commit_hash", "deployed_by", "status", "created_at", "updated_at"}
        assert set(data.keys()).issubset(allowed_keys)