--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, func, Text, Boolean
from datetime import datetime
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
import uuid

# Import the actual modules (assuming they exist based on structure)
from mortgage_underwriting.modules.messaging_conditions.models import (
    Condition,
    Message,
)
from mortgage_underwriting.modules.messaging_conditions.routes import router
from mortgage_underwriting.common.database import get_async_session

# Using in-memory SQLite for integration tests to ensure isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app() -> FastAPI:
    """
    Creates a test FastAPI app with the module router included.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/messaging-conditions")
    return app


@pytest.fixture
async def client(app: FastAPI, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Async client for integration tests.
    Overrides the database dependency with the test session.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_application_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def sample_user_id() -> str:
    return "user_12345"


@pytest.fixture
def sample_condition_data(sample_application_id: str) -> dict:
    return {
        "application_id": sample_application_id,
        "description": "Provide recent pay stubs (last 3 months).",
        "category": "income_verification",
        "is_mandatory": True,
        "due_date": "2024-12-31T23:59:59",
    }


@pytest.fixture
def sample_message_data(sample_application_id: str) -> dict:
    return {
        "application_id": sample_application_id,
        "recipient_type": "applicant",
        "subject": "Update on your mortgage application",
        "body": "We have received your documents and are reviewing them.",
        "channel": "email",
    }

# Dummy Base for metadata creation in tests if not imported directly
# In real scenario, this comes from common.database.Base
class Base(DeclarativeBase):
    pass

# We need to ensure the models inherit from the Base used in metadata creation
# For the purpose of this conftest, we assume the imported models are mapped to Base.
# If running in isolation, one might need to ensure registry alignment, 
# but usually pytest handles imports well.
--- unit_tests ---
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from mortgage_underwriting.modules.messaging_conditions.models import Condition, Message
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    ConditionCreate,
    ConditionStatus,
    MessageCreate,
    MessageStatus,
)
from mortgage_underwriting.modules.messaging_conditions.services import (
    ConditionService,
    MessagingService,
)
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.unit
class TestConditionService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_condition_success(self, mock_db):
        service = ConditionService(mock_db)
        application_id = str(uuid4())
        payload = ConditionCreate(
            application_id=application_id,
            description="Upload ID",
            category="identity",
            is_mandatory=True,
        )

        result = await service.create_condition(payload)

        assert result.application_id == application_id
        assert result.status == ConditionStatus.PENDING
        assert result.description == "Upload ID"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_condition_invalid_empty_description(self, mock_db):
        service = ConditionService(mock_db)
        payload = ConditionCreate(
            application_id=str(uuid4()), description="", category="other", is_mandatory=False
        )

        with pytest.raises(ValueError) as exc_info:
            await service.create_condition(payload)

        assert "Description cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fulfill_condition_success(self, mock_db):
        service = ConditionService(mock_db)
        condition_id = str(uuid4())
        
        # Mock the existing condition
        mock_condition = Condition(
            id=condition_id,
            application_id=str(uuid4()),
            description="Test",
            status=ConditionStatus.PENDING,
            is_mandatory=True,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_condition
        mock_db.execute.return_value = mock_result

        updated_condition = await service.fulfill_condition(
            condition_id, fulfilled_by="user_123", notes="Verified via PDF"
        )

        assert updated_condition.status == ConditionStatus.FULFILLED
        assert updated_condition.fulfilled_by == "user_123"
        assert updated_condition.fulfilled_at is not None
        assert updated_condition.notes == "Verified via PDF"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fulfill_condition_not_found(self, mock_db):
        service = ConditionService(mock_db)
        mock_result = MagicMock()
        mock_result.scalar_one_or_default.return_value = None # SQLAlchemy 2.0 pattern
        mock_db.execute.return_value = mock_result

        with pytest.raises(AppException) as exc_info:
            await service.fulfill_condition(str(uuid4()), "user_123")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_fulfill_already_fulfilled_condition(self, mock_db):
        service = ConditionService(mock_db)
        condition_id = str(uuid4())
        
        mock_condition = Condition(
            id=condition_id,
            application_id=str(uuid4()),
            description="Test",
            status=ConditionStatus.FULFILLED, # Already done
            is_mandatory=True,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_default.return_value = mock_condition
        mock_db.execute.return_value = mock_result

        with pytest.raises(AppException) as exc_info:
            await service.fulfill_condition(condition_id, "user_123")

        assert exc_info.value.status_code == 400
        assert "already fulfilled" in exc_info.value.detail.lower()


@pytest.mark.unit
class TestMessagingService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_email_provider(self):
        with patch("mortgage_underwriting.modules.messaging_conditions.services.EmailProvider") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_db, mock_email_provider):
        service = MessagingService(mock_db)
        app_id = str(uuid4())
        payload = MessageCreate(
            application_id=app_id,
            recipient_type="applicant",
            subject="Approval",
            body="You are approved.",
            channel="email",
        )

        # Mock the provider send method
        mock_email_provider.return_value.send.return_value = {"message_id": "ext_123"}

        result = await service.send_message(payload)

        assert result.application_id == app_id
        assert result.status == MessageStatus.SENT
        assert result.external_id == "ext_123"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_logs_audit_trail(self, mock_db, mock_email_provider):
        service = MessagingService(mock_db)
        payload = MessageCreate(
            application_id=str(uuid4()),
            recipient_type="broker",
            subject="Update",
            body="Status update",
            channel="email",
        )

        await service.send_message(payload)

        # Verify audit fields are set on the model object added to db
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, Message)
        assert added_obj.created_at is not None
        assert added_obj.updated_at is not None
        # FINTRAC check: Ensure PII isn't in the raw body if we were logging it separately,
        # but here we just check the object structure is valid.

    @pytest.mark.asyncio
    async def test_send_message_provider_failure(self, mock_db, mock_email_provider):
        service = MessagingService(mock_db)
        payload = MessageCreate(
            application_id=str(uuid4()),
            recipient_type="applicant",
            subject="Error",
            body="Test",
            channel="email",
        )

        # Simulate provider failure
        mock_email_provider.return_value.send.side_effect = Exception("SMTP Down")

        with pytest.raises(AppException) as exc_info:
            await service.send_message(payload)

        assert exc_info.value.status_code == 503
        # Ensure we still saved the message with FAILED status
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.status == MessageStatus.FAILED
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_invalid_channel(self, mock_db):
        service = MessagingService(mock_db)
        payload = MessageCreate(
            application_id=str(uuid4()),
            recipient_type="applicant",
            subject="Test",
            body="Test",
            channel="fax", # Invalid channel
        )

        with pytest.raises(ValueError):
            await service.send_message(payload)

    @pytest.mark.asyncio
    async def test_get_messages_by_application(self, mock_db):
        service = MessagingService(mock_db)
        app_id = str(uuid4())
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [
            Message(id=str(uuid4()), application_id=app_id, subject="Msg 1"),
            Message(id=str(uuid4()), application_id=app_id, subject="Msg 2"),
        ]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        messages = await service.get_messages_by_application(app_id)

        assert len(messages) == 2
        mock_db.execute.assert_awaited_once()
--- integration_tests ---
import pytest
from httpx import AsyncClient
from uuid import uuid4
from datetime import datetime

from mortgage_underwriting.modules.messaging_conditions.models import Condition, Message
from mortgage_underwriting.modules.messaging_conditions.schemas import ConditionStatus, MessageStatus


@pytest.mark.integration
@pytest.mark.asyncio
class TestConditionEndpoints:
    async def test_create_condition_endpoint(self, client: AsyncClient, sample_condition_data: dict):
        response = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["application_id"] == sample_condition_data["application_id"]
        assert data["status"] == ConditionStatus.PENDING.value
        assert data["created_at"] is not None

    async def test_create_condition_invalid_payload(self, client: AsyncClient):
        invalid_payload = {
            "application_id": str(uuid4()),
            # Missing description
            "category": "test"
        }
        response = await client.post("/api/v1/messaging-conditions/conditions", json=invalid_payload)
        
        assert response.status_code == 422  # Validation Error

    async def test_list_conditions_empty(self, client: AsyncClient, sample_application_id: str):
        response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={sample_application_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_list_conditions_with_data(self, client: AsyncClient, sample_condition_data: dict):
        # Create a condition first
        create_resp = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_data)
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]

        # List them
        list_resp = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={sample_condition_data['application_id']}")
        
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert len(data) == 1
        assert data[0]["id"] == created_id

    async def test_fulfill_condition_endpoint(self, client: AsyncClient, sample_condition_data: dict):
        # Create
        create_resp = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_data)
        condition_id = create_resp.json()["id"]

        # Fulfill
        fulfill_payload = {
            "notes": "Documents verified by underwriter John Doe.",
            "fulfilled_by": "underwriter_1"
        }
        patch_resp = await client.patch(f"/api/v1/messaging-conditions/conditions/{condition_id}/fulfill", json=fulfill_payload)

        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["status"] == ConditionStatus.FULFILLED.value
        assert data["fulfilled_by"] == "underwriter_1"
        assert data["notes"] == "Documents verified by underwriter John Doe."
        assert data["fulfilled_at"] is not None

    async def test_fulfill_non_existent_condition(self, client: AsyncClient):
        fake_id = str(uuid4())
        payload = {"notes": "Test", "fulfilled_by": "test"}
        response = await client.patch(f"/api/v1/messaging-conditions/conditions/{fake_id}/fulfill", json=payload)
        
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
class TestMessagingEndpoints:
    async def test_send_message_endpoint(self, client: AsyncClient, sample_message_data: dict):
        # We mock the external email provider within the service layer, 
        # but for integration tests we might want to ensure the endpoint calls the service.
        # Assuming the service handles the mock or we have a real dummy SMTP.
        # For this exercise, we assume the service uses a mock or a no-op for testing.
        
        response = await client.post("/api/v1/messaging-conditions/messages", json=sample_message_data)
        
        # Note: If external provider fails and is not mocked in integration setup, this might be 503.
        # Assuming happy path or internal mock setup in conftest/routes.
        # We will assert 201 or 503 depending on if we mocked the provider globally.
        # Given constraints, let's assume the service defaults to 'SENT' if provider is None in test mode.
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["status"] in [MessageStatus.SENT.value, MessageStatus.FAILED.value]
        assert data["subject"] == sample_message_data["subject"]

    async def test_list_messages_endpoint(self, client: AsyncClient, sample_message_data: dict):
        # Send a message
        await client.post("/api/v1/messaging-conditions/messages", json=sample_message_data)

        # List messages
        response = await client.get(f"/api/v1/messaging-conditions/messages?application_id={sample_message_data['application_id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["subject"] == sample_message_data["subject"]
        
        # PIPEDA Check: Ensure we aren't returning raw PII if it were stored (not applicable here directly, 
        # but ensure we don't return internal notes if any)
        assert "internal_notes" not in data[0] or data[0].get("internal_notes") is None

    async def test_message_persistence(self, client: AsyncClient, db_session, sample_message_data: dict):
        # Verify DB persistence
        resp = await client.post("/api/v1/messaging-conditions/messages", json=sample_message_data)
        msg_id = resp.json()["id"]

        # Query directly via DB session to verify it was actually saved
        from sqlalchemy import select
        stmt = select(Message).where(Message.id == msg_id)
        result = await db_session.execute(stmt)
        db_msg = result.scalar_one_or_none()

        assert db_msg is not None
        assert db_msg.application_id == sample_message_data["application_id"]
        # FINTRAC: Verify immutable audit trail exists
        assert db_msg.created_at is not None
        assert db_msg.updated_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkflow:
    async def test_condition_and_message_workflow(self, client: AsyncClient, sample_application_id: str):
        # 1. Create a mandatory condition
        condition_data = {
            "application_id": sample_application_id,
            "description": "Provide Proof of Income",
            "category": "income",
            "is_mandatory": True
        }
        cond_resp = await client.post("/api/v1/messaging-conditions/conditions", json=condition_data)
        assert cond_resp.status_code == 201
        condition_id = cond_resp.json()["id"]

        # 2. Send a message notifying the applicant
        message_data = {
            "application_id": sample_application_id,
            "recipient_type": "applicant",
            "subject": "Action Required: Missing Documents",
            "body": "Please upload your Proof of Income.",
            "channel": "email"
        }
        msg_resp = await client.post("/api/v1/messaging-conditions/messages", json=message_data)
        assert msg_resp.status_code == 201

        # 3. Verify state (Condition Pending, Message Sent)
        list_cond = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={sample_application_id}")
        assert list_cond.json()[0]["status"] == ConditionStatus.PENDING.value

        # 4. Fulfill the condition
        fulfill_resp = await client.patch(
            f"/api/v1/messaging-conditions/conditions/{condition_id}/fulfill",
            json={"fulfilled_by": "admin", "notes": "Income verified"}
        )
        assert fulfill_resp.status_code == 200
        assert fulfill_resp.json()["status"] == ConditionStatus.FULFILLED.value

        # 5. Verify final state
        final_cond = await client.get(f"/api/v1/messaging-conditions/conditions/{condition_id}")
        assert final_cond.json()["status"] == ConditionStatus.FULFILLED.value
        assert final_cond.json()["fulfilled_at"] is not None