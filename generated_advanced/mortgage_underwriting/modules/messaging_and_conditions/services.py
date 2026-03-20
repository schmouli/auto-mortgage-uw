from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple
from sqlalchemy import select, func, and_, desc
import structlog
from mortgage_underwriting.common.exceptions import NotFoundError, AppException
from mortgage_underwriting.modules.messaging_conditions.models import Message, Condition
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    MessageLookupRequest,
    MessageCreateRequest,
    MessageResponse,
    ConditionCreateRequest,
    ConditionUpdateRequest,
    ConditionResponse,
    OutstandingConditionsResponse
)

logger = structlog.get_logger()


class MessagingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_message(
        self, 
        application_id: int, 
        sender_id: int, 
        payload: MessageCreateRequest
    ) -> MessageResponse:
        """Send a new message."""
        # FIXED: Added input validation
        if application_id <= 0:
            raise ValueError("Invalid application ID")
        if sender_id <= 0:
            raise ValueError("Invalid sender ID")
        if not payload.body.strip():
            raise ValueError("Message body cannot be empty")
            
        logger.info(
            "sending_message",
            application_id=application_id,
            sender_id=sender_id,
            recipient_id=payload.recipient_id
        )
        
        # Create message instance
        message_dict = payload.model_dump()
        message_dict.update({
            "application_id": application_id,
            "sender_id": sender_id
        })
        
        message = Message(**message_dict)
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        
        return MessageResponse.model_validate(message)

    async def get_message_thread(
        self, 
        application_id: int, 
        filters: MessageLookupRequest
    ) -> Tuple[List[MessageResponse], Optional[datetime], int]:
        """Get paginated message thread."""
        # FIXED: Added input validation
        if application_id <= 0:
            raise ValueError("Invalid application ID")
        if filters.limit <= 0 or filters.limit > 200:
            raise ValueError("Invalid limit value")
            
        logger.info(
            "fetching_message_thread",
            application_id=application_id,
            cursor=filters.cursor,
            limit=filters.limit
        )
        
        # Build query
        stmt = select(Message).where(Message.application_id == application_id)
        
        # Apply filters
        if filters.is_read is not None:
            stmt = stmt.where(Message.is_read == filters.is_read)
        if filters.message_type:
            stmt = stmt.where(Message.message_type == filters.message_type)
        if filters.cursor:
            stmt = stmt.where(Message.sent_at < filters.cursor)
            
        # Order and limit
        stmt = stmt.order_by(desc(Message.sent_at)).limit(filters.limit)
        
        # Execute query
        result = await self.db.execute(stmt)
        messages = result.scalars().all()
        
        # Calculate next cursor
        next_cursor = None
        if len(messages) == filters.limit and messages:
            next_cursor = messages[-1].sent_at
            
        # Get total count
        count_stmt = select(func.count()).select_from(Message).where(Message.application_id == application_id)
        if filters.is_read is not None:
            count_stmt = count_stmt.where(Message.is_read == filters.is_read)
        if filters.message_type:
            count_stmt = count_stmt.where(Message.message_type == filters.message_type)
            
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar_one()
        
        return [
            MessageResponse.model_validate(msg) for msg in messages
        ], next_cursor, total_count

    async def mark_as_read(self, message_id: int, user_id: int) -> MessageResponse:
        """Mark a message as read."""
        # FIXED: Added input validation
        if message_id <= 0:
            raise ValueError("Invalid message ID")
        if user_id <= 0:
            raise ValueError("Invalid user ID")
            
        logger.info(
            "marking_message_read",
            message_id=message_id,
            user_id=user_id
        )
        
        stmt = select(Message).where(
            and_(
                Message.id == message_id,
                Message.recipient_id == user_id
            )
        )
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()
        
        if not message:
            raise NotFoundError(detail="Message not found or unauthorized access", error_code="MESSAGING_004")
            
        if not message.is_read:
            message.is_read = True
            message.read_at = datetime.now()
            await self.db.commit()
            await self.db.refresh(message)
        
        return MessageResponse.model_validate(message)


class ConditionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_condition(
        self, 
        application_id: int, 
        payload: ConditionCreateRequest
    ) -> ConditionResponse:
        """Add a new condition."""
        # FIXED: Added input validation
        if application_id <= 0:
            raise ValueError("Invalid application ID")
        if not payload.description.strip():
            raise ValueError("Condition description cannot be empty")
            
        logger.info(
            "adding_condition",
            application_id=application_id,
            condition_type=payload.condition_type
        )
        
        condition_dict = payload.model_dump()
        condition_dict["application_id"] = application_id
        
        condition = Condition(**condition_dict)
        self.db.add(condition)
        await self.db.commit()
        await self.db.refresh(condition)
        
        return ConditionResponse.model_validate(condition)

    async def list_conditions(self, application_id: int) -> List[ConditionResponse]:
        """List all conditions for an application."""
        # FIXED: Added input validation
        if application_id <= 0:
            raise ValueError("Invalid application ID")
            
        logger.info(
            "listing_conditions",
            application_id=application_id
        )
        
        stmt = select(Condition).where(Condition.application_id == application_id)
        result = await self.db.execute(stmt)
        conditions = result.scalars().all()
        
        return [
            ConditionResponse.model_validate(cond) for cond in conditions
        ]

    async def update_condition_status(
        self, 
        condition_id: int, 
        application_id: int, 
        payload: ConditionUpdateRequest
    ) -> ConditionResponse:
        """Update condition status."""
        # FIXED: Added input validation
        if condition_id <= 0:
            raise ValueError("Invalid condition ID")
        if application_id <= 0:
            raise ValueError("Invalid application ID")
            
        logger.info(
            "updating_condition_status",
            condition_id=condition_id,
            status=payload.status
        )
        
        stmt = select(Condition).where(
            and_(
                Condition.id == condition_id,
                Condition.application_id == application_id
            )
        )
        result = await self.db.execute(stmt)
        condition = result.scalar_one_or_none()
        
        if not condition:
            raise NotFoundError(detail="Condition not found", error_code="CONDITION_001")
            
        # Update fields
        condition.status = payload.status
        if payload.satisfied_at:
            condition.satisfied_at = payload.satisfied_at
        if payload.satisfied_by:
            condition.satisfied_by = payload.satisfied_by
            
        await self.db.commit()
        await self.db.refresh(condition)
        
        return ConditionResponse.model_validate(condition)

    async def list_outstanding_conditions(self, application_id: int) -> OutstandingConditionsResponse:
        """List outstanding conditions for an application."""
        # FIXED: Added input validation
        if application_id <= 0:
            raise ValueError("Invalid application ID")
            
        logger.info(
            "listing_outstanding_conditions",
            application_id=application_id
        )
        
        stmt = select(Condition).where(
            and_(
                Condition.application_id == application_id,
                Condition.status == "outstanding"
            )
        )
        result = await self.db.execute(stmt)
        conditions = result.scalars().all()
        
        return OutstandingConditionsResponse(
            conditions=[ConditionResponse.model_validate(cond) for cond in conditions],
            total_count=len(conditions)
        )