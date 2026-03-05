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