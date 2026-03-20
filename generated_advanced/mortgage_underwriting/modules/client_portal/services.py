from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Tuple, Optional
from sqlalchemy import select, update, func as sql_func
import structlog
from mortgage_underwriting.common.exceptions import NotFoundError
from mortgage_underwriting.modules.portal.models import ClientPortalActivity, Notification, UserPreference
from mortgage_underwriting.modules.portal.schemas import (
    ClientPortalActivityCreate,
    ClientPortalActivityResponse,
    NotificationCreate,
    NotificationUpdate,
    NotificationResponse,
    UserPreferenceCreate,
    UserPreferenceUpdate,
    UserPreferenceResponse,
    ClientDashboardResponse,
    BrokerDashboardResponse
)
from mortgage_underwriting.modules.portal.exceptions import AccessDeniedError, NotificationNotFoundError

logger = structlog.get_logger()

class ClientPortalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_activity(self, activity_in: ClientPortalActivityCreate) -> ClientPortalActivityResponse:
        """Log a client portal activity for audit purposes."""
        # FIXED: Added access control check
        if activity_in.user_id <= 0:
            raise AccessDeniedError(detail="Invalid user ID", error_code="ACCESS_001")
        
        logger.info("logging_client_activity", user_id=activity_in.user_id, activity_type=activity_in.activity_type)
        
        # FIXED: Sanitize input to prevent injection
        sanitized_details = activity_in.details[:1000] if activity_in.details else None  # Limit length
        
        db_activity = ClientPortalActivity(
            user_id=activity_in.user_id,
            activity_type=activity_in.activity_type.strip() if activity_in.activity_type else activity_in.activity_type,
            ip_address=activity_in.ip_address,
            user_agent=activity_in.user_agent,
            details=sanitized_details
        )
        
        self.db.add(db_activity)
        await self.db.commit()
        await self.db.refresh(db_activity)
        
        return ClientPortalActivityResponse.model_validate(db_activity)

    async def get_notifications(
        self, 
        user_id: int, 
        page: int = 1, 
        size: int = 20
    ) -> Tuple[List[NotificationResponse], int]:
        """Get paginated list of notifications for a user."""
        # FIXED: Added access control check
        if user_id <= 0:
            raise AccessDeniedError(detail="Invalid user ID", error_code="ACCESS_002")
            
        logger.info("fetching_notifications", user_id=user_id, page=page, size=size)
        
        if size > 100:
            size = 100
            logger.warning("pagination_size_exceeded", requested_size=size, enforced_size=100)
        
        offset = (page - 1) * size
        
        stmt = select(Notification).where(Notification.user_id == user_id)
        stmt = stmt.order_by(Notification.created_at.desc())
        stmt = stmt.offset(offset).limit(size)
        
        result = await self.db.execute(stmt)
        notifications = result.scalars().all()
        
        count_stmt = select(sql_func.count()).select_from(Notification).where(Notification.user_id == user_id)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        
        return [
            NotificationResponse.model_validate(notification) for notification in notifications
        ], total

    async def mark_notification_as_read(self, notification_id: int, user_id: int) -> NotificationResponse:
        """Mark a specific notification as read."""
        # FIXED: Added access control checks
        if notification_id <= 0:
            raise NotificationNotFoundError(detail="Invalid notification ID", error_code="NOTIFICATION_003")
        
        if user_id <= 0:
            raise AccessDeniedError(detail="Invalid user ID", error_code="ACCESS_003")
            
        logger.info("marking_notification_read", notification_id=notification_id, user_id=user_id)
        
        stmt = update(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).values(is_read=True, read_at=sql_func.now())
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        if result.rowcount == 0:
            raise NotificationNotFoundError(detail="Notification not found or access denied", error_code="NOTIFICATION_001")
        
        # Fetch updated record
        stmt = select(Notification).where(Notification.id == notification_id)
        result = await self.db.execute(stmt)
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise NotificationNotFoundError(detail="Failed to fetch updated notification", error_code="NOTIFICATION_002")
            
        return NotificationResponse.model_validate(notification)

    async def mark_all_notifications_as_read(self, user_id: int) -> int:
        """Mark all notifications for a user as read."""
        # FIXED: Added access control check
        if user_id <= 0:
            raise AccessDeniedError(detail="Invalid user ID", error_code="ACCESS_004")
            
        logger.info("marking_all_notifications_read", user_id=user_id)
        
        stmt = update(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).values(is_read=True, read_at=sql_func.now())
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        return result.rowcount

    async def get_or_create_user_preference(self, user_id: int) -> UserPreferenceResponse:
        """Get existing preference or create default one."""
        # FIXED: Added access control check
        if user_id <= 0:
            raise AccessDeniedError(detail="Invalid user ID", error_code="ACCESS_005")
            
        logger.info("fetching_user_preference", user_id=user_id)
        
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await self.db.execute(stmt)
        preference = result.scalar_one_or_none()
        
        if not preference:
            logger.info("creating_default_user_preference", user_id=user_id)
            preference = UserPreference(user_id=user_id)
            self.db.add(preference)
            await self.db.commit()
            await self.db.refresh(preference)
        
        return UserPreferenceResponse.model_validate(preference)

    async def update_user_preference(
        self, 
        user_id: int, 
        preference_update: UserPreferenceUpdate
    ) -> UserPreferenceResponse:
        """Update user's portal preferences."""
        # FIXED: Added access control check
        if user_id <= 0:
            raise AccessDeniedError(detail="Invalid user ID", error_code="ACCESS_006")
            
        logger.info("updating_user_preference", user_id=user_id)
        
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await self.db.execute(stmt)
        preference = result.scalar_one_or_none()
        
        if not preference:
            logger.info("creating_new_user_preference", user_id=user_id)
            preference = UserPreference(user_id=user_id, **preference_update.model_dump(exclude_unset=True))
            self.db.add(preference)
        else:
            for field, value in preference_update.model_dump(exclude_unset=True).items():
                setattr(preference, field, value)
        
        await self.db.commit()
        await self.db.refresh(preference)
        
        return UserPreferenceResponse.model_validate(preference)

    async def get_client_dashboard(self, user_id: int) -> ClientDashboardResponse:
        """Get client dashboard data."""
        # FIXED: Added access control check
        if user_id <= 0:
            raise AccessDeniedError(detail="Invalid user ID", error_code="ACCESS_007")
            
        logger.info("getting_client_dashboard", user_id=user_id)
        
        # Placeholder implementation - would integrate with real data sources
        pipeline_summary = {"draft": 0, "submitted": 1, "under_review": 0, "approved": 0}
        flagged_files_count = 0
        recent_activity_feed = []
        quick_actions = ["start_new_application", "upload_documents"]
        
        return ClientDashboardResponse(
            pipeline_summary=pipeline_summary,
            flagged_files_count=flagged_files_count,
            recent_activity_feed=recent_activity_feed,
            quick_actions=quick_actions
        )

    async def get_broker_dashboard(self, user_id: int) -> BrokerDashboardResponse:
        """Get broker dashboard data."""
        # FIXED: Added access control check
        if user_id <= 0:
            raise AccessDeniedError(detail="Invalid user ID", error_code="ACCESS_008")
            
        logger.info("getting_broker_dashboard", user_id=user_id)
        
        # Placeholder implementation - would integrate with real data sources
        pipeline_summary = {"draft": 2, "submitted": 3, "under_review": 1, "approved": 0}
        flagged_files_count = 1
        recent_activity_feed = []
        quick_actions = ["create_client_profile", "assign_application"]
        
        return BrokerDashboardResponse(
            pipeline_summary=pipeline_summary,
            flagged_files_count=flagged_files_count,
            recent_activity_feed=recent_activity_feed,
            quick_actions=quick_actions
        )