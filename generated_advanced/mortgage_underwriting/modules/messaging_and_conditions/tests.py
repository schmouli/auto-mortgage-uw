--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, func, Numeric, Text, Integer
from datetime import datetime
from fastapi import FastAPI

# Import the module under test
from mortgage_underwriting.modules.messaging_conditions.routes import router
from mortgage_underwriting.common.config import settings

# Test Database Setup (In-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

# Mock Models matching the expected schema structure for testing
class ConditionModel(Base):
    __tablename__ = "conditions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, index=True)
    description: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="PENDING") # PENDING, MET, WAIVED
    required_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

class MessageModel(Base):
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, index=True)
    recipient: Mapped[str] = mapped_column(String(255)) # Encrypted in real impl
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/messaging-conditions")
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Async client that overrides the get_db dependency to use the test session.
    """
    # Dependency override
    from mortgage_underwriting.common.database import get_async_session
    
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

# --- Fixtures for Test Data ---

@pytest.fixture
def valid_condition_payload():
    return {
        "application_id": 101,
        "description": "Provide recent pay stubs",
        "status": "PENDING",
        "required_amount": None
    }

@pytest.fixture
def monetary_condition_payload():
    return {
        "application_id": 102,
        "description": "Down payment verification",
        "status": "PENDING",
        "required_amount": "50000.00"
    }

@pytest.fixture
def valid_message_payload():
    return {
        "application_id": 101,
        "recipient": "applicant@example.com",
        "subject": "Underwriting Condition Added",
        "body": "Please upload your pay stubs."
    }

@pytest.fixture
async def seeded_condition(db_session: AsyncSession):
    # Helper to seed a condition for GET/UPDATE tests
    condition = ConditionModel(
        application_id=999,
        description="Test Condition",
        status="PENDING"
    )
    db_session.add(condition)
    await db_session.commit()
    await db_session.refresh(condition)
    return condition
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

# Import from the module under test
from mortgage_underwriting.modules.messaging_conditions.services import (
    ConditionService,
    MessageService
)
from mortgage_underwriting.modules.messaging_conditions.exceptions import (
    ConditionNotFoundError,
    InvalidStatusTransitionError
)

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
        payload = {
            "application_id": 1,
            "description": "Provide ID",
            "required_amount": Decimal("0.00")
        }
        
        result = await service.create_condition(payload)
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        # Check that the returned object matches expected structure
        assert result.application_id == 1
        assert result.status == "PENDING" # Default status

    @pytest.mark.asyncio
    async def test_create_condition_with_monetary_value(self, mock_db):
        service = ConditionService(mock_db)
        payload = {
            "application_id": 1,
            "description": "Pay Fee",
            "required_amount": Decimal("500.00")
        }
        
        result = await service.create_condition(payload)
        
        assert result.required_amount == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_create_condition_db_failure(self, mock_db):
        mock_db.commit.side_effect = SQLAlchemyError("DB Connection failed")
        service = ConditionService(mock_db)
        
        with pytest.raises(SQLAlchemyError):
            await service.create_condition({"application_id": 1, "description": "Fail"})

    @pytest.mark.asyncio
    async def test_update_condition_status_valid_transition(self, mock_db):
        # Mock the fetch logic
        mock_condition = MagicMock()
        mock_condition.id = 1
        mock_condition.status = "PENDING"
        mock_db.scalar.return_value = mock_condition
        
        service = ConditionService(mock_db)
        
        updated = await service.update_condition_status(condition_id=1, new_status="MET")
        
        assert updated.status == "MET"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_condition_status_invalid_transition(self, mock_db):
        # Mock the fetch logic - already MET
        mock_condition = MagicMock()
        mock_condition.id = 1
        mock_condition.status = "MET"
        mock_db.scalar.return_value = mock_condition
        
        service = ConditionService(mock_db)
        
        # Assuming logic prevents moving MET back to PENDING
        with pytest.raises(InvalidStatusTransitionError):
            await service.update_condition_status(condition_id=1, new_status="PENDING")

    @pytest.mark.asyncio
    async def test_update_condition_not_found(self, mock_db):
        mock_db.scalar.return_value = None
        service = ConditionService(mock_db)
        
        with pytest.raises(ConditionNotFoundError):
            await service.update_condition_status(condition_id=999, new_status="MET")

    @pytest.mark.asyncio
    async def test_get_conditions_by_application(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            MagicMock(id=1, description="Cond 1"),
            MagicMock(id=2, description="Cond 2")
        ]
        mock_db.execute.return_value = mock_result
        
        service = ConditionService(mock_db)
        conditions = await service.get_conditions_by_application(application_id=1)
        
        assert len(conditions) == 2
        mock_db.execute.assert_awaited_once()

@pytest.mark.unit
class TestMessageService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_db):
        service = MessageService(mock_db)
        payload = {
            "application_id": 1,
            "recipient": "user@example.com",
            "subject": "Test",
            "body": "Content"
        }
        
        result = await service.send_message(payload)
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        assert result.recipient == "user@example.com"

    @pytest.mark.asyncio
    async def test_send_message_sanitizes_pii_in_logs(self, mock_db, caplog):
        """
        Verify that sensitive data (like SIN if present in body) is not logged.
        Although this module handles generic messages, we ensure PII protection pattern.
        """
        service = MessageService(mock_db)
        payload = {
            "application_id": 1,
            "recipient": "user@example.com",
            "subject": "Urgent",
            "body": "Please verify your SIN: 123-456-789"
        }
        
        # Patch logger to capture output
        with patch("mortgage_underwriting.modules.messaging_conditions.services.logger") as mock_logger:
            await service.send_message(payload)
            
            # Ensure info was called, but check that the specific SIN string is NOT in the call args
            # (In a real scenario, the service would sanitize before logging)
            calls = str(mock_logger.info.call_args)
            assert "123-456-789" not in calls

    @pytest.mark.asyncio
    async def test_send_message_empty_body_raises_error(self, mock_db):
        service = MessageService(mock_db)
        payload = {
            "application_id": 1,
            "recipient": "user@example.com",
            "subject": "Test",
            "body": ""
        }
        
        # Assuming Pydantic validation happens before or inside service
        # Here we test service level validation if exists
        with pytest.raises(ValueError): # Or specific AppException
            await service.send_message(payload)
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal

@pytest.mark.integration
@pytest.mark.asyncio
class TestMessagingConditionsAPI:

    async def test_create_condition_endpoint(self, client, valid_condition_payload):
        response = await client.post("/api/v1/messaging-conditions/conditions", json=valid_condition_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["application_id"] == 101
        assert data["status"] == "PENDING"
        assert "created_at" in data

    async def test_create_monetary_condition_endpoint(self, client, monetary_condition_payload):
        response = await client.post("/api/v1/messaging-conditions/conditions", json=monetary_condition_payload)
        
        assert response.status_code == 201
        data = response.json()
        # Ensure Decimal is serialized correctly (string in JSON)
        assert data["required_amount"] == "50000.00"

    async def test_create_condition_invalid_payload(self, client):
        # Missing required fields
        response = await client.post("/api/v1/messaging-conditions/conditions", json={"application_id": 1})
        
        assert response.status_code == 422 # Unprocessable Entity

    async def test_get_conditions_for_application(self, client, valid_condition_payload):
        # Create two conditions
        await client.post("/api/v1/messaging-conditions/conditions", json=valid_condition_payload)
        payload_2 = {**valid_condition_payload, "description": "Second Condition"}
        await client.post("/api/v1/messaging-conditions/conditions", json=payload_2)
        
        # Retrieve
        response = await client.get(f"/api/v1/messaging-conditions/conditions?application_id={valid_condition_payload['application_id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_update_condition_status(self, client, seeded_condition):
        # seeded_condition comes from conftest with ID
        response = await client.patch(
            f"/api/v1/messaging-conditions/conditions/{seeded_condition.id}",
            json={"status": "MET"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "MET"
        assert data["id"] == seeded_condition.id

    async def test_update_condition_invalid_status(self, client, seeded_condition):
        response = await client.patch(
            f"/api/v1/messaging-conditions/conditions/{seeded_condition.id}",
            json={"status": "INVALID_STATUS"}
        )
        
        assert response.status_code == 422

    async def test_update_nonexistent_condition(self, client):
        response = await client.patch(
            "/api/v1/messaging-conditions/conditions/99999",
            json={"status": "MET"}
        )
        
        assert response.status_code == 404

    async def test_send_message_endpoint(self, client, valid_message_payload):
        response = await client.post("/api/v1/messaging-conditions/messages", json=valid_message_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["subject"] == "Underwriting Condition Added"

    async def test_send_message_missing_recipient(self, client):
        payload = {
            "application_id": 1,
            "subject": "Hello",
            "body": "World"
            # Missing recipient
        }
        response = await client.post("/api/v1/messaging-conditions/messages", json=payload)
        assert response.status_code == 422

    async def test_get_messages_for_application(self, client, valid_message_payload):
        await client.post("/api/v1/messaging-conditions/messages", json=valid_message_payload)
        
        response = await client.get(f"/api/v1/messaging-conditions/messages?application_id={valid_message_payload['application_id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["application_id"] == valid_message_payload['application_id']

    async def test_full_workflow_condition_to_message(self, client, valid_condition_payload, valid_message_payload):
        # 1. Create Condition
        cond_resp = await client.post("/api/v1/messaging-conditions/conditions", json=valid_condition_payload)
        assert cond_resp.status_code == 201
        cond_id = cond_resp.json()["id"]
        
        # 2. Send Message about the condition
        msg_payload = {
            **valid_message_payload,
            "body": f"Please address condition #{cond_id}"
        }
        msg_resp = await client.post("/api/v1/messaging-conditions/messages", json=msg_payload)
        assert msg_resp.status_code == 201
        
        # 3. Mark condition as Met
        patch_resp = await client.patch(f"/api/v1/messaging-conditions/conditions/{cond_id}", json={"status": "MET"})
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "MET"
        
        # 4. Verify history (audit fields)
        get_cond_resp = await client.get(f"/api/v1/messaging-conditions/conditions/{cond_id}")
        cond_data = get_cond_resp.json()
        assert cond_data["created_at"] is not None
        assert cond_data["updated_at"] is not None
```