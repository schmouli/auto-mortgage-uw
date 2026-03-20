--- conftest.py ---
import pytest
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.document_management.models import Document, DocumentStatus
from mortgage_underwriting.modules.document_management.schemas import DocumentUpload, DocumentResponse

# Test Database Configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def mock_storage_service() -> MagicMock:
    """Mock the external S3/Storage service."""
    storage = MagicMock()
    storage.upload_file = AsyncMock(return_value="https://storage.example.com/docs/123.pdf")
    storage.delete_file = AsyncMock(return_value=True)
    storage.get_file_url = AsyncMock(return_value="https://storage.example.com/docs/123.pdf")
    return storage


@pytest.fixture
def document_payload() -> dict:
    """Valid payload for document upload."""
    return {
        "applicant_id": "uuid-applicant-123",
        "document_type": "PAY_STUB",
        "file_name": "pay_stub_jan_2024.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": 102400
    }


@pytest.fixture
def sample_document(document_payload: dict) -> Document:
    """A sample ORM Document object."""
    return Document(
        id="uuid-doc-123",
        **document_payload,
        storage_key="docs/uuid-doc-123.pdf",
        status=DocumentStatus.UPLOADED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        created_by="system"
    )


@pytest.fixture
def app() -> FastAPI:
    """Fixture for the FastAPI app used in integration tests."""
    from mortgage_underwriting.modules.document_management.routes import router
    
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/documents", tags=["documents"])
    
    # Dependency override for storage would go here in a real setup
    # For this test, we assume the app uses a default or we override in the test
    return app

--- unit_tests ---
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.document_management.models import Document, DocumentStatus
from mortgage_underwriting.modules.document_management.schemas import DocumentUpload, DocumentResponse
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
        db.scalar = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.fixture
    def mock_storage(self):
        storage = MagicMock()
        storage.upload_file = AsyncMock(return_value="s3://bucket/key.pdf")
        return storage

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_storage, document_payload):
        """Test successful document upload and record creation."""
        # Arrange
        service = DocumentService(mock_db, mock_storage)
        payload = DocumentUpload(**document_payload)

        # Act
        result = await service.upload_document(file_content=b"fake_pdf_content", payload=payload)

        # Assert
        assert isinstance(result, DocumentResponse)
        assert result.applicant_id == document_payload["applicant_id"]
        assert result.status == DocumentStatus.UPLOADED
        assert result.file_name == document_payload["file_name"]
        
        mock_storage.upload_file.assert_awaited_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_storage_failure(self, mock_db, mock_storage, document_payload):
        """Test rollback when storage service fails."""
        # Arrange
        mock_storage.upload_file = AsyncMock(side_effect=Exception("S3 Connection Error"))
        service = DocumentService(mock_db, mock_storage)
        payload = DocumentUpload(**document_payload)

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.upload_document(file_content=b"fake_pdf_content", payload=payload)
        
        assert "Failed to upload document" in str(exc_info.value)
        mock_db.rollback.assert_awaited_once()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_document_db_failure(self, mock_db, mock_storage, document_payload):
        """Test handling of database errors during save."""
        # Arrange
        mock_db.commit = AsyncMock(side_effect=SQLAlchemyError("DB constraint violation"))
        service = DocumentService(mock_db, mock_storage)
        payload = DocumentUpload(**document_payload)

        # Act & Assert
        with pytest.raises(AppException):
            await service.upload_document(file_content=b"fake", payload=payload)
        
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, mock_db, sample_document):
        """Test retrieving a document by ID."""
        # Arrange
        mock_db.scalar.return_value = sample_document
        service = DocumentService(mock_db, MagicMock())

        # Act
        result = await service.get_document(document_id="uuid-doc-123")

        # Assert
        assert result is not None
        assert result.id == sample_document.id
        assert result.file_name == sample_document.file_name
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, mock_db):
        """Test retrieving a non-existent document."""
        # Arrange
        mock_db.scalar.return_value = None
        service = DocumentService(mock_db, MagicMock())

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_document(document_id="non-existent-id")
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_verify_document_success(self, mock_db, sample_document):
        """Test verifying a document (status update)."""
        # Arrange
        mock_db.scalar.return_value = sample_document
        service = DocumentService(mock_db, MagicMock())

        # Act
        result = await service.verify_document(document_id="uuid-doc-123", verified_by="underwriter_1")

        # Assert
        assert result.status == DocumentStatus.VERIFIED
        assert result.verified_by == "underwriter_1"
        assert result.verified_at is not None
        
        # Compliance: Ensure audit fields are updated
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_documents_by_applicant(self, mock_db, sample_document):
        """Test listing all documents for a specific applicant."""
        # Arrange
        # Mocking the execute().scalars().all() chain
        mock_result = AsyncMock()
        mock_result.all.return_value = [sample_document]
        mock_db.execute.return_value = mock_result
        
        service = DocumentService(mock_db, MagicMock())

        # Act
        results = await service.list_documents(applicant_id="uuid-applicant-123")

        # Assert
        assert len(results) == 1
        assert results[0].applicant_id == "uuid-applicant-123"

    @pytest.mark.asyncio
    async def test_delete_document_success(self, mock_db, sample_document, mock_storage):
        """Test soft delete or marking as deleted."""
        # Arrange
        mock_db.scalar.return_value = sample_document
        service = DocumentService(mock_db, mock_storage)

        # Act
        await service.delete_document(document_id="uuid-doc-123")

        # Assert
        # Compliance: FINTRAC requires immutable records, so we check for status change or soft delete flag
        # Assuming 'is_deleted' flag or status change to DELETED
        assert sample_document.is_deleted is True 
        mock_db.commit.assert_awaited_once()
        # Storage should eventually be cleaned up, maybe via async task, 
        # but for now let's assume service handles it or just marks DB
        # If service deletes from storage immediately:
        # mock_storage.delete_file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_file_type(self, mock_db, mock_storage, document_payload):
        """Test rejection of unauthorized file types (e.g., .exe)."""
        # Arrange
        document_payload["file_name"] = "virus.exe"
        document_payload["mime_type"] = "application/x-msdownload"
        service = DocumentService(mock_db, mock_storage)
        payload = DocumentUpload(**document_payload)

        # Act & Assert
        with pytest.raises(ValueError): # Or AppException depending on implementation
            await service.upload_document(file_content=b"binary", payload=payload)
        
        mock_db.add.assert_not_called()

--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from mortgage_underwriting.modules.document_management.models import Document, DocumentStatus
from mortgage_underwriting.common.database import get_async_session


@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_upload_document_workflow(self, app: FastAPI, db_session: AsyncSession):
        """
        Test the full workflow of uploading a document via API.
        Ensures database record is created correctly.
        """
        # Dependency override to use test session
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            files = {"file": ("pay_stub.pdf", b"%PDF-1.4 fake content", "application/pdf")}
            data = {
                "applicant_id": "applicant-uuid-1",
                "document_type": "PAY_STUB",
                "file_name": "pay_stub.pdf",
                "mime_type": "application/pdf",
                "file_size_bytes": 1024
            }
            
            response = await client.post("/api/v1/documents/upload", data=data, files=files)

            # Assert
            assert response.status_code == 201
            json_resp = response.json()
            assert "id" in json_resp
            assert json_resp["applicant_id"] == "applicant-uuid-1"
            assert json_resp["status"] == DocumentStatus.UPLOADED.value
            
            # Database Verification
            stmt = select(Document).where(Document.id == json_resp["id"])
            result = await db_session.execute(stmt)
            doc = result.scalar_one_or_none()
            
            assert doc is not None
            assert doc.file_name == "pay_stub.pdf"
            assert doc.created_at is not None # Compliance: Audit trail
            assert doc.created_by is not None # Compliance: Audit trail

        app.dependency_overrides.clear()

    async def test_get_document_endpoint(self, app: FastAPI, db_session: AsyncSession, sample_document: Document):
        """Test retrieving a specific document via GET."""
        # Setup
        db_session.add(sample_document)
        await db_session.commit()
        
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(f"/api/v1/documents/{sample_document.id}")

            # Assert
            assert response.status_code == 200
            json_resp = response.json()
            assert json_resp["id"] == sample_document.id
            assert json_resp["file_name"] == sample_document.file_name
            
            # Compliance Check: Ensure sensitive data isn't leaked
            assert "storage_key" not in json_resp # Internal detail should not be exposed

        app.dependency_overrides.clear()

    async def test_verify_document_endpoint(self, app: FastAPI, db_session: AsyncSession, sample_document: Document):
        """Test verifying a document via PATCH."""
        # Setup
        sample_document.status = DocumentStatus.UPLOADED
        db_session.add(sample_document)
        await db_session.commit()
        
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            payload = {"verified": True, "notes": "Matches payroll records"}
            response = await client.patch(f"/api/v1/documents/{sample_document.id}/verify", json=payload)

            # Assert
            assert response.status_code == 200
            json_resp = response.json()
            assert json_resp["status"] == DocumentStatus.VERIFIED.value
            assert json_resp["verified_by"] is not None
            
            # DB Verification
            await db_session.refresh(sample_document)
            assert sample_document.status == DocumentStatus.VERIFIED
            assert sample_document.verified_at is not None

        app.dependency_overrides.clear()

    async def test_list_documents_pagination(self, app: FastAPI, db_session: AsyncSession):
        """Test listing documents with pagination."""
        # Setup - Create multiple documents
        docs = []
        for i in range(5):
            docs.append(Document(
                id=f"doc-{i}",
                applicant_id="applicant-1",
                document_type="ID",
                file_name=f"file_{i}.pdf",
                mime_type="application/pdf",
                file_size_bytes=1000,
                storage_key=f"key-{i}",
                status=DocumentStatus.UPLOADED,
                created_at=datetime.utcnow(),
                created_by="system"
            ))
        db_session.add_all(docs)
        await db_session.commit()
        
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/api/v1/documents?applicant_id=applicant-1&limit=2&offset=0")

            # Assert
            assert response.status_code == 200
            json_resp = response.json()
            assert "items" in json_resp
            assert len(json_resp["items"]) == 2
            assert json_resp["total"] == 5
            assert json_resp["offset"] == 0

        app.dependency_overrides.clear()

    async def test_get_document_not_found_integration(self, app: FastAPI, db_session: AsyncSession):
        """Test 404 response when document does not exist."""
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents/does-not-exist")
            assert response.status_code == 404
            assert "detail" in response.json()

        app.dependency_overrides.clear()

    async def test_upload_unsupported_mime_type(self, app: FastAPI, db_session: AsyncSession):
        """Test rejection of unsafe file types at the API boundary."""
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("script.js", b"console.log('xss')", "application/javascript")}
            data = {
                "applicant_id": "applicant-1",
                "document_type": "OTHER",
                "file_name": "script.js",
                "mime_type": "application/javascript",
                "file_size_bytes": 100
            }
            
            response = await client.post("/api/v1/documents/upload", data=data, files=files)
            
            # Assert - Should be rejected by validation logic
            assert response.status_code == 400 or response.status_code == 422
            
            # Verify no record created
            stmt = select(Document).where(Document.file_name == "script.js")
            result = await db_session.execute(stmt)
            assert result.scalar_one_or_none() is None

        app.dependency_overrides.clear()