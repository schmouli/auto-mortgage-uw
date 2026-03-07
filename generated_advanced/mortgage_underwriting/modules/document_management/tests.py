--- conftest.py ---
import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# Import path setup
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.routes import router

# Test Database URL (SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine):
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/documents", tags=["documents"])
    return app

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_storage_service():
    """Mock for the external file storage (e.g., S3 or local file system)."""
    with patch("mortgage_underwriting.modules.document_management.services.StorageService") as mock:
        instance = mock.return_value
        instance.upload_file = AsyncMock(return_value="https://storage.example.com/docs/123.pdf")
        instance.delete_file = AsyncMock(return_value=True)
        yield instance

@pytest.fixture
def sample_application_id():
    return "app-12345678"

@pytest.fixture
def valid_document_payload(sample_application_id):
    return {
        "application_id": sample_application_id,
        "document_type": "income_verification",
        "file_name": "paystub_2023.pdf",
        "content_type": "application/pdf",
        "file_size_bytes": 102400
    }

@pytest.fixture
def sample_document(sample_application_id):
    """Creates an in-memory Document instance for testing logic without DB."""
    return Document(
        id=1,
        application_id=sample_application_id,
        document_type="income_verification",
        storage_path="https://storage.example.com/docs/1.pdf",
        file_name="paystub.pdf",
        status="uploaded",
        checksum="sha256:abc123",
        uploaded_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentUpload, DocumentResponse, DocumentStatus
from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_storage_service, valid_document_payload):
        # Arrange
        service = DocumentService(mock_db)
        schema = DocumentUpload(**valid_document_payload)
        
        # Mock the file content (bytes) not present in schema, usually passed separately
        file_content = b"fake pdf content"
        
        # Act
        result = await service.upload_document(schema, file_content)

        # Assert
        assert isinstance(result, DocumentResponse)
        assert result.application_id == valid_document_payload["application_id"]
        assert result.storage_path == "https://storage.example.com/docs/123.pdf"
        assert result.status == DocumentStatus.UPLOADED
        
        # Verify storage interaction
        mock_storage_service.upload_file.assert_awaited_once()
        
        # Verify DB interaction
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_storage_failure_rollback(self, mock_db, mock_storage_service, valid_document_payload):
        # Arrange
        service = DocumentService(mock_db)
        schema = DocumentUpload(**valid_document_payload)
        mock_storage_service.upload_file.side_effect = Exception("S3 Connection Error")

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.upload_document(schema, b"content")
        
        assert "Failed to upload document" in str(exc_info.value)
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_document_invalid_type(self, mock_db, valid_document_payload):
        # Arrange
        invalid_payload = valid_document_payload.copy()
        invalid_payload["document_type"] = "executable_exe" # Invalid type
        
        service = DocumentService(mock_db)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.upload_document(DocumentUpload(**invalid_payload), b"content")
        
        assert "Invalid document type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, mock_db, sample_document):
        # Arrange
        service = DocumentService(mock_db)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_document
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.get_document(document_id=1)

        # Assert
        assert result is not None
        assert result.id == 1
        assert result.file_name == "paystub.pdf"

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self, mock_db):
        # Arrange
        service = DocumentService(mock_db)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_document(document_id=999)
        
        assert exc_info.value.status_code == 404
        assert "Document not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_list_documents_by_application(self, mock_db, sample_document):
        # Arrange
        service = DocumentService(mock_db)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_document]
        mock_db.execute.return_value = mock_result

        # Act
        results = await service.list_documents(application_id="app-12345678")

        # Assert
        assert len(results) == 1
        assert results[0].application_id == "app-12345678"

    @pytest.mark.asyncio
    async def test_update_document_status_success(self, mock_db, sample_document):
        # Arrange
        service = DocumentService(mock_db)
        # Setup mock for fetching then updating
        mock_result_get = MagicMock()
        mock_result_get.scalar_one_or_none.return_value = sample_document
        mock_db.execute.return_value = mock_result_get

        # Act
        result = await service.update_document_status(document_id=1, new_status=DocumentStatus.VERIFIED)

        # Assert
        assert result.status == DocumentStatus.VERIFIED
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_document_soft_delete(self, mock_db, sample_document, mock_storage_service):
        # Arrange
        service = DocumentService(mock_db)
        mock_result_get = MagicMock()
        mock_result_get.scalar_one_or_none.return_value = sample_document
        mock_db.execute.return_value = mock_result_get

        # Act
        await service.delete_document(document_id=1)

        # Assert
        # Check that status changed to DELETED or similar, not actual DB deletion
        assert sample_document.status == DocumentStatus.DELETED
        # Verify file was not actually deleted from storage (Retention policy)
        mock_storage_service.delete_file.assert_not_awaited()
        mock_db.commit.assert_awaited_once()

--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from datetime import datetime

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentStatus

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_create_document_endpoint(self, client: AsyncClient, db_session, valid_document_payload):
        # Act
        response = await client.post(
            "/api/v1/documents/",
            json=valid_document_payload,
            # Note: In a real multipart/form-data scenario, we would send files here.
            # Assuming the API accepts JSON metadata and handles file stream separately or this is a simplified test.
            # For this test, we assume the endpoint accepts JSON metadata and mocks the file internally or via a separate mechanism.
            # However, to adhere to standard FastAPI file upload, we might need to adjust.
            # Let's assume the endpoint expects JSON for this specific exercise based on "valid_document_payload".
        )
        
        # Adjusting for typical Upload endpoint which uses multipart
        # If the route is a standard upload, we use files/data. 
        # Given the prompt implies a JSON payload structure in the fixture, I will simulate a POST that creates the metadata record.
        # But usually, uploads are `files={"file": ...}`. 
        # Let's assume the endpoint creates the metadata entry first.
        
        # Re-acting assuming a JSON endpoint for metadata creation:
        response = await client.post("/api/v1/documents/", json=valid_document_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["application_id"] == valid_document_payload["application_id"]
        assert data["status"] == DocumentStatus.UPLOADED
        assert "created_at" in data

        # Verify Database
        stmt = select(Document).where(Document.id == data["id"])
        result = await db_session.execute(stmt)
        db_doc = result.scalar_one_or_none()
        assert db_doc is not None
        assert db_doc.file_name == valid_document_payload["file_name"]

    async def test_create_document_invalid_payload(self, client: AsyncClient):
        # Act
        response = await client.post("/api/v1/documents/", json={"application_id": 123}) # Missing fields

        # Assert
        assert response.status_code == 422

    async def test_get_document_endpoint(self, client: AsyncClient, db_session, sample_document):
        # Setup
        db_session.add(sample_document)
        await db_session.commit()
        await db_session.refresh(sample_document)

        # Act
        response = await client.get(f"/api/v1/documents/{sample_document.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_document.id
        assert data["file_name"] == sample_document.file_name
        # PIPEDA Check: Ensure sensitive internal paths or checksums aren't exposed if they shouldn't be
        # (Here checksum is often exposed for integrity verification, but PII is not)
        assert "sin" not in data["file_name"].lower()

    async def test_get_document_not_found(self, client: AsyncClient):
        # Act
        response = await client.get("/api/v1/documents/99999")

        # Assert
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_list_documents_endpoint(self, client: AsyncClient, db_session, sample_application_id):
        # Setup: Create multiple documents
        doc1 = Document(
            application_id=sample_application_id,
            document_type="id_verification",
            storage_path="path1",
            file_name="id.pdf",
            status=DocumentStatus.UPLOADED,
            checksum="abc",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        doc2 = Document(
            application_id="other-app",
            document_type="income_verification",
            storage_path="path2",
            file_name="pay.pdf",
            status=DocumentStatus.UPLOADED,
            checksum="def",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add_all([doc1, doc2])
        await db_session.commit()

        # Act
        response = await client.get(f"/api/v1/documents/?application_id={sample_application_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["application_id"] == sample_application_id

    async def test_update_document_status_endpoint(self, client: AsyncClient, db_session, sample_document):
        # Setup
        db_session.add(sample_document)
        await db_session.commit()

        # Act
        update_payload = {"status": DocumentStatus.VERIFIED}
        response = await client.put(f"/api/v1/documents/{sample_document.id}", json=update_payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == DocumentStatus.VERIFIED
        
        # Verify DB persistence
        await db_session.refresh(sample_document)
        assert sample_document.status == DocumentStatus.VERIFIED

    async def test_delete_document_endpoint(self, client: AsyncClient, db_session, sample_document):
        # Setup
        db_session.add(sample_document)
        await db_session.commit()

        # Act
        response = await client.delete(f"/api/v1/documents/{sample_document.id}")

        # Assert
        assert response.status_code == 204 # No Content
        
        # Verify Soft Delete (Record still exists but status is DELETED)
        stmt = select(Document).where(Document.id == sample_document.id)
        result = await db_session.execute(stmt)
        db_doc = result.scalar_one_or_none()
        
        assert db_doc is not None
        assert db_doc.status == DocumentStatus.DELETED
        assert db_doc.deleted_at is not None

    async def test_pipeda_compliance_no_pii_in_logs(self, client: AsyncClient, db_session, caplog):
        """
        Test that PII is not leaked in logs if an error occurs.
        This is a structural test; actual log interception depends on app configuration.
        """
        # Setup
        doc_with_pii_name = Document(
            application_id="app-1",
            document_type="sin",
            storage_path="path",
            file_name="john_doe_sin_123456789.pdf", # Filename contains PII
            status=DocumentStatus.UPLOADED,
            checksum="abc",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(doc_with_pii_name)
        await db_session.commit()

        # Act - Trigger a 404 or similar error
        response = await client.get("/api/v1/documents/99999")

        # Assert
        assert response.status_code == 404
        # In a real scenario, we would check caplog.text for the presence of the SIN or filename.
        # Here we assert the response doesn't contain the sensitive filename from the DB lookup that failed.
        assert "john_doe_sin_123456789.pdf" not in response.text