--- conftest.py ---
```python
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Ensure pytest-asyncio is used correctly
pytest_plugins = ("pytest_asyncio",)

# Mock Base for testing if actual models aren't fully available in test env context,
# but we usually import the real Base.
# For the purpose of this test file, we assume the project structure exists.

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings

# Use in-memory SQLite for integration tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    Applies migrations/schema creation automatically.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Import all models to ensure they are registered with Base.metadata
    # This is a critical step for SQLAlchemy to know what tables to create
    from mortgage_underwriting.modules.document_management.models import Document

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

@pytest.fixture
def mock_s3_client() -> MagicMock:
    """
    Mocks the S3/Storage client to prevent actual file uploads during tests.
    """
    mock_client = MagicMock()
    mock_client.upload_fileobj = AsyncMock()
    mock_client.delete_object = AsyncMock()
    mock_client.generate_presigned_url = MagicMock(return_value="https://mock-s3-url.com/file.pdf")
    return mock_client

@pytest.fixture
def app(mock_s3_client: MagicMock) -> "FastAPI":
    """
    Creates a test FastAPI app with the Document Management router included.
    Overrides dependencies to use mocks.
    """
    from fastapi import FastAPI
    from mortgage_underwriting.modules.document_management.routes import router
    from mortgage_underwriting.modules.document_management.dependencies import get_storage_client

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/documents", tags=["documents"])

    # Override the storage dependency
    app.dependency_overrides[get_storage_client] = lambda: mock_s3_client

    yield app

    # Clean up overrides
    app.dependency_overrides.clear()

@pytest.fixture
def sample_document_payload() -> dict:
    """Standard payload for document creation."""
    return {
        "borrower_id": 123,
        "file_name": "employment_letter.pdf",
        "document_type": "income_verification",
        "mime_type": "application/pdf"
    }
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

# Absolute imports as per project conventions
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentUpload,
    DocumentResponse,
    DocumentStatusUpdate
)
from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.modules.document_management.exceptions import (
    DocumentUploadError,
    DocumentNotFoundError,
    InvalidFileTypeError
)

@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def mock_db(self):
        """Mock async database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.fixture
    def mock_storage(self):
        """Mock S3/Storage client."""
        storage = MagicMock()
        storage.upload_fileobj = AsyncMock()
        storage.delete_object = AsyncMock()
        storage.generate_presigned_url = MagicMock(return_value="http://secure.url/file")
        return storage

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_storage):
        """Test successful document upload and DB record creation."""
        service = DocumentService(mock_db, mock_storage)
        
        payload = DocumentUpload(
            borrower_id=1,
            file_name="paystub_2023.pdf",
            document_type="income_verification",
            mime_type="application/pdf",
            file_data=b"fake_pdf_content"
        )

        # Mock the DB result after commit to return the object with ID
        def refresh_side_effect(obj):
            obj.id = 999
            obj.created_at = datetime.utcnow()
            obj.updated_at = datetime.utcnow()
        
        mock_db.refresh.side_effect = refresh_side_effect

        result = await service.upload_document(payload)

        # Assertions
        assert isinstance(result, Document)
        assert result.id == 999
        assert result.file_name == "paystub_2023.pdf"
        assert result.status == "uploaded"
        assert result.s3_key is not None
        
        # Verify interactions
        mock_storage.upload_fileobj.assert_awaited_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_invalid_file_type(self, mock_db, mock_storage):
        """Test that uploading an executable file is rejected (Security)."""
        service = DocumentService(mock_db, mock_storage)
        
        payload = DocumentUpload(
            borrower_id=1,
            file_name="virus.exe",
            document_type="other",
            mime_type="application/x-msdownload",
            file_data=b"malicious"
        )

        with pytest.raises(InvalidFileTypeError):
            await service.upload_document(payload)

        # Ensure no DB or S3 operations occurred
        mock_db.add.assert_not_called()
        mock_storage.upload_fileobj.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_document_s3_failure(self, mock_db, mock_storage):
        """Test handling of S3 upload failure."""
        service = DocumentService(mock_db, mock_storage)
        
        payload = DocumentUpload(
            borrower_id=1,
            file_name="doc.pdf",
            document_type="id",
            mime_type="application/pdf",
            file_data=b"data"
        )

        mock_storage.upload_fileobj.side_effect = Exception("S3 Connection Timeout")

        with pytest.raises(DocumentUploadError):
            await service.upload_document(payload)

        # Verify transaction rollback logic (service should handle rollback)
        mock_db.rollback.assert_awaited_once()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, mock_db, mock_storage):
        """Test retrieving an existing document."""
        service = DocumentService(mock_db, mock_storage)
        
        # Mock DB return
        mock_doc = Document(
            id=1,
            borrower_id=1,
            file_name="test.pdf",
            s3_key="docs/test.pdf",
            status="uploaded"
        )
        mock_db.scalar.return_value = mock_doc

        result = await service.get_document_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.file_name == "test.pdf"

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self, mock_db, mock_storage):
        """Test retrieving a non-existent document raises error."""
        service = DocumentService(mock_db, mock_storage)
        mock_db.scalar.return_value = None

        with pytest.raises(DocumentNotFoundError):
            await service.get_document_by_id(999)

    @pytest.mark.asyncio
    async def test_update_document_status_success(self, mock_db, mock_storage):
        """Test updating document status (e.g., Verified)."""
        service = DocumentService(mock_db, mock_storage)
        
        mock_doc = Document(
            id=1,
            borrower_id=1,
            file_name="test.pdf",
            s3_key="docs/test.pdf",
            status="uploaded"
        )
        mock_db.scalar.return_value = mock_doc

        update_payload = DocumentStatusUpdate(status="verified", notes="Clear")
        result = await service.update_document_status(1, update_payload)

        assert result.status == "verified"
        assert result.verification_notes == "Clear"
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_document_soft_delete_logic(self, mock_db, mock_storage):
        """
        Test document deletion. 
        Per FINTRAC, records should be immutable. 
        We expect a soft delete (status change to 'archived' or 'deleted') 
        rather than a hard DB delete, or a specific audit log entry.
        """
        service = DocumentService(mock_db, mock_storage)
        
        mock_doc = Document(
            id=1,
            borrower_id=1,
            file_name="test.pdf",
            s3_key="docs/test.pdf",
            status="uploaded"
        )
        mock_db.scalar.return_value = mock_doc

        await service.delete_document(1)

        # Assuming soft delete implementation for compliance
        assert mock_doc.status == "deleted" or mock_doc.status == "archived"
        mock_db.commit.assert_awaited_once()
        
        # Verify S3 file is also removed for security
        mock_storage.delete_object.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_documents_by_borrower(self, mock_db, mock_storage):
        """Test filtering documents by borrower_id."""
        service = DocumentService(mock_db, mock_storage)
        
        mock_docs = [
            Document(id=1, borrower_id=5, file_name="a.pdf", s3_key="a", status="uploaded"),
            Document(id=2, borrower_id=5, file_name="b.pdf", s3_key="b", status="verified"),
        ]
        
        # Mocking the scalars().all() chain
        mock_result = MagicMock()
        mock_result.all.return_value = mock_docs
        mock_db.scalars.return_value = mock_result

        results = await service.list_documents(borrower_id=5)

        assert len(results) == 2
        assert all(doc.borrower_id == 5 for doc in results)
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from datetime import datetime

# Absolute imports
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_upload_document_endpoint_success(self, app, db_session, mock_s3_client):
        """
        Test the full flow: API Request -> Service -> S3 Mock -> DB.
        """
        # Override the DB dependency to use our test session
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Prepare multipart form data
            files = {
                "file": ("test_income.pdf", b"%PDF-1.4 fake content", "application/pdf")
            }
            data = {
                "borrower_id": "101",
                "document_type": "income_verification"
            }

            response = await client.post("/api/v1/documents/upload", files=files, data=data)

            assert response.status_code == 201
            
            json_resp = response.json()
            assert "id" in json_resp
            assert json_resp["file_name"] == "test_income.pdf"
            assert json_resp["status"] == "uploaded"
            assert json_resp["borrower_id"] == 101
            
            # Verify DB record
            stmt = select(Document).where(Document.id == json_resp["id"])
            result = await db_session.execute(stmt)
            db_doc = result.scalar_one_or_none()
            
            assert db_doc is not None
            assert db_doc.s3_key is not None
            assert db_doc.created_at is not None  # FINTRAC audit check

        app.dependency_overrides.clear()

    async def test_upload_document_unsupported_type(self, app, db_session, mock_s3_client):
        """Test API rejects .exe files."""
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {
                "file": ("bad.exe", b"binary content", "application/x-msdownload")
            }
            data = {
                "borrower_id": "101",
                "document_type": "other"
            }

            response = await client.post("/api/v1/documents/upload", files=files, data=data)

            assert response.status_code == 400
            assert "error_code" in response.json()

        app.dependency_overrides.clear()

    async def test_get_document_endpoint(self, app, db_session, mock_s3_client):
        """Test retrieving a specific document."""
        # Seed data
        new_doc = Document(
            borrower_id=202,
            file_name="id_card.jpg",
            document_type="id_verification",
            s3_key="uploads/id_card.jpg",
            status="uploaded",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(new_doc)
        await db_session.commit()
        await db_session.refresh(new_doc)

        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/documents/{new_doc.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == new_doc.id
            assert data["file_name"] == "id_card.jpg"
            # Ensure PIPEDA compliance: No raw PII in logs (implicit, but we check response structure)
            assert "s3_key" in data # Internal ID might be exposed or not depending on schema, assuming yes here

        app.dependency_overrides.clear()

    async def test_update_status_endpoint(self, app, db_session, mock_s3_client):
        """Test updating document status to 'verified'."""
        # Seed data
        new_doc = Document(
            borrower_id=303,
            file_name="stmt.pdf",
            document_type="income_verification",
            s3_key="u/stmt.pdf",
            status="uploaded",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(new_doc)
        await db_session.commit()
        await db_session.refresh(new_doc)

        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "status": "verified",
                "notes": "Matches application data"
            }
            response = await client.patch(f"/api/v1/documents/{new_doc.id}", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "verified"
            assert data["verification_notes"] == "Matches application data"

            # Verify DB update
            await db_session.refresh(new_doc)
            assert new_doc.status == "verified"
            # Verify audit timestamp update
            assert new_doc.updated_at > new_doc.created_at

        app.dependency_overrides.clear()

    async def test_list_documents_filtering(self, app, db_session, mock_s3_client):
        """Test listing documents filtered by borrower_id."""
        # Seed data for two borrowers
        doc1 = Document(borrower_id=404, file_name="a.pdf", s3_key="a", status="uploaded", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        doc2 = Document(borrower_id=404, file_name="b.pdf", s3_key="b", status="uploaded", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        doc3 = Document(borrower_id=505, file_name="c.pdf", s3_key="c", status="uploaded", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        
        db_session.add_all([doc1, doc2, doc3])
        await db_session.commit()

        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Filter for borrower 404
            response = await client.get("/api/v1/documents", params={"borrower_id": 404})

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert all(d["borrower_id"] == 404 for d in data)

        app.dependency_overrides.clear()

    async def test_delete_document_endpoint(self, app, db_session, mock_s3_client):
        """Test soft delete via endpoint."""
        new_doc = Document(
            borrower_id=606,
            file_name="to_delete.pdf",
            s3_key="del.pdf",
            status="uploaded",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(new_doc)
        await db_session.commit()
        
        doc_id = new_doc.id

        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/documents/{doc_id}")

            assert response.status_code == 204 # No Content

            # Verify Soft Delete in DB
            await db_session.refresh(new_doc)
            assert new_doc.status == "deleted"
            
            # Verify S3 cleanup was called
            mock_s3_client.delete_object.assert_called_once()

        app.dependency_overrides.clear()
```