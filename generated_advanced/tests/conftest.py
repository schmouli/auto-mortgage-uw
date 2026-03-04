import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
import uuid

# Assuming Base is defined in common.database, but we create a local one for test setup if needed
# or import it. For fixture purposes, we will mock the structure or import if available.
# Here we assume the models exist in the module.

@pytest.fixture(scope="session")
def engine():
    """Create an async engine for testing (SQLite in-memory)."""
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for a test."""
    async with engine.begin() as conn:
        # In a real scenario, we would run Alembic migrations here
        # await conn.run_sync(Base.metadata.create_all)
        pass
    
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def sample_applicant_id() -> str:
    return str(uuid.uuid4())

@pytest.fixture
def fintrac_report_payload(sample_applicant_id) -> dict:
    return {
        "applicant_id": sample_applicant_id,
        "transaction_amount": "12500.00", # String to ensure Decimal parsing
        "transaction_type": "large_cash",
        "currency": "CAD",
        "occurrence_date": "2023-10-27T10:00:00Z"
    }

@pytest.fixture
def identity_verification_payload(sample_applicant_id) -> dict:
    return {
        "applicant_id": sample_applicant_id,
        "verification_method": "credit_bureau",
        "verified_by": "underwriter_1",
        "ip_address": "192.168.1.1"
    }

@pytest.fixture
def mock_security_context():
    """Mock the security context for user tracking."""
    return {
        "user_id": "test_user_123",
        "correlation_id": "req-abc-123"
    }