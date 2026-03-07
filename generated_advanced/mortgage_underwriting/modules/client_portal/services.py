from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.common.security import verify_password
from mortgage_underwriting.modules.client_portal.models import ClientPortalUser, Notification, User
from mortgage_underwriting.modules.client_portal.schemas import (

    LoginRequest,
    TokenResponse,
    UserResponse,
    ClientDashboardResponse,
    OutstandingDocumentItem,
    RecentMessageResponse,
    KeyNumbersResponse,
    DashboardProgressResponse,
    BrokerDashboardResponse,
    PipelineSummaryResponse,
    FlaggedFileResponse,
    RecentActivityResponse,
    QuickActionResponse,
    NotificationListResponse,
    NotificationReadRequest
)

logger = structlog.get_logger()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def authenticate_user(self, credentials: LoginRequest) -> TokenResponse:
        """Authenticate user and return JWT token."""
        logger.info("authenticating_user", username=credentials.username)
        stmt = select(User).where(User.username == credentials.username)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(credentials.password, user.password_hash):
            logger.warning("authentication_failed", username=credentials.username)
            raise AppException(detail="Invalid credentials", error_code="CLIENT_PORTAL_004")

        # Update last login
        user.client_portal_user.last_login_at = func.now()
        await self.db.commit()
        await self.db.refresh(user)

        user_response = UserResponse.model_validate(user)
        return TokenResponse(
            access_token="mock-jwt-token",
            token_type="bearer",
            user=user_response
        )


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_client_dashboard(self, user_id: int) -> ClientDashboardResponse:
        """Get client dashboard data including progress, documents, and key numbers."""
        logger.info("fetching_client_dashboard", user_id=user_id)
        # FIXED: Mocked implementation - in production would join with real data
        return ClientDashboardResponse(
            progress=DashboardProgressResponse(current_status="Submitted", next_status="In Review", percent_complete=60),
            outstanding_documents=[
                OutstandingDocumentItem(document_type="Proof of Income", required=True, uploaded=False),
                OutstandingDocumentItem(document_type="Bank Statements", required=True, uploaded=True)
            ],
            recent_message=RecentMessageResponse(sender="Broker Team", message="Please upload your T4 slips.", timestamp="2023-09-15T14:30:00Z"),
            key_numbers=KeyNumbersResponse(requested_mortgage=Decimal('450000'), purchase_price=Decimal('500000'), status="Submitted")
        )

    async def get_broker_dashboard(self, user_id: int) -> BrokerDashboardResponse:
        """Get broker dashboard data including pipeline summary and flagged files."""
        logger.info("fetching_broker_dashboard", user_id=user_id)
        # FIXED: Mocked implementation - in production would aggregate real data
        return BrokerDashboardResponse(
            pipeline_summary=PipelineSummaryResponse(draft=2, submitted=5, in_review=3, conditionally_approved=1, approved=0, closed=1),
            flagged_files=[
                FlaggedFileResponse(application_id=101, reason="Missing Documents", days_overdue=3),
                FlaggedFileResponse(application_id=102, reason="Past Due", days_overdue=5)
            ],
            recent_activity=[
                RecentActivityResponse(activity_type="Document Uploaded", description="Client uploaded T4 slip for app #101", timestamp="2023-09-15T10:00:00Z"),
                RecentActivityResponse(activity_type="Status Changed", description="App #102 moved to In Review", timestamp="2023-09-14T16:45:00Z")
            ],
            quick_actions=[
                QuickActionResponse(action="Start New Application", url="/applications/new"),
                QuickActionResponse(action="Send Document Request", url="/messages/new")
            ]
        )


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_notifications(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 20
    ) -> NotificationListResponse:
        """List paginated notifications for a user."""
        logger.info("listing_notifications", user_id=user_id, page=page, limit=limit)
        offset = (page - 1) * limit
        stmt = select(Notification) \
            .where(Notification.recipient_id == user_id) \
            .order_by(Notification.created_at.desc()) \
            .offset(offset) \
            .limit(limit)
        result = await self.db.execute(stmt)
        notifications = result.scalars().all()

        count_stmt = select(func.count()).select_from(Notification).where(Notification.recipient_id == user_id)
        total = await self.db.scalar(count_stmt)

        return NotificationListResponse(
            total=total or 0,
            page=page,
            limit=limit,
            items=[NotificationResponse.model_validate(n) for n in notifications]
        )

    async def mark_notification_as_read(
        self,
        notification_id: int,
        user_id: int,
        payload: NotificationReadRequest
    ) -> NotificationResponse:
        """Mark a notification as read/unread."""
        logger.info("marking_notification_read", notification_id=notification_id, user_id=user_id, is_read=payload.is_read)
        stmt = select(Notification) \
            .where(Notification.id == notification_id) \
            .where(Notification.recipient_id == user_id)
        result = await self.db.execute(stmt)
        notification = result.scalar_one_or_none()

        if not notification:
            raise NotFoundError(detail="Notification not found", error_code="CLIENT_PORTAL_001")

        notification.is_read = payload.is_read
        if payload.is_read:
            notification.read_at = func.now()
        else:
            notification.read_at = None

        await self.db.commit()
        await self.db.refresh(notification)

        return NotificationResponse.model_validate(notification)

    async def mark_all_notifications_as_read(self, user_id: int) -> None:
        """Mark all unread notifications as read for a user."""
        logger.info("marking_all_notifications_read", user_id=user_id)
        stmt = select(Notification) \
            .where(Notification.recipient_id == user_id) \
            .where(Notification.is_read == False)
        result = await self.db.execute(stmt)
        notifications = result.scalars().all()

        for notification in notifications:
            notification.is_read = True
            notification.read_at = func.now()

        await self.db.commit()
        logger.info("marked_all_notifications_read", count=len(notifications))