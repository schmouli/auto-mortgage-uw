from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.client_portal.schemas import (

    LoginRequest,
    TokenResponse,
    ClientDashboardResponse,
    BrokerDashboardResponse,
    NotificationListResponse,
    NotificationReadRequest
)
from mortgage_underwriting.modules.client_portal.services import (
    AuthService,
    DashboardService,
    NotificationService
)

router = APIRouter(prefix="/api/v1/client-portal", tags=["Client Portal"])

# TODO: Add authentication dependency

@router.post("/auth/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_async_session)
) -> TokenResponse:
    """Authenticate user and return access token."""
    auth_service = AuthService(db)
    return await auth_service.authenticate_user(credentials)

@router.get("/client/dashboard", response_model=ClientDashboardResponse)
async def get_client_dashboard(
    user_id: int,  # TODO: Extract from JWT token
    db: AsyncSession = Depends(get_async_session)
) -> ClientDashboardResponse:
    """Get client dashboard data."""
    dashboard_service = DashboardService(db)
    return await dashboard_service.get_client_dashboard(user_id)

@router.get("/broker/dashboard", response_model=BrokerDashboardResponse)
async def get_broker_dashboard(
    user_id: int,  # TODO: Extract from JWT token
    db: AsyncSession = Depends(get_async_session)
) -> BrokerDashboardResponse:
    """Get broker dashboard data."""
    dashboard_service = DashboardService(db)
    return await dashboard_service.get_broker_dashboard(user_id)

@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    user_id: int,  # TODO: Extract from JWT token
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session)
) -> NotificationListResponse:
    """List paginated notifications for the authenticated user."""
    notification_service = NotificationService(db)
    return await notification_service.list_notifications(user_id, page, limit)

@router.put("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: int,
    payload: NotificationReadRequest,
    user_id: int,  # TODO: Extract from JWT token
    db: AsyncSession = Depends(get_async_session)
) -> None:
    """Mark a specific notification as read/unread."""
    notification_service = NotificationService(db)
    await notification_service.mark_notification_as_read(notification_id, user_id, payload)

@router.put("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_read(
    user_id: int,  # TODO: Extract from JWT token
    db: AsyncSession = Depends(get_async_session)
) -> None:
    """Mark all unread notifications as read."""
    notification_service = NotificationService(db)
    await notification_service.mark_all_notifications_as_read(user_id)