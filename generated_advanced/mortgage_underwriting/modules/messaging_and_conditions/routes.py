from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.messaging.schemas import (
    MessageCreate, MessageUpdateRead, MessageResponse, PaginatedMessagesResponse,
    ConditionCreate, ConditionUpdateStatus, ConditionResponse, PaginatedConditionsResponse
)
from mortgage_underwriting.modules.messaging.services import MessagingService, ConditionService
from mortgage_underwriting.modules.messaging.exceptions import MessagingError, ConditionError

router = APIRouter(prefix="/api/v1/applications", tags=["Messaging & Conditions"])

# Message Routes

@router.post("/{application_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    application_id: int,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_async_session)
) -> MessageResponse:
    """Send a new message within an application thread."""
    try:
        service = MessagingService(db)
        # In real implementation, we'd get sender_id from auth context
        sender_id = 1  # Placeholder
        return await service.send_message(application_id, sender_id, payload)
    except MessagingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{application_id}/messages", response_model=PaginatedMessagesResponse)
async def get_messages(
    application_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    is_read: Optional[bool] = None,
    sender_id: Optional[int] = None,
    before_date: Optional[datetime] = None,
    after_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_async_session)
) -> PaginatedMessagesResponse:
    """Retrieve paginated message thread for an application."""
    try:
        service = MessagingService(db)
        messages, total = await service.get_messages(
            application_id, page, per_page, is_read, sender_id, before_date, after_date
        )
        return {
            "items": messages,
            "total": total,
            "page": page,
            "per_page": per_page
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{application_id}/messages/{message_id}/read", response_model=MessageResponse)
async def mark_message_as_read(
    application_id: int,
    message_id: int,
    payload: MessageUpdateRead,
    db: AsyncSession = Depends(get_async_session)
) -> MessageResponse:
    """Mark a message as read."""
    try:
        service = MessagingService(db)
        # In real implementation, we'd get user_id from auth context
        user_id = 1  # Placeholder
        return await service.mark_message_as_read(message_id, user_id)
    except MessagingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# Condition Routes

@router.post("/{application_id}/conditions", response_model=ConditionResponse, status_code=status.HTTP_201_CREATED)
async def add_condition(
    application_id: int,
    payload: ConditionCreate,
    db: AsyncSession = Depends(get_async_session)
) -> ConditionResponse:
    """Add a new condition to an application."""
    try:
        service = ConditionService(db)
        return await service.add_condition(application_id, payload)
    except ConditionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{application_id}/conditions", response_model=PaginatedConditionsResponse)
async def get_conditions(
    application_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> PaginatedConditionsResponse:
    """List all conditions for an application."""
    try:
        service = ConditionService(db)
        conditions = await service.get_conditions(application_id)
        return {
            "items": conditions,
            "total": len(conditions),
            "page": 1,
            "per_page": len(conditions)
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{application_id}/conditions/{condition_id}", response_model=ConditionResponse)
async def update_condition_status(
    application_id: int,
    condition_id: int,
    payload: ConditionUpdateStatus,
    db: AsyncSession = Depends(get_async_session)
) -> ConditionResponse:
    """Update condition status."""
    try:
        service = ConditionService(db)
        # In real implementation, we'd get user_id from auth context
        user_id = 1  # Placeholder
        return await service.update_condition_status(condition_id, payload, user_id)
    except ConditionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{application_id}/conditions/outstanding", response_model=PaginatedConditionsResponse)
async def get_outstanding_conditions(
    application_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> PaginatedConditionsResponse:
    """List outstanding conditions for an application."""
    try:
        service = ConditionService(db)
        conditions = await service.get_outstanding_conditions(application_id)
        return {
            "items": conditions,
            "total": len(conditions),
            "page": 1,
            "per_page": len(conditions)
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))