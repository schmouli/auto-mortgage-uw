from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.security import verify_token
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    MessageLookupRequest,
    MessageCreateRequest,
    MessageResponse,
    MessageThreadResponse,
    ConditionCreateRequest,
    ConditionUpdateRequest,
    ConditionResponse,
    OutstandingConditionsResponse
)
from mortgage_underwriting.modules.messaging_conditions.services import MessagingService, ConditionService

router = APIRouter(prefix="/api/v1/applications", tags=["Messaging & Conditions"])

# Message Routes

@router.post("/{application_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    application_id: int,
    payload: MessageCreateRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(verify_token)
) -> MessageResponse:
    """Send a new message on an application thread."""
    service = MessagingService(db)
    try:
        return await service.send_message(application_id, current_user.user_id, payload)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to send message", "error_code": "MESSAGING_005"}
        )

@router.get("/{application_id}/messages", response_model=MessageThreadResponse)
async def get_message_thread(
    application_id: int,
    filters: MessageLookupRequest = Depends(),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(verify_token)
) -> MessageThreadResponse:
    """Retrieve paginated message thread."""
    service = MessagingService(db)
    try:
        messages, next_cursor, total_count = await service.get_message_thread(application_id, filters)
        return MessageThreadResponse(
            messages=messages,
            next_cursor=next_cursor,
            total_count=total_count
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to fetch messages", "error_code": "MESSAGING_006"}
        )

@router.put("/{application_id}/messages/{message_id}/read", response_model=MessageResponse)
async def mark_message_as_read(
    application_id: int,
    message_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(verify_token)
) -> MessageResponse:
    """Mark a message as read."""
    service = MessagingService(db)
    try:
        return await service.mark_as_read(message_id, current_user.user_id)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to mark message as read", "error_code": "MESSAGING_007"}
        )

# Condition Routes

@router.post("/{application_id}/conditions", response_model=ConditionResponse, status_code=status.HTTP_201_CREATED)
async def add_condition(
    application_id: int,
    payload: ConditionCreateRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(verify_token)
) -> ConditionResponse:
    """Add a new condition to an application."""
    service = ConditionService(db)
    try:
        return await service.add_condition(application_id, payload)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to add condition", "error_code": "CONDITION_002"}
        )

@router.get("/{application_id}/conditions", response_model=List[ConditionResponse])
async def list_conditions(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(verify_token)
) -> List[ConditionResponse]:
    """List all conditions for an application."""
    service = ConditionService(db)
    try:
        return await service.list_conditions(application_id)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to list conditions", "error_code": "CONDITION_003"}
        )

@router.put("/{application_id}/conditions/{condition_id}", response_model=ConditionResponse)
async def update_condition_status(
    application_id: int,
    condition_id: int,
    payload: ConditionUpdateRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(verify_token)
) -> ConditionResponse:
    """Update the status of a condition."""
    service = ConditionService(db)
    try:
        return await service.update_condition_status(condition_id, application_id, payload)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to update condition", "error_code": "CONDITION_004"}
        )

@router.get("/{application_id}/conditions/outstanding", response_model=OutstandingConditionsResponse)
async def list_outstanding_conditions(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(verify_token)
) -> OutstandingConditionsResponse:
    """List outstanding conditions for an application."""
    service = ConditionService(db)
    try:
        return await service.list_outstanding_conditions(application_id)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to list outstanding conditions", "error_code": "CONDITION_005"}
        )