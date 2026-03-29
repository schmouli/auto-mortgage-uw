--- conftest.py ---
import pytest
from collections.abc import AsyncGenerator, Generator
from typing import AsyncGenerator
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from fastapi import FastAPI

# Configure pytest for async
pytest_plugins = ("pytest_asyncio",)

# Database Setup (In-memory SQLite for speed)
DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Base class for models in tests (mirrors common/database.py)
Base = declarative_base()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    Handles schema creation and teardown.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def app() -> FastAPI:
    """
    Fixture to provide the FastAPI app instance.
    We dynamically import and include routers here to avoid import errors 
    if the module doesn't exist yet during initial scaffolding.
    """
    from mortgage_underwriting.modules.messaging_conditions.routes import router
    from mortgage_underwriting.common.config import settings

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/messaging-conditions", tags=["Messaging & Conditions"])
    return app

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an asynchronous HTTP client for testing endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def sample_application_id() -> str:
    return "550e8400-e29b-41d4-a716-446655440000"

@pytest.fixture
def sample_borrower_id() -> str:
    return "660e8400-e29b-41d4-a716-446655440001"

@pytest.fixture
def mock_email_gateway():
    """Mocks the external email service dependency."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    mock.send_email.return_value = {"message_id": "ext-123", "status": "queued"}
    return mock

# Helper to create models if they don't exist for the test runner
# (In a real scenario, these models are in the module, but we ensure imports work)
try:
    from mortgage_underwriting.modules.messaging_conditions.models import Message, Condition
    Base.metadata.create_all(bind=engine.sync_engine if hasattr(engine, 'sync_engine') else engine)
except ImportError:
    # Allow tests to run even if models aren't fully implemented yet (TDD)
    pass
--- unit_tests ---
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.messaging_conditions.models import Message, Condition
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    MessageCreate, 
    ConditionCreate, 
    ConditionUpdate, 
    ConditionStatusEnum,
    MessageCategoryEnum
)
from mortgage_underwriting.modules.messaging_conditions.services import (
    MessagingService, 
    ConditionService
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestMessagingService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_gateway(self):
        gateway = AsyncMock()
        gateway.send_email.return_value = {"status": "sent", "message_id": "ext-123"}
        return gateway

    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_db, mock_gateway, sample_application_id):
        """Test successful sending of a notification and persistence."""
        service = MessagingService(mock_db, mock_gateway)
        payload = MessageCreate(
            application_id=sample_application_id,
            recipient_email="borrower@example.com",
            subject="Underwriting Update",
            content="Please provide additional documents.",
            category=MessageCategoryEnum.DOCUMENT_REQUEST
        )

        result = await service.send_notification(payload)

        # Verify DB interaction
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        
        # Verify Gateway interaction
        mock_gateway.send_email.assert_awaited_once_with(
            to=payload.recipient_email,
            subject=payload.subject,
            content=payload.content
        )

        # Verify Result
        assert result.recipient_email == "borrower@example.com"
        assert result.status == "SENT"

    @pytest.mark.asyncio
    async def test_send_notification_gateway_failure(self, mock_db, mock_gateway, sample_application_id):
        """Test handling when external email gateway fails."""
        # Configure gateway to raise exception
        mock_gateway.send_email.side_effect = Exception("SMTP Timeout")
        
        service = MessagingService(mock_db, mock_gateway)
        payload = MessageCreate(
            application_id=sample_application_id,
            recipient_email="borrower@example.com",
            subject="Test",
            content="Test",
            category=MessageCategoryEnum.GENERAL
        )

        with pytest.raises(AppException) as exc_info:
            await service.send_notification(payload)
        
        assert "Failed to send notification" in str(exc_info.value)
        # Ensure DB rollback or no commit happened depending on logic, 
        # here we check commit wasn't called successfully
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_message_history(self, mock_db):
        """Test retrieving message history for an application."""
        service = MessagingService(mock_db)
        
        # Mock the query chain
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [
            Message(id=1, recipient_email="test@example.com", content="Msg 1", created_at=datetime.utcnow()),
            Message(id=2, recipient_email="test@example.com", content="Msg 2", created_at=datetime.utcnow())
        ]
        mock_db.execute.return_value = mock_result

        messages = await service.get_message_history(sample_application_id="app-123")
        
        assert len(messages) == 2
        mock_db.execute.assert_awaited_once()


@pytest.mark.unit
class TestConditionService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.get = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_condition_defaults_to_pending(self, mock_db, sample_application_id):
        """Test that creating a condition defaults status to PENDING."""
        service = ConditionService(mock_db)
        payload = ConditionCreate(
            application_id=sample_application_id,
            description="Provide recent pay stubs.",
            required_by_date=datetime(2024, 12, 31)
        )

        result = await service.create_condition(payload)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        
        # We inspect the object passed to add to verify defaults
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.status == ConditionStatusEnum.PENDING
        assert added_obj.description == "Provide recent pay stubs."

    @pytest.mark.asyncio
    async def test_fulfill_condition_success(self, mock_db):
        """Test marking a condition as MET."""
        service = ConditionService(mock_db)
        
        # Mock existing condition
        existing_condition = Condition(
            id=1,
            application_id="app-123",
            description="Test",
            status=ConditionStatusEnum.PENDING
        )
        mock_db.get.return_value = existing_condition

        update_payload = ConditionUpdate(status=ConditionStatusEnum.MET, notes="Documents verified.")
        result = await service.update_condition(condition_id=1, payload=update_payload)

        assert result.status == ConditionStatusEnum.MET
        assert result.notes == "Documents verified."
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fulfill_condition_not_found(self, mock_db):
        """Test error when trying to update a non-existent condition."""
        service = ConditionService(mock_db)
        mock_db.get.return_value = None

        with pytest.raises(AppException) as exc_info:
            await service.update_condition(condition_id=999, payload=ConditionUpdate(status=ConditionStatusEnum.MET))
        
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_pending_conditions_count(self, mock_db):
        """Test logic for counting pending conditions."""
        service = ConditionService(mock_db)
        
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 3
        mock_db.execute.return_value = mock_result

        count = await service.get_pending_conditions_count(application_id="app-123")
        
        assert count == 3
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_condition_invalid_date(self, mock_db, sample_application_id):
        """Test validation logic for required_by_date (must be in future)."""
        service = ConditionService(mock_db)
        
        # Date in the past
        past_date = datetime(2020, 1, 1)
        payload = ConditionCreate(
            application_id=sample_application_id,
            description="Test",
            required_by_date=past_date
        )

        with pytest.raises(ValueError) as exc_info:
            await service.create_condition(payload)
        
        assert "must be in the future" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_audit_fields_on_update(self, mock_db):
        """Ensure updated_at is modified when condition status changes."""
        service = ConditionService(mock_db)
        
        old_date = datetime(2023, 1, 1)
        condition = Condition(
            id=1,
            application_id="app-1",
            description="Test",
            status=ConditionStatusEnum.PENDING,
            updated_at=old_date
        )
        mock_db.get.return_value = condition

        await service.update_condition(1, ConditionUpdate(status=ConditionStatusEnum.MET))
        
        assert condition.updated_at > old_date

--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal
from datetime import datetime, timedelta

from mortgage_underwriting.modules.messaging_conditions.models import Condition, Message
from mortgage_underwriting.modules.messaging_conditions.schemas import ConditionStatusEnum, MessageCategoryEnum

@pytest.mark.integration
class TestConditionsAPI:
    
    @pytest.mark.asyncio
    async def test_create_condition_endpoint(self, client: AsyncClient, db_session, sample_application_id):
        """Test creating a condition via API."""
        # Mock the email gateway dependency in the app if necessary, 
        # but for conditions, it might not trigger an email immediately.
        # Here we test the endpoint persistence.
        
        payload = {
            "application_id": sample_application_id,
            "description": "Employment verification letter required.",
            "required_by_date": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }

        response = await client.post("/api/v1/messaging-conditions/conditions", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["status"] == ConditionStatusEnum.PENDING.value
        assert data["description"] == payload["description"]
        
        # Verify DB Persistence
        stmt = select(Condition).where(Condition.application_id == sample_application_id)
        result = await db_session.execute(stmt)
        db_condition = result.scalar_one_or_none()
        assert db_condition is not None
        assert db_condition.description == payload["description"]

    @pytest.mark.asyncio
    async def test_list_conditions_by_application(self, client: AsyncClient, db_session, sample_application_id):
        """Test retrieving all conditions for a specific application."""
        # Seed data
        cond1 = Condition(
            application_id=sample_application_id,
            description="Condition 1",
            status=ConditionStatusEnum.PENDING
        )
        cond2 = Condition(
            application_id=sample_application_id,
            description="Condition 2",
            status=ConditionStatusEnum.MET
        )
        db_session.add(cond1)
        db_session.add(cond2)
        await db_session.commit()

        response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={sample_application_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        descriptions = [c["description"] for c in data]
        assert "Condition 1" in descriptions
        assert "Condition 2" in descriptions

    @pytest.mark.asyncio
    async def test_update_condition_status(self, client: AsyncClient, db_session, sample_application_id):
        """Test updating a condition status (e.g., fulfilling it)."""
        # Seed data
        cond = Condition(
            application_id=sample_application_id,
            description="Initial Condition",
            status=ConditionStatusEnum.PENDING
        )
        db_session.add(cond)
        await db_session.commit()
        await db_session.refresh(cond)

        update_payload = {
            "status": ConditionStatusEnum.MET.value,
            "notes": "Document uploaded to portal."
        }

        response = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond.id}", json=update_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ConditionStatusEnum.MET.value
        assert data["notes"] == update_payload["notes"]
        
        # Verify DB Update
        await db_session.refresh(cond)
        assert cond.status == ConditionStatusEnum.MET
        assert cond.notes == update_payload["notes"]
        assert cond.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_condition_invalid_transition(self, client: AsyncClient, db_session, sample_application_id):
        """Test that invalid status transitions are rejected (if business logic enforces this)."""
        cond = Condition(
            application_id=sample_application_id,
            description="Completed",
            status=ConditionStatusEnum.MET
        )
        db_session.add(cond)
        await db_session.commit()
        await db_session.refresh(cond)

        # Attempt to revert MET to PENDING (assuming this is invalid logic)
        update_payload = {"status": ConditionStatusEnum.PENDING.value}
        
        response = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond.id}", json=update_payload)
        
        # Expecting 422 or 400 depending on implementation detail
        assert response.status_code in [400, 422]


@pytest.mark.integration
class TestMessagingAPI:
    
    @pytest.mark.asyncio
    async def test_send_message_endpoint(self, client: AsyncClient, db_session, sample_application_id):
        """Test sending a message via API."""
        payload = {
            "application_id": sample_application_id,
            "recipient_email": "user@example.com",
            "subject": "Application Update",
            "content": "Your application is under review.",
            "category": MessageCategoryEnum.GENERAL.value
        }

        # We expect 201, but the actual email sending might be mocked in the app setup 
        # or handled via background task. We check the DB record.
        response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["status"] in ["SENT", "QUEUED"] # Depending on sync/async implementation
        
        # Verify DB
        stmt = select(Message).where(Message.application_id == sample_application_id)
        result = await db_session.execute(stmt)
        db_msg = result.scalar_one_or_none()
        assert db_msg is not None
        assert db_msg.subject == "Application Update"
        # PIPEDA Check: Ensure content is not returned in list view (if implemented), 
        # but here we get detail view so it's okay for internal system.

    @pytest.mark.asyncio
    async def test_get_messages_by_application(self, client: AsyncClient, db_session, sample_application_id):
        """Test retrieving message history."""
        msg = Message(
            application_id=sample_application_id,
            recipient_email="test@example.com",
            subject="Subject 1",
            content="Body 1",
            status="SENT"
        )
        db_session.add(msg)
        await db_session.commit()

        response = await client.get(f"/api/v1/messaging-conditions/messages?application_id={sample_application_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["subject"] == "Subject 1"
        # Ensure PII is not leaked in logs (implicit check by not crashing)

    @pytest.mark.asyncio
    async def test_message_validation_missing_fields(self, client: AsyncClient):
        """Test validation error on missing required fields."""
        payload = {
            "recipient_email": "user@example.com",
            # Missing application_id, subject, content
        }

        response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
        
        assert response.status_code == 422 # Unprocessable Entity
        errors = response.json()["detail"]
        error_fields = [e["loc"][1] for e in errors]
        assert "application_id" in error_fields
        assert "subject" in error fields

    @pytest.mark.asyncio
    async def test_condition_workflow_integration(self, client: AsyncClient, db_session, sample_application_id):
        """Test a workflow: Create condition -> Send Message -> Fulfill Condition."""
        
        # 1. Create Condition
        cond_payload = {
            "application_id": sample_application_id,
            "description": "Upload ID",
            "required_by_date": (datetime.utcnow() + timedelta(days=5)).isoformat()
        }
        cond_resp = await client.post("/api/v1/messaging-conditions/conditions", json=cond_payload)
        assert cond_resp.status_code == 201
        cond_id = cond_resp.json()["id"]

        # 2. Send Message about Condition
        msg_payload = {
            "application_id": sample_application_id,
            "recipient_email": "borrower@example.com",
            "subject": "Action Required: Upload ID",
            "content": f"Please fulfill condition ID {cond_id}",
            "category": MessageCategoryEnum.DOCUMENT_REQUEST.value
        }
        msg_resp = await client.post("/api/v1/messaging-conditions/messages", json=msg_payload)
        assert msg_resp.status_code == 201

        # 3. Fulfill Condition
        update_resp = await client.patch(
            f"/api/v1/messaging-conditions/conditions/{cond_id}", 
            json={"status": ConditionStatusEnum.MET.value}
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == ConditionStatusEnum.MET.value

        # 4. Verify Final State
        final_cond_resp = await client.get(f"/api/v1/messaging-conditions/conditions/{cond_id}")
        assert final_cond_resp.json()["status"] == ConditionStatusEnum.MET.value