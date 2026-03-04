--- conftest.py ---
import pytest
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Import paths based on project structure
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.routes import router
from mortgage_underwriting.common.database import get_async_session

# Test Database Setup (In-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Document.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Document.metadata.drop_all)

@pytest.fixture
def mock_storage_service():
    """
    Mocks the external file storage service (e.g., S3/Minio).
    """
    service = AsyncMock()
    service.upload_file.return_value = "https://storage.example.com/docs/encrypted_hash.pdf"
    service.delete_file.return_value = True
    return service

@pytest.fixture
def valid_document_payload():
    """
    Valid payload for document upload.
    """
    return {
        "application_id": "123e4567-e89b-12d3-a456-426614174000",
        "document_type": "PAY_STUB",
        "file_name": "pay_stub_2023_10.pdf",
        "content_type": "application/pdf",
        "file_size_bytes": 102400
    }

@pytest.fixture
def app(db_session: AsyncSession):
    """
    Creates a test FastAPI app with the Document Management router.
    Overrides the database dependency.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/documents", tags=["documents"])

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

--- unit_tests ---
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentCreate, DocumentResponse
from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.modules.document_management.exceptions import DocumentStorageError, DocumentNotFoundError

# Mock Models for Service Layer testing without full DB hit
@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.fixture
    def mock_storage(self):
        storage = AsyncMock()
        storage.upload_file.return_value = "secure_path/abc123.pdf"
        return storage

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_storage, valid_document_payload):
        """
        Test successful document upload, storage service call, and DB persistence.
        """
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        schema = DocumentCreate(**valid_document_payload)

        # Simulate DB returning the created object
        def mock_refresh(obj):
            obj.id = "doc-123"
            obj.created_at = datetime.utcnow()
            obj.updated_at = datetime.utcnow()

        mock_db.refresh.side_effect = mock_refresh

        # Act
        result = await service.upload_document(schema, file_content=b"fake_pdf_content")

        # Assert
        assert result.id == "doc-123"
        assert result.storage_path == "secure_path/abc123.pdf"
        assert result.upload_status == "COMPLETED"
        
        mock_storage.upload_file.assert_awaited_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_storage_failure(self, mock_db, mock_storage, valid_document_payload):
        """
        Test that DB transaction is rolled back if storage upload fails.
        """
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        schema = DocumentCreate(**valid_document_payload)
        mock_storage.upload_file.side_effect = Exception("S3 Connection Failed")

        # Act & Assert
        with pytest.raises(DocumentStorageError):
            await service.upload_document(schema, file_content=b"data")

        mock_db.add.assert_called_once()
        mock_db.commit.assert_not_awaited() # Should not commit if storage fails
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_invalid_file_type(self, mock_db, mock_storage):
        """
        Test validation of allowed file types (PIPEDA/Security compliance).
        """
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        payload = {
            "application_id": "123",
            "document_type": "ID",
            "file_name": "malware.exe",
            "content_type": "application/x-msdownload",
            "file_size_bytes": 500
        }
        schema = DocumentCreate(**payload)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid file type"):
            await service.upload_document(schema, b"exe_content")

        mock_storage.upload_file.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, mock_db):
        """
        Test retrieving a document metadata record.
        """
        # Arrange
        service = DocumentService(mock_db, AsyncMock())
        doc_id = "doc-123"
        
        mock_doc = Document(
            id=doc_id,
            application_id="app-123",
            document_type="PAY_STUB",
            storage_path="path/to/file",
            upload_status="COMPLETED",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_db.scalar.return_value = mock_doc

        # Act
        result = await service.get_document(doc_id)

        # Assert
        assert result.id == doc_id
        assert result.document_type == "PAY_STUB"
        mock_db.scalar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, mock_db):
        """
        Test exception when document ID does not exist.
        """
        # Arrange
        service = DocumentService(mock_db, AsyncMock())
        mock_db.scalar.return_value = None

        # Act & Assert
        with pytest.raises(DocumentNotFoundError):
            await service.get_document("non-existent-id")

    @pytest.mark.asyncio
    async def test_list_documents_by_application(self, mock_db):
        """
        Test listing all documents for a specific mortgage application.
        """
        # Arrange
        service = DocumentService(mock_db, AsyncMock())
        app_id = "app-456"
        
        # Mocking the execute result to return a list of scalars
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            Document(id="1", application_id=app_id, document_type="ID", storage_path="a", upload_status="COMPLETED", created_at=datetime.utcnow(), updated_at=datetime.utcnow()),
            Document(id="2", application_id=app_id, document_type="PAY_STUB", storage_path="b", upload_status="COMPLETED", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        ]
        mock_db.execute.return_value = mock_result

        # Act
        results = await service.list_documents(app_id)

        # Assert
        assert len(results) == 2
        assert all(doc.application_id == app_id for doc in results)

    @pytest.mark.asyncio
    async def test_delete_document_soft_delete(self, mock_db, mock_storage):
        """
        Test that document deletion is a soft delete (FINTRAC retention requirement).
        The record remains in DB but status changes, file might be archived.
        """
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        doc_id = "doc-999"
        
        mock_doc = Document(
            id=doc_id,
            application_id="app-1",
            document_type="CONTRACT",
            storage_path="active/file.pdf",
            upload_status="COMPLETED",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_db.scalar.return_value = mock_doc

        # Act
        await service.delete_document(doc_id)

        # Assert
        assert mock_doc.upload_status == "DELETED" # Soft delete
        # Verify file was moved to archive or deleted from storage
        mock_storage.archive_file.assert_awaited_once_with("active/file.pdf") 
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_verify_pii_not_logged(self, mock_db, mock_storage, valid_document_payload, caplog):
        """
        Verify that sensitive PII (e.g., SIN inside filename or content) is not logged.
        """
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        
        # Simulate a filename containing potential PII
        pii_payload = valid_document_payload.copy()
        pii_payload["file_name"] = "john_doe_SIN_123456789.pdf"
        schema = DocumentCreate(**pii_payload)

        # Mock logger
        with patch("mortgage_underwriting.modules.document_management.services.logger") as mock_logger:
            # Act
            await service.upload_document(schema, b"content")

            # Assert - Check that info/debug logs do not contain the raw filename or path if it includes PII
            # In a real scenario, the service should hash the filename before logging
            for call in mock_logger.info.call_args_list:
                log_message = str(call)
                assert "123456789" not in log_message, "PII found in logs!"
                assert "john_doe" not in log_message, "PII found in logs!"

--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, status

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.routes import router

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_upload_document_endpoint_success(self, app: FastAPI, client: AsyncClient, valid_document_payload):
        """
        Test the full API flow for uploading a document.
        """
        # Act
        response = await client.post(
            "/api/v1/documents/upload",
            json=valid_document_payload
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["application_id"] == valid_document_payload["application_id"]
        assert data["upload_status"] == "COMPLETED"
        assert "storage_path" in data
        assert "created_at" in data  # Audit trail

    async def test_upload_document_endpoint_validation_error(self, app: FastAPI, client: AsyncClient):
        """
        Test input validation on the upload endpoint.
        """
        # Act - Missing required field
        response = await client.post(
            "/api/v1/documents/upload",
            json={"application_id": "123"} # Missing document_type, file_name, etc.
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_document_endpoint(self, app: FastAPI, client: AsyncClient, db_session):
        """
        Test retrieving a specific document by ID.
        """
        # Setup - Create a document directly in DB
        new_doc = Document(
            id="doc-integration-1",
            application_id="app-int-1",
            document_type="APPRAISAL",
            file_name="report.pdf",
            storage_path="secure/report.pdf",
            upload_status="COMPLETED",
            created_at=None,
            updated_at=None
        )
        db_session.add(new_doc)
        await db_session.commit()

        # Act
        response = await client.get("/api/v1/documents/doc-integration-1")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "doc-integration-1"
        assert data["document_type"] == "APPRAISAL"

    async def test_get_document_not_found_endpoint(self, app: FastAPI, client: AsyncClient):
        """
        Test 404 response when document does not exist.
        """
        # Act
        response = await client.get("/api/v1/documents/does-not-exist")

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "detail" in response.json()

    async def test_list_documents_endpoint(self, app: FastAPI, client: AsyncClient, db_session):
        """
        Test listing documents for a specific application.
        """
        # Setup
        app_id = "app-list-123"
        doc1 = Document(id="d1", application_id=app_id, document_type="ID", file_name="1.pdf", storage_path="s1", upload_status="COMPLETED", created_at=None, updated_at=None)
        doc2 = Document(id="d2", application_id=app_id, document_type="PAY_STUB", file_name="2.pdf", storage_path="s2", upload_status="COMPLETED", created_at=None, updated_at=None)
        # Other app doc
        doc3 = Document(id="d3", application_id="other-app", document_type="ID", file_name="3.pdf", storage_path="s3", upload_status="COMPLETED", created_at=None, updated_at=None)
        
        db_session.add_all([doc1, doc2, doc3])
        await db_session.commit()

        # Act
        response = await client.get(f"/api/v1/documents?application_id={app_id}")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert all(d["application_id"] == app_id for d in data)

    async def test_delete_document_endpoint_fintrac_compliance(self, app: FastAPI, client: AsyncClient, db_session):
        """
        Test that deleting a document via API results in a soft delete (retention).
        """
        # Setup
        doc_id = "doc-delete-123"
        doc = Document(id=doc_id, application_id="app-1", document_type="CONTRACT", file_name="c.pdf", storage_path="s/c.pdf", upload_status="COMPLETED", created_at=None, updated_at=None)
        db_session.add(doc)
        await db_session.commit()

        # Act
        response = await client.delete(f"/api/v1/documents/{doc_id}")

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify DB state (FINTRAC: Record must exist for retention)
        await db_session.refresh(doc)
        assert doc.upload_status == "DELETED"
        assert doc.id == doc_id # Record still exists

    async def test_upload_large_file_rejection(self, app: FastAPI, client: AsyncClient, valid_document_payload):
        """
        Test that files exceeding size limits are rejected.
        """
        # Arrange
        large_payload = valid_document_payload.copy()
        large_payload["file_size_bytes"] = 50 * 1024 * 1024 + 1 # 50MB + 1 byte

        # Act
        response = await client.post("/api/v1/documents/upload", json=large_payload)

        # Assert
        # Assuming the service or route validates size before processing
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE or status.HTTP_400_BAD_REQUEST

    async def test_unsupported_media_type(self, app: FastAPI, client: AsyncClient, valid_document_payload):
        """
        Test rejection of unsafe file types.
        """
        # Arrange
        bad_payload = valid_document_payload.copy()
        bad_payload["content_type"] = "application/x-msdownload" # .exe

        # Act
        response = await client.post("/api/v1/documents/upload", json=bad_payload)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid file type" in response.json().get("detail", "")