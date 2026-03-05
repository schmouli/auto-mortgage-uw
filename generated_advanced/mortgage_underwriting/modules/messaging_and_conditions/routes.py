from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import structlog

# Local imports
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.dependencies import get_current_user
from mortgage_underwriting.modules.users.schemas import UserResponse
from mortgage_underwriting.modules.messaging_conditions.schemas import (
    MessageCreateRequest,
    MessageUpdateReadRequest,
    ConditionCreateRequest,
    ConditionUpdateRequest,
    MessageListResponse,
    ConditionListResponse,
    MessageResponse,
    ConditionResponse
)
from mortgage_underwriting.modules.messaging_conditions.services import MessagingService, ConditionService

router = APIRouter(prefix="/applications/{application_id}", tags=["Messaging & Conditions"])
logger = structlog.get_logger(__name__)


@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    application_id: int,
    message_data: MessageCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db_session=Depends(get_async_session)
):
    """
    Send a new message within an application context
    
    Args:
        application_id: ID of the mortgage application
        message_data: Message content and recipient information
        current_user: Authenticated user sending the message
        
    Returns:
        Created message details
    """
    try:
        service = MessagingService(db_session)
        return await service.create_message(application_id, current_user.id, message_data)
    except ValueError as e:
        logger.error("send_message_validation_error", error=str(e), application_id=application_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("send_message_unexpected_error", error=str(e), application_id=application_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    application_id: int,
    message_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db_session=Depends(get_async_session)
):
    """
    Get a specific message by ID
    
    Args:
        application_id: ID of the mortgage application
        message_id: ID of the message to retrieve
        current_user: Authenticated user requesting the message
        
    Returns:
        Message details
    """
    try:
        service = MessagingService(db_session)
        return await service.get_message_by_id(message_id, current_user.id)
    except Exception as e:
        logger.error("get_message_error", error=str(e), message_id=message_id, application_id=application_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/messages", response_model=MessageListResponse)
async def list_messages(
    application_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: UserResponse = Depends(get_current_user),
    db_session=Depends(get_async_session)
):
    """
    List messages for an application with pagination
    
    Args:
        application_id: ID of the mortgage application
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Authenticated user requesting messages
        
    Returns:
        List of messages with pagination info
    """
    try:
        service = MessagingService(db_session)
        messages, total = await service.list_messages(application_id, current_user.id, skip, limit)
        return MessageListResponse(messages=messages, total=total, skip=skip, limit=limit)
    except Exception as e:
        logger.error("list_messages_error", error=str(e), application_id=application_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.patch("/messages/{message_id}/read", response_model=MessageResponse)
async def mark_message_as_read(
    application_id: int,
    message_id: int,
    read_data: MessageUpdateReadRequest,
    current_user: UserResponse = Depends(get_current_user),
    db_session=Depends(get_async_session)
):
    """
    Mark a message as read/unread
    
    Args:
        application_id: ID of the mortgage application
        message_id: ID of the message to update
        read_data: Read status update information
        current_user: Authenticated user updating the message
        
    Returns:
        Updated message details
    """
    try:
        service = MessagingService(db_session)
        return await service.mark_message_as_read(message_id, current_user.id, read_data)
    except Exception as e:
        logger.error("mark_message_read_error", error=str(e), message_id=message_id, application_id=application_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/conditions", response_model=ConditionResponse, status_code=status.HTTP_201_CREATED)
async def create_condition(
    application_id: int,
    condition_data: ConditionCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db_session=Depends(get_async_session)
):
    """
    Create a new condition for an application
    
    Args:
        application_id: ID of the mortgage application
        condition_data: Condition creation information
        current_user: Authenticated user creating the condition
        
    Returns:
        Created condition details
    """
    try:
        service = ConditionService(db_session)
        return await service.create_condition(application_id, condition_data)
    except ValueError as e:
        logger.error("create_condition_validation_error", error=str(e), application_id=application_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("create_condition_unexpected_error", error=str(e), application_id=application_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/conditions/{condition_id}", response_model=ConditionResponse)
async def get_condition(
    application_id: int,
    condition_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db_session=Depends(get_async_session)
):
    """
    Get a specific condition by ID
    
    Args:
        application_id: ID of the mortgage application
        condition_id: ID of the condition to retrieve
        current_user: Authenticated user requesting the condition
        
    Returns:
        Condition details
    """
    try:
        service = ConditionService(db_session)
        return await service.get_condition_by_id(condition_id, current_user.id)
    except Exception as e:
        logger.error("get_condition_error", error=str(e), condition_id=condition_id, application_id=application_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/conditions", response_model=ConditionListResponse)
async def list_conditions(
    application_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: UserResponse = Depends(get_current_user),
    db_session=Depends(get_async_session)
):
    """
    List conditions for an application with pagination
    
    Args:
        application_id: ID of the mortgage application
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Authenticated user requesting conditions
        
    Returns:
        List of conditions with pagination info
    """
    try:
        service = ConditionService(db_session)
        conditions, total = await service.list_conditions(application_id, skip, limit)
        return ConditionListResponse(conditions=conditions, total=total, skip=skip, limit=limit)
    except Exception as e:
        logger.error("list_conditions_error", error=str(e), application_id=application_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.patch("/conditions/{condition_id}", response_model=ConditionResponse)
async def update_condition_status(
    application_id: int,
    condition_id: int,
    condition_data: ConditionUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db_session=Depends(get_async_session)
):
    """
    Update condition status
    
    Args:
        application_id: ID of the mortgage application
        condition_id: ID of the condition to update
        condition_data: Condition status update information
        current_user: Authenticated user updating the condition
        
    Returns:
        Updated condition details
    """
    try:
        service = ConditionService(db_session)
        return await service.update_condition_status(condition_id, condition_data, current_user.id)
    except Exception as e:
        logger.error("update_condition_status_error", error=str(e), condition_id=condition_id, application_id=application_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
```

```