```python
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.routes import router
from main import app  # Assuming main.py exists to bootstrap the app

# Using an in-memory SQLite database for speed and isolation in tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_engine():
    """Create a fresh database engine for each test."""
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
    """Create a new database session for each test."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def test_app():
    """Fixture to provide the FastAPI app with the document router included."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/documents", tags=["documents"])
    return app

@pytest.fixture(scope="function")
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Async client for integration tests."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# Unit Test Fixtures
@pytest.fixture
def mock_storage_service():
    """Mock the external storage service (e.g., S3)."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.upload_file.return_value = "https://storage.example.com/docs/123.pdf"
    mock.delete_file.return_value = True
    return mock

@pytest.fixture
def mock_virus_scanner():
    """Mock the virus scanning service."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.scan_file.return_value = True # True = Clean
    return mock

@pytest.fixture
def sample_document_payload():
    """Valid payload for document creation."""
    return {
        "application_id": "app_12345",
        "document_type": "income_verification",
        "file_name": "pay_stub_2023.pdf",
        "mime_type": "application/pdf",
        "metadata": {"month": "October", "year": 2023}
    }

@pytest.fixture
def sample_document_model():
    """A pre-created Document ORM model instance."""
    return Document(
        id="doc_uuid_123",
        application_id="app_12345",
        document_type="income_verification",
        file_name="pay_stub_2023.pdf",
        storage_path="https://storage.example.com/docs/123.pdf",
        status="UPLOADED",
        metadata={"month": "October"},
        created_by="system"
    )
```