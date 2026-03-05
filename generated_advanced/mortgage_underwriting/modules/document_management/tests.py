--- conftest.py ---
```python
import pytest
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Import application components
from mortgage_underwriting.common.database import Base, get_async_session
from mortgage_underwriting.modules.document_management.routes import router as document_router
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentUpload, DocumentStatus

# Test Database Configuration (SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    Handles schema creation and teardown.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def mock_storage_service():
    """
    Mocks the external S3/MinIO storage service.
    """
    mock = AsyncMock()
    mock.upload_file.return_value = "https://secure-storage.example.com/docs/uuid123.pdf"
    mock.delete_file.return_value = True
    mock.get_file_url.return_value = "https://secure-storage.example.com/docs/uuid123.pdf?presigned=xyz"
    return mock

@pytest.fixture
def mock_virus_scanner():
    """
    Mocks the anti-virus scanning service.
    """
    mock = AsyncMock()
    mock.scan_file.return_value = True  # True = Clean
    return mock

@pytest.fixture
def sample_document_payload():
    return {
        "applicant_id": "123e4567-e89b-12d3-a456-426614174000",
        "file_name": "employment_letter.pdf",
        "file_type": "application/pdf",
        "file_size_bytes": 1024000, # 1MB
        "document_type": "EMPLOYMENT_VERIFICATION"
    }

@pytest.fixture
def app(db_session: AsyncSession, mock_storage_service, mock_virus_scanner) -> FastAPI:
    """
    Creates a test FastAPI app with overridden dependencies.
    """
    app = FastAPI()
    app.include_router(document_router, prefix="/api/v1/documents", tags=["documents"])
    
    # Override database dependency
    async def override_get_db():
        yield db_session
    
    # Override storage dependency (assuming it's injected)
    # Note: In a real app, these overrides happen in specific test modules or via a dependency_overrides dict
    # Here we provide the app instance ready for overrides in tests
    
    app.dependency_overrides[get_async_session] = override_get_db
    
    yield app
    
    app.dependency_overrides.clear()

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for integration testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

--- unit_tests ---
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.document_management.services import DocumentService
from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentUpload, DocumentStatus
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def service(self, mock_db: AsyncSession, mock_storage_service, mock_virus_scanner):
        return DocumentService(mock_db, mock_storage_service, mock_virus_scanner)

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_upload_document_success(self, service, mock_db, mock_storage_service, mock_virus_scanner, sample_document_payload):
        # Arrange
        payload = DocumentUpload(**sample_document_payload)
        file_content = b"fake pdf content"
        
        # Mock DB result for refresh
        mock_doc = Document(
            id=uuid4(),
            applicant_id=payload.applicant_id,
            file_name=payload.file_name,
            storage_key="test_key",
            status=DocumentStatus.UPLOADED
        )
        mock_db.refresh.side_effect = lambda x: None # Simulate refresh

        # Act
        result = await service.upload_document(payload, file_content)

        # Assert
        assert result.status == DocumentStatus.UPLOADED
        mock_storage_service.upload_file.assert_awaited_once()
        mock_virus_scanner.scan_file.assert_awaited_once_with(file_content)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_virus_detected(self, service, mock_storage_service, mock_virus_scanner, sample_document_payload):
        # Arrange
        payload = DocumentUpload(**sample_document_payload)
        file_content = b"malicious content"
        mock_virus_scanner.scan_file.return_value = False # Virus found

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.upload_document(payload, file_content)
        
        assert "security" in str(exc_info.value).lower()
        mock_storage_service.upload_file.assert_not_awaited() # Should not upload if virus found
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_document_unsupported_type(self, service, sample_document_payload):
        # Arrange
        invalid_payload_dict = sample_document_payload.copy()
        invalid_payload_dict["file_type"] = "application/exe"
        payload = DocumentUpload(**invalid_payload_dict)
        file_content = b"content"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.upload_document(payload, file_content)
        
        assert "file type" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, service, mock_db):
        # Arrange
        doc_id = uuid4()
        mock_doc = Document(id=doc_id, file_name="test.pdf", status=DocumentStatus.UPLOADED)
        
        # Mock the SQLAlchemy query chain
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.get_document_by_id(doc_id)

        # Assert
        assert result is not None
        assert result.id == doc_id
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_soft_delete_document_fintrac_compliance(self, service, mock_db):
        # Arrange
        doc_id = uuid4()
        mock_doc = Document(id=doc_id, file_name="test.pdf", status=DocumentStatus.UPLOADED)
        
        # Mock fetching the document
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db.execute.return_value = mock_result

        # Act
        await service.delete_document(doc_id)

        # Assert
        # FINTRAC: Verify record is NOT deleted from DB, but status updated
        assert mock_doc.status == DocumentStatus.DELETED
        # Verify we did NOT call session.delete(mock_doc)
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_documents_by_applicant(self, service, mock_db):
        # Arrange
        applicant_id = uuid4()
        mock_docs = [
            Document(id=uuid4(), applicant_id=applicant_id, file_name="doc1.pdf"),
            Document(id=uuid4(), applicant_id=applicant_id, file_name="doc2.pdf")
        ]
        
        # Mock scalars().all()
        mock_scalars = AsyncMock()
        mock_scalars.all.return_value = mock_docs
        mock_db.execute.return_value.scalars.return_value = mock_scalars

        # Act
        results = await service.list_documents(applicant_id)

        # Assert
        assert len(results) == 2
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_document_status_success(self, service, mock_db):
        # Arrange
        doc_id = uuid4()
        mock_doc = Document(id=doc_id, file_name="test.pdf", status=DocumentStatus.PENDING)
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db.execute.return_value = mock_result

        # Act
        updated = await service.update_document_status(doc_id, DocumentStatus.APPROVED)

        # Assert
        assert updated.status == DocumentStatus.APPROVED
        mock_db.commit.assert_awaited_once()
```

--- integration_tests ---
```python
import pytest
from uuid import uuid4
from httpx import AsyncClient

from mortgage_underwriting.modules.document_management.models import Document
from mortgage_underwriting.modules.document_management.schemas import DocumentStatus

@pytest.mark.integration
@pytest.mark.asyncio
class TestDocumentRoutes:

    async def test_create_document_endpoint_success(self, client: AsyncClient, db_session, mock_storage_service, mock_virus_scanner, sample_document_payload):
        """
        Test full upload flow: API -> Service -> DB -> Storage
        """
        # Act
        response = await client.post(
            "/api/v1/documents/upload",
            json=sample_document_payload,
            # In real multipart, we'd send files, here we simulate the metadata creation
            # Assuming the endpoint handles metadata creation based on JSON schema
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["file_name"] == sample_document_payload["file_name"]
        assert data["status"] == DocumentStatus.UPLOADED
        
        # Verify DB state
        result = await db_session.execute(
            f"SELECT * FROM documents WHERE id = '{data['id']}'"
        )
        # Note: raw SQL check or ORM check depending on session type
        # Here we assume ORM was used in the route logic
        from sqlalchemy import select
        stmt = select(Document).where(Document.id == uuid4()) # Placeholder logic
        # In a real integration test, we would query the DB using the session to verify persistence

    async def test_get_document_endpoint(self, client: AsyncClient, db_session, sample_document_payload):
        """
        Test retrieving a document by ID.
        """
        # 1. Create a document directly in DB (bypassing upload logic for isolation)
        doc_id = uuid4()
        new_doc = Document(
            id=doc_id,
            applicant_id=uuid4(),
            file_name="pay_stub.pdf",
            file_type="application/pdf",
            storage_key="uploads/pay_stub.pdf",
            status=DocumentStatus.PROCESSING
        )
        db_session.add(new_doc)
        await db_session.commit()
        await db_session.refresh(new_doc)

        # 2. Retrieve via API
        response = await client.get(f"/api/v1/documents/{doc_id}")

        # 3. Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(doc_id)
        assert data["status"] == DocumentStatus.PROCESSING

    async def test_list_documents_by_applicant_endpoint(self, client: AsyncClient, db_session):
        """
        Test filtering documents by applicant_id.
        """
        applicant_id = uuid4()
        
        # Seed data
        doc1 = Document(id=uuid4(), applicant_id=applicant_id, file_name="a.pdf", storage_key="a", status=DocumentStatus.UPLOADED)
        doc2 = Document(id=uuid4(), applicant_id=applicant_id, file_name="b.pdf", storage_key="b", status=DocumentStatus.UPLOADED)
        other_doc = Document(id=uuid4(), applicant_id=uuid4(), file_name="c.pdf", storage_key="c", status=DocumentStatus.UPLOADED)
        
        db_session.add_all([doc1, doc2, other_doc])
        await db_session.commit()

        # Act
        response = await client.get(f"/api/v1/documents/applicant/{applicant_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert all(doc["applicant_id"] == str(applicant_id) for doc in data["items"])

    async def test_update_document_status_endpoint(self, client: AsyncClient, db_session):
        """
        Test updating document status (e.g., Underwriter approves a doc).
        """
        # Setup
        doc_id = uuid4()
        doc = Document(id=doc_id, applicant_id=uuid4(), file_name="id.pdf", storage_key="id", status=DocumentStatus.PENDING)
        db_session.add(doc)
        await db_session.commit()

        # Act
        payload = {"status": "APPROVED", "reviewer_id": str(uuid4())}
        response = await client.put(f"/api/v1/documents/{doc_id}/status", json=payload)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == DocumentStatus.APPROVED
        
        # Verify DB update
        await db_session.refresh(doc)
        assert doc.status == DocumentStatus.APPROVED

    async def test_delete_document_soft_delete_compliance(self, client: AsyncClient, db_session):
        """
        FINTRAC: Ensure DELETE endpoint performs a soft delete and record remains in DB.
        """
        # Setup
        doc_id = uuid4()
        doc = Document(id=doc_id, applicant_id=uuid4(), file_name="tax.pdf", storage_key="tax", status=DocumentStatus.UPLOADED)
        db_session.add(doc)
        await db_session.commit()

        # Act
        response = await client.delete(f"/api/v1/documents/{doc_id}")

        # Assert API Response
        assert response.status_code == 204

        # Assert DB State (Record still exists)
        from sqlalchemy import select
        stmt = select(Document).where(Document.id == doc_id)
        result = await db_session.execute(stmt)
        deleted_doc = result.scalar_one_or_none()

        assert deleted_doc is not None # FINTRAC: Record not deleted
        assert deleted_doc.status == DocumentStatus.DELETED # Soft delete flag

    async def test_upload_large_file_rejected(self, client: AsyncClient, sample_document_payload):
        """
        Test validation logic for file size limits.
        """
        # Arrange
        large_payload = sample_document_payload.copy()
        large_payload["file_size_bytes"] = 50 * 1024 * 1024 # 50MB (assuming limit is 10MB)

        # Act
        response = await client.post("/api/v1/documents/upload", json=large_payload)

        # Assert
        assert response.status_code == 422 # Unprocessable Entity / Validation Error

    async def test_get_nonexistent_document_returns_404(self, client: AsyncClient):
        """
        Test handling of missing resources.
        """
        fake_id = uuid4()
        response = await client.get(f"/api/v1/documents/{fake_id}")
        assert response.status_code == 404
```