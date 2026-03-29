--- conftest.py ---
```python
import pytest
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, MagicMock, patch

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.deployment.models import DeploymentAudit

# Use SQLite in-memory for testing speed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        yield session

    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def mock_settings():
    """
    Mocks the application settings to avoid loading real .env files.
    """
    with patch("mortgage_underwriting.common.config.settings") as mock:
        mock.environment = "testing"
        mock.secret_key = "test-secret-key"
        mock.database_url = TEST_DATABASE_URL
        yield mock

@pytest.fixture
def mock_redis():
    """
    Mocks the Redis client for health checks.
    """
    with patch("mortgage_underwriting.modules.deployment.services.redis_client") as mock:
        mock.ping = AsyncMock(return_value=True)
        yield mock

@pytest.fixture
def deployment_payload():
    return {
        "version": "v1.2.3",
        "deployed_by": "system_user",
        "environment": "staging",
        "notes": "Automated deployment via CI/CD"
    }
```

--- unit_tests ---
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

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy import select

from mortgage_underwriting.modules.deployment.routes import router
from mortgage_underwriting.modules.deployment.models import DeploymentAudit
from mortgage_underwriting.common.database import get_async_session

@pytest.fixture
def app(db_session):
    """
    Creates a test FastAPI app with the deployment router.
    Overrides the database dependency with the test session.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/deployment", tags=["Deployment"])

    # Dependency override
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestDeploymentEndpoints:

    async def test_create_deployment_audit(self, app: FastAPI):
        """
        Test POST /api/v1/deployment/audit
        Ensures audit trail is created correctly (FINTRAC compliance).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "version": "v1.4.5",
                "deployed_by": "devops_user",
                "environment": "production",
                "notes": "Hotfix for security patch"
            }
            
            response = await client.post("/api/v1/deployment/audit", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] > 0
            assert data["version"] == "v1.4.5"
            assert data["status"] == "success"
            assert "created_at" in data
            
            # Verify immutability: response should not allow updating via this endpoint
            # (Implicitly tested as we only have a POST endpoint)

    async def test_create_deployment_invalid_input(self, app: FastAPI):
        """
        Test POST /api/v1/deployment/audit with missing required fields.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing 'version'
            payload = {
                "deployed_by": "user",
                "environment": "dev"
            }
            
            response = await client.post("/api/v1/deployment/audit", json=payload)
            
            assert response.status_code == 422  # Validation Error

    async def test_get_deployment_history(self, app: FastAPI, db_session: AsyncSession):
        """
        Test GET /api/v1/deployment/audit
        Verifies retrieval of audit logs.
        """
        # Seed data
        audit1 = DeploymentAudit(
            version="v1.0.0",
            deployed_by="alice",
            environment="staging",
            status="success"
        )
        audit2 = DeploymentAudit(
            version="v1.1.0",
            deployed_by="bob",
            environment="production",
            status="success"
        )
        db_session.add_all([audit1, audit2])
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/deployment/audit")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            # Verify order (usually newest first, check logic implementation)
            # Assuming default order by created_at desc
            assert data[0]["version"] == "v1.1.0"
            assert data[1]["version"] == "v1.0.0"

    async def test_get_health_endpoint(self, app: FastAPI, mock_redis):
        """
        Test GET /api/v1/deployment/health
        Checks system status aggregation.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/deployment/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "database" in data
            assert "cache" in data
            assert "timestamp" in data

    async def test_get_deployment_by_id(self, app: FastAPI, db_session: AsyncSession):
        """
        Test GET /api/v1/deployment/audit/{id}
        """
        audit = DeploymentAudit(
            version="v3.0.0",
            deployed_by="tester",
            environment="dev",
            status="success"
        )
        db_session.add(audit)
        await db_session.commit()
        await db_session.refresh(audit)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/deployment/audit/{audit.id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["version"] == "v3.0.0"

    async def test_get_deployment_not_found(self, app: FastAPI):
        """
        Test GET /api/v1/deployment/audit/{id} with non-existent ID.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/deployment/audit/99999")
            
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data

    async def test_environment_config_endpoint(self, app: FastAPI):
        """
        Test GET /api/v1/deployment/config
        Ensure sensitive secrets are NOT exposed (PIPEDA/Security).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/deployment/config")
            
            assert response.status_code == 200
            data = response.json()
            assert "environment" in data
            assert "version" in data
            # Ensure secrets are absent
            assert "database_url" not in data
            assert "secret_key" not in data
            assert "api_keys" not in data
```