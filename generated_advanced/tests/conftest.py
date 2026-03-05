import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from unittest.mock import AsyncMock, MagicMock

# Mock models and schemas to avoid import errors if module doesn't exist yet in the environment
# In a real scenario, these would be imported from mortgage_underwriting.modules.client_intake
Base = declarative_base()

# Use in-memory SQLite for integration tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app() -> FastAPI:
    """
    Creates a FastAPI app instance including the client_intake router.
    """
    from mortgage_underwriting.modules.client_intake.routes import router
    from mortgage_underwriting.common.database import get_async_session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-intake", tags=["Client Intake"])

    # Dependency override for testing
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for integration testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_security():
    """
    Mocks security functions to avoid actual encryption overhead during unit tests.
    """
    with pytest.mock.patch("mortgage_underwriting.common.security.encrypt_pii") as mock_enc, \
         pytest.mock.patch("mortgage_underwriting.common.security.hash_value") as mock_hash:
        mock_enc.return_value = "encrypted_string"
        mock_hash.return_value = "hashed_string"
        yield mock_enc, mock_hash


@pytest.fixture
def valid_client_payload():
    return {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-01",
        "sin": "123456789",
        "email": "john.doe@example.com",
        "phone_number": "+14155552671",
        "address": {
            "street": "123 Main St",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M5V1A1"
        }
    }

@pytest.fixture
def valid_application_payload():
    return {
        "client_id": 1, # Assumed existing client
        "property_value": "500000.00",
        "down_payment": "100000.00",
        "loan_amount": "400000.00",
        "amortization_years": 25,
        "interest_rate": "5.00",
        "income_monthly": "8000.00",
        "property_tax_monthly": "300.00",
        "heating_monthly": "150.00"
    }