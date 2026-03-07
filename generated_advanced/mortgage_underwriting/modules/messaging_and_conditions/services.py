from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.modules.messaging.exceptions import MessagingError, ConditionError
from mortgage_underwriting.modules.messaging.models import Message, Condition
from mortgage_underwriting.modules.messaging.schemas import MessageCreate, MessageUpdateRead, ConditionCreate, ConditionUpdateStatus

logger = structlog.get_logger()

class MessagingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def send_message(self, application_id: int, sender_id: int, payload: MessageCreate) -> Message:
        # FIXED: Added proper validation for all inputs
        if application_id <= 0:
            raise MessagingError("Invalid application ID")
        if sender_id <= 0:
            raise MessagingError("Invalid sender ID")
        if payload.recipient_id <= 0:
            raise MessagingError("Invalid recipient ID")
        
        logger.info("sending_message", application_id=application_id, sender_id=sender_id)
        
        message = Message(
            application_id=application_id,
            sender_id=sender_id,
            recipient_id=payload.recipient_id,
            body=payload.body
        )
        
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        
        logger.info("message_sent", message_id=message.id)
        return message

    async def get_messages(
        self,
        application_id: int,
        page: int = 1,
        per_page: int = 50,
        is_read: Optional[bool] = None,
        sender_id: Optional[int] = None,
        before_date: Optional[datetime] = None,
        after_date: Optional[datetime] = None
    ) -> Tuple[List[Message], int]:
        # FIXED: Added validation for all inputs
        if application_id <= 0:
            raise MessagingError("Invalid application ID")
        if page < 1:
            raise MessagingError("Page must be greater than 0")
        if per_page < 1 or per_page > 200:
            raise MessagingError("Per page must be between 1 and 200")
        
        logger.info("fetching_messages", application_id=application_id, page=page, per_page=per_page)
        
        query = select(Message).where(Message.application_id == application_id)
        
        if is_read is not None:
            query = query.where(Message.is_read == is_read)
        if sender_id is not None:
            query = query.where(Message.sender_id == sender_id)
        if before_date is not None:
            query = query.where(Message.sent_at <= before_date)
        if after_date is not None:
            query = query.where(Message.sent_at >= after_date)
            
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        result = await self.db.execute(query)
        messages = result.scalars().all()
        
        logger.info("messages_fetched", total=total, returned=len(messages))
        return messages, total

    async def mark_message_as_read(self, message_id: int, user_id: int) -> Message:
        # FIXED: Added validation for all inputs
        if message_id <= 0:
            raise MessagingError("Invalid message ID")
        if user_id <= 0:
            raise MessagingError("Invalid user ID")
            
        logger.info("marking_message_read", message_id=message_id, user_id=user_id)
        
        query = select(Message).where(Message.id == message_id)
        result = await self.db.execute(query)
        message = result.scalar_one_or_none()
        
        if not message:
            raise MessagingError(f"Message {message_id} not found")
            
        if message.recipient_id != user_id:
            raise MessagingError("Only recipient can mark message as read")
            
        message.is_read = True
        message.read_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(message)
        
        logger.info("message_marked_read", message_id=message.id)
        return message

class ConditionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add_condition(self, application_id: int, payload: ConditionCreate) -> Condition:
        # FIXED: Added validation for all inputs
        if application_id <= 0:
            raise ConditionError("Invalid application ID")
        
        logger.info("adding_condition", application_id=application_id)
        
        condition = Condition(
            application_id=application_id,
            description=payload.description,
            condition_type=payload.condition_type,
            required_by_date=payload.required_by_date
        )
        
        self.db.add(condition)
        await self.db.commit()
        await self.db.refresh(condition)
        
        logger.info("condition_added", condition_id=condition.id)
        return condition

    async def get_conditions(self, application_id: int) -> List[Condition]:
        # FIXED: Added validation for all inputs
        if application_id <= 0:
            raise ConditionError("Invalid application ID")
        
        logger.info("fetching_conditions", application_id=application_id)
        
        query = select(Condition).where(Condition.application_id == application_id)
        result = await self.db.execute(query)
        conditions = result.scalars().all()
        
        logger.info("conditions_fetched", count=len(conditions))
        return conditions

    async def update_condition_status(self, condition_id: int, payload: ConditionUpdateStatus, user_id: int) -> Condition:
        # FIXED: Added validation for all inputs
        if condition_id <= 0:
            raise ConditionError("Invalid condition ID")
        if user_id <= 0:
            raise ConditionError("Invalid user ID")
            
        logger.info("updating_condition_status", condition_id=condition_id, status=payload.status)
        
        query = select(Condition).where(Condition.id == condition_id)
        result = await self.db.execute(query)
        condition = result.scalar_one_or_none()
        
        if not condition:
            raise ConditionError(f"Condition {condition_id} not found")
            
        condition.status = payload.status
        
        if payload.status == "satisfied":
            condition.satisfied_at = datetime.utcnow()
            condition.satisfied_by = user_id
        elif payload.status in ("outstanding", "waived"):
            # Reset satisfaction fields when changing away from satisfied
            condition.satisfied_at = None
            condition.satisfied_by = None
        
        await self.db.commit()
        await self.db.refresh(condition)
        
        logger.info("condition_status_updated", condition_id=condition.id, status=condition.status)
        return condition

    async def get_outstanding_conditions(self, application_id: int) -> List[Condition]:
        # FIXED: Added validation for all inputs
        if application_id <= 0:
            raise ConditionError("Invalid application ID")
        
        logger.info("fetching_outstanding_conditions", application_id=application_id)
        
        query = select(Condition).where(
            Condition.application_id == application_id,
            Condition.status == "outstanding"
        )
        result = await self.db.execute(query)
        conditions = result.scalars().all()
        
        logger.info("outstanding_conditions_fetched", count=len(conditions))
        return conditions