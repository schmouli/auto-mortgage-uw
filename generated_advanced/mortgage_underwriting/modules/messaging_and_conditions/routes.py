```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging

from ..dependencies import get_db_session, get_current_user
from ..schemas.user import UserResponse
from .schemas import (
    MessageCreateRequest,
    MessageUpdateReadRequest,
    ConditionCreateRequest,
    ConditionUpdateRequest,
    MessageListResponse,
    ConditionListResponse,
    MessageResponse,
    ConditionResponse
)
from .services import MessagingService, ConditionService

router = APIRouter(prefix="/applications/{application_id}", tags=["Messaging & Conditions"])
logger = logging.getLogger(__name__)


@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    application_id: int,
    message_data: MessageCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db_session = Depends(get_db_session)
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
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not send message")


@router.get("/messages", response_model=MessageListResponse)
async def get_message_thread(
    application_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db_session = Depends(get_db_session)
):
    """
    Retrieve message thread for an application
    
    Args:
        application_id: ID of the mortgage application
        current_user: Authenticated user requesting messages
        
    Returns:
        List of messages in the conversation
    """
    try:
        service = MessagingService(db_session)
        messages = await service.get_message_thread(application_id, current_user.id)
        return MessageListResponse(messages=messages)
    except Exception as e:
        logger.error(f"Failed to retrieve messages: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve messages")


@router.put("/messages/{message_id}/read", response_model=MessageResponse)
async def mark_message_read(
    application_id: int,
    message_id: int,
    read_data: MessageUpdateReadRequest,
    current_user: UserResponse = Depends(get_current_user),
    db_session = Depends(get_db_session)
):
    """
    Mark a message as read
    
    Args:
        application_id: ID of the mortgage application
        message_id: ID of the specific message
        read_data: Read status update
        current_user: Authenticated user marking the message
        
    Returns:
        Updated message details
    """
    try:
        service = MessagingService(db_session)
        return await service.mark_message_as_read(application_id, message_id, current_user.id, read_data)
    except Exception as e:
        logger.error(f"Failed to update message read status: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update message")


@router.post("/conditions", response_model=ConditionResponse, status_code=status.HTTP_201_CREATED)
async def add_condition(
    application_id: int,
    condition_data: ConditionCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db_session = Depends(get_db_session)
):
    """
    Add a new condition to an application
    
    Args:
        application_id: ID of the mortgage application
        condition_data: Details of the new condition
        current_user: Authenticated user adding the condition
        
    Returns:
        Created condition details
    """
    try:
        service = ConditionService(db_session)
        return await service.create_condition(application_id, condition_data)
    except Exception as e:
        logger.error(f"Failed to create condition: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create condition")


@router.get("/conditions", response_model=ConditionListResponse)
async def list_all_conditions(
    application_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db_session = Depends(get_db_session)
):
    """
    List all conditions for an application
    
    Args:
        application_id: ID of the mortgage application
        current_user: Authenticated user requesting conditions
        
    Returns:
        List of all conditions
    """
    try:
        service = ConditionService(db_session)
        conditions = await service.list_conditions(application_id)
        return ConditionListResponse(conditions=conditions)
    except Exception as e:
        logger.error(f"Failed to list conditions: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list conditions")


@router.put("/conditions/{condition_id}", response_model=ConditionResponse)
async def update_condition_status(
    application_id: int,
    condition_id: int,
    update_data: ConditionUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db_session = Depends(get_db_session)
):
    """
    Update the status of a condition
    
    Args:
        application_id: ID of the mortgage application
        condition_id: ID of the specific condition
        update_data: New status and satisfaction details
        current_user: Authenticated user updating the condition
        
    Returns:
        Updated condition details
    """
    try:
        service = ConditionService(db_session)
        return await service.update_condition_status(application_id, condition_id, current_user.id, update_data)
    except Exception as e:
        logger.error(f"Failed to update condition: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update condition")


@router.get("/conditions/outstanding", response_model=ConditionListResponse)
async def list_outstanding_conditions(
    application_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db_session = Depends(get_db_session)
):
    """
    List only outstanding conditions for an application
    
    Args:
        application_id: ID of the mortgage application
        current_user: Authenticated user requesting conditions
        
    Returns:
        List of outstanding conditions
    """
    try:
        service = ConditionService(db_session)
        conditions = await service.list_outstanding_conditions(application_id)
        return ConditionListResponse(conditions=conditions)
    except Exception as e:
        logger.error(f"Failed to list outstanding conditions: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list conditions")
```