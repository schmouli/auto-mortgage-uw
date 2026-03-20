from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# --- Activity Log Schemas ---

class ClientPortalActivityBase(BaseModel):
    activity_type: str = Field(..., max_length=50, description="Type of activity performed")
    ip_address: Optional[str] = Field(None, max_length=45, description="IP address of the user")
    user_agent: Optional[str] = Field(None, description="Browser/user agent string")
    details: Optional[str] = Field(None, description="Additional details about the activity (JSON)")


class ClientPortalActivityCreate(ClientPortalActivityBase):
    user_id: int = Field(..., gt=0, description="ID of the user performing the activity")


class ClientPortalActivityResponse(ClientPortalActivityBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime


# --- Notification Schemas ---

class NotificationBase(BaseModel):
    title: str = Field(..., max_length=255)
    message: str
    notification_type: str = Field(..., max_length=50)
    reference_id: Optional[int] = Field(None, gt=0)


class NotificationCreate(NotificationBase):
    user_id: int = Field(..., gt=0)


class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = Field(None)
    read_at: Optional[datetime] = Field(None)


class NotificationResponse(NotificationBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    size: int


class NotificationMarkReadAllRequest(BaseModel):
    mark_all_as_read: bool = Field(True, description="Set to true to mark all notifications as read")


# --- User Preference Schemas ---

class UserPreferenceBase(BaseModel):
    timezone: str = Field("UTC", max_length=50)
    language: str = Field("en", max_length=10)
    email_notifications_enabled: bool = True
    in_app_notifications_enabled: bool = True
    dashboard_layout: Optional[str] = Field(None, description="JSON string of dashboard layout")


class UserPreferenceCreate(UserPreferenceBase):
    user_id: int = Field(..., gt=0)


class UserPreferenceUpdate(UserPreferenceBase):
    pass


class UserPreferenceResponse(UserPreferenceBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


# --- Dashboard Schemas ---

class ClientDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    pipeline_summary: Dict[str, int]  # e.g., {'draft': 2, 'submitted': 1}
    flagged_files_count: int
    recent_activity_feed: List[Dict[str, Any]]  # Simplified representation
    quick_actions: List[str]  # e.g., ['start_new_application']


class BrokerDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    pipeline_summary: Dict[str, int]
    flagged_files_count: int
    recent_activity_feed: List[Dict[str, Any]]
    quick_actions: List[str]