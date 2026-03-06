import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
import uuid

# Assuming the Base is imported from common.database as per conventions
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_intake.models import ClientApplication
from mortgage_underwriting.modules.client_intake.schemas import ClientApplicationCreate

# Database URL for testing (In-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create async engine
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    Handles schema creation and teardown.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def valid_application_payload() -> dict:
    """
    Provides a valid payload for creating a client application.
    Complies with PIPEDA (SIN included for encryption testing) and CMHC (Loan/Value).
    """
    return {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1985-05-15",
        "sin": "123456789", # Will be encrypted/hashed
        "email": "john.doe@example.com",
        "phone_number": "4165550199",
        "property_address": "123 Maple Ave, Toronto, ON",
        "property_value": Decimal("500000.00"),
        "loan_amount": Decimal("400000.00"),
        "down_payment": Decimal("100000.00"),
        "employment_status": "employed",
        "annual_income": Decimal("95000.00")
    }

@pytest.fixture
def high_ltv_payload() -> dict:
    """
    Payload with LTV > 80% to trigger CMHC insurance requirement logic.
    """
    return {
        "first_name": "Jane",
        "last_name": "Smith",
        "date_of_birth": "1990-01-01",
        "sin": "987654321",
        "email": "jane.smith@example.com",
        "phone_number": "6475550199",
        "property_address": "456 Oak St, Vancouver, BC",
        "property_value": Decimal("500000.00"),
        "loan_amount": Decimal("450000.00"), # 90% LTV
        "down_payment": Decimal("50000.00"),
        "employment_status": "employed",
        "annual_income": Decimal("120000.00")
    }

@pytest.fixture
def invalid_payload_missing_sin() -> dict:
    """Invalid payload missing mandatory SIN."""
    return {
        "first_name": "Error",
        "last_name": "Case",
        "date_of_birth": "1990-01-01",
        "email": "error@example.com"
    }