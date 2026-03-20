```python
--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
import asyncio

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.infrastructure.models import SystemHealth, DeploymentRecord

# Use an in-memory SQLite database for fast test execution
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_test_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_test_session() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def mock_health_data():
    return {
        "service_name": "postgres_db",
        "status": "healthy",
        "latency_ms": 12
    }

@pytest.fixture
def mock_deployment_data():
    return {
        "version": "v1.4.2",
        "environment": "staging",
        "deployer_id": "user_12345",
        "resource_cost": Decimal("150.00")
    }

@pytest.fixture
def app():
    """
    Fixture to provide the FastAPI application instance.
    In a real scenario, this would import main.app or construct it.
    Here we assume the router is attached to an app for integration testing.
    """
    from fastapi import FastAPI
    from mortgage_underwriting.modules.infrastructure.routes import router
    
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/infrastructure", tags=["infrastructure"])
    return app
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.infrastructure.services import InfrastructureService
from mortgage_underwriting.modules.infrastructure.models import SystemHealth, DeploymentRecord
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestInfrastructureService:
    
    @pytest.fixture
    def service(self):
        # Service doesn't hold state usually, but instantiated per test for clarity
        return InfrastructureService()

    @pytest.mark.asyncio
    async def test_check_database_health_success(self, service):
        """
        Test that database health check returns True when connection is successful.
        """
        mock_db = AsyncMock()
        # Mock the execute call to return a result
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result

        result = await service.check_database_health(mock_db)
        
        assert result is True
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_database_health_failure(self, service):
        """
        Test that database health check returns False when connection fails.
        """
        mock_db = AsyncMock()
        mock_db.execute.side_effect = SQLAlchemyError("Connection failed")

        result = await service.check_database_health(mock_db)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_record_deployment_success(self, service, mock_deployment_data):
        """
        Test successful recording of a deployment event.
        Ensures audit fields are populated.
        """
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock the refresh to populate the object
        def mock_refresh(obj):
            obj.id = 1
            obj.created_at = datetime.utcnow()
        
        mock_db.refresh.side_effect = mock_refresh

        result = await service.record_deployment(mock_db, mock_deployment_data)

        assert isinstance(result, DeploymentRecord)
        assert result.version == mock_deployment_data["version"]
        assert result.environment == mock_deployment_data["environment"]
        assert result.resource_cost == mock_deployment_data["resource_cost"]
        assert result.id is not None
        assert result.created_at is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_deployment_invalid_cost(self, service, mock_deployment_data):
        """
        Test that recording deployment with negative cost raises ValueError.
        Financial validation: Cost cannot be negative.
        """
        mock_db = AsyncMock()
        invalid_data = mock_deployment_data.copy()
        invalid_data["resource_cost"] = Decimal("-50.00")

        with pytest.raises(ValueError) as excinfo:
            await service.record_deployment(mock_db, invalid_data)
        
        assert "Resource cost cannot be negative" in str(excinfo.value)
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_deployment_missing_version(self, service, mock_deployment_data):
        """
        Test that missing version raises appropriate error.
        """
        mock_db = AsyncMock()
        invalid_data = mock_deployment_data.copy()
        del invalid_data["version"]

        with pytest.raises(KeyError):
            await service.record_deployment(mock_db, invalid_data)

    @pytest.mark.asyncio
    async def test_get_system_status_aggregates_correctly(self, service):
        """
        Test that get_system_status aggregates multiple health checks.
        """
        mock_db = AsyncMock()
        
        # Mock the service methods
        with patch.object(service, 'check_database_health', return_value=True), \
             patch.object(service, 'check_external_api_health', return_value=True):
            
            status = await service.get_system_status(mock_db)
            
            assert status["overall_status"] == "healthy"
            assert status["database"] is True
            assert status["external_api"] is True

    @pytest.mark.asyncio
    async def test_get_system_status_degraded_if_one_fails(self, service):
        """
        Test that overall status is 'degraded' if one component fails.
        """
        mock_db = AsyncMock()
        
        with patch.object(service, 'check_database_health', return_value=True), \
             patch.object(service, 'check_external_api_health', return_value=False):
            
            status = await service.get_system_status(mock_db)
            
            assert status["overall_status"] == "degraded"
            assert "database" in status

    @pytest.mark.asyncio
    async def test_log_infrastructure_event_sanitizes_secrets(self, service):
        """
        Test that logging infrastructure events does not leak secrets.
        """
        mock_db = AsyncMock()
        mock_logger = MagicMock()
        
        # Payload containing a fake secret
        payload = {
            "event": "config_update",
            "details": {"api_key": "super_secret_key_123"}
        }

        await service.log_infrastructure_event(mock_db, payload, logger=mock_logger)
        
        # Verify the logger was called
        mock_logger.info.assert_called_once()
        
        # Verify the secret is NOT in the logged message
        call_args = mock_logger.info.call_args[0][0]
        assert "super_secret_key_123" not in call_args
        assert "REDACTED" in call_args or "api_key" not in call_args

--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from decimal import Decimal

from mortgage_underwriting.modules.infrastructure.models import SystemHealth, DeploymentRecord

@pytest.mark.integration
@pytest.mark.asyncio
class TestInfrastructureRoutes:

    async def test_health_check_endpoint_returns_200(self, app):
        """
        Test the GET /health endpoint returns 200 OK and status.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert data["status"] in ["healthy", "degraded", "unhealthy"]
            assert "timestamp" in data

    async def test_create_deployment_record_success(self, app, db_session, mock_deployment_data):
        """
        Test POST /deployments creates a record in DB.
        """
        transport = ASGITransport(app=app)
        
        # We need to override the dependency for the DB session in the route
        # This is typically done in conftest or via app.dependency_overrides
        from mortgage_underwriting.common.database import get_async_session
        
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/infrastructure/deployments", json=mock_deployment_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] > 0
            assert data["version"] == mock_deployment_data["version"]
            assert data["environment"] == mock_deployment_data["environment"]
            assert Decimal(str(data["resource_cost"])) == mock_deployment_data["resource_cost"]
            assert "created_at" in data

        # Cleanup overrides
        app.dependency_overrides = {}

    async def test_create_deployment_record_validates_cost(self, app, db_session, mock_deployment_data):
        """
        Test that negative costs are rejected at the API level.
        """
        transport = ASGITransport(app=app)
        from mortgage_underwriting.common.database import get_async_session
        
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db

        invalid_data = mock_deployment_data.copy()
        invalid_data["resource_cost"] = "-100.00"

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/infrastructure/deployments", json=invalid_data)
            
            # Expecting 422 Unprocessable Entity due to Pydantic validation
            # or 400 if service logic handles it and raises HTTPException
            assert response.status_code in [400, 422]

        app.dependency_overrides = {}

    async def test_list_deployments_pagination(self, app, db_session):
        """
        Test GET /deployments returns a list and handles pagination.
        """
        from mortgage_underwriting.common.database import get_async_session
        
        # Seed data
        deploy1 = DeploymentRecord(
            version="v1.0.0", environment="prod", deployer_id="admin", resource_cost=Decimal("100.00")
        )
        deploy2 = DeploymentRecord(
            version="v1.0.1", environment="prod", deployer_id="admin", resource_cost=Decimal("105.00")
        )
        
        db_session.add(deploy1)
        db_session.add(deploy2)
        await db_session.commit()

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/deployments?limit=10&offset=0")
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert len(data["items"]) >= 2
            assert data["total"] >= 2

        app.dependency_overrides = {}

    async def test_config_endpoint_sanitizes_secrets(self, app):
        """
        Test GET /config returns config but masks sensitive values.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/config")
            
            assert response.status_code == 200
            data = response.json()
            
            # Ensure sensitive keys are present but masked
            if "database_url" in data:
                assert "password" not in data["database_url"]
            
            if "secret_key" in data:
                assert data["secret_key"] == "*****"

    async def test_maintenance_mode_toggle(self, app, db_session):
        """
        Test POST /maintenance toggles maintenance mode.
        """
        from mortgage_underwriting.common.database import get_async_session
        
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Turn on
            response_on = await client.post("/api/v1/infrastructure/maintenance", json={"enabled": True})
            assert response_on.status_code == 200
            assert response_on.json()["maintenance_mode"] is True

            # Turn off
            response_off = await client.post("/api/v1/infrastructure/maintenance", json={"enabled": False})
            assert response_off.status_code == 200
            assert response_off.json()["maintenance_mode"] is False

        app.dependency_overrides = {}
```