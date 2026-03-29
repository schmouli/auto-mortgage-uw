from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from sqlalchemy import or_

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    MessageCreate,
    MessageUpdateRead,
    ConditionCreate,
    ConditionStatusUpdate,
    MessageResponse,
    ConditionResponse,
    PaginatedMessageResponse,
    PaginatedConditionResponse,
    MessageQueryParams
)
from mortgage_underwriting.modules.messaging_conditions.services import MessagingConditionsService

router = APIRouter(prefix="/api/v1/applications", tags=["Messaging & Conditions"])


# In a real implementation, you'd have proper authentication dependency
# For example:
# async def get_current_user(...) -> User: ...
# But for this exercise, we'll simulate with a placeholder


async def get_current_user_id() -> int:
    # Placeholder - should come from auth token
    return 1


@router.post("/{application_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)


async def send_message(
    application_id: int,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id)
):
    """Send a new message in an application's conversation thread."""
    try:
        # Ensure application_id in path matches payload
        if payload.application_id != application_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Application ID mismatch", "error_code": "MESSAGING_002"}
            )
        service = MessagingConditionsService(db)
        return await service.send_message(payload, current_user_id)
    except Exception as e:
        # FIXED: Enhanced error logging
        import structlog
        logger = structlog.get_logger()
        logger.error("send_message_error", 
                    error=str(e), 
                    application_id=application_id,
                    user_id=current_user_id)
        raise HTTPException(
            status_code=getattr(e, 'status_code', 500),
            detail={"detail": str(e), "error_code": getattr(e, 'error_code', 'INTERNAL_ERROR')}
        )


@router.get("/{application_id}/messages", response_model=PaginatedMessageResponse)


async def get_message_thread(
    application_id: int,
    params: Annotated[MessageQueryParams, Depends()],
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id)
):
    """Retrieve paginated message history for an application."""
    try:
        service = MessagingConditionsService(db)
        return await service.get_message_thread(application_id, params, current_user_id)
    except Exception as e:
        # FIXED: Enhanced error logging
        import structlog
        logger = structlog.get_logger()
        logger.error("get_message_thread_error", 
                    error=str(e), 
                    application_id=application_id,
                    user_id=current_user_id)
        raise HTTPException(
            status_code=getattr(e, 'status_code', 500),
            detail={"detail": str(e), "error_code": getattr(e, 'error_code', 'INTERNAL_ERROR')}
        )


@router.put("/{application_id}/messages/{message_id}/read", response_model=MessageResponse)


async def mark_message_as_read(
    application_id: int,
    message_id: int,
    payload: MessageUpdateRead,  # Using payload to enforce PUT semantics even though it's just a flag
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id)
):
    """Mark a received message as read."""
    try:
        service = MessagingConditionsService(db)
        return await service.mark_message_as_read(application_id, message_id, current_user_id)
    except Exception as e:
        # FIXED: Enhanced error logging
        import structlog
        logger = structlog.get_logger()
        logger.error("mark_message_as_read_error", 
                    error=str(e), 
                    application_id=application_id,
                    message_id=message_id,
                    user_id=current_user_id)
        raise HTTPException(
            status_code=getattr(e, 'status_code', 500),
            detail={"detail": str(e), "error_code": getattr(e, 'error_code', 'INTERNAL_ERROR')}
        )


@router.post("/{application_id}/conditions", response_model=ConditionResponse, status_code=status.HTTP_201_CREATED)


async def add_condition(
    application_id: int,
    payload: ConditionCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id)
):
    """Add a new condition to an application."""
    try:
        # Ensure application_id in path matches payload
        if payload.application_id != application_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Application ID mismatch", "error_code": "CONDITION_003"}
            )
        service = MessagingConditionsService(db)
        return await service.add_condition(payload, current_user_id)
    except Exception as e:
        # FIXED: Enhanced error logging
        import structlog
        logger = structlog.get_logger()
        logger.error("add_condition_error", 
                    error=str(e), 
                    application_id=application_id,
                    user_id=current_user_id)
        raise HTTPException(
            status_code=getattr(e, 'status_code', 500),
            detail={"detail": str(e), "error_code": getattr(e, 'error_code', 'INTERNAL_ERROR')}
        )


@router.get("/{application_id}/conditions", response_model=PaginatedConditionResponse)


async def list_conditions(
    application_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id)
):
    """List all conditions associated with an application."""
    try:
        service = MessagingConditionsService(db)
        return await service.list_conditions(application_id, page, limit, current_user_id)
    except Exception as e:
        # FIXED: Enhanced error logging
        import structlog
        logger = structlog.get_logger()
        logger.error("list_conditions_error", 
                    error=str(e), 
                    application_id=application_id,
                    user_id=current_user_id)
        raise HTTPException(
            status_code=getattr(e, 'status_code', 500),
            detail={"detail": str(e), "error_code": getattr(e, 'error_code', 'INTERNAL_ERROR')}
        )


@router.put("/{application_id}/conditions/{condition_id}", response_model=ConditionResponse)


async def update_condition_status(
    application_id: int,
    condition_id: int,
    payload: ConditionStatusUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id)
):
    """Update the fulfillment status of a condition."""
    try:
        service = MessagingConditionsService(db)
        return await service.update_condition_status(application_id, condition_id, payload, current_user_id)
    except Exception as e:
        # FIXED: Enhanced error logging
        import structlog
        logger = structlog.get_logger()
        logger.error("update_condition_status_error", 
                    error=str(e), 
                    application_id=application_id,
                    condition_id=condition_id,
                    user_id=current_user_id)
        raise HTTPException(
            status_code=getattr(e, 'status_code', 500),
            detail={"detail": str(e), "error_code": getattr(e, 'error_code', 'INTERNAL_ERROR')}
        )


@router.get("/{application_id}/conditions/{condition_id}", response_model=ConditionResponse)


async def get_condition_details(
    application_id: int,
    condition_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id)
):
    """Get detailed information about a specific condition."""
    try:
        service = MessagingConditionsService(db)
        # This would be implemented similar to other methods
        # For brevity, implementation omitted but would follow same patterns
        raise NotImplementedError("Endpoint not yet implemented")
    except Exception as e:
        # FIXED: Enhanced error logging
        import structlog
        logger = structlog.get_logger()
        logger.error("get_condition_details_error", 
                    error=str(e), 
                    application_id=application_id,
                    condition_id=condition_id,
                    user_id=current_user_id)
        raise HTTPException(
            status_code=getattr(e, 'status_code', 500),
            detail={"detail": str(e), "error_code": getattr(e, 'error_code', 'INTERNAL_ERROR')}
        )