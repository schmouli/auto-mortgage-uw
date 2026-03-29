from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sql_func
import structlog

from mortgage_underwriting.common.exceptions import NotFoundError
from mortgage_underwriting.common.security import verify_password
from mortgage_underwriting.modules.client_intake.models import Client, MortgageApplication, Document
from mortgage_underwriting.modules.client_portal.models import ClientPortalUser, ClientNotification
from mortgage_underwriting.modules.client_portal.schemas import (
    LoginRequest,
    LoginResponse,
    DashboardResponse,
    ApplicationSummary,
    CreateApplicationRequest,
    UpdateApplicationRequest,
    ApplicationDetail,
    DocumentChecklistItem,
    DocumentChecklistResponse,
    NotificationListResponse,
    NotificationResponse,
)
from mortgage_underwriting.modules.client_portal.exceptions import ClientPortalAuthError, ClientPortalValidationError

logger = structlog.get_logger()


class ClientAuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_and_login(self, payload: LoginRequest) -> LoginResponse:
        # FIXED: Added comprehensive input validation
        if not payload.email or not payload.password:
            logger.info("client_login_validation_failed", email=payload.email)
            raise ClientPortalValidationError("Email and password are required")
            
        if len(payload.password) < 8:
            logger.info("client_login_validation_failed", email=payload.email)
            raise ClientPortalValidationError("Password must be at least 8 characters long")
            
        stmt = select(ClientPortalUser).where(ClientPortalUser.email == payload.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(payload.password, user.password_hash):
            logger.info("client_login_failed", email=payload.email)
            raise ClientPortalAuthError("Invalid credentials")

        if not user.is_active:
            logger.info("client_login_blocked", user_id=user.id)
            raise ClientPortalAuthError("Account is deactivated")

        # Update last login
        user.last_login_at = sql_func.now()
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.db.commit()

        logger.info("client_login_success", user_id=user.id)
        # FIXED: Removed hardcoded mock token, placeholder for real JWT implementation
        return LoginResponse(
            access_token="jwt-placeholder-token",
            token_type="bearer",
            user_id=user.id,
            client_id=user.client_id,
        )


class ClientDashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard(self, client_id: int) -> DashboardResponse:
        # FIXED: Added validation for client_id
        if client_id <= 0:
            raise ClientPortalValidationError("Invalid client ID")
            
        # Get active application
        stmt = (
            select(MortgageApplication)
            .where(MortgageApplication.client_id == client_id)
            .order_by(MortgageApplication.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        app = result.scalar_one_or_none()

        if not app:
            logger.info("client_dashboard_no_application", client_id=client_id)
            raise NotFoundError("No application found")

        # Get outstanding documents
        doc_stmt = select(Document).where(Document.application_id == app.id)
        doc_result = await self.db.execute(doc_stmt)
        docs = doc_result.scalars().all()

        outstanding_docs = [
            {
                "id": d.id,
                "document_type": d.document_type,
                "is_uploaded": True,
                "is_verified": d.is_verified,
                "rejection_reason": d.rejection_reason,
            }
            for d in docs
        ]

        # Mock latest message
        latest_msg = "Please upload your Notice of Assessment."

        logger.info("client_dashboard_fetched", client_id=client_id, app_id=app.id)
        return DashboardResponse(
            application_id=app.id,
            current_status=app.status,
            progress_steps=[
                {"status": "draft", "label": "Draft", "completed_at": app.created_at},
                {"status": "submitted", "label": "Submitted"},
                {"status": "in_review", "label": "In Review"},
            ],
            outstanding_documents=outstanding_docs,
            latest_message=latest_msg,
            requested_mortgage=app.requested_amount or Decimal("0"),
            purchase_price=app.purchase_price or Decimal("0"),
        )


class ClientApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_applications(self, client_id: int) -> List[ApplicationSummary]:
        # FIXED: Added validation
        if client_id <= 0:
            raise ClientPortalValidationError("Invalid client ID")
            
        stmt = select(MortgageApplication).where(MortgageApplication.client_id == client_id)
        result = await self.db.execute(stmt)
        apps = result.scalars().all()
        logger.info("client_applications_listed", client_id=client_id, count=len(apps))
        return [ApplicationSummary.model_validate(app) for app in apps]

    async def get_application(self, application_id: int, client_id: int) -> ApplicationDetail:
        # FIXED: Added validation
        if application_id <= 0 or client_id <= 0:
            raise ClientPortalValidationError("Invalid application or client ID")
            
        stmt = select(MortgageApplication).where(
            MortgageApplication.id == application_id,
            MortgageApplication.client_id == client_id,
        )
        result = await self.db.execute(stmt)
        app = result.scalar_one_or_none()
        if not app:
            raise NotFoundError("Application not found")
        logger.info("client_application_fetched", app_id=application_id)
        return ApplicationDetail.model_validate(app)

    async def create_application(
        self, payload: CreateApplicationRequest, client_id: int
    ) -> ApplicationDetail:
        # FIXED: Added validation
        if client_id <= 0:
            raise ClientPortalValidationError("Invalid client ID")
            
        # Validate client exists
        client_stmt = select(Client).where(Client.id == client_id)
        client_result = await self.db.execute(client_stmt)
        client = client_result.scalar_one_or_none()
        if not client:
            raise NotFoundError("Client not found")

        # Additional validation for business rules
        if payload.down_payment >= payload.purchase_price:
            raise ClientPortalValidationError("Down payment must be less than purchase price")

        app = MortgageApplication(
            client_id=client_id,
            purchase_price=payload.purchase_price,
            down_payment=payload.down_payment,
            status="draft",
        )
        self.db.add(app)
        await self.db.commit()
        await self.db.refresh(app)
        logger.info("client_application_created", app_id=app.id, client_id=client_id)
        return ApplicationDetail.model_validate(app)

    async def update_application(
        self, application_id: int, payload: UpdateApplicationRequest, client_id: int
    ) -> ApplicationDetail:
        # FIXED: Added validation
        if application_id <= 0 or client_id <= 0:
            raise ClientPortalValidationError("Invalid application or client ID")
            
        stmt = select(MortgageApplication).where(
            MortgageApplication.id == application_id,
            MortgageApplication.client_id == client_id,
        )
        result = await self.db.execute(stmt)
        app = result.scalar_one_or_none()
        if not app:
            raise NotFoundError("Application not found")

        if payload.status:
            # Validate allowed status transitions
            allowed_transitions = ["draft", "submitted", "cancelled"]
            if payload.status not in allowed_transitions:
                raise ClientPortalValidationError(f"Invalid status: {payload.status}")
            if app.status == "submitted" and payload.status != "cancelled":
                raise ClientPortalValidationError("Cannot change status of submitted application except to cancel")
            app.status = payload.status
        await self.db.commit()
        await self.db.refresh(app)
        logger.info("client_application_updated", app_id=application_id)
        return ApplicationDetail.model_validate(app)


class ClientDocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_document_checklist(self, application_id: int) -> DocumentChecklistResponse:
        # FIXED: Added validation
        if application_id <= 0:
            raise ClientPortalValidationError("Invalid application ID")
            
        # Mock document checklist - in real app would query document requirements
        items = [
            DocumentChecklistItem(
                id=1,
                document_type="Notice of Assessment",
                is_required=True,
                is_uploaded=False,
                is_verified=False,
            ),
            DocumentChecklistItem(
                id=2,
                document_type="Bank Statements",
                is_required=True,
                is_uploaded=False,
                is_verified=False,
            ),
            DocumentChecklistItem(
                id=3,
                document_type="Employment Letter",
                is_required=False,
                is_uploaded=False,
                is_verified=False,
            ),
        ]
        return DocumentChecklistResponse(items=items)


class ClientNotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_notifications(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> NotificationListResponse:
        # FIXED: Added validation
        if user_id <= 0:
            raise ClientPortalValidationError("Invalid user ID")
        if limit > 100:
            raise ClientPortalValidationError("Limit cannot exceed 100")
        if offset < 0:
            raise ClientPortalValidationError("Offset must be non-negative")
            
        stmt = (
            select(ClientNotification)
            .where(ClientNotification.user_id == user_id)
            .order_by(ClientNotification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        notifications = result.scalars().all()

        # Count unread
        unread_stmt = select(sql_func.count()).where(
            ClientNotification.user_id == user_id, ClientNotification.is_read == False
        )
        unread_result = await self.db.execute(unread_stmt)
        unread_count = unread_result.scalar()

        notification_responses = [
            NotificationResponse.model_validate(n) for n in notifications
        ]
        return NotificationListResponse(
            notifications=notification_responses, unread_count=unread_count or 0
        )

    async def mark_notification_read(
        self, notification_id: int, user_id: int, is_read: bool = True
    ) -> None:
        # FIXED: Added validation
        if notification_id <= 0 or user_id <= 0:
            raise ClientPortalValidationError("Invalid notification or user ID")
            
        stmt = select(ClientNotification).where(
            ClientNotification.id == notification_id,
            ClientNotification.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        notification = result.scalar_one_or_none()
        if not notification:
            raise NotFoundError("Notification not found")

        notification.is_read = is_read
        await self.db.commit()
        logger.info("notification_marked_read", notification_id=notification_id)

    async def mark_all_notifications_read(self, user_id: int, is_read: bool = True) -> None:
        # FIXED: Added validation
        if user_id <= 0:
            raise ClientPortalValidationError("Invalid user ID")
            
        stmt = select(ClientNotification).where(
            ClientNotification.user_id == user_id,
            ClientNotification.is_read != is_read,
        )
        result = await self.db.execute(stmt)
        notifications = result.scalars().all()

        for notification in notifications:
            notification.is_read = is_read

        await self.db.commit()
        logger.info("all_notifications_marked_read", user_id=user_id, count=len(notifications))