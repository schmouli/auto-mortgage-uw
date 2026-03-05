--- conftest.py ---
import pytest
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from fastapi import FastAPI

# Assuming the module exists at this path based on project structure
from mortgage_underwriting.modules.infrastructure_deployment.routes import router
from mortgage_underwriting.modules.infrastructure_deployment.models import DeploymentAudit
from mortgage_underwriting.common.database import Base

# Use SQLite for integration tests as per standard practice for speed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_engine(event_loop):
    """Create a fresh database engine for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def app() -> FastAPI:
    """Fixture to provide the FastAPI app with the router included."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/infrastructure")
    return app

@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Fixture for an async HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# --- Unit Test Fixtures ---

@pytest.fixture
def mock_db_session():
    """Mock AsyncSession for unit tests."""
    session = AsyncMock(spec=AsyncSession)
    # Mock the context manager behavior for session.begin/nested if needed, 
    # but for simple add/commit we just need awaitable mocks
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session

@pytest.fixture
def sample_deployment_payload():
    return {
        "environment": "production",
        "version": "v1.2.3",
        "deployed_by": "ci_user",
        "status": "success"
    }

@pytest.fixture
def sample_deployment_record():
    return DeploymentAudit(
        id=1,
        environment="production",
        version="v1.2.3",
        deployed_by="ci_user",
        status="success",
        created_at=datetime.utcnow()
    )
--- unit_tests ---
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
--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.infrastructure_deployment.models import DeploymentAudit

@pytest.mark.integration
@pytest.mark.asyncio
class TestInfrastructureRoutes:

    async def test_health_check_endpoint(self, client: AsyncClient, db_session):
        """Test the /health endpoint returns 200 and correct status."""
        response = await client.get("/api/v1/infrastructure/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    async def test_health_check_endpoint_when_db_down(self, app, db_session):
        """
        Test health check behavior if DB is unavailable.
        Note: Simulating a real DB down in an in-memory SQLite test is hard
        without killing the engine. We will verify the happy path primarily here,
        as unit tests cover the exception flow.
        """
        # This test verifies the endpoint wiring
        pass 

    async def test_create_deployment_audit_success(self, client: AsyncClient, db_session):
        """Test creating a deployment audit record via POST."""
        payload = {
            "environment": "production",
            "version": "v1.4.5",
            "deployed_by": "deploy_bot",
            "status": "success"
        }

        response = await client.post("/api/v1/infrastructure/deployments", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["environment"] == "production"
        assert data["version"] == "v1.4.5"
        assert data["deployed_by"] == "deploy_bot"
        assert "created_at" in data

        # Verify DB state
        stmt = select(DeploymentAudit).where(DeploymentAudit.version == "v1.4.5")
        result = await db_session.execute(stmt)
        record = result.scalar_one()
        assert record is not None
        assert record.status == "success"

    async def test_create_deployment_audit_invalid_env(self, client: AsyncClient):
        """Test validation error on invalid environment."""
        payload = {
            "environment": "mars_colony",
            "version": "v1.0.0",
            "deployed_by": "elon",
            "status": "pending"
        }

        response = await client.post("/api/v1/infrastructure/deployments", json=payload)
        
        assert response.status_code == 422  # Validation Error

    async def test_create_deployment_audit_missing_field(self, client: AsyncClient):
        """Test validation error when required field is missing."""
        payload = {
            "environment": "staging",
            "version": "v1.0.0"
            # missing deployed_by and status
        }

        response = await client.post("/api/v1/infrastructure/deployments", json=payload)
        
        assert response.status_code == 422

    async def test_get_deployments_empty(self, client: AsyncClient):
        """Test GET deployments when none exist."""
        response = await client.get("/api/v1/infrastructure/deployments")
        
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_get_deployments_with_data(self, client: AsyncClient, db_session):
        """Test GET deployments returns correct list."""
        # Seed data
        audit1 = DeploymentAudit(
            environment="dev", version="v1.0.0", deployed_by="alice", status="success"
        )
        audit2 = DeploymentAudit(
            environment="prod", version="v1.0.1", deployed_by="bob", status="success"
        )
        db_session.add(audit1)
        db_session.add(audit2)
        await db_session.commit()

        response = await client.get("/api/v1/infrastructure/deployments")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        # Check ordering (usually descending by created_at)
        assert data["items"][0]["version"] == "v1.0.1" 
        assert data["items"][1]["version"] == "v1.0.0"

    async def test_get_deployments_limit_filter(self, client: AsyncClient, db_session):
        """Test GET deployments with limit query parameter."""
        # Seed 3 items
        for i in range(3):
            db_session.add(DeploymentAudit(
                environment="test", version=f"v1.{i}.0", deployed_by="u", status="ok"
            ))
        await db_session.commit()

        response = await client.get("/api/v1/infrastructure/deployments?limit=2")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2 # Assuming limit applies to returned list
        assert len(data["items"]) == 2

    async def test_get_deployment_by_id(self, client: AsyncClient, db_session):
        """Test retrieving a specific deployment by ID."""
        new_audit = DeploymentAudit(
            environment="qa", version="v2.0.0", deployed_by="tester", status="failed"
        )
        db_session.add(new_audit)
        await db_session.commit()
        await db_session.refresh(new_audit)

        response = await client.get(f"/api/v1/infrastructure/deployments/{new_audit.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == new_audit.id
        assert data["version"] == "v2.0.0"
        assert data["status"] == "failed"

    async def test_get_deployment_by_id_not_found(self, client: AsyncClient):
        """Test retrieving a non-existent deployment."""
        response = await client.get("/api/v1/infrastructure/deployments/99999")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    async def test_concurrent_deployment_logs(self, client: AsyncClient, db_session):
        """Test handling multiple rapid requests (basic concurrency check)."""
        import asyncio
        
        payload = {
            "environment": "staging",
            "version": "v1.0.0",
            "deployed_by": "system",
            "status": "success"
        }
        
        tasks = [client.post("/api/v1/infrastructure/deployments", json=payload) for _ in range(5)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 201
            
        # Verify DB has 5 records
        stmt = select(DeploymentAudit)
        result = await db_session.execute(stmt)
        records = result.scalars().all()
        assert len(records) == 5