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