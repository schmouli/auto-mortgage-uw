--- conftest.py ---
import pytest
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from fastapi import FastAPI

from mortgage_underwriting.common.config import settings
from mortgage_underwriting.modules.document_management.routes import router as document_router
from mortgage_underwriting.modules.application.routes import router as application_router

# Use SQLite in-memory for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

class Base(DeclarativeBase):
    pass

@pytest.fixture(scope="session")
def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def app() -> FastAPI:
    """
    Create a test application instance.
    We include both the document router and a mock application router
    to satisfy foreign key constraints if necessary.
    """
    app = FastAPI()
    app.include_router(document_router, prefix="/api/v1/documents", tags=["documents"])
    app.include_router(application_router, prefix="/api/v1/applications", tags=["applications"])
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async client for testing FastAPI endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_storage_service():
    """
    Mocks the external file storage (e.g., S3) interactions.
    """
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.upload_file.return_value = "https://storage.example.com/docs/12345.pdf"
    mock.delete_file.return_value = True
    return mock

@pytest.fixture
def sample_application_payload():
    return {
        "applicant_id": "test-user-123",
        "property_address": "123 Test St, Toronto, ON",
        "purchase_price": "500000.00", # Decimal string
        "down_payment": "100000.00"    # Decimal string
    }

@pytest.fixture
def sample_document_payload():
    return {
        "application_id": 1,
        "file_name": "pay_stub_2023.pdf",
        "file_type": "application/pdf",
        "document_type": "INCOME_VERIFICATION",
        "content_type": "PAY_STUB"
    }
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentUpload, DocumentResponse, DocumentUpdate
)
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
        return db

    @pytest.fixture
    def mock_storage(self):
        storage = AsyncMock()
        storage.upload_file.return_value = "https://secure-storage.mortgage-co/uploads/uuid.pdf"
        storage.generate_presigned_url.return_value = "https://secure-storage.mortgage-co/downloads/uuid.pdf"
        return storage

    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_db, mock_storage):
        """Test successful document upload with audit trail creation."""
        payload = DocumentUpload(
            application_id=1,
            file_name="tax_return.pdf",
            file_type="application/pdf",
            document_type="T1_GENERAL"
        )
        file_content = b"fake pdf content"
        
        service = DocumentService(mock_db, mock_storage)
        
        # Mock the result of the refresh to simulate DB returning the object
        mock_db.refresh.side_effect = lambda obj: setattr(obj, 'id', 123)

        result = await service.upload_document(payload, file_content, user_id="user_123")

        assert result.id == 123
        assert result.file_name == "tax_return.pdf"
        assert result.uploaded_by == "user_123"
        assert result.status == "UPLOADED"
        assert result.file_path == "https://secure-storage.mortgage-co/uploads/uuid.pdf"
        
        # FINTRAC Compliance: Audit fields must be set
        assert result.created_at is not None
        assert result.updated_at is not None
        
        mock_storage.upload_file.assert_awaited_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_invalid_file_type(self, mock_db, mock_storage):
        """Test rejection of disallowed file types (e.g., .exe)."""
        payload = DocumentUpload(
            application_id=1,
            file_name="virus.exe",
            file_type="application/x-msdownload",
            document_type="OTHER"
        )
        
        service = DocumentService(mock_db, mock_storage)
        
        with pytest.raises(AppException) as exc_info:
            await service.upload_document(payload, b"content", user_id="user_123")
        
        assert exc_info.value.error_code == "INVALID_FILE_TYPE"
        assert "not allowed" in exc_info.value.detail
        mock_storage.upload_file.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_document_storage_failure(self, mock_db, mock_storage):
        """Test handling of external storage failure."""
        payload = DocumentUpload(
            application_id=1,
            file_name="large_file.pdf",
            file_type="application/pdf",
            document_type="APPRAISAL"
        )
        
        mock_storage.upload_file.side_effect = Exception("S3 Bucket Full")
        service = DocumentService(mock_db, mock_storage)
        
        with pytest.raises(AppException) as exc_info:
            await service.upload_document(payload, b"content", user_id="user_123")
        
        assert exc_info.value.error_code == "STORAGE_ERROR"
        # Ensure DB transaction is rolled back or not committed
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, mock_db, mock_storage):
        """Test retrieving document metadata."""
        # Mock the DB return value
        mock_doc = Document(
            id=1,
            application_id=1,
            file_name="report.pdf",
            file_type="application/pdf",
            file_path="path/to/file",
            status="UPLOADED",
            uploaded_by="user_1"
        )
        mock_db.scalar.return_value = mock_doc
        
        service = DocumentService(mock_db, mock_storage)
        result = await service.get_document_by_id(document_id=1)
        
        assert isinstance(result, DocumentResponse)
        assert result.file_name == "report.pdf"
        # PIPEDA Compliance: Ensure sensitive fields aren't exposed if they existed
        # (In this module, we mostly store metadata, but we ensure no raw content in response)
        assert "file_content" not in result.model_dump()

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, mock_db, mock_storage):
        """Test 404 scenario when document does not exist."""
        mock_db.scalar.return_value = None
        service = DocumentService(mock_db, mock_storage)
        
        with pytest.raises(AppException) as exc_info:
            await service.get_document_by_id(999)
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_soft_delete_document_fintrac_compliance(self, mock_db, mock_storage):
        """Test that documents are soft-deleted to satisfy FINTRAC retention rules."""
        mock_doc = Document(
            id=1,
            application_id=1,
            file_name="old_doc.pdf",
            file_type="application/pdf",
            file_path="path/to/file",
            status="UPLOADED",
            uploaded_by="user_1"
        )
        mock_db.scalar.return_value = mock_doc
        
        service = DocumentService(mock_db, mock_storage)
        await service.delete_document(document_id=1, user_id="admin_user")
        
        # FINTRAC: Never deleted or modified (in the sense of hard delete)
        # We verify status change, not removal from DB
        assert mock_doc.status == "DELETED"
        assert mock_doc.deleted_at is not None
        assert mock_doc.deleted_by == "admin_user"
        
        mock_storage.delete_file.assert_not_awaited() # We keep the file for retention
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_document_status(self, mock_db, mock_storage):
        """Test updating document status (e.g., UPLOADED -> VERIFIED)."""
        mock_doc = Document(
            id=1,
            application_id=1,
            file_name="doc.pdf",
            file_type="application/pdf",
            file_path="path",
            status="UPLOADED",
            uploaded_by="user_1"
        )
        mock_db.scalar.return_value = mock_doc
        
        service = DocumentService(mock_db, mock_storage)
        update_schema = DocumentUpdate(status="VERIFIED", notes="Reviewed by agent")
        
        result = await service.update_document(1, update_schema)
        
        assert result.status == "VERIFIED"
        assert result.notes == "Reviewed by agent"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_documents_by_application(self, mock_db, mock_storage):
        """Test retrieving all documents for a specific mortgage application."""
        # Mocking the execute/scalar chain for listing
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            Document(id=1, file_name="a.pdf", application_id=10, status="UPLOADED", uploaded_by="u1", file_type="pdf", file_path="p1"),
            Document(id=2, file_name="b.jpg", application_id=10, status="UPLOADED", uploaded_by="u1", file_type="jpg", file_path="p2"),
        ]
        mock_db.execute.return_value = mock_result
        
        service = DocumentService(mock_db, mock_storage)
        results = await service.list_documents(application_id=10)
        
        assert len(results) == 2
        assert results[0].file_name == "a.pdf"
        assert results[1].file_name == "b.jpg"

    @pytest.mark.asyncio
    async def test_pipeda_check_no_logging_of_pii(self, mock_db, mock_storage, caplog):
        """Ensure that sensitive info (if passed) is not logged."""
        payload = DocumentUpload(
            application_id=1,
            file_name="sin_card.jpg", # Sensitive name
            file_type="image/jpeg",
            document_type="IDENTITY"
        )
        
        service = DocumentService(mock_db, mock_storage)
        
        # Suppress actual logging logic for this test, just verify logic flow
        with patch("mortgage_underwriting.modules.document_management.services.logger") as mock_logger:
            await service.upload_document(payload, b"img", user_id="user_123")
            
            # Verify any log calls do not contain raw binary data or specific PII strings if they were in payload
            for call in mock_logger.info.call_args_list:
                log_str = str(call)
                assert "sin_card.jpg" not in log_str or "sanitized" in log_str 

--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.document_management.models import Document

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_create_document_success(self, client: AsyncClient, db_session, sample_application_payload):
        """
        Test full workflow: Create Application -> Upload Document -> Verify Record.
        """
        # 1. Create an application first (Foreign Key dependency)
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        assert app_resp.status_code == 201
        app_id = app_resp.json()["id"]

        # 2. Upload a document
        files = {
            "file": ("pay_stub.pdf", b"%PDF-1.4 fake content...", "application/pdf")
        }
        data = {
            "application_id": str(app_id),
            "document_type": "INCOME_VERIFICATION",
            "content_type": "PAY_STUB"
        }
        
        doc_resp = await client.post("/api/v1/documents", files=files, data=data)
        assert doc_resp.status_code == 201
        
        json_data = doc_resp.json()
        assert json_data["file_name"] == "pay_stub.pdf"
        assert json_data["application_id"] == app_id
        assert json_data["status"] == "UPLOADED"
        assert json_data["uploaded_by"] == "test_user" # Assuming auth sets this
        
        # FINTRAC Compliance: Verify Audit fields in response
        assert "created_at" in json_data
        assert "id" in json_data

        # 3. Verify Database Record
        stmt = select(Document).where(Document.id == json_data["id"])
        result = await db_session.execute(stmt)
        doc_obj = result.scalar_one_or_none()
        
        assert doc_obj is not None
        assert doc_obj.file_name == "pay_stub.pdf"
        assert doc_obj.file_path is not None # Should point to storage

    async def test_create_document_unsupported_type(self, client: AsyncClient, db_session, sample_application_payload):
        """Test that uploading an executable file is rejected."""
        # Create App
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]

        # Upload malicious file type
        files = {
            "file": ("script.exe", b"MZ\x90\x00", "application/x-msdownload")
        }
        data = {
            "application_id": str(app_id),
            "document_type": "OTHER",
            "content_type": "OTHER"
        }
        
        doc_resp = await client.post("/api/v1/documents", files=files, data=data)
        assert doc_resp.status_code == 400
        assert "error_code" in doc_resp.json()

    async def test_get_document(self, client: AsyncClient, db_session, sample_application_payload):
        """Test retrieving a specific document."""
        # Setup
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]
        
        files = {"file": ("id.pdf", b"pdf", "application/pdf")}
        data = {"application_id": str(app_id), "document_type": "IDENTITY", "content_type": "DRIVER_LICENSE"}
        upload_resp = await client.post("/api/v1/documents", files=files, data=data)
        doc_id = upload_resp.json()["id"]

        # Act
        get_resp = await client.get(f"/api/v1/documents/{doc_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == doc_id
        assert data["document_type"] == "IDENTITY"

    async def test_list_documents_by_application(self, client: AsyncClient, db_session, sample_application_payload):
        """Test filtering documents by application ID."""
        # Setup App
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]

        # Upload 2 docs
        for i in range(2):
            files = {"file": (f"doc_{i}.pdf", b"pdf", "application/pdf")}
            data = {"application_id": str(app_id), "document_type": "INCOME_VERIFICATION", "content_type": "PAY_STUB"}
            await client.post("/api/v1/documents", files=files, data=data)

        # List
        list_resp = await client.get(f"/api/v1/documents?application_id={app_id}")
        
        assert list_resp.status_code == 200
        docs = list_resp.json()["items"]
        assert len(docs) == 2
        # Verify all belong to the app
        for doc in docs:
            assert doc["application_id"] == app_id

    async def test_delete_document_soft_delete(self, client: AsyncClient, db_session, sample_application_payload):
        """
        Test FINTRAC compliance: Ensure delete endpoint soft-deletes (retains record).
        """
        # Setup
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]
        
        files = {"file": ("to_delete.pdf", b"pdf", "application/pdf")}
        data = {"application_id": str(app_id), "document_type": "OTHER", "content_type": "OTHER"}
        upload_resp = await client.post("/api/v1/documents", files=files, data=data)
        doc_id = upload_resp.json()["id"]

        # Delete
        del_resp = await client.delete(f"/api/v1/documents/{doc_id}")
        assert del_resp.status_code == 200 # OK, not 204 No Content, to confirm action

        # Verify in DB
        stmt = select(Document).where(Document.id == doc_id)
        result = await db_session.execute(stmt)
        doc_obj = result.scalar_one()
        
        # FINTRAC: Record still exists
        assert doc_obj is not None
        # But marked deleted
        assert doc_obj.status == "DELETED"
        assert doc_obj.deleted_at is not None

        # Verify it doesn't appear in normal list
        list_resp = await client.get(f"/api/v1/documents?application_id={app_id}")
        docs = list_resp.json()["items"]
        # Should be empty or not contain the deleted doc depending on filter implementation
        # Assuming list endpoint filters out DELETED status
        assert doc_id not in [d["id"] for d in docs]

    async def test_update_document_status(self, client: AsyncClient, db_session, sample_application_payload):
        """Test updating a document's verification status."""
        # Setup
        app_resp = await client.post("/api/v1/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]
        
        files = {"file": ("review.pdf", b"pdf", "application/pdf")}
        data = {"application_id": str(app_id), "document_type": "APPRAISAL", "content_type": "OTHER"}
        upload_resp = await client.post("/api/v1/documents", files=files, data=data)
        doc_id = upload_resp.json()["id"]

        # Update
        update_payload = {
            "status": "VERIFIED",
            "notes": "Matches property records"
        }
        patch_resp = await client.patch(f"/api/v1/documents/{doc_id}", json=update_payload)
        
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["status"] == "VERIFIED"
        assert data["notes"] == "Matches property records"

    async def test_get_non_existent_document(self, client: AsyncClient):
        """Test 404 response."""
        resp = await client.get("/api/v1/documents/99999")
        assert resp.status_code == 404
        assert "error_code" in resp.json()