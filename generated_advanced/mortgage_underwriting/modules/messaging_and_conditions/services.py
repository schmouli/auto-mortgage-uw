```python
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, update
from datetime import datetime
import logging

from .models import Message, Condition, ConditionStatus
from .schemas import (
    MessageCreateRequest,
    MessageUpdateReadRequest,
    ConditionCreateRequest,
    ConditionUpdateRequest,
    MessageResponse,
    ConditionResponse
)
from .exceptions import (
    MessageNotFoundError,
    ConditionNotFoundError,
    UnauthorizedAccessError
)

logger = logging.getLogger(__name__)


class MessagingService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_message(
        self,
        application_id: int,
        sender_id: int,
        data: MessageCreateRequest
    ) -> MessageResponse:
        """Create a new message"""
        message = Message(
            application_id=application_id,
            sender_id=sender_id,
            recipient_id=data.recipient_id,
            body=data.body
        )
        
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        
        logger.info(f"Message {message.id} created from user {sender_id} to {data.recipient_id}")
        return MessageResponse.model_validate(message)

    async def get_message_thread(
        self,
        application_id: int,
        user_id: int
    ) -> List[MessageResponse]:
        """Get all messages for an application visible to the user"""
        result = await self.db.execute(
            select(Message)
            .where(
                and_(
                    Message.application_id == application_id,
                    Message.sender_id == user_id or Message.recipient_id == user_id
                )
            )
            .order_by(Message.sent_at.asc())
        )
        messages = result.scalars().all()
        return [MessageResponse.model_validate(msg) for msg in messages]

    async def mark_message_as_read(
        self,
        application_id: int,
        message_id: int,
        user_id: int,
        data: MessageUpdateReadRequest
    ) -> MessageResponse:
        """Mark a message as read if user is recipient"""
        result = await self.db.execute(
            select(Message)
            .where(
                and_(
                    Message.id == message_id,
                    Message.application_id == application_id,
                    Message.recipient_id == user_id
                )
            )
        )
        message = result.scalar_one_or_none()
        
        if not message:
            raise MessageNotFoundError(f"Message {message_id} not found")
            
        if data.is_read and not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(message)
            logger.info(f"Message {message_id} marked as read by user {user_id}")
        
        return MessageResponse.model_validate(message)


class ConditionService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_condition(
        self,
        application_id: int,
        data: ConditionCreateRequest
    ) -> ConditionResponse:
        """Create a new condition"""
        condition = Condition(
            application_id=application_id,
            lender_submission_id=data.lender_submission_id,
            description=data.description,
            condition_type=data.condition_type,
            required_by_date=data.required_by_date
        )
        
        self.db.add(condition)
        await self.db.flush()
        await self.db.refresh(condition)
        
        logger.info(f"Condition {condition.id} created for application {application_id}")
        return ConditionResponse.model_validate(condition)

    async def list_conditions(
        self,
        application_id: int
    ) -> List[ConditionResponse]:
        """List all conditions for an application"""
        result = await self.db.execute(
            select(Condition)
            .where(Condition.application_id == application_id)
            .order_by(Condition.created_at.desc())
        )
        conditions = result.scalars().all()
        return [ConditionResponse.model_validate(cond) for cond in conditions]

    async def list_outstanding_conditions(
        self,
        application_id: int
    ) -> List[ConditionResponse]:
        """List only outstanding conditions for an application"""
        result = await self.db.execute(
            select(Condition)
            .where(
                and_(
                    Condition.application_id == application_id,
                    Condition.status == ConditionStatus.OUTSTANDING
                )
            )
            .order_by(Condition.required_by_date.asc())
        )
        conditions = result.scalars().all()
        return [ConditionResponse.model_validate(cond) for cond in conditions]

    async def update_condition_status(
        self,
        application_id: int,
        condition_id: int,
        user_id: int,
        data: ConditionUpdateRequest
    ) -> ConditionResponse:
        """Update the status of a condition"""
        result = await self.db.execute(
            select(Condition)
            .where(
                and_(
                    Condition.id == condition_id,
                    Condition.application_id == application_id
                )
            )
        )
        condition = result.scalar_one_or_none()
        
        if not condition:
            raise ConditionNotFoundError(f"Condition {condition_id} not found")

        # Update fields based on status change
        if data.status != condition.status:
            condition.status = data.status
            
            if data.status == ConditionStatus.SATISFIED:
                condition.satisfied_at = datetime.utcnow()
                condition.satisfied_by = user_id
            elif data.status in (ConditionStatus.OUTSTANDING, ConditionStatus.WAIVED):
                condition.satisfied_at = None
                condition.satisfied_by = None
                
            await self.db.commit()
            await self.db.refresh(condition)
            logger.info(f"Condition {condition_id} status updated to {data.status}")

        return ConditionResponse.model_validate(condition)
```