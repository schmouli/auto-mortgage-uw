import structlog
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, update
from sqlalchemy.orm import selectinload
from datetime import datetime

# FIXED: Reorganized imports - standard library first
from datetime import datetime
from typing import List, Optional

# Third-party imports
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, update
from sqlalchemy.orm import selectinload

# Local imports
from mortgage_underwriting.modules.messaging_conditions.models import Message, Condition, ConditionStatus
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    MessageCreateRequest,
    MessageUpdateReadRequest,
    ConditionCreateRequest,
    ConditionUpdateRequest,
    MessageResponse,
    ConditionResponse
)
from mortgage_underwriting.modules.messaging_conditions.exceptions import (
    MessageNotFoundError,
    ConditionNotFoundError,
    UnauthorizedAccessError
)

logger = structlog.get_logger(__name__)  # FIXED: Using structlog instead of logging


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
        
        logger.info("message_created", 
                   message_id=message.id, 
                   sender_id=sender_id, 
                   recipient_id=data.recipient_id)
        return MessageResponse.model_validate(message)

    async def get_message_by_id(self, message_id: int, user_id: int) -> MessageResponse:
        """Get a specific message by ID"""
        stmt = select(Message).where(Message.id == message_id)
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()
        
        if not message:
            logger.warning("message_not_found", message_id=message_id)
            raise MessageNotFoundError(f"Message with ID {message_id} not found")
            
        # Check if user has access to this message
        if message.sender_id != user_id and message.recipient_id != user_id:
            logger.warning("unauthorized_message_access", 
                          message_id=message_id, 
                          user_id=user_id)
            raise UnauthorizedAccessError("You do not have access to this message")
            
        return MessageResponse.model_validate(message)

    async def list_messages(
        self, 
        application_id: int, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> tuple[List[MessageResponse], int]:
        """List messages for an application with pagination"""
        # Count total messages
        count_stmt = select(func.count(Message.id)).where(
            and_(Message.application_id == application_id,
                 or_(Message.sender_id == user_id, Message.recipient_id == user_id))
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        
        # Get paginated messages
        stmt = select(Message).where(
            and_(Message.application_id == application_id,
                 or_(Message.sender_id == user_id, Message.recipient_id == user_id))
        ).order_by(Message.sent_at.desc()).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        messages = result.scalars().all()
        
        message_responses = [MessageResponse.model_validate(msg) for msg in messages]
        
        logger.info("messages_listed", 
                   application_id=application_id, 
                   user_id=user_id,
                   count=len(messages))
        return message_responses, total

    async def mark_message_as_read(
        self, 
        message_id: int, 
        user_id: int, 
        data: MessageUpdateReadRequest
    ) -> MessageResponse:
        """Mark a message as read/unread"""
        stmt = select(Message).where(Message.id == message_id)
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()
        
        if not message:
            logger.warning("message_not_found_for_update", message_id=message_id)
            raise MessageNotFoundError(f"Message with ID {message_id} not found")
            
        # Only recipient can mark as read
        if message.recipient_id != user_id:
            logger.warning("unauthorized_read_status_update", 
                          message_id=message_id, 
                          user_id=user_id)
            raise UnauthorizedAccessError("Only the recipient can update read status")
            
        update_stmt = update(Message).where(Message.id == message_id).values(
            is_read=data.is_read,
            read_at=datetime.utcnow() if data.is_read else None
        )
        await self.db.execute(update_stmt)
        await self.db.commit()
        
        # Refresh the message
        await self.db.refresh(message)
        
        logger.info("message_read_status_updated", 
                   message_id=message_id, 
                   is_read=data.is_read)
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
        
        logger.info("condition_created", 
                   condition_id=condition.id, 
                   application_id=application_id)
        return ConditionResponse.model_validate(condition)

    async def get_condition_by_id(self, condition_id: int, user_id: int) -> ConditionResponse:
        """Get a specific condition by ID"""
        stmt = select(Condition).where(Condition.id == condition_id)
        result = await self.db.execute(stmt)
        condition = result.scalar_one_or_none()
        
        if not condition:
            logger.warning("condition_not_found", condition_id=condition_id)
            raise ConditionNotFoundError(f"Condition with ID {condition_id} not found")
            
        return ConditionResponse.model_validate(condition)

    async def list_conditions(
        self, 
        application_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> tuple[List[ConditionResponse], int]:
        """List conditions for an application with pagination"""
        # Count total conditions
        count_stmt = select(func.count(Condition.id)).where(
            Condition.application_id == application_id
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        
        # Get paginated conditions
        stmt = select(Condition).where(
            Condition.application_id == application_id
        ).order_by(Condition.created_at.desc()).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        conditions = result.scalars().all()
        
        condition_responses = [ConditionResponse.model_validate(cond) for cond in conditions]
        
        logger.info("conditions_listed", 
                   application_id=application_id,
                   count=len(conditions))
        return condition_responses, total

    async def update_condition_status(
        self, 
        condition_id: int, 
        data: ConditionUpdateRequest,
        user_id: int
    ) -> ConditionResponse:
        """Update condition status"""
        stmt = select(Condition).where(Condition.id == condition_id)
        result = await self.db.execute(stmt)
        condition = result.scalar_one_or_none()
        
        if not condition:
            logger.warning("condition_not_found_for_update", condition_id=condition_id)
            raise ConditionNotFoundError(f"Condition with ID {condition_id} not found")
            
        update_data = {
            "status": data.status
        }
        
        if data.status == ConditionStatus.SATISFIED:
            update_data["satisfied_by"] = data.satisfied_by or user_id
            update_data["satisfied_at"] = datetime.utcnow()
            
        update_stmt = update(Condition).where(Condition.id == condition_id).values(**update_data)
        await self.db.execute(update_stmt)
        await self.db.commit()
        
        # Refresh the condition
        await self.db.refresh(condition)
        
        logger.info("condition_status_updated", 
                   condition_id=condition_id, 
                   status=data.status)
        return ConditionResponse.model_validate(condition)
```

```