import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings
from mortgage_underwriting.modules.client_intake.routes import router as client_intake_router
from mortgage_underwriting.modules.client_intake.models import Client, Application

# Use in-memory SQLite for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(client_intake_router, prefix="/api/v1/client-intake", tags=["Client Intake"])
    return app

@pytest.fixture(scope="function")
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_client_payload() -> dict:
    return {
        "first_name": "John",
        "last_name": "Doe",
        "sin": "123456789",
        "dob": "1985-05-20",
        "email": "john.doe@example.com",
        "phone": "4165550199",
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M4W1A5"
    }

@pytest.fixture
def valid_application_payload() -> dict:
    return {
        "client_id": 1, # Will be replaced in tests
        "requested_amount": "450000.00",
        "property_value": "500000.00",
        "property_type": "detached",
        "property_address": "123 Maple St",
        "property_city": "Toronto",
        "property_province": "ON",
        "property_postal_code": "M4W1A5"
    }

@pytest.fixture
def mock_security():
    """Mock security functions to avoid real encryption overhead in unit tests."""
    from unittest.mock import MagicMock
    with pytest.mock.patch("mortgage_underwriting.common.security.encrypt_pii", return_value="encrypted_string") as m1, \
         pytest.mock.patch("mortgage_underwriting.common.security.hash_sin", return_value="hashed_sin") as m2:
        yield m1, m2