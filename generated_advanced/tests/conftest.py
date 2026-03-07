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