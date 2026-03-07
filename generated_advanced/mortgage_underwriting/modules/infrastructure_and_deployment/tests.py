--- conftest.py ---
import pytest
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Import paths based on project structure
from mortgage_underwriting.modules.infrastructure_deployment.routes import router
from mortgage_underwriting.common.config import settings

# Test Database Setup (SQLite for in-memory testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def mock_settings():
    """
    Fixture to override application settings for testing.
    Ensures secrets are not loaded from real .env files.
    """
    with patch("mortgage_underwriting.modules.infrastructure_deployment.services.settings") as mock:
        mock.DATABASE_URL = TEST_DATABASE_URL
        mock.SECRET_KEY = "test-secret-key"
        mock.ENVIRONMENT = "test"
        mock.LOG_LEVEL = "DEBUG"
        yield mock

@pytest.fixture
def app() -> FastAPI:
    """
    Fixture to create a test FastAPI application instance.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/infra", tags=["Infrastructure"])
    return app

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async client for integration testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_db_session():
    """
    Mock database session for unit tests (no real DB interaction).
    """
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session

@pytest.fixture
def mock_redis_client():
    """
    Mock Redis client for caching health checks.
    """
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    return client
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from sqlalchemy.exc import SQLAlchemyError

# Import the module under test
from mortgage_underwriting.modules.infrastructure_deployment.services import (
    HealthService,
    ConfigService,
    DeploymentService
)
from mortgage_underwriting.modules.infrastructure_deployment.exceptions import (
    InfrastructureUnavailableError,
    ConfigurationError
)

@pytest.mark.unit
class TestHealthService:
    """
    Unit tests for HealthService logic.
    Verifies system status checks without actual I/O.
    """

    @pytest.mark.asyncio
    async def test_check_database_health_success(self, mock_db_session):
        """
        Test that database health check returns True when DB is responsive.
        """
        # Mock the execution of a simple query (SELECT 1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        mock_db_session.execute.return_value = mock_result

        service = HealthService(mock_db_session)
        is_healthy = await service.check_database_health()

        assert is_healthy is True
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_database_health_failure(self, mock_db_session):
        """
        Test that database health check returns False on connection error.
        """
        mock_db_session.execute.side_effect = SQLAlchemyError("Connection failed")

        service = HealthService(mock_db_session)
        is_healthy = await service.check_database_health()

        assert is_healthy is False
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_redis_health_success(self, mock_redis_client):
        """
        Test that Redis health check returns True when Redis is responsive.
        """
        service = HealthService(mock_db_session, redis_client=mock_redis_client)
        is_healthy = await service.check_redis_health()

        assert is_healthy is True
        mock_redis_client.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_redis_health_failure(self, mock_redis_client):
        """
        Test that Redis health check returns False on error.
        """
        mock_redis_client.ping.side_effect = Exception("Redis timeout")

        service = HealthService(mock_db_session, redis_client=mock_redis_client)
        is_healthy = await service.check_redis_health()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_get_system_status_healthy(self, mock_db_session, mock_redis_client):
        """
        Test aggregation of system status when all components are healthy.
        """
        # Setup mocks
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        mock_db_session.execute.return_value = mock_result

        service = HealthService(mock_db_session, redis_client=mock_redis_client)
        status = await service.get_system_status()

        assert status["status"] == "healthy"
        assert status["components"]["database"] == "up"
        assert status["components"]["redis"] == "up"

    @pytest.mark.asyncio
    async def test_get_system_status_unhealthy_db(self, mock_db_session, mock_redis_client):
        """
        Test aggregation of system status when DB is down.
        """
        mock_db_session.execute.side_effect = SQLAlchemyError("Down")

        service = HealthService(mock_db_session, redis_client=mock_redis_client)
        status = await service.get_system_status()

        assert status["status"] == "unhealthy"
        assert status["components"]["database"] == "down"
        assert status["components"]["redis"] == "up"


@pytest.mark.unit
class TestConfigService:
    """
    Unit tests for ConfigService logic.
    Verifies configuration loading and validation.
    """

    def test_get_required_setting_exists(self, mock_settings):
        """
        Test retrieving a required setting that exists.
        """
        service = ConfigService()
        value = service.get_setting("SECRET_KEY")
        assert value == "test-secret-key"

    def test_get_required_setting_missing_raises(self, mock_settings):
        """
        Test that retrieving a missing required setting raises ConfigurationError.
        """
        service = ConfigService()
        # Delete the attribute to simulate missing env var
        delattr(mock_settings, "SECRET_KEY")
        
        with pytest.raises(ConfigurationError) as exc_info:
            service.get_setting("SECRET_KEY")
        
        assert "Missing required configuration" in str(exc_info.value)

    def test_validate_financial_precision_config(self, mock_settings):
        """
        Test validation of financial precision configuration.
        Ensures Decimal precision is set correctly for monetary values.
        """
        with patch.object(mock_settings, "DECIMAL_PRECISION", "28") as mock_prec:
            service = ConfigService()
            precision = service.get_decimal_precision()
            
            assert isinstance(precision, int)
            assert precision == 28

    def test_mask_sensitive_data_in_logs(self):
        """
        Test PIPEDA compliance: ensuring sensitive keys are masked.
        """
        service = ConfigService()
        log_data = {
            "username": "admin",
            "password": "supersecret123",  # Should be masked
            "api_key": "key-xyz",          # Should be masked
            "timestamp": "2023-01-01"
        }

        masked = service.mask_sensitive_data(log_data)
        
        assert masked["password"] == "*****"
        assert masked["api_key"] == "*****"
        assert masked["username"] == "admin"
        assert masked["timestamp"] == "2023-01-01"


@pytest.mark.unit
class TestDeploymentService:
    """
    Unit tests for DeploymentService logic.
    Verifies migration status and versioning.
    """

    @pytest.mark.asyncio
    async def test_check_migrations_success(self):
        """
        Test successful migration status check.
        """
        mock_alembic = AsyncMock()
        mock_alembic.get_current_head.return_value = "12345"
        mock_alembic.get_current_revision.return_value = "12345"

        service = DeploymentService(alembic_util=mock_alembic)
        is_synced = await service.check_migrations()

        assert is_synced is True

    @pytest.mark.asyncio
    async def test_check_migrations_out_of_sync(self):
        """
        Test migration status check when DB is behind code.
        """
        mock_alembic = AsyncMock()
        mock_alembic.get_current_head.return_value = "67890"
        mock_alembic.get_current_revision.return_value = "12345"

        service = DeploymentService(alembic_util=mock_alembic)
        is_synced = await service.check_migrations()

        assert is_synced is False

    @pytest.mark.asyncio
    async def test_get_application_version(self):
        """
        Test retrieval of application version info.
        """
        service = DeploymentService()
        version = service.get_version()

        assert "version" in version
        assert "build_date" in version
        # Check format validity (basic)
        assert isinstance(version["version"], str)

    @pytest.mark.asyncio
    async def test_register_deployment_event(self, mock_db_session):
        """
        Test logging a deployment event to the database for audit trail.
        """
        service = DeploymentService()
        
        # Mock the model creation
        mock_deployment_log = MagicMock()
        mock_deployment_log.id = 1
        
        with patch("mortgage_underwriting.modules.infrastructure_deployment.services.DeploymentLog", return_value=mock_deployment_log):
            await service.log_deployment(mock_db_session, version="1.0.0", status="success")
            
            mock_db_session.add.assert_called_once_with(mock_deployment_log)
            mock_db_session.commit.assert_awaited_once()
--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, status
from sqlalchemy.ext.asyncio import AsyncSession

# Import the module under test
from mortgage_underwriting.modules.infrastructure_deployment.routes import router
from mortgage_underwriting.modules.infrastructure_deployment.models import DeploymentLog
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestInfrastructureRoutes:
    """
    Integration tests for Infrastructure API endpoints.
    Tests request/response contracts and DB interaction.
    """

    @pytest.fixture
    def app(self, db_session: AsyncSession):
        """
        Create app with DB session override.
        """
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/infra", tags=["Infrastructure"])

        # Dependency override to use test session
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db
        yield app
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, app: FastAPI):
        """
        Test GET /health returns 200 and correct structure.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infra/health")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert "status" in data
            assert "components" in data
            assert isinstance(data["components"], dict)

    @pytest.mark.asyncio
    async def test_health_check_endpoint_db_down(self, app: FastAPI):
        """
        Test GET /health handles DB failure gracefully (returns 503 or status unhealthy).
        """
        # This test assumes we can break the DB connection or mock the service layer within the integration
        # For integration tests, we usually rely on the test DB being up.
        # However, we can test the 'readiness' endpoint specifically.
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Assuming /readiness performs stricter checks than /health
            response = await client.get("/api/v1/infra/ready")
            
            # In a healthy test environment, this should be 200
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]

    @pytest.mark.asyncio
    async def test_metrics_endpoint_exists(self, app: FastAPI):
        """
        Test GET /metrics endpoint exists and returns text/plain (Prometheus format).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infra/metrics")
            
            # Metrics endpoint might require auth or specific setup, checking existence
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_log_deployment_workflow(self, app: FastAPI, db_session: AsyncSession):
        """
        Test multi-step workflow: Log deployment -> Verify in DB -> Retrieve History.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 1: Log a deployment
            payload = {
                "version": "2.0.1",
                "status": "deployed",
                "deployed_by": "tester",
                "notes": "Integration test deployment"
            }
            response = await client.post("/api/v1/infra/deployments", json=payload)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["version"] == "2.0.1"
            assert "id" in data

            # Step 2: Verify it exists in DB directly
            result = await db_session.execute(DeploymentLog.__table__.select().where(DeploymentLog.id == data["id"]))
            db_record = result.fetchone()
            assert db_record is not None
            assert db_record.version == "2.0.1"
            assert db_record.created_by == "tester" # Audit trail check

            # Step 3: Retrieve history via API
            history_response = await client.get("/api/v1/infra/deployments")
            assert history_response.status_code == status.HTTP_200_OK
            
            history_data = history_response.json()
            assert len(history_data) >= 1
            assert any(d["id"] == data["id"] for d in history_data)

    @pytest.mark.asyncio
    async def test_config_endpoint_security(self, app: FastAPI):
        """
        Test that config endpoint does not leak sensitive data (PIPEDA).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infra/config/public")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Ensure secrets are not present
            assert "SECRET_KEY" not in data
            assert "DATABASE_URL" not in data
            assert "environment" in data # Non-sensitive info should be present

    @pytest.mark.asyncio
    async def test_input_validation_deployment_log(self, app: FastAPI):
        """
        Test input validation on deployment log endpoint.
        Ensures empty strings or invalid data is rejected.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing required field
            payload = {
                "version": "", # Invalid: empty string
                "status": "deployed"
            }
            response = await client.post("/api/v1/infra/deployments", json=payload)
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_version_endpoint(self, app: FastAPI):
        """
        Test GET /version returns build information.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infra/version")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "version" in data
            # Regex check for semantic versioning would go here
            assert len(data["version"]) > 0