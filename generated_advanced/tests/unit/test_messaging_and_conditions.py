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