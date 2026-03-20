--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from unittest.mock import AsyncMock, MagicMock

# Adjust imports based on actual project structure
from mortgage_underwriting.common.database import Base, get_async_session
from mortgage_underwriting.modules.messaging_conditions.routes import router as messaging_router
from mortgage_underwriting.modules.messaging_conditions.models import Condition, Message
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    ConditionCreate,
    ConditionStatus,
    MessageCreate,
    MessageType
)

# Test Database Configuration (SQLite in-memory for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncIterator[AsyncSession]:
    """
    Fixture to create a new database session for a test.
    Creates tables before test and drops them after.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """
    Fixture to create a test client that overrides the database dependency.
    """
    def override_get_db():
        yield db_session

    app = FastAPI()
    app.include_router(messaging_router, prefix="/api/v1/messaging-conditions")
    app.dependency_overrides[get_async_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

# --- Unit Test Fixtures ---

@pytest.fixture
def mock_db_session():
    """Mock AsyncSession for unit tests."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    return session

@pytest.fixture
def sample_condition_payload():
    return {
        "application_id": "app_12345",
        "description": "Provide latest T4 slip",
        "condition_type": "DocumentRequest",
        "due_date": "2024-12-31",
        "assigned_to": "underwriter_1"
    }

@pytest.fixture
def sample_condition_update_payload():
    return {
        "status": "Met",
        "notes": "Document received and verified."
    }

@pytest.fixture
def sample_message_payload():
    return {
        "application_id": "app_12345",
        "recipient_type": "Applicant",
        "subject": "Mortgage Application Update",
        "body": "Your application is under review. Please submit the requested documents.",
        "priority": "Normal"
    }

@pytest.fixture
def mock_condition_model():
    """Mocked ORM object for a Condition."""
    cond = MagicMock(spec=Condition)
    cond.id = 1
    cond.application_id = "app_12345"
    cond.description = "Provide latest T4 slip"
    cond.status = ConditionStatus.PENDING
    cond.created_by = "system"
    return cond

@pytest.fixture
def mock_message_model():
    """Mocked ORM object for a Message."""
    msg = MagicMock(spec=Message)
    msg.id = 1
    msg.application_id = "app_12345"
    msg.subject = "Mortgage Application Update"
    msg.status = "Sent"
    return msg
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.messaging_conditions.services import (
    ConditionService,
    MessageService
)
from mortgage_underwriting.modules.messaging_conditions.models import Condition, Message
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    ConditionCreate,
    ConditionUpdate,
    MessageCreate,
    ConditionStatus
)
from mortgage_underwriting.common.exceptions import AppException

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit

class TestConditionService:
    
    @pytest.mark.asyncio
    async def test_create_condition_success(self, mock_db_session, sample_condition_payload):
        # Arrange
        payload = ConditionCreate(**sample_condition_payload)
        service = ConditionService(mock_db_session)
        
        # Act
        result = await service.create_condition(payload, user_id="underwriter_1")
        
        # Assert
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()
        assert result.application_id == "app_12345"
        assert result.status == ConditionStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_condition_db_error(self, mock_db_session, sample_condition_payload):
        # Arrange
        payload = ConditionCreate(**sample_condition_payload)
        mock_db_session.commit.side_effect = SQLAlchemyError("DB connection failed")
        service = ConditionService(mock_db_session)
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_condition(payload, user_id="underwriter_1")
        
        assert "database error" in str(exc_info.value).lower()
        mock_db_session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_condition_status_success(self, mock_db_session):
        # Arrange
        mock_condition = MagicMock(spec=Condition)
        mock_condition.id = 1
        mock_condition.status = ConditionStatus.PENDING
        
        # Mock the result of get() to return our mock_condition
        service = ConditionService(mock_db_session)
        service.get_condition_by_id = AsyncMock(return_value=mock_condition)
        
        update_data = ConditionUpdate(status=ConditionStatus.MET, notes="Verified")
        
        # Act
        result = await service.update_condition(1, update_data)
        
        # Assert
        assert result.status == ConditionStatus.MET
        assert result.notes == "Verified"
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_condition_invalid_transition(self, mock_db_session):
        # Arrange
        # Logic: Cannot move from MET to PENDING usually, or WAIVED to PENDING
        mock_condition = MagicMock(spec=Condition)
        mock_condition.id = 1
        mock_condition.status = ConditionStatus.MET
        
        service = ConditionService(mock_db_session)
        service.get_condition_by_id = AsyncMock(return_value=mock_condition)
        
        update_data = ConditionUpdate(status=ConditionStatus.PENDING)
        
        # Act & Assert
        # Assuming service logic prevents invalid state changes
        with pytest.raises(AppException) as exc_info:
            await service.update_condition(1, update_data)
        
        assert "invalid status transition" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_list_conditions_by_application(self, mock_db_session):
        # Arrange
        app_id = "app_12345"
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            MagicMock(id=1, application_id=app_id, description="Cond A"),
            MagicMock(id=2, application_id=app_id, description="Cond B"),
        ]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        service = ConditionService(mock_db_session)
        
        # Act
        results = await service.list_conditions(application_id=app_id)
        
        # Assert
        assert len(results) == 2
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_condition_fails_immutability(self, mock_db_session):
        # Arrange
        # Regulatory Requirement: FINTRAC - Immutable audit trail
        # We should not have a delete method, or it should raise an error
        service = ConditionService(mock_db_session)
        
        # Check if method exists or raises NotImplementedError
        with pytest.raises(AttributeError):
             await service.delete_condition(1)


class TestMessageService:

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_db_session, sample_message_payload):
        # Arrange
        payload = MessageCreate(**sample_message_payload)
        service = MessageService(mock_db_session)
        
        # Act
        result = await service.send_message(payload, sender_id="system")
        
        # Assert
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        assert result.application_id == "app_12345"
        assert "subject" in str(result)

    @pytest.mark.asyncio
    async def test_send_message_pii_validation(self, mock_db_session):
        # Arrange
        # PIPEDA: Ensure no PII in subject/body is handled (logic usually in service or validator)
        # Here we test the service catches it if implemented
        dirty_payload = {
            "application_id": "app_123",
            "recipient_type": "Applicant",
            "subject": "SIN is 123-456-789", # Violation
            "body": "Clean body",
            "priority": "Normal"
        }
        payload = MessageCreate(**dirty_payload)
        service = MessageService(mock_db_session)
        
        # Act & Assert
        # Assuming service checks for PII patterns
        with pytest.raises(AppException) as exc_info:
            await service.send_message(payload, sender_id="user")
        
        assert "pii" in str(exc_info.value).lower() or "sensitive" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_message_history(self, mock_db_session):
        # Arrange
        app_id = "app_999"
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            MagicMock(id=1, application_id=app_id, subject="Msg 1"),
            MagicMock(id=2, application_id=app_id, subject="Msg 2"),
        ]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        service = MessageService(mock_db_session)
        
        # Act
        history = await service.get_messages(application_id=app_id)
        
        # Assert
        assert len(history) == 2
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mark_message_as_read(self, mock_db_session):
        # Arrange
        mock_message = MagicMock(spec=Message)
        mock_message.id = 1
        mock_message.is_read = False
        
        service = MessageService(mock_db_session)
        service.get_message_by_id = AsyncMock(return_value=mock_message)
        
        # Act
        result = await service.mark_as_read(message_id=1)
        
        # Assert
        assert result.is_read is True
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_invalid_recipient(self, mock_db_session):
        # Arrange
        invalid_payload = {
            "application_id": "app_123",
            "recipient_type": "Alien", # Invalid enum
            "subject": "Hello",
            "body": "World",
            "priority": "Normal"
        }
        
        # This should fail at Pydantic validation level
        with pytest.raises(ValueError):
            MessageCreate(**invalid_payload)

--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.messaging_conditions.models import Condition, Message
from mortgage_underwriting.modules.messaging_conditions.schemas import ConditionStatus

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_create_condition_endpoint(client: AsyncClient):
    # Arrange
    payload = {
        "application_id": "app_integration_01",
        "description": "Employment Letter Required",
        "condition_type": "DocumentRequest",
        "due_date": "2024-12-31",
        "assigned_to": "underwriter_A"
    }
    
    # Act
    response = await client.post("/api/v1/messaging-conditions/conditions", json=payload)
    
    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["application_id"] == "app_integration_01"
    assert data["status"] == "Pending"
    assert "created_at" in data

@pytest.mark.asyncio
async def test_get_conditions_endpoint(client: AsyncClient, db_session: AsyncSession):
    # Arrange - Create a condition directly in DB
    new_cond = Condition(
        application_id="app_integration_02",
        description="Bank Statements",
        status=ConditionStatus.PENDING,
        created_by="test_runner"
    )
    db_session.add(new_cond)
    await db_session.commit()
    await db_session.refresh(new_cond)
    
    # Act
    response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id=app_integration_02")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["description"] == "Bank Statements"

@pytest.mark.asyncio
async def test_update_condition_workflow(client: AsyncClient, db_session: AsyncSession):
    # Arrange - Create condition
    create_payload = {
        "application_id": "app_workflow_01",
        "description": "Proof of Income",
        "condition_type": "DocumentRequest",
        "assigned_to": "underwriter_B"
    }
    create_resp = await client.post("/api/v1/messaging-conditions/conditions", json=create_payload)
    cond_id = create_resp.json()["id"]
    
    # Act - Update condition to Met
    update_payload = {
        "status": "Met",
        "notes": "Verified via Paystub"
    }
    update_resp = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond_id}", json=update_payload)
    
    # Assert
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["status"] == "Met"
    assert updated_data["notes"] == "Verified via Paystub"
    
    # Verify in DB
    db_result = await db_session.get(Condition, cond_id)
    assert db_result.status == ConditionStatus.MET

@pytest.mark.asyncio
async def test_update_nonexistent_condition(client: AsyncClient):
    # Act
    update_payload = {"status": "Met"}
    response = await client.patch("/api/v1/messaging-conditions/conditions/99999", json=update_payload)
    
    # Assert
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_send_message_endpoint(client: AsyncClient):
    # Arrange
    payload = {
        "application_id": "app_msg_01",
        "recipient_type": "Applicant",
        "subject": "Application Status",
        "body": "Your file has been approved pending conditions.",
        "priority": "High"
    }
    
    # Act
    response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
    
    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["subject"] == "Application Status"
    assert data["status"] == "Sent" # Assuming default status

@pytest.mark.asyncio
async def test_get_messages_endpoint(client: AsyncClient, db_session: AsyncSession):
    # Arrange
    msg = Message(
        application_id="app_msg_history",
        recipient_type="Applicant",
        subject="Welcome",
        body="Welcome to the portal",
        created_by="system"
    )
    db_session.add(msg)
    await db_session.commit()
    
    # Act
    response = await client.get("/api/v1/messaging-conditions/messages?application_id=app_msg_history")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(m["subject"] == "Welcome" for m in data)

@pytest.mark.asyncio
async def test_pii_protection_in_logs(client: AsyncClient, caplog):
    """
    Test that sensitive data isn't logged.
    Note: In a real integration test, we might check the log output directly.
    Here we ensure the endpoint handles PII validation if configured.
    """
    # Arrange - Payload with potential PII pattern (SIN)
    payload = {
        "application_id": "app_pii_test",
        "recipient_type": "Applicant",
        "subject": "Update regarding SIN 123456789",
        "body": "Please verify info",
        "priority": "Normal"
    }
    
    # Act
    # Depending on implementation, this might return 400 or 422
    response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
    
    # Assert - If the service blocks PII
    # (Assuming the service implements this check as per regulations)
    # If the service doesn't block, this test documents the behavior.
    # For this exercise, we assume strict validation is active.
    assert response.status_code in [400, 422]

@pytest.mark.asyncio
async def test_audit_fields_immutable(client: AsyncClient, db_session: AsyncSession):
    """
    Regulatory: FINTRAC - Verify created_at/created_by are set and cannot be updated via API.
    """
    # Arrange
    payload = {
        "application_id": "app_audit_01",
        "description": "Audit Test",
        "condition_type": "Generic",
        "assigned_to": "user1"
    }
    resp = await client.post("/api/v1/messaging-conditions/conditions", json=payload)
    cond_id = resp.json()["id"]
    original_created_at = resp.json()["created_at"]
    
    # Act - Try to update created_at (should be ignored or rejected by schema)
    update_payload = {
        "status": "Waived",
        "created_at": "2020-01-01T00:00:00" # Malicious attempt
    }
    update_resp = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond_id}", json=update_payload)
    
    # Assert
    assert update_resp.status_code == 200
    # Verify created_at did not change
    assert update_resp.json()["created_at"] == original_created_at

@pytest.mark.asyncio
async def test_validation_empty_description(client: AsyncClient):
    # Arrange
    payload = {
        "application_id": "app_val_01",
        "description": "", # Invalid
        "condition_type": "Generic",
        "assigned_to": "user1"
    }
    
    # Act
    response = await client.post("/api/v1/messaging-conditions/conditions", json=payload)
    
    # Assert
    assert response.status_code == 422 # Validation Error