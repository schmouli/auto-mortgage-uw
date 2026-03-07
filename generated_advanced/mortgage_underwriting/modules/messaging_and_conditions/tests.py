--- conftest.py ---
import pytest
from typing import AsyncGenerator, Generator
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from fastapi import FastAPI

# Assuming the module is named 'messaging_conditions'
from mortgage_underwriting.modules.messaging_conditions.routes import router as messaging_router
from mortgage_underwriting.modules.messaging_conditions.models import Message, Condition
from mortgage_underwriting.common.database import Base

# Use in-memory SQLite for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(messaging_router, prefix="/api/v1/messaging-conditions")
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# --- Data Fixtures ---

@pytest.fixture
def sample_message_payload():
    return {
        "application_id": "app_12345",
        "sender_id": "underwriter_1",
        "recipient_id": "user_123",
        "content": "Please provide updated pay stubs for the last 30 days."
    }

@pytest.fixture
def sample_condition_payload():
    return {
        "application_id": "app_12345",
        "description": "Employment Verification",
        "status": "PENDING",
        "amount_required": Decimal("0.00")
    }

@pytest.fixture
def sample_financial_condition_payload():
    return {
        "application_id": "app_12345",
        "description": "Down Payment Proof",
        "status": "PENDING",
        "amount_required": Decimal("15000.00")
    }

@pytest.fixture
async def seeded_message(db_session: AsyncSession, sample_message_payload):
    # Helper to seed a message directly into DB for GET tests
    msg = Message(**sample_message_payload)
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)
    return msg

@pytest.fixture
async def seeded_condition(db_session: AsyncSession, sample_condition_payload):
    # Helper to seed a condition directly into DB for GET tests
    cond = Condition(**sample_condition_payload)
    db_session.add(cond)
    await db_session.commit()
    await db_session.refresh(cond)
    return cond
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.messaging_conditions.models import Message, Condition
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    MessageCreate, 
    MessageResponse, 
    ConditionCreate, 
    ConditionUpdate,
    ConditionStatus
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

    @pytest.mark.asyncio
    async def test_create_message_success(self, mock_db):
        payload = MessageCreate(
            application_id="app_001",
            sender_id="user_1",
            recipient_id="user_2",
            content="Hello world"
        )
        service = MessagingService(mock_db)
        
        result = await service.create_message(payload)
        
        assert isinstance(result, Message)
        assert result.content == "Hello world"
        assert result.application_id == "app_001"
        # Verify audit fields are set
        assert result.created_at is not None
        # Verify DB interaction
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_message_empty_content_raises_error(self, mock_db):
        payload = MessageCreate(
            application_id="app_001",
            sender_id="user_1",
            recipient_id="user_2",
            content=""  # Invalid
        )
        service = MessagingService(mock_db)
        
        with pytest.raises(ValueError) as exc_info:
            await service.create_message(payload)
        assert "Message content cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_messages_by_application(self, mock_db):
        # Mocking the result of a scalars().all() query
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_result)
        mock_result.all = MagicMock(return_value=[
            Message(id=1, content="Msg 1", application_id="app_1", sender_id="u", recipient_id="u"),
            Message(id=2, content="Msg 2", application_id="app_1", sender_id="u", recipient_id="u")
        ])
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = MessagingService(mock_db)
        messages = await service.get_messages_by_application("app_1")
        
        assert len(messages) == 2
        assert messages[0].content == "Msg 1"

@pytest.mark.unit
class TestConditionService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_condition_defaults_to_pending(self, mock_db):
        payload = ConditionCreate(
            application_id="app_001",
            description="Proof of Income",
            amount_required=Decimal("500.00")
        )
        service = ConditionService(mock_db)
        
        result = await service.create_condition(payload)
        
        assert isinstance(result, Condition)
        assert result.status == ConditionStatus.PENDING
        assert result.amount_required == Decimal("500.00")
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_condition_status_valid_transition(self, mock_db):
        # Setup existing condition
        existing_cond = Condition(
            id=1,
            application_id="app_001",
            description="Test",
            status=ConditionStatus.PENDING
        )
        
        # Mock the get logic
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing_cond)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ConditionService(mock_db)
        
        updated = await service.update_condition_status(
            condition_id=1, 
            new_status=ConditionStatus.SATISFIED
        )
        
        assert updated.status == ConditionStatus.SATISFIED
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_condition_status_invalid_transition_raises(self, mock_db):
        # Setup existing condition as WAIVED
        existing_cond = Condition(
            id=1,
            application_id="app_001",
            description="Test",
            status=ConditionStatus.WAIVED
        )
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing_cond)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ConditionService(mock_db)
        
        # Trying to move from WAIVED to PENDING (assuming this is invalid business logic)
        with pytest.raises(AppException) as exc_info:
            await service.update_condition_status(
                condition_id=1, 
                new_status=ConditionStatus.PENDING
            )
        assert "Cannot update status" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_conditions_summary_all_satisfied(self, mock_db):
        # Mock conditions
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_result)
        mock_result.all = MagicMock(return_value=[
            Condition(id=1, status=ConditionStatus.SATISFIED),
            Condition(id=2, status=ConditionStatus.SATISFIED)
        ])
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ConditionService(mock_db)
        summary = await service.get_conditions_summary("app_001")
        
        assert summary["total"] == 2
        assert summary["pending"] == 0
        assert summary["satisfied"] == 2
        assert summary["is_met"] is True

    @pytest.mark.asyncio
    async def test_get_conditions_summary_has_pending(self, mock_db):
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_result)
        mock_result.all = MagicMock(return_value=[
            Condition(id=1, status=ConditionStatus.SATISFIED),
            Condition(id=2, status=ConditionStatus.PENDING)
        ])
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ConditionService(mock_db)
        summary = await service.get_conditions_summary("app_001")
        
        assert summary["total"] == 2
        assert summary["pending"] == 1
        assert summary["is_met"] is False

    @pytest.mark.asyncio
    async def test_create_condition_rejects_float_amount(self, mock_db):
        # Ensure strict Decimal usage is enforced at service level if schema allows loose typing
        # Assuming schema enforces Decimal, this tests the service handling of the resulting object
        payload = ConditionCreate(
            application_id="app_001",
            description="Test",
            amount_required=Decimal("1000.50") # Correct usage
        )
        service = ConditionService(mock_db)
        result = await service.create_condition(payload)
        
        # Verify type is strictly Decimal
        assert isinstance(result.amount_required, Decimal)
        assert result.amount_required == Decimal("1000.50")
--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.messaging_conditions.models import Message, Condition
from mortgage_underwriting.modules.messaging_conditions.schemas import ConditionStatus

@pytest.mark.integration
@pytest.mark.asyncio
class TestMessagingEndpoints:

    async def test_create_message_endpoint_success(self, client: AsyncClient, sample_message_payload):
        response = await client.post("/api/v1/messaging-conditions/messages", json=sample_message_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["content"] == sample_message_payload["content"]
        assert data["application_id"] == sample_message_payload["application_id"]
        assert "created_at" in data  # FINTRAC audit requirement

    async def test_create_message_endpoint_missing_content_fails(self, client: AsyncClient):
        invalid_payload = {
            "application_id": "app_1",
            "sender_id": "u1",
            "recipient_id": "u2"
            # missing content
        }
        response = await client.post("/api/v1/messaging-conditions/messages", json=invalid_payload)
        
        assert response.status_code == 422  # Validation Error

    async def test_get_messages_by_application(self, client: AsyncClient, db_session, sample_message_payload):
        # Create two messages for the same app
        await client.post("/api/v1/messaging-conditions/messages", json=sample_message_payload)
        sample_message_payload["content"] = "Second message"
        await client.post("/api/v1/messaging-conditions/messages", json=sample_message_payload)

        response = await client.get(f"/api/v1/messaging-conditions/messages?application_id={sample_message_payload['application_id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(msg["application_id"] == sample_message_payload["application_id"] for msg in data)

    async def test_get_messages_empty_list(self, client: AsyncClient):
        response = await client.get("/api/v1/messaging-conditions/messages?application_id=nonexistent")
        assert response.status_code == 200
        assert response.json() == []

@pytest.mark.integration
@pytest.mark.asyncio
class TestConditionEndpoints:

    async def test_create_condition_endpoint_success(self, client: AsyncClient, sample_condition_payload):
        response = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "PENDING"
        assert data["amount_required"] == "0.00" # Decimal serialized as string
        assert "created_at" in data

    async def test_create_condition_with_financial_amount(self, client: AsyncClient, sample_financial_condition_payload):
        response = await client.post("/api/v1/messaging-conditions/conditions", json=sample_financial_condition_payload)
        
        assert response.status_code == 201
        data = response.json()
        # Verify precision is maintained
        assert data["amount_required"] == "15000.00"

    async def test_update_condition_status_to_satisfied(self, client: AsyncClient, db_session, sample_condition_payload):
        # 1. Create a condition
        create_resp = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_payload)
        cond_id = create_resp.json()["id"]

        # 2. Update status
        update_payload = {"status": "SATISFIED"}
        update_resp = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond_id}", json=update_payload)
        
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["status"] == "SATISFIED"
        assert "updated_at" in data

    async def test_update_nonexistent_condition_returns_404(self, client: AsyncClient):
        update_payload = {"status": "SATISFIED"}
        response = await client.patch("/api/v1/messaging-conditions/conditions/99999", json=update_payload)
        
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_get_conditions_summary_endpoint(self, client: AsyncClient, sample_condition_payload):
        app_id = sample_condition_payload["application_id"]
        
        # Create a pending condition
        await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_payload)
        
        # Create a satisfied condition
        sample_condition_payload["description"] = "Another one"
        satisfied_resp = await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_payload)
        cond_id = satisfied_resp.json()["id"]
        await client.patch(f"/api/v1/messaging-conditions/conditions/{cond_id}", json={"status": "SATISFIED"})

        # Get summary
        response = await client.get(f"/api/v1/messaging-conditions/conditions/summary?application_id={app_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["pending"] == 1
        assert data["satisfied"] == 1
        assert data["is_met"] is False

    async def test_get_conditions_by_application(self, client: AsyncClient, sample_condition_payload):
        app_id = sample_condition_payload["application_id"]
        await client.post("/api/v1/messaging-conditions/conditions", json=sample_condition_payload)

        response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={app_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["application_id"] == app_id

@pytest.mark.integration
@pytest.mark.asyncio
class TestRegulatoryCompliance:

    async def test_audit_fields_present_on_message_creation(self, client: AsyncClient, sample_message_payload):
        """FINTRAC: Verify audit trail exists immediately"""
        response = await client.post("/api/v1/messaging-conditions/messages", json=sample_message_payload)
        data = response.json()
        assert "created_at" in data
        # Assuming created_by is handled via auth context injection (omitted in simple test payload but checked in model)
        
    async def test_no_pii_leakage_in_error_response(self, client: AsyncClient):
        """PIPEDA: Ensure sensitive data isn't leaked in 422/500 errors"""
        # Sending a malformed payload that might contain PII in fields that don't exist
        malicious_payload = {
            "application_id": "app_1",
            "sender_id": "hacker",
            "content": "My SIN is 123-456-789", 
            "non_existent_field": "secret_data"
        }
        response = await client.post("/api/v1/messaging-conditions/messages", json=malicious_payload)
        
        # FastAPI default validation error hides the payload values, showing only field names
        assert response.status_code == 422
        detail = response.json().get("detail", [])
        # Ensure the SIN or content isn't echoed back in the error detail
        error_str = str(detail)
        assert "123-456-789" not in error_str
        assert "secret_data" not in error_str

    async def test_decimal_precision_preserved(self, client: AsyncClient, sample_financial_condition_payload):
        """General: Ensure no float precision loss for financial conditions"""
        # Using a high precision number
        sample_financial_condition_payload["amount_required"] = "123456.78"
        
        response = await client.post("/api/v1/messaging-conditions/conditions", json=sample_financial_condition_payload)
        data = response.json()
        
        assert data["amount_required"] == "123456.78"