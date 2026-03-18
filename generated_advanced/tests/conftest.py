import pytest
import asyncio
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicy
from mortgage_underwriting.modules.xml_policy_service.routes import router

# Database URL for in-memory SQLite (fast, isolated tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def engine():
    """Create a new engine for each test function."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test."""
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session

@pytest.fixture
def valid_policy_xml() -> str:
    """Returns a valid XML structure for underwriting policy."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Provider>CMHC</Provider>
        <Version>1.0</Version>
        <Rules>
            <MaxLTV>95.00</MaxLTV>
            <MinCreditScore>600</MinCreditScore>
            <StressTestThreshold>5.25</StressTestThreshold>
            <GDSLimit>39.00</GDSLimit>
            <TDSLimit>44.00</TDSLimit>
        </Rules>
    </MortgagePolicy>
    """

@pytest.fixture
def invalid_policy_xml() -> str:
    """Returns a malformed XML string."""
    return "<?xml version='1.0'?><MortgagePolicy><Provider>CMHC"

@pytest.fixture
def non_compliant_policy_xml() -> str:
    """Returns XML that violates OSFI B-20 limits (e.g., TDS > 44%)."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <MortgagePolicy>
        <Provider>RiskyLender</Provider>
        <Version>1.0</Version>
        <Rules>
            <MaxLTV>99.00</MaxLTV>
            <TDSLimit>50.00</TDSLimit>
        </Rules>
    </MortgagePolicy>
    """

@pytest.fixture
def app() -> FastAPI:
    """Fixture for the FastAPI application."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/xml-policy-service", tags=["XML Policy"])
    return app

@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async client for integration testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac