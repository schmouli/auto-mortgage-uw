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