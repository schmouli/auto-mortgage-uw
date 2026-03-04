import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.modules.authentication.routes import router
from fastapi import FastAPI

# Database URL for in-memory SQLite (lightweight for testing)
# Note: Project uses PG 15, but SQLite is standard for isolated unit/integration tests
# unless a specific PG container is mandated.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_engine():
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
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/auth", tags=["Authentication"])
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_user_payload():
    return {
        "username": "test_underwriter",
        "email": "underwriter@example.com",
        "password": "SecurePass123!",
        "role": "underwriter"
    }

@pytest.fixture
def admin_user_payload():
    return {
        "username": "admin_user",
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "role": "admin"
    }

@pytest.fixture
async def seeded_user(db_session: AsyncSession):
    # Helper to create a user directly in DB for login tests
    from mortgage_underwriting.common.security import hash_password
    
    user = User(
        username="existing_user",
        email="existing@example.com",
        hashed_password=hash_password("ExistingPass123!"),
        role="underwriter"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user