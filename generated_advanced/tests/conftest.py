import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from unittest.mock import AsyncMock, MagicMock

# Import paths based on project conventions
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings
from mortgage_underwriting.modules.auth.routes import router as auth_router

# Use in-memory SQLite for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    yield engine
    engine.sync_engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def app(db_session: AsyncSession) -> FastAPI:
    """
    Create a test application with the auth router.
    Override the dependency for the database session.
    """
    from mortgage_underwriting.common.database import get_async_session
    
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    
    # Dependency override
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async client for integration testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_user_payload():
    return {
        "username": "testuser",
        "password": "SecurePassword123!",
        "email": "test@example.com",
        "full_name": "Test User",
        "sin": "123456789", # PIPEDA: Must be encrypted
        "date_of_birth": "1990-01-01",
        "annual_income": "95000.00" # Decimal required for financial values
    }

@pytest.fixture
def mock_security_service():
    """Mock for security utility functions"""
    from mortgage_underwriting.common.security import encrypt_pii, verify_token, hash_password
    
    # We use patching in tests, but this fixture provides a consistent mock object if needed
    mock_sec = MagicMock()
    mock_sec.encrypt_pii = MagicMock(side_effect=lambda x: f"encrypted_{x}")
    mock_sec.hash_password = MagicMock(side_effect=lambda x: f"hashed_{x}")
    mock_sec.verify_password = MagicMock(return_value=True)
    return mock_sec