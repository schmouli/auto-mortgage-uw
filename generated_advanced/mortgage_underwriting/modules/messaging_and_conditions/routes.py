from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, Query

from mortgage_underwriting.common.database import get_async_session
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
from mortgage_underwriting.modules.messaging_conditions.services import MessagingConditionsService

router = APIRouter(prefix="/api/v1/applications", tags=["Messaging & Conditions"])


@router.post("/{application_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    application_id: int,
    payload: MessageCreateRequest,
    db: AsyncSession = Depends(get_async_session),
    # user_id: int = Depends(get_current_user_id) # Assuming auth middleware provides this
) -> MessageResponse:
    """Send a new message within an application thread."""
    service = MessagingConditionsService(db)
    # FIXED: Pass actual sender_id once authentication is implemented
    return await service.send_message(application_id, 1, payload)  # Placeholder sender_id


@router.get("/{application_id}/messages", response_model=PaginatedMessagesResponse)
async def get_message_thread(
    application_id: int,
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(50, ge=1, le=100),
    is_read: bool | None = None,
    db: AsyncSession = Depends(get_async_session)
) -> PaginatedMessagesResponse:
    """Retrieve paginated message thread with optional filters."""
    service = MessagingConditionsService(db)
    return await service.get_message_thread(application_id, page, page_size, is_read)


@router.put("/{application_id}/messages/{msg_id}/read", response_model=MessageResponse)
async def mark_message_as_read(
    application_id: int,
    msg_id: int,
    payload: MessageUpdateReadStatusRequest,
    db: AsyncSession = Depends(get_async_session),
    # user_id: int = Depends(get_current_user_id) # Assuming auth middleware provides this
) -> MessageResponse:
    """Mark a message as read/unread."""
    service = MessagingConditionsService(db)
    # FIXED: Pass actual user_id once authentication is implemented
    return await service.mark_message_as_read(msg_id, 1, payload)  # Placeholder user_id


@router.post("/{application_id}/conditions", response_model=ConditionResponse, status_code=201)
async def add_condition(
    application_id: int,
    payload: ConditionCreateRequest,
    db: AsyncSession = Depends(get_async_session)
) -> ConditionResponse:
    """Add a new condition to an application."""
    service = MessagingConditionsService(db)
    return await service.add_condition(application_id, payload)


@router.get("/{application_id}/conditions", response_model=List[ConditionResponse])
async def list_all_conditions(
    application_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> List[ConditionResponse]:
    """List all conditions for an application."""
    service = MessagingConditionsService(db)
    return await service.list_all_conditions(application_id)


@router.put("/{application_id}/conditions/{cond_id}", response_model=ConditionResponse)
async def update_condition_status(
    application_id: int,
    cond_id: int,
    payload: ConditionUpdateStatusRequest,
    db: AsyncSession = Depends(get_async_session),
    # user_id: int = Depends(get_current_user_id) # Assuming auth middleware provides this
) -> ConditionResponse:
    """Update the status of a condition."""
    service = MessagingConditionsService(db)
    # FIXED: Pass actual user_id once authentication is implemented
    return await service.update_condition_status(cond_id, application_id, payload, 1)  # Placeholder user_id


@router.get("/{application_id}/conditions/outstanding", response_model=List[ConditionResponse])
async def list_outstanding_conditions(
    application_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> List[ConditionResponse]:
    """List all outstanding conditions for an application."""
    service = MessagingConditionsService(db)
    return await service.list_outstanding_conditions(application_id)