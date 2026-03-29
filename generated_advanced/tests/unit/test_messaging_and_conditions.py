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