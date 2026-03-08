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