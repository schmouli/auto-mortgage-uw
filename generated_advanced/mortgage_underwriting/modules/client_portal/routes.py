from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.portal.schemas import (
    ClientPortalActivityCreate,
    ClientPortalActivityResponse,
    NotificationResponse,
    NotificationListResponse,
    NotificationUpdate,
    NotificationMarkReadAllRequest,
    UserPreferenceResponse,
    UserPreferenceUpdate,
    ClientDashboardResponse,
    BrokerDashboardResponse
)
from mortgage_underwriting.modules.portal.services import ClientPortalService
from mortgage_underwriting.modules.portal.exceptions import AccessDeniedError, NotificationNotFoundError

router = APIRouter(prefix="/api/v1/portal", tags=["Client Portal"])


def get_portal_service(db: AsyncSession = Depends(get_async_session)) -> ClientPortalService:
    return ClientPortalService(db)


@router.post("/activities/", response_model=ClientPortalActivityResponse, status_code=status.HTTP_201_CREATED)
async def log_client_activity(
    activity_in: ClientPortalActivityCreate,
    service: ClientPortalService = Depends(get_portal_service)
) -> ClientPortalActivityResponse:
    """Log a client portal activity."""
    # FIXED: Added input validation and proper error handling
    if not activity_in.activity_type or len(activity_in.activity_type.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Activity type is required", "error_code": "VALIDATION_001"}
        )
    
    if activity_in.ip_address and len(activity_in.ip_address) > 45:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "IP address too long", "error_code": "VALIDATION_002"}
        )
    
    try:
        return await service.log_activity(activity_in)
    except AccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": e.detail, "error_code": e.error_code}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to log activity", "error_code": "PORTAL_006"}
        )


@router.get("/notifications/", response_model=NotificationListResponse)
async def list_notifications(
    user_id: int = Query(..., gt=0),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: ClientPortalService = Depends(get_portal_service)
) -> NotificationListResponse:
    """Get paginated list of notifications for a user."""
    # FIXED: Added validation and proper error handling
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Page must be >= 1", "error_code": "VALIDATION_003"}
        )
    
    if size < 1 or size > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Size must be between 1 and 100", "error_code": "VALIDATION_004"}
        )
    
    try:
        notifications, total = await service.get_notifications(user_id, page, size)
        return NotificationListResponse(
            items=notifications,
            total=total,
            page=page,
            size=size
        )
    except AccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": e.detail, "error_code": e.error_code}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to fetch notifications", "error_code": "PORTAL_007"}
        )


@router.put("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    user_id: int = Query(..., gt=0),
    service: ClientPortalService = Depends(get_portal_service)
) -> NotificationResponse:
    """Mark a notification as read."""
    # FIXED: Added validation and proper error handling
    if notification_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Invalid notification ID", "error_code": "VALIDATION_005"}
        )
    
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Invalid user ID", "error_code": "VALIDATION_006"}
        )
    
    try:
        return await service.mark_notification_as_read(notification_id, user_id)
    except NotificationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": e.detail, "error_code": e.error_code}
        )
    except AccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": e.detail, "error_code": e.error_code}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to mark notification as read", "error_code": "PORTAL_008"}
        )


@router.put("/notifications/read-all", response_model=dict)
async def mark_all_notifications_read(
    user_id: int = Query(..., gt=0),
    request: Optional[NotificationMarkReadAllRequest] = None,
    service: ClientPortalService = Depends(get_portal_service)
) -> dict:
    """Mark all notifications as read for a user."""
    # FIXED: Added validation
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Invalid user ID", "error_code": "VALIDATION_007"}
        )
    
    try:
        count = await service.mark_all_notifications_as_read(user_id)
        return {"message": f"{count} notifications marked as read"}
    except AccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": e.detail, "error_code": e.error_code}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to mark all notifications as read", "error_code": "PORTAL_009"}
        )


@router.get("/preferences/{user_id}", response_model=UserPreferenceResponse)
async def get_user_preference(
    user_id: int,
    service: ClientPortalService = Depends(get_portal_service)
) -> UserPreferenceResponse:
    """Get user's portal preferences."""
    # FIXED: Added validation
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Invalid user ID", "error_code": "VALIDATION_008"}
        )
    
    try:
        return await service.get_or_create_user_preference(user_id)
    except AccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": e.detail, "error_code": e.error_code}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to fetch user preferences", "error_code": "PORTAL_010"}
        )


@router.patch("/preferences/{user_id}", response_model=UserPreferenceResponse)
async def update_user_preference(
    user_id: int,
    preference_update: UserPreferenceUpdate,
    service: ClientPortalService = Depends(get_portal_service)
) -> UserPreferenceResponse:
    """Update user's portal preferences."""
    # FIXED: Added validation
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Invalid user ID", "error_code": "VALIDATION_009"}
        )
    
    try:
        return await service.update_user_preference(user_id, preference_update)
    except AccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": e.detail, "error_code": e.error_code}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to update user preferences", "error_code": "PORTAL_011"}
        )


@router.get("/dashboard/client/{user_id}", response_model=ClientDashboardResponse)
async def get_client_dashboard(
    user_id: int,
    service: ClientPortalService = Depends(get_portal_service)
) -> ClientDashboardResponse:
    """Get client dashboard data."""
    # FIXED: Added validation
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Invalid user ID", "error_code": "VALIDATION_010"}
        )
    
    try:
        return await service.get_client_dashboard(user_id)
    except AccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": e.detail, "error_code": e.error_code}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to fetch client dashboard", "error_code": "PORTAL_012"}
        )


@router.get("/dashboard/broker/{user_id}", response_model=BrokerDashboardResponse)
async def get_broker_dashboard(
    user_id: int,
    service: ClientPortalService = Depends(get_portal_service)
) -> BrokerDashboardResponse:
    """Get broker dashboard data."""
    # FIXED: Added validation
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Invalid user ID", "error_code": "VALIDATION_011"}
        )
    
    try:
        return await service.get_broker_dashboard(user_id)
    except AccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": e.detail, "error_code": e.error_code}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to fetch broker dashboard", "error_code": "PORTAL_013"}
        )