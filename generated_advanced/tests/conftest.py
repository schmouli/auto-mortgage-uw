```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Import project specific modules
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_intake.routes import router as client_intake_router
from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.common.config import settings

# Using SQLite for test isolation as permitted by prompt requirements
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

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

@pytest.fixture(scope="function")
def app() -> FastAPI:
    """
    Creates a test FastAPI application instance.
    """
    app = FastAPI()
    app.include_router(client_intake_router, prefix="/api/v1")
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for testing endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_client_payload() -> dict:
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "4165550199",
        "date_of_birth": "1985-05-20",
        "sin": "123456789", # In real scenario, ensure encryption happens
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M4W1A5"
    }

@pytest.fixture
def valid_application_payload() -> dict:
    return {
        "client_id": 1, # Will be overridden in tests
        "property_address": "456 Oak Ave",
        "property_city": "Toronto",
        "property_province": "ON",
        "property_postal_code": "M5B2H1",
        "purchase_price": "500000.00",
        "down_payment": "100000.00",
        "loan_amount": "400000.00",
        "amortization_years": 25,
        "interest_rate": "5.00",
        "employment_status": "employed",
        "employer_name": "Tech Corp",
        "annual_income": "95000.00",
        "monthly_debt_payments": "500.00"
    }
```