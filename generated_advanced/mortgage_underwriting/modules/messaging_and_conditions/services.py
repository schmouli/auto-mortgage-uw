from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from sqlalchemy import select, func
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.messaging_conditions.models import Message, Condition
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    MessageCreateRequest,
    MessageUpdateReadStatusRequest,
    MessageResponse,
    ConditionCreateRequest,
    ConditionUpdateStatusRequest,
    ConditionResponse,
    PaginatedMessagesResponse,
    PaginatedConditionsResponse
)

logger = structlog.get_logger()


class MessagingConditionsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_message(self, application_id: int, sender_id: int, payload: MessageCreateRequest) -> MessageResponse:
        logger.info(
            "sending_message",
            application_id=application_id,
            sender_id=sender_id,
            recipient_id=payload.recipient_id
        )

        # TODO: Validate that sender and recipient are participants in the application
        message = Message(
            application_id=application_id,
            sender_id=sender_id,
            recipient_id=payload.recipient_id,
            body=payload.body
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return MessageResponse.model_validate(message)

    async def get_message_thread(
        self,
        application_id: int,
        page: int = 1,
        page_size: int = 50,
        is_read: Optional[bool] = None
    ) -> PaginatedMessagesResponse:
        logger.info(
            "fetching_message_thread",
            application_id=application_id,
            page=page,
            page_size=page_size,
            is_read=is_read
        )

        query = select(Message).where(Message.application_id == application_id)
        if is_read is not None:
            query = query.where(Message.is_read == is_read)

        # Apply pagination
        offset = (page - 1) * page_size
        paginated_query = query.offset(offset).limit(page_size)
        result = await self.db.execute(paginated_query)
        messages = result.scalars().all()

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        return PaginatedMessagesResponse(
            items=[MessageResponse.model_validate(m) for m in messages],
            total=total,
            page=page,
            page_size=page_size
        )

    async def mark_message_as_read(self, msg_id: int, user_id: int, payload: MessageUpdateReadStatusRequest) -> MessageResponse:
        logger.info(
            "marking_message_read",
            msg_id=msg_id,
            user_id=user_id,
            is_read=payload.is_read
        )

        stmt = select(Message).where(Message.id == msg_id, Message.recipient_id == user_id)
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()
        if not message:
            logger.error("message_not_found", msg_id=msg_id, user_id=user_id)
            raise AppException(f"Message {msg_id} not found or access denied")

        message.is_read = payload.is_read
        if payload.is_read and message.read_at is None:
            message.read_at = datetime.utcnow()
        elif not payload.is_read:
            message.read_at = None

        await self.db.commit()
        await self.db.refresh(message)
        return MessageResponse.model_validate(message)

    async def add_condition(self, application_id: int, payload: ConditionCreateRequest) -> ConditionResponse:
        logger.info(
            "adding_condition",
            application_id=application_id,
            condition_type=payload.condition_type
        )

        condition = Condition(
            application_id=application_id,
            lender_submission_id=payload.lender_submission_id,
            description=payload.description,
            condition_type=payload.condition_type,
            required_by_date=payload.required_by_date
        )
        self.db.add(condition)
        await self.db.commit()
        await self.db.refresh(condition)
        return ConditionResponse.model_validate(condition)

    async def list_all_conditions(self, application_id: int) -> List[ConditionResponse]:
        logger.info("listing_all_conditions", application_id=application_id)

        stmt = select(Condition).where(Condition.application_id == application_id)
        result = await self.db.execute(stmt)
        conditions = result.scalars().all()
        return [ConditionResponse.model_validate(c) for c in conditions]

    async def update_condition_status(
        self,
        cond_id: int,
        application_id: int,
        payload: ConditionUpdateStatusRequest,
        user_id: int
    ) -> ConditionResponse:
        logger.info(
            "updating_condition_status",
            cond_id=cond_id,
            application_id=application_id,
            new_status=payload.status
        )

        stmt = select(Condition).where(
            Condition.id == cond_id,
            Condition.application_id == application_id
        )
        result = await self.db.execute(stmt)
        condition = result.scalar_one_or_none()
        if not condition:
            logger.error("condition_not_found", cond_id=cond_id, application_id=application_id)
            raise AppException(f"Condition {cond_id} not found in application {application_id}")

        condition.status = payload.status
        if payload.status == "satisfied":
            condition.satisfied_at = datetime.utcnow()
            condition.satisfied_by = payload.satisfied_by or user_id
        else:
            condition.satisfied_at = None
            condition.satisfied_by = None

        await self.db.commit()
        await self.db.refresh(condition)
        return ConditionResponse.model_validate(condition)

    async def list_outstanding_conditions(self, application_id: int) -> List[ConditionResponse]:
        logger.info("listing_outstanding_conditions", application_id=application_id)

        stmt = select(Condition).where(
            Condition.application_id == application_id,
            Condition.status == "outstanding"
        )
        result = await self.db.execute(stmt)
        conditions = result.scalars().all()
        return [ConditionResponse.model_validate(c) for c in conditions]