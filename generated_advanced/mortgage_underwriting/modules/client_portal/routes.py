from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.client_portal.schemas import (
    LoginRequest,
    LoginResponse,
    DashboardResponse,
    ApplicationSummary,
    ApplicationDetail,
    CreateApplicationRequest,
    UpdateApplicationRequest,
    DocumentChecklistResponse,
    NotificationListResponse,
    NotificationResponse,
    MarkNotificationReadRequest,
    MarkAllNotificationsReadRequest,
)
from mortgage_underwriting.modules.client_portal.services import (
    ClientAuthService,
    ClientDashboardService,
    ClientApplicationService,
    ClientDocumentService,
    ClientNotificationService,
)
from mortgage_underwriting.modules.client_portal.exceptions import ClientPortalAuthError, ClientPortalValidationError

# Mock dependency - in real app use OAuth2 + JWT middleware


async def get_current_client_user(session: AsyncSession = Depends(get_async_session)) -> int:
    # Simulate getting user from JWT token
    return 1  # mock client user ID

router = APIRouter(prefix="/api/v1/client-portal", tags=["Client Portal"])


@router.post("/auth/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def client_login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_async_session),
) -> LoginResponse:
    """Authenticate client user and return access token."""
    try:
        # FIXED: Added input validation
        if not payload.email or not payload.password:
            raise ClientPortalValidationError("Email and password are required")
            
        service = ClientAuthService(db)
        return await service.authenticate_and_login(payload)
    except ClientPortalAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": str(e), "error_code": "CLIENT_PORTAL_002"},
        )
    except ClientPortalValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "CLIENT_PORTAL_007"},
        )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def client_logout() -> None:
    """Logout client user (invalidate token)."""
    # In real app, invalidate JWT token
    return


@router.post("/auth/refresh", response_model=LoginResponse)
async def client_refresh_token() -> LoginResponse:
    """Refresh access token using refresh token."""
    # In real app, validate refresh token and issue new access token
    return LoginResponse(
        access_token="new-jwt-token",
        token_type="bearer",
        user_id=1,
        client_id=1,
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def client_dashboard(
    client_id: int = Depends(get_current_client_user),
    db: AsyncSession = Depends(get_async_session),
) -> DashboardResponse:
    """Get client dashboard summary."""
    # FIXED: Added validation
    if client_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid client ID", "error_code": "CLIENT_PORTAL_007"},
        )
    service = ClientDashboardService(db)
    return await service.get_dashboard(client_id)


@router.get("/applications", response_model=List[ApplicationSummary])
async def list_client_applications(
    client_id: int = Depends(get_current_client_user),
    db: AsyncSession = Depends(get_async_session),
) -> List[ApplicationSummary]:
    """List all applications for the authenticated client."""
    # FIXED: Added validation
    if client_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid client ID", "error_code": "CLIENT_PORTAL_007"},
        )
    service = ClientApplicationService(db)
    return await service.list_applications(client_id)


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
async def get_client_application(
    application_id: int,
    client_id: int = Depends(get_current_client_user),
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationDetail:
    """Get detailed view of a specific application."""
    # FIXED: Added validation
    if application_id <= 0 or client_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid application or client ID", "error_code": "CLIENT_PORTAL_007"},
        )
    service = ClientApplicationService(db)
    return await service.get_application(application_id, client_id)


@router.post("/applications", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
async def create_client_application(
    payload: CreateApplicationRequest,
    client_id: int = Depends(get_current_client_user),
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationDetail:
    """Create a new mortgage application draft."""
    # FIXED: Added validation
    if client_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid client ID", "error_code": "CLIENT_PORTAL_007"},
        )
    service = ClientApplicationService(db)
    return await service.create_application(payload, client_id)


@router.put("/applications/{application_id}", response_model=ApplicationDetail)
async def update_client_application(
    application_id: int,
    payload: UpdateApplicationRequest,
    client_id: int = Depends(get_current_client_user),
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationDetail:
    """Update an existing application (e.g., change status)."""
    # FIXED: Added validation
    if application_id <= 0 or client_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid application or client ID", "error_code": "CLIENT_PORTAL_007"},
        )
    service = ClientApplicationService(db)
    return await service.update_application(application_id, payload, client_id)


@router.get("/applications/{application_id}/documents/checklist", response_model=DocumentChecklistResponse)
async def get_document_checklist(
    application_id: int,
    client_id: int = Depends(get_current_client_user),
    db: AsyncSession = Depends(get_async_session),
) -> DocumentChecklistResponse:
    """Get document checklist for an application."""
    # FIXED: Added validation
    if application_id <= 0 or client_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid application or client ID", "error_code": "CLIENT_PORTAL_007"},
        )
    service = ClientDocumentService(db)
    return await service.get_document_checklist(application_id)


@router.post("/applications/{application_id}/documents/upload")
async def upload_document(
    application_id: int,
    # file: UploadFile = File(...),  # Would handle file upload in real app
    client_id: int = Depends(get_current_client_user),
) -> dict:
    """Upload a document for an application (stub)."""
    # FIXED: Added validation
    if application_id <= 0 or client_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid application or client ID", "error_code": "CLIENT_PORTAL_007"},
        )
    return {"message": f"Document upload initiated for app {application_id}"}


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    client_id: int = Depends(get_current_client_user),
    db: AsyncSession = Depends(get_async_session),
) -> NotificationListResponse:
    """List paginated notifications for the client."""
    # FIXED: Added validation
    if client_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid client ID", "error_code": "CLIENT_PORTAL_007"},
        )
    if limit <= 0 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Limit must be between 1 and 100", "error_code": "CLIENT_PORTAL_007"},
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Offset must be non-negative", "error_code": "CLIENT_PORTAL_007"},
        )
    service = ClientNotificationService(db)
    return await service.list_notifications(client_id, limit, offset)


@router.put("/notifications/{notification_id}", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    payload: MarkNotificationReadRequest,
    client_id: int = Depends(get_current_client_user),
    db: AsyncSession = Depends(get_async_session),
) -> NotificationResponse:
    """Mark a notification as read/unread."""
    # FIXED: Added validation
    if notification_id <= 0 or client_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid notification or client ID", "error_code": "CLIENT_PORTAL_007"},
        )
    service = ClientNotificationService(db)
    return await service.mark_notification_read(notification_id, payload, client_id)


@router.put("/notifications/mark-all-read")
async def mark_all_notifications_read(
    payload: MarkAllNotificationsReadRequest,
    client_id: int = Depends(get_current_client_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    """Mark all notifications as read."""
    # FIXED: Added validation
    if client_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid client ID", "error_code": "CLIENT_PORTAL_007"},
        )
    service = ClientNotificationService(db)
    await service.mark_all_notifications_read(payload, client_id)
    return {"message": "All notifications marked as read"}