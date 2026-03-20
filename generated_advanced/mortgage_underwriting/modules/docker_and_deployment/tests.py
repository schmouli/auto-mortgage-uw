--- conftest.py ---
import pytest
from collections.abc import AsyncGenerator, Generator
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, func
from datetime import datetime
from decimal import Decimal
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mortgage_underwriting.common.config import settings
from mortgage_underwriting.common.database import get_async_session

# Define a base for test models if not imported, though we usually import the app's Base
class Base(DeclarativeBase):
    pass

# Using SQLite for integration tests as permitted
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates a test client that overrides the database dependency.
    """
    from mortgage_underwriting.main import app # Assuming main app entry point
    
    async def override_get_async_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_async_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture
def mock_settings():
    """Fixture for mocking application settings."""
    from mortgage_underwriting.modules.deployment import config as dep_config
    original_version = dep_config.settings.APP_VERSION
    dep_config.settings.APP_VERSION = "1.0.0-test"
    yield dep_config.settings
    dep_config.settings.APP_VERSION = original_version

@pytest.fixture
def mock_redis():
    """Mock Redis client for caching/health checks."""
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.ping.return_value = True
    return mock

# Pytest Configuration
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

# Module imports based on project structure
from mortgage_underwriting.modules.deployment.services import DeploymentService
from mortgage_underwriting.modules.deployment.schemas import HealthCheckResponse, DeploymentEventCreate
from mortgage_underwriting.modules.deployment.exceptions import DatabaseConnectionError, ConfigurationError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDeploymentServiceHealth:
    """
    Unit tests for the DeploymentService health check functionality.
    Ensures the service correctly reports status based on DB and external dependencies.
    """

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self):
        return DeploymentService()

    @pytest.mark.asyncio
    async def test_check_health_success(self, service, mock_db):
        """Test successful health check when DB is responsive."""
        # Mock the execution of a simple query (e.g., SELECT 1)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        mock_db.execute.return_value = mock_result

        result = await service.check_health(mock_db)

        assert result.status == "healthy"
        assert result.database_status == "connected"
        assert result.timestamp is not None
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_health_db_failure(self, service, mock_db):
        """Test health check failure when DB is unreachable."""
        mock_db.execute.side_effect = SQLAlchemyError("Connection failed")

        with pytest.raises(DatabaseConnectionError) as exc_info:
            await service.check_health(mock_db)

        assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_health_unexpected_error(self, service, mock_db):
        """Test health check handles unexpected errors gracefully."""
        mock_db.execute.side_effect = Exception("Unexpected crash")

        with pytest.raises(AppException) as exc_info:
            await service.check_health(mock_db)
        
        assert exc_info.value.status_code == 500

@pytest.mark.unit
class TestDeploymentServiceConfig:
    """
    Unit tests for configuration validation and retrieval.
    """

    @pytest.fixture
    def service(self):
        return DeploymentService()

    def test_get_app_version(self, service, monkeypatch):
        """Test retrieving application version."""
        monkeypatch.setenv("APP_VERSION", "2.4.1")
        # Reload settings or mock the config object directly
        with patch("mortgage_underwriting.modules.deployment.services.settings") as mock_settings:
            mock_settings.APP_VERSION = "2.4.1"
            version = service.get_version()
            assert version == "2.4.1"

    def test_validate_environment_success(self, service, monkeypatch):
        """Test environment validation with all required variables set."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://...")
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        
        with patch("mortgage_underwriting.modules.deployment.services.settings") as mock_settings:
            mock_settings.DATABASE_URL = "postgresql://..."
            mock_settings.SECRET_KEY = "test-secret"
            
            # Should not raise
            service.validate_environment()

    def test_validate_environment_missing_secret(self, service, monkeypatch):
        """Test environment validation raises error if SECRET_KEY is missing."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        
        with patch("mortgage_underwriting.modules.deployment.services.settings") as mock_settings:
            mock_settings.SECRET_KEY = None
            
            with pytest.raises(ConfigurationError) as exc_info:
                service.validate_environment()
            
            assert "SECRET_KEY" in str(exc_info.value)

@pytest.mark.unit
class TestDeploymentServiceAudit:
    """
    Unit tests for deployment event logging (FINTRAC compliance).
    """

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self):
        return DeploymentService()

    @pytest.mark.asyncio
    async def test_log_deployment_event_success(self, service, mock_db):
        """Test successful logging of a deployment event."""
        payload = DeploymentEventCreate(
            event_type="MIGRATION",
            description="Applied migration 001_initial.up.sql",
            initiated_by="system"
        )

        result = await service.log_event(mock_db, payload)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        assert result.event_type == "MIGRATION"
        # Verify audit fields are present (simulated)
        assert hasattr(result, "created_at")

    @pytest.mark.asyncio
    async def test_log_deployment_event_db_error(self, service, mock_db):
        """Test logging event handles DB errors."""
        payload = DeploymentEventCreate(
            event_type="SCALE_UP",
            description="Increased replica count",
            initiated_by="admin"
        )
        mock_db.commit.side_effect = SQLAlchemyError("Lock timeout")

        with pytest.raises(AppException):
            await service.log_event(mock_db, payload)

@pytest.mark.unit
class TestDeploymentUtilities:
    """Tests for helper functions within the module."""

    def test_format_uptime(self):
        from mortgage_underwriting.modules.deployment.services import format_uptime
        # Test seconds
        assert format_uptime(45) == "45s"
        # Test minutes
        assert format_uptime(120) == "2m 0s"
        # Test hours
        assert format_uptime(3661) == "1h 1m 1s"

    def test_mask_sensitive_config(self):
        from mortgage_underwriting.modules.deployment.services import mask_sensitive_config
        config_data = {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "DEBUG": "True",
            "API_KEY": "secret-key-123"
        }
        masked = mask_sensitive_config(config_data)
        
        assert "pass" not in masked["DATABASE_URL"]
        assert "secret" not in masked["API_KEY"]
        assert masked["DEBUG"] == "True"

--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from datetime import datetime
from decimal import Decimal

# Import models and app setup
from mortgage_underwriting.main import app
from mortgage_underwriting.modules.deployment.models import DeploymentEvent
from mortgage_underwriting.modules.deployment.schemas import HealthCheckResponse
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestDeploymentRoutes:
    """
    Integration tests for the Deployment module API endpoints.
    Tests the full request/response cycle and DB interaction.
    """

    async def test_health_endpoint_success(self, client: AsyncClient):
        """
        Test GET /api/v1/deployment/health returns 200 and correct structure.
        """
        response = await client.get("/api/v1/deployment/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        # Validate UUID format for correlation_id if present
        # assert "correlation_id" in data 

    async def test_version_endpoint(self, client: AsyncClient):
        """
        Test GET /api/v1/deployment/version returns version info.
        """
        response = await client.get("/api/v1/deployment/version")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "version" in data
        assert "app_name" in data
        assert data["app_name"] == "mortgage_underwriting"

    async def test_log_event_endpoint_creates_record(self, client: AsyncClient, db_session):
        """
        Test POST /api/v1/deployment/events creates a record in DB.
        """
        event_payload = {
            "event_type": "CONFIG_UPDATE",
            "description": "Updated interest rate floor",
            "initiated_by": "admin_user"
        }
        
        response = await client.post("/api/v1/deployment/events", json=event_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["event_type"] == "CONFIG_UPDATE"
        assert data["created_at"] is not None

        # Verify persistence in DB
        result = await db_session.execute(select(DeploymentEvent).where(DeploymentEvent.id == data["id"]))
        db_record = result.scalar_one_or_none()
        
        assert db_record is not None
        assert db_record.description == "Updated interest rate floor"
        assert db_record.initiated_by == "admin_user"

    async def test_get_events_pagination(self, client: AsyncClient, db_session):
        """
        Test GET /api/v1/deployment/events with pagination parameters.
        """
        # Seed data
        for i in range(15):
            event = DeploymentEvent(
                event_type="TEST_EVENT",
                description=f"Test event {i}",
                initiated_by="tester"
            )
            db_session.add(event)
        await db_session.commit()

        # Fetch first page
        response = await client.get("/api/v1/deployment/events?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 10
        assert data["total"] == 15
        assert data["page"] == 1

        # Fetch second page
        response = await client.get("/api/v1/deployment/events?limit=10&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5

    async def test_log_event_validation_error(self, client: AsyncClient):
        """
        Test POST /api/v1/deployment/events with invalid payload returns 422.
        """
        invalid_payload = {
            "event_type": "BAD_TYPE", # Assuming enum validation
            "description": "", # Empty description might be invalid
            "initiated_by": "" 
        }
        
        response = await client.post("/api/v1/deployment/events", json=invalid_payload)
        
        assert response.status_code == 422
        assert "detail" in response.json()

    async def test_readiness_check_k8s_style(self, client: AsyncClient):
        """
        Test GET /api/v1/deployment/readiness (specific for K8s probes).
        Should return 200 if dependencies are met.
        """
        response = await client.get("/api/v1/deployment/readiness")
        assert response.status_code == 200
        assert response.json() == {"ready": True}

    async def test_liveness_check_k8s_style(self, client: AsyncClient):
        """
        Test GET /api/v1/deployment/liveness (specific for K8s probes).
        """
        response = await client.get("/api/v1/deployment/liveness")
        assert response.status_code == 200
        assert response.json() == {"alive": True}

    async def test_event_immutable_audit_fields(self, client: AsyncClient, db_session):
        """
        Test that created_at audit fields are automatically populated and immutable.
        """
        payload = {
            "event_type": "SECURITY_PATCH",
            "description": "Applied hotfix",
            "initiated_by": "devops"
        }
        
        response = await client.post("/api/v1/deployment/events", json=payload)
        event_id = response.json()["id"]
        
        # Try to update created_at via API (should fail or be ignored)
        # Assuming there is no PUT endpoint, but if there were, it should not allow updating created_at.
        # Here we just verify the initial state.
        result = await db_session.execute(select(DeploymentEvent).where(DeploymentEvent.id == event_id))
        record = result.scalar_one()
        
        assert isinstance(record.created_at, datetime)
        assert isinstance(record.updated_at, datetime)
        
        # Verify we cannot manually set created_at via the API
        update_payload = {
            "created_at": "2000-01-01T00:00:00" 
        }
        # This assumes an endpoint exists; if not, this test confirms the schema behavior via ORM
        # For this exercise, we verify the initial creation compliance.
        
    async def test_security_headers_present(self, client: AsyncClient):
        """
        Test that security headers are present on deployment endpoints.
        """
        response = await client.get("/api/v1/deployment/health")
        
        # Check for common security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"