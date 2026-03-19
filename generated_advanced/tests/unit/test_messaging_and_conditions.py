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