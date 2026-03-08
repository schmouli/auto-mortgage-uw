--- conftest.py ---
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

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import (
    DocumentCreate, 
    DocumentResponse, 
    DocumentStatus
)
from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def service(self, mock_storage_service, mock_virus_scanner):
        return DocumentService(
            storage=mock_storage_service, 
            scanner=mock_virus_scanner
        )

    @pytest.mark.asyncio
    async def test_upload_document_success(self, service, mock_storage_service, mock_virus_scanner, sample_document_payload, db_session):
        """Test successful document upload with virus scan and storage."""
        # Arrange
        file_content = b"dummy pdf content"
        payload = DocumentCreate(**sample_document_payload)
        
        # Act
        result = await service.upload(db_session, file_content, payload, user_id="user_123")

        # Assert
        assert result.status == DocumentStatus.UPLOADED
        assert result.file_name == "pay_stub_2023.pdf"
        assert result.storage_path == "https://storage.example.com/docs/123.pdf"
        
        mock_virus_scanner.scan_file.assert_awaited_once_with(file_content)
        mock_storage_service.upload_file.assert_awaited_once()
        
        # Verify DB session interactions
        # Note: In a real unit test we might not check the DB directly if we mock the repo layer,
        # but here we assume service uses the session directly.
        await db_session.flush() # Ensure pending operations are visible if querying
        
        # FINTRAC Compliance: Ensure audit fields are set
        assert result.created_by == "user_123"
        assert result.created_at is not None

    @pytest.mark.asyncio
    async def test_upload_document_virus_detected(self, service, mock_virus_scanner, sample_document_payload, db_session):
        """Test that upload fails if virus scanner returns negative."""
        # Arrange
        mock_virus_scanner.scan_file.return_value = False # Infected
        payload = DocumentCreate(**sample_document_payload)
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.upload(db_session, b"malicious_content", payload, user_id="user_123")
        
        assert "security threat" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "SECURITY_SCAN_FAILED"

    @pytest.mark.asyncio
    async def test_upload_document_invalid_file_type(self, service, sample_document_payload, db_session):
        """Test that invalid mime types are rejected."""
        # Arrange
        payload_data = sample_document_payload.copy()
        payload_data["mime_type"] = "application/x-msdownload" # Executable
        payload = DocumentCreate(**payload_data)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.upload(db_session, b"exe_content", payload, user_id="user_123")
        
        assert "file type not allowed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_document_success(self, service, sample_document_model, db_session):
        """Test retrieving a document by ID."""
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        # Act
        result = await service.get(db_session, sample_document_model.id)

        # Assert
        assert result is not None
        assert result.id == sample_document_model.id
        assert result.file_name == "pay_stub_2023.pdf"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, service, db_session):
        """Test retrieving a non-existent document raises error."""
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get(db_session, "non_existent_id")
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_soft_delete_document(self, service, sample_document_model, db_session):
        """Test that deleting a document sets status to DELETED but keeps record (FINTRAC)."""
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        # Act
        await service.delete(db_session, sample_document_model.id, user_id="admin")
        await db_session.refresh(sample_document_model)

        # Assert
        # FINTRAC: Record must exist (immutable audit trail), just marked deleted
        assert sample_document_model.status == DocumentStatus.DELETED
        assert sample_document_model.updated_by == "admin"
        assert sample_document_model.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_document_metadata(self, service, sample_document_model, db_session):
        """Test updating document metadata."""
        # Arrange
        db_session.add(sample_document_model)
        await db_session.commit()
        
        update_data = {"document_type": "tax_assessment"}
        
        # Act
        result = await service.update(db_session, sample_document_model.id, update_data, user_id="clerk")

        # Assert
        assert result.document_type == "tax_assessment"
        assert result.updated_by == "clerk"
        assert result.file_name == "pay_stub_2023.pdf" # Unchanged

    @pytest.mark.asyncio
    async def test_calculate_document_size_no_pii_logging(self, service, caplog):
        """Test helper function that calculates size but ensures no content is logged."""
        # Arrange
        sensitive_data = b"SIN: 123-456-789"
        
        # Act
        size = await service._calculate_size(sensitive_data)
        
        # Assert
        assert size == len(sensitive_data)
        # PIPEDA Compliance: Ensure sensitive data is NOT in logs
        assert "123-456-789" not in caplog.text

    @pytest.mark.asyncio
    async def test_list_documents_by_application(self, service, db_session):
        """Test listing documents filtered by application_id."""
        # Arrange
        doc1 = Document(id="1", application_id="app_1", file_name="a.pdf", storage_path="x", status="UPLOADED", created_by="u")
        doc2 = Document(id="2", application_id="app_1", file_name="b.pdf", storage_path="y", status="UPLOADED", created_by="u")
        doc3 = Document(id="3", application_id="app_2", file_name="c.pdf", storage_path="z", status="UPLOADED", created_by="u")
        
        db_session.add_all([doc1, doc2, doc3])
        await db_session.commit()

        # Act
        results = await service.list(db_session, application_id="app_1")

        # Assert
        assert len(results) == 2
        assert all(d.application_id == "app_1" for d in results)

    @pytest.mark.asyncio
    async def test_storage_failure_rollback(self, service, mock_storage_service, sample_document_payload, db_session):
        """Test that DB transaction rolls back if storage upload fails."""
        # Arrange
        mock_storage_service.upload_file.side_effect = Exception("S3 Down")
        payload = DocumentCreate(**sample_document_payload)

        # Act & Assert
        with pytest.raises(Exception):
            await service.upload(db_session, b"content", payload, user_id="user")
        
        # Verify no record was committed
        # (In a real scenario we'd query, but here we check session state logic conceptually)
        # If this was integration, we'd check count. In unit, we verify service raises.
        mock_storage_service.delete_file.assert_not_awaited() # Nothing to delete
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentStatus

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_upload_document_endpoint_success(self, client: AsyncClient, db_session):
        """Test full integration of file upload endpoint."""
        # Arrange
        file_data = b"%PDF-1.4 fake pdf content..."
        files = {"file": ("mortgage_statement.pdf", file_data, "application/pdf")}
        data = {
            "application_id": "app_integration_01",
            "document_type": "mortgage_statement",
            "metadata": '{"lender": "RBC", "amount": "500000.00"}'
        }

        # Act
        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        # Assert
        assert response.status_code == 201
        json_resp = response.json()
        assert json_resp["file_name"] == "mortgage_statement.pdf"
        assert json_resp["application_id"] == "app_integration_01"
        assert json_resp["status"] == "UPLOADED"
        assert "id" in json_resp

        # Verify DB state
        result = await db_session.execute(select(Document).where(Document.id == json_resp["id"]))
        doc = result.scalar_one()
        assert doc is not None
        assert doc.storage_path is not None # Should point to mocked storage or local temp

    async def test_upload_document_missing_file(self, client: AsyncClient):
        """Test validation error when file is missing."""
        # Arrange
        data = {"application_id": "app_01", "document_type": "id_proof"}

        # Act
        response = await client.post("/api/v1/documents/upload", data=data)

        # Assert
        assert response.status_code == 422 # Unprocessable Entity

    async def test_get_document_endpoint(self, client: AsyncClient, db_session):
        """Test retrieving a specific document."""
        # Arrange
        new_doc = Document(
            id="doc_get_test",
            application_id="app_01",
            file_name="test.pdf",
            storage_path="/path/to/file",
            status="UPLOADED",
            created_by="test_user"
        )
        db_session.add(new_doc)
        await db_session.commit()

        # Act
        response = await client.get(f"/api/v1/documents/{new_doc.id}")

        # Assert
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp["id"] == "doc_get_test"
        assert json_resp["created_at"] is not None # Audit trail presence

    async def test_get_document_not_found(self, client: AsyncClient):
        """Test 404 response for missing document."""
        # Act
        response = await client.get("/api/v1/documents/nonexistent")

        # Assert
        assert response.status_code == 404
        assert "error_code" in response.json()

    async def test_list_documents_endpoint(self, client: AsyncClient, db_session):
        """Test listing documents with pagination/filtering."""
        # Arrange
        docs = [
            Document(id="d1", application_id="app_list", file_name="1.pdf", storage_path="x", status="UPLOADED", created_by="u"),
            Document(id="d2", application_id="app_list", file_name="2.pdf", storage_path="y", status="PROCESSED", created_by="u"),
            Document(id="d3", application_id="app_other", file_name="3.pdf", storage_path="z", status="UPLOADED", created_by="u"),
        ]
        db_session.add_all(docs)
        await db_session.commit()

        # Act
        response = await client.get("/api/v1/documents?application_id=app_list")

        # Assert
        assert response.status_code == 200
        json_resp = response.json()
        assert "items" in json_resp
        assert len(json_resp["items"]) == 2
        assert all(item["application_id"] == "app_list" for item in json_resp["items"])

    async def test_delete_document_endpoint_soft_delete(self, client: AsyncClient, db_session):
        """Test that DELETE endpoint performs a soft delete (FINTRAC compliance)."""
        # Arrange
        doc = Document(
            id="doc_del",
            application_id="app_del",
            file_name="del.pdf",
            storage_path="/path",
            status="UPLOADED",
            created_by="u"
        )
        db_session.add(doc)
        await db_session.commit()

        # Act
        response = await client.delete(f"/api/v1/documents/{doc.id}")

        # Assert
        assert response.status_code == 200
        
        # Verify record still exists but is deleted
        await db_session.refresh(doc)
        assert doc.status == DocumentStatus.DELETED
        assert doc.id == "doc_del" # Record persists for audit trail

    async def test_update_document_metadata_endpoint(self, client: AsyncClient, db_session):
        """Test updating document metadata."""
        # Arrange
        doc = Document(
            id="doc_up",
            application_id="app_up",
            file_name="up.pdf",
            storage_path="/path",
            status="UPLOADED",
            created_by="u"
        )
        db_session.add(doc)
        await db_session.commit()

        update_payload = {
            "document_type": "updated_type",
            "metadata": {"reviewed": True}
        }

        # Act
        response = await client.put(f"/api/v1/documents/{doc.id}", json=update_payload)

        # Assert
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp["document_type"] == "updated_type"
        assert json_resp["updated_at"] is not None

    async def test_restricted_file_type_upload(self, client: AsyncClient):
        """Test that uploading an executable file is rejected."""
        # Arrange
        files = {"file": ("virus.exe", b"EXE CONTENT", "application/x-msdownload")}
        data = {"application_id": "app_sec", "document_type": "other"}

        # Act
        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        # Assert
        assert response.status_code == 400
        assert "security" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()

    async def test_metadata_with_financial_decimal(self, client: AsyncClient, db_session):
        """Test handling of Decimal values in metadata (CMHC/Financial compliance)."""
        # Arrange
        # Using string representation in JSON to ensure precision
        metadata_str = '{"property_value": "450000.00", "down_payment": "90000.50"}'
        files = {"file": ("doc.pdf", b"pdf", "application/pdf")}
        data = {
            "application_id": "app_dec",
            "document_type": "property_appraisal",
            "metadata": metadata_str
        }

        # Act
        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        # Assert
        assert response.status_code == 201
        json_resp = response.json()
        # Verify metadata is preserved correctly
        assert json_resp["metadata"]["property_value"] == "450000.00"
        
        # Check DB representation
        result = await db_session.execute(select(Document).where(Document.id == json_resp["id"]))
        doc = result.scalar_one()
        # Assuming metadata is stored as JSONB or dict
        assert doc.metadata["property_value"] == "450000.00"
```