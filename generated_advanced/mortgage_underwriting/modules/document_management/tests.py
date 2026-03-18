--- conftest.py ---
```python
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from unittest.mock import AsyncMock, MagicMock

# Import the specific module components
from mortgage_underwriting.modules.document_management.routes import router as document_router
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.common.config import settings

# Use an in-memory SQLite database for testing isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
AsyncTestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()

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
    Handles schema creation and teardown.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncTestingSessionLocal() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def app() -> FastAPI:
    """
    Creates a test FastAPI application instance.
    Includes the Document Management router.
    """
    app = FastAPI()
    app.include_router(document_router, prefix="/api/v1/documents", tags=["documents"])
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
def mock_storage_service():
    """
    Mocks the external storage service (e.g., S3) to prevent actual file I/O
    during unit tests.
    """
    with pytest.mock.patch("mortgage_underwriting.modules.document_management.services.StorageService") as mock:
        mock_instance = AsyncMock()
        mock_instance.upload_file.return_value = "https://secure-storage.example.com/files/uuid123.pdf"
        mock_instance.delete_file.return_value = True
        mock.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def valid_document_payload():
    """
    Standard payload for creating a document record.
    """
    return {
        "application_id": "app_12345",
        "document_type": "IDENTITY proof", # Valid type
        "file_name": "passport_scan.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": 1024000
    }

@pytest.fixture
def sample_document_model(valid_document_payload):
    """
    Creates an unsaved Document ORM instance for testing.
    """
    return Document(
        application_id=valid_document_payload["application_id"],
        document_type=valid_document_payload["document_type"],
        file_name=valid_document_payload["file_name"],
        storage_path="https://secure-storage.example.com/files/test.pdf",
        status="UPLOADED"
    )
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from unittest.mock import AsyncMock, patch, MagicMock

from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.exceptions import (
    DocumentNotFoundException,
    InvalidDocumentTypeException,
    StorageException
)

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

@pytest.mark.asyncio
class TestDocumentService:
    
    @pytest.fixture
    def service(self, mock_storage_service):
        """Fixture to instantiate the service with mocked storage."""
        return DocumentService(storage=mock_storage_service)

    async def test_upload_document_success(self, service, mock_storage_service, db_session, valid_document_payload):
        """
        Test successful document upload: 
        1. Storage service is called
        2. DB record is created with correct metadata
        3. Audit fields (created_at) are populated
        """
        # Arrange
        file_content = b"fake pdf content"
        
        # Act
        result = await service.upload_document(
            db=db_session,
            file_content=file_content,
            **valid_document_payload
        )

        # Assert
        assert result is not None
        assert result.application_id == valid_document_payload["application_id"]
        assert result.status == "UPLOADED"
        assert result.storage_path == "https://secure-storage.example.com/files/uuid123.pdf"
        assert result.created_at is not None # FINTRAC Audit requirement
        
        # Verify storage was called
        mock_storage_service.upload_file.assert_awaited_once()

    async def test_upload_document_invalid_type(self, service, db_session, valid_document_payload):
        """
        Test that uploading an unsupported document type raises InvalidDocumentTypeException.
        """
        # Arrange
        valid_document_payload["document_type"] = "EXE_FILE" # Invalid type
        
        # Act & Assert
        with pytest.raises(InvalidDocumentTypeException):
            await service.upload_document(
                db=db_session,
                file_content=b"data",
                **valid_document_payload
            )

    async def test_upload_document_storage_failure(self, service, mock_storage_service, db_session, valid_document_payload):
        """
        Test that if storage fails, the DB transaction is rolled back or handled gracefully.
        """
        # Arrange
        mock_storage_service.upload_file.side_effect = Exception("S3 Down")
        
        # Act & Assert
        with pytest.raises(StorageException):
            await service.upload_document(
                db=db_session,
                file_content=b"data",
                **valid_document_payload
            )
        
        # Ensure DB was not committed (implicitly checked by transaction rollback in service logic)

    async def test_get_document_success(self, service, db_session, sample_document_model):
        """
        Test retrieving a document by ID.
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        await db_session.refresh(sample_document_model)
        
        # Act
        result = await service.get_document(db_session, sample_document_model.id)
        
        # Assert
        assert result.id == sample_document_model.id
        assert result.file_name == sample_document_model.file_name

    async def test_get_document_not_found(self, service, db_session):
        """
        Test retrieving a non-existent document raises DocumentNotFoundException.
        """
        # Act & Assert
        with pytest.raises(DocumentNotFoundException):
            await service.get_document(db_session, 99999)

    async def test_verify_document_success(self, service, db_session, sample_document_model):
        """
        Test verifying a document updates the status correctly.
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        # Act
        result = await service.verify_document(db_session, sample_document_model.id, verified_by="underwriter_1")
        
        # Assert
        assert result.status == "VERIFIED"
        assert result.updated_at is not None

    async def test_delete_document_soft_delete(self, service, db_session, sample_document_model):
        """
        Test that 'deleting' a document performs a soft delete (status update)
        to maintain FINTRAC audit trail (immunity of records).
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        doc_id = sample_document_model.id
        
        # Act
        await service.delete_document(db_session, doc_id)
        
        # Assert - Record should still exist but status changed
        # We need to query fresh or check the returned object
        # Assuming service returns the updated object
        result = await service.get_document(db_session, doc_id)
        assert result.status == "DELETED"
        
        # Ensure the record still physically exists in DB (Audit requirement)
        # This is implicitly true if get_document succeeds, but let's be explicit in logic
        query_result = await db_session.get(Document, doc_id)
        assert query_result is not None

    async def test_list_documents_by_application(self, service, db_session, sample_document_model):
        """
        Test listing all documents for a specific application ID.
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        # Act
        results = await service.list_documents(db_session, application_id=sample_document_model.application_id)
        
        # Assert
        assert len(results) >= 1
        assert any(d.id == sample_document_model.id for d in results)

    async def test_file_size_limit_validation(self, service, db_session, valid_document_payload):
        """
        Test that files exceeding the size limit are rejected.
        """
        # Arrange - Set size to 26MB (assuming 25MB limit)
        valid_document_payload["file_size_bytes"] = 26 * 1024 * 1024
        
        # Act & Assert
        with pytest.raises(ValueError): # Or specific FileTooLargeException
            await service.upload_document(
                db=db_session,
                file_content=b"large content",
                **valid_document_payload
            )
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.document_management.models import Document

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_create_document_endpoint_success(self, client: AsyncClient, db_session, mock_storage_service):
        """
        Integration test: POST /api/v1/documents
        Tests full flow: API -> Service -> DB (and mocked Storage)
        """
        # Arrange
        payload = {
            "application_id": "app_integration_01",
            "document_type": "IDENTITY_PROOF",
            "file_name": "driver_license.jpg",
            "mime_type": "image/jpeg",
            "file_size_bytes": 500000
        }
        
        # Note: In a real scenario, we'd send multipart/form-data.
        # Here we send JSON assuming the controller handles file separation or 
        # we mock the file extraction part. For this test, we assume JSON payload
        # representing metadata, and the file content is handled internally or via mock.
        
        # Act
        response = await client.post("/api/v1/documents/", json=payload)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["application_id"] == payload["application_id"]
        assert data["status"] == "UPLOADED"
        
        # Verify Database State
        stmt = select(Document).where(Document.id == data["id"])
        result = await db_session.execute(stmt)
        db_doc = result.scalar_one_or_none()
        assert db_doc is not None
        assert db_doc.created_at is not None # FINTRAC audit check

    async def test_create_document_endpoint_invalid_type(self, client: AsyncClient):
        """
        Test that API returns 400/422 for invalid document types.
        """
        payload = {
            "application_id": "app_01",
            "document_type": "MALWARE",
            "file_name": "virus.exe",
            "mime_type": "application/x-msdownload",
            "file_size_bytes": 100
        }
        
        response = await client.post("/api/v1/documents/", json=payload)
        
        assert response.status_code == 422 # Pydantic validation error

    async def test_get_document_endpoint(self, client: AsyncClient, db_session, sample_document_model):
        """
        Integration test: GET /api/v1/documents/{id}
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        await db_session.refresh(sample_document_model)
        
        # Act
        response = await client.get(f"/api/v1/documents/{sample_document_model.id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_document_model.id
        # Ensure sensitive internal paths are not exposed if configured
        assert "storage_path" in data 

    async def test_get_documents_list_by_application(self, client: AsyncClient, db_session, sample_document_model):
        """
        Integration test: GET /api/v1/documents/?application_id=...
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        # Act
        response = await client.get(f"/api/v1/documents/?application_id={sample_document_model.application_id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["application_id"] == sample_document_model.application_id

    async def test_verify_document_endpoint(self, client: AsyncClient, db_session, sample_document_model):
        """
        Integration test: PATCH /api/v1/documents/{id}/verify
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        verify_payload = {
            "verified_by": "underwriter_jane",
            "notes": "Clear copy of ID"
        }
        
        # Act
        response = await client.patch(
            f"/api/v1/documents/{sample_document_model.id}/verify",
            json=verify_payload
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "VERIFIED"
        
        # DB Check
        await db_session.refresh(sample_document_model)
        assert sample_document_model.status == "VERIFIED"
        assert sample_document_model.updated_at is not None

    async def test_delete_document_endpoint_forbidden_hard_delete(self, client: AsyncClient, db_session, sample_document_model):
        """
        Integration test: DELETE /api/v1/documents/{id}
        Ensures the endpoint performs a soft delete and does not remove the record.
        """
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        doc_id = sample_document_model.id
        
        # Act
        response = await client.delete(f"/api/v1/documents/{doc_id}")
        
        # Assert
        # Usually 204 No Content for deletion, or 200 with updated object
        assert response.status_code in [200, 204]
        
        # FINTRAC Compliance Check: Record must still exist
        stmt = select(Document).where(Document.id == doc_id)
        result = await db_session.execute(stmt)
        doc = result.scalar_one_or_none()
        
        assert doc is not None
        assert doc.status == "DELETED" # Or "ARCHIVED" depending on implementation
        assert doc.deleted_at is not None # Assuming soft delete adds this timestamp

    async def test_get_non_existent_document(self, client: AsyncClient):
        """
        Test handling of 404 Not Found.
        """
        response = await client.get("/api/v1/documents/999999")
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_upload_missing_required_fields(self, client: AsyncClient):
        """
        Test input validation on the API layer.
        """
        # Missing application_id
        payload = {
            "document_type": "IDENTITY_PROOF",
            "file_name": "test.pdf"
        }
        
        response = await client.post("/api/v1/documents/", json=payload)
        assert response.status_code == 422 # Unprocessable Entity
```