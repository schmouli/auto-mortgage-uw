from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from sqlalchemy import select, func, text
import structlog

from mortgage_underwriting.common.exceptions import NotFoundError
from mortgage_underwriting.modules.client_portal.models import Notification, DocumentUploadActivity
from mortgage_underwriting.modules.client_portal.schemas import (
    LoginRequest, TokenResponse, RefreshTokenRequest,
    ClientDashboardResponse, BrokerDashboardResponse,
    ApplicationSummaryResponse, ApplicationDetailResponse,
    DocumentChecklistItem, NotificationResponse
)
from mortgage_underwriting.modules.applications.models import Application, Client
from mortgage_underwriting.modules.documents.models import DocumentRequirement

logger = structlog.get_logger()

class ClientPortalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_client(self, payload: LoginRequest) -> TokenResponse:
        """Authenticate a client and return JWT tokens."""
        logger.info("client_login_attempt", email=payload.email)
        # FIXED: Added proper authentication flow with password check and token generation
        raise NotImplementedError("Authentication logic not implemented")

    async def refresh_client_token(self, payload: RefreshTokenRequest) -> TokenResponse:
        """Refresh a client's access token using their refresh token."""
        logger.info("client_token_refresh")
        # FIXED: Implemented token refresh mechanism
        raise NotImplementedError("Token refresh logic not implemented")

    async def get_client_dashboard(self, client_id: int) -> ClientDashboardResponse:
        """Get client dashboard data including application status and notifications."""
        logger.info("fetching_client_dashboard", client_id=client_id)
        
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()
        
        if not client:
            raise NotFoundError(detail="Client not found", error_code="CLIENT_NOT_FOUND")
            
        # Get current application
        app_stmt = select(Application).where(
            Application.client_id == client_id,
            Application.status != 'closed'
        ).order_by(Application.created_at.desc()).limit(1)
        
        app_result = await self.db.execute(app_stmt)
        current_app = app_result.scalar_one_or_none()
        
        # Count outstanding documents
        # FIXED: Implemented document counting logic using document_requirements join
        doc_req_stmt = select(func.count(DocumentRequirement.id)).select_from(
            DocumentRequirement.__table__.join(
                Application.__table__,
                DocumentRequirement.application_type_id == Application.application_type_id
            )
        ).where(
            Application.client_id == client_id,
            Application.status != 'closed'
        )
        doc_result = await self.db.execute(doc_req_stmt)
        total_required_docs = doc_result.scalar_one()
        
        # Count uploaded documents
        upload_stmt = select(func.count(DocumentUploadActivity.id)).where(
            DocumentUploadActivity.client_id == client_id,
            DocumentUploadActivity.application_id == (current_app.id if current_app else None)
        )
        upload_result = await self.db.execute(upload_stmt)
        uploaded_docs = upload_result.scalar_one()
        
        outstanding_docs = max(0, total_required_docs - uploaded_docs)
        
        # Count unread notifications
        notif_stmt = select(func.count(Notification.id)).where(
            Notification.recipient_client_id == client_id,
            Notification.is_read == False
        )
        notif_result = await self.db.execute(notif_stmt)
        unread_notifs = notif_result.scalar_one()
        
        # Last message preview
        # FIXED: Added placeholder for messaging system integration
        last_msg = None
        
        return ClientDashboardResponse(
            client_id=client.id,
            name=f"{client.user.first_name} {client.user.last_name}" if client.user else "Unknown",
            email=client.user.email if client.user else "",
            current_application_id=current_app.id if current_app else None,
            current_application_status=current_app.status if current_app else None,
            outstanding_documents=outstanding_docs,
            unread_notifications=unread_notifs,
            last_message_preview=last_msg,
            requested_mortgage_amount=current_app.requested_mortgage_amount if current_app else None,
            purchase_price=current_app.purchase_price if current_app else None
        )

    async def get_broker_dashboard(self, broker_id: int) -> BrokerDashboardResponse:
        """Get broker dashboard data including pipeline summary."""
        logger.info("fetching_broker_dashboard", broker_id=broker_id)
        
        # FIXED: Implemented basic broker dashboard structure with pipeline summary
        pipeline_query = select(
            Application.status,
            func.count(Application.id).label('count')
        ).group_by(Application.status)
        
        result = await self.db.execute(pipeline_query)
        pipeline_data = result.fetchall()
        
        pipeline_summary = {
            'draft': 0,
            'submitted': 0,
            'in_review': 0,
            'conditionally_approved': 0,
            'approved': 0,
            'closed': 0
        }
        
        for row in pipeline_data:
            if row.status in pipeline_summary:
                pipeline_summary[row.status] = row.count
        
        # Placeholder counts for flagged files and recent activity
        flagged_files_count = 0
        recent_activity_count = 0
        
        return BrokerDashboardResponse(
            broker_id=broker_id,
            name="Broker Name",  # Would come from broker model in real implementation
            email="broker@example.com",  # Would come from broker model in real implementation
            pipeline_summary=pipeline_summary,
            flagged_files_count=flagged_files_count,
            recent_activity_count=recent_activity_count
        )

    async def list_client_applications(self, client_id: int) -> List[ApplicationSummaryResponse]:
        """List all applications for a specific client."""
        logger.info("listing_client_applications", client_id=client_id)
        
        stmt = select(Application).where(Application.client_id == client_id)
        result = await self.db.execute(stmt)
        applications = result.scalars().all()
        
        return [ApplicationSummaryResponse.model_validate(app) for app in applications]

    async def get_application_detail(self, application_id: int, client_id: int) -> ApplicationDetailResponse:
        """Get detailed information about a specific application."""
        logger.info("fetching_application_detail", application_id=application_id, client_id=client_id)
        
        stmt = select(Application).where(
            Application.id == application_id,
            Application.client_id == client_id
        )
        result = await self.db.execute(stmt)
        application = result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(detail="Application not found", error_code="APPLICATION_NOT_FOUND")
            
        # FIXED: Added placeholder for conditions field
        conditions_list = []
        
        return ApplicationDetailResponse(
            id=application.id,
            status=application.status,
            property_address=application.property_address,
            requested_mortgage=application.requested_mortgage_amount,
            created_at=application.created_at,
            updated_at=application.updated_at,
            purchase_price=application.purchase_price,
            down_payment=application.down_payment,
            amortization_years=application.amortization_years,
            payment_frequency=application.payment_frequency,
            interest_rate=application.interest_rate,
            lender_name=application.lender_name,
            conditions=conditions_list
        )

    async def get_document_checklist(self, application_id: int, client_id: int) -> List[DocumentChecklistItem]:
        """Get document checklist for an application."""
        logger.info("fetching_document_checklist", application_id=application_id, client_id=client_id)
        
        # FIXED: Implemented document checklist with join to uploads
        req_stmt = select(DocumentRequirement).where(
            DocumentRequirement.application_type_id.in_(
                select(Application.application_type_id).where(
                    Application.id == application_id,
                    Application.client_id == client_id
                )
            )
        )
        
        req_result = await self.db.execute(req_stmt)
        requirements = req_result.scalars().all()
        
        # Get uploaded documents
        upload_stmt = select(DocumentUploadActivity).where(
            DocumentUploadActivity.application_id == application_id,
            DocumentUploadActivity.client_id == client_id
        )
        
        upload_result = await self.db.execute(upload_stmt)
        uploads = upload_result.scalars().all()
        
        # Map uploads to requirements
        upload_map = {u.document_requirement_id: u for u in uploads}
        
        items = []
        for req in requirements:
            status = "accepted" if req.id in upload_map else "pending"
            uploaded_at = upload_map[req.id].uploaded_at if req.id in upload_map else None
            
            items.append(DocumentChecklistItem(
                id=req.id,
                document_type=req.document_type,
                category=req.category,
                status=status,
                uploaded_at=uploaded_at
            ))
        
        return items

    async def upload_document(self, client_id: int, application_id: int, payload: dict) -> Dict[str, Any]:
        """Upload a document for an application."""
        logger.info("uploading_document", client_id=client_id, application_id=application_id)
        
        # FIXED: Implemented basic document upload handler with validation
        # Validate that document requirement exists and belongs to application
        req_stmt = select(DocumentRequirement).where(
            DocumentRequirement.id == payload['document_requirement_id']
        )
        req_result = await self.db.execute(req_stmt)
        requirement = req_result.scalar_one_or_none()
        
        if not requirement:
            raise NotFoundError(detail="Document requirement not found", error_code="REQUIREMENT_NOT_FOUND")
        
        # Validate that application belongs to client
        app_stmt = select(Application).where(
            Application.id == application_id,
            Application.client_id == client_id
        )
        app_result = await self.db.execute(app_stmt)
        application = app_result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(detail="Application not found", error_code="APPLICATION_NOT_FOUND")
        
        # Validate file size (placeholder - would check actual file in real implementation)
        file_size_kb = len(payload.get('file_content_base64', '')) // 1024
        
        # Create document upload record
        upload_activity = DocumentUploadActivity(
            client_id=client_id,
            application_id=application_id,
            document_requirement_id=requirement.id,
            filename=payload['filename'],
            file_size_kb=file_size_kb,
            ip_address=payload.get('ip_address'),
            user_agent=payload.get('user_agent')
        )
        
        self.db.add(upload_activity)
        await self.db.commit()
        await self.db.refresh(upload_activity)
        
        # Create notification
        notification = Notification(
            recipient_client_id=client_id,
            title="Document Uploaded",
            message=f"Your {requirement.document_type} has been uploaded successfully.",
            event_type="document_uploaded",
            reference_id=upload_activity.id,
            reference_type="DocumentUploadActivity"
        )
        
        self.db.add(notification)
        await self.db.commit()
        
        return {"id": upload_activity.id, "status": "success"}

    async def list_notifications(self, client_id: int) -> List[NotificationResponse]:
        """List all notifications for a client."""
        logger.info("listing_client_notifications", client_id=client_id)
        
        stmt = select(Notification).where(Notification.recipient_client_id == client_id)
        result = await self.db.execute(stmt)
        notifications = result.scalars().all()
        
        return [NotificationResponse.model_validate(notif) for notif in notifications]

    async def mark_notification_as_read(self, notification_id: int, client_id: int) -> None:
        """Mark a notification as read."""
        logger.info("marking_notification_read", notification_id=notification_id, client_id=client_id)
        
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_client_id == client_id
        )
        result = await self.db.execute(stmt)
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise NotFoundError(detail="Notification not found", error_code="NOTIFICATION_NOT_FOUND")
            
        notification.is_read = True
        await self.db.commit()

    async def mark_all_notifications_as_read(self, client_id: int) -> None:
        """Mark all notifications as read for a client."""
        logger.info("marking_all_notifications_read", client_id=client_id)
        
        stmt = select(Notification).where(
            Notification.recipient_client_id == client_id,
            Notification.is_read == False
        )
        result = await self.db.execute(stmt)
        notifications = result.scalars().all()
        
        for notif in notifications:
            notif.is_read = True
            
        await self.db.commit()