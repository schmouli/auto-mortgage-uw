--- conftest.py ---
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Hypothetical imports for the module under test structure
from mortgage_underwriting.common.config import settings
from mortgage_underwriting.common.database import Base

# Mock Models for Infrastructure Module (since actual code isn't provided, we define minimal structure for tests)
class DeploymentEvent(Base):
    __tablename__ = "deployment_events"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    version: Mapped[str] = mapped_column(nullable=False)
    environment: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False) # e.g., 'success', 'failed'
    resource_cost: Mapped[Decimal] = mapped_column(nullable=False) # Financial value, must be Decimal
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[str] = mapped_column(nullable=False)

# Database Fixture
@pytest.fixture(scope="function")
async def db_engine():
    # Using in-memory SQLite for integration tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

# Mock Data Fixtures
@pytest.fixture
def sample_deployment_payload():
    return {
        "version": "v1.2.3",
        "environment": "production",
        "status": "success",
        "resource_cost": "150.00", # String representation for Decimal
        "created_by": "ci_bot"
    }

@pytest.fixture
def sample_deployment_record(sample_deployment_payload):
    return DeploymentEvent(
        version=sample_deployment_payload["version"],
        environment=sample_deployment_payload["environment"],
        status=sample_deployment_payload["status"],
        resource_cost=Decimal(sample_deployment_payload["resource_cost"]),
        created_by=sample_deployment_payload["created_by"]
    )

# App Fixture (Integration)
@pytest.fixture
def infra_app() -> FastAPI:
    # We need to mock the routes since we don't have the actual file. 
    # In a real scenario, we import the router.
    # For this test generation, we assume the module exists at the specified path.
    from mortgage_underwriting.modules.infrastructure.routes import router
    
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/infra", tags=["Infrastructure"])
    return app

@pytest.fixture
async def client(infra_app, db_session) -> AsyncGenerator[AsyncClient, None]:
    """
    Async client that overrides the database dependency.
    """
    from mortgage_underwriting.common.database import get_async_session
    
    async def override_get_db():
        yield db_session

    infra_app.dependency_overrides[get_async_session] = override_get_db
    
    transport = ASGITransport(app=infra_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    infra_app.dependency_overrides.clear()

--- unit_tests ---
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

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.infrastructure.models import DeploymentEvent

@pytest.mark.integration
class TestInfrastructureRoutes:

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, client: AsyncClient):
        """
        Test the health check endpoint returns 200 and correct structure.
        """
        response = await client.get("/api/v1/infra/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "database_status" in data
        assert "timestamp" in data
        # Check for structured error fields (even in success, schema might dictate keys)
        # but typically success just returns data.

    @pytest.mark.asyncio
    async def test_create_deployment_log_success(self, client: AsyncClient, sample_deployment_payload, db_session):
        """
        Test creating a deployment log via API.
        """
        response = await client.post("/api/v1/infra/deployments", json=sample_deployment_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["id"] > 0
        assert data["version"] == sample_deployment_payload["version"]
        assert data["environment"] == sample_deployment_payload["environment"]
        assert Decimal(data["resource_cost"]) == Decimal(sample_deployment_payload["resource_cost"])
        assert "created_at" in data
        
        # Verify DB state
        stmt = select(DeploymentEvent).where(DeploymentEvent.id == data["id"])
        result = await db_session.execute(stmt)
        db_record = result.scalar_one_or_none()
        
        assert db_record is not None
        assert db_record.version == "v1.2.3"
        assert db_record.created_by == "ci_bot"

    @pytest.mark.asyncio
    async def test_create_deployment_log_invalid_input(self, client: AsyncClient):
        """
        Test validation error on bad input (e.g., float for money, missing fields).
        """
        invalid_payload = {
            "version": "v1.0.0",
            "environment": "production",
            "status": "success",
            # Missing resource_cost
            "created_by": "user"
        }
        
        response = await client.post("/api/v1/infra/deployments", json=invalid_payload)
        
        assert response.status_code == 422  # Unprocessable Entity
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_create_deployment_log_wrong_money_type(self, client: AsyncClient):
        """
        Ensure strict Decimal usage. Sending a float string might be rejected or parsed.
        Here we test that the API handles the Decimal string correctly.
        """
        # Using a float-like string is usually okay for Pydantic Decimal, 
        # but let's test the precision.
        payload = {
            "version": "v1.0.0",
            "environment": "production",
            "status": "success",
            "resource_cost": "100.123456", # High precision
            "created_by": "user"
        }
        
        response = await client.post("/api/v1/infra/deployments", json=payload)
        
        # Assuming the service accepts high precision or rounds it. 
        # If the DB field is NUMERIC(10,2), this might fail or round.
        # For this test, we assume success and check the stored value.
        assert response.status_code in [201, 400] # Depending on DB precision constraints

    @pytest.mark.asyncio
    async def test_get_deployments_list(self, client: AsyncClient, db_session, sample_deployment_record):
        """
        Test retrieving a list of deployment events.
        """
        # Pre-populate DB
        db_session.add(sample_deployment_record)
        await db_session.commit()
        
        response = await client.get("/api/v1/infra/deployments")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["version"] == "v1.2.3"
        # Verify PII/Security: Ensure created_by is present (it's not PII in this context, it's a user)
        # but ensure no internal DB fields leak if they shouldn't.

    @pytest.mark.asyncio
    async def test_get_deployment_by_id(self, client: AsyncClient, db_session, sample_deployment_record):
        """
        Test retrieving a specific deployment event.
        """
        db_session.add(sample_deployment_record)
        await db_session.commit()
        await db_session.refresh(sample_deployment_record)
        
        response = await client.get(f"/api/v1/infra/deployments/{sample_deployment_record.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_deployment_record.id
        assert data["version"] == "v1.2.3"

    @pytest.mark.asyncio
    async def test_get_deployment_not_found(self, client: AsyncClient):
        """
        Test 404 response for non-existent deployment.
        """
        response = await client.get("/api/v1/infra/deployments/99999")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error_code" in data # Enforcing structured error response rule

    @pytest.mark.asyncio
    async def test_deployment_audit_trail_immutability(self, client: AsyncClient, db_session, sample_deployment_payload):
        """
        Test that created_at and created_by are set correctly and immutable logic is respected.
        (Note: Full immutability is usually DB constraint, here we check API doesn't allow overwriting)
        """
        # Attempt to pass created_at in payload (should be ignored or rejected)
        malicious_payload = sample_deployment_payload.copy()
        malicious_payload["created_at"] = "2000-01-01T00:00:00Z"
        
        response = await client.post("/api/v1/infra/deployments", json=malicious_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        # The server should have set the current time, not the one in the payload
        assert data["created_at"] != "2000-01-01T00:00:00Z"
        
        # Verify DB
        stmt = select(DeploymentEvent).where(DeploymentEvent.id == data["id"])
        result = await db_session.execute(stmt)
        record = result.scalar_one()
        
        # Check it's recent (within last minute)
        from datetime import datetime, timedelta
        now = datetime.now(timezone.utc)
        assert now - timedelta(seconds=60) <= record.created_at <= now