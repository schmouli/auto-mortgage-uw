"""Client portal schemas for mortgage underwriting system."""

from pydantic import BaseModel, Field, EmailStr, ConfigDict
from decimal import Decimal
from datetime import datetime
from typing import Optional
from uuid import UUID


class ClientBase(BaseModel):
    email: EmailStr = Field(..., description="Client's email address")
    first_name: str = Field(..., max_length=50, description="Client's first name")
    last_name: str = Field(..., max_length=50, description="Client's last name")
    phone: str = Field(..., max_length=20, description="Client's phone number")


class ClientCreate(ClientBase):
    pass


class ClientUpdate(ClientBase):
    email: Optional[EmailStr] = Field(None, description="Client's email address")
    first_name: Optional[str] = Field(None, max_length=50, description="Client's first name")
    last_name: Optional[str] = Field(None, max_length=50, description="Client's last name")
    phone: Optional[str] = Field(None, max_length=20, description="Client's phone number")


class ClientInDBBase(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClientResponse(ClientInDBBase):
    pass


class ClientPortalSessionBase(BaseModel):
    client_id: int = Field(..., description="ID of the associated client")
    session_token: str = Field(..., max_length=255, description="Unique session token")
    ip_address: str = Field(..., max_length=45, description="IP address of the client")
    user_agent: str = Field(..., description="User agent string")
    session_expiry_hours: Decimal = Field(..., gt=0, le=720, description="Session expiry in hours")


class SessionCreate(ClientPortalSessionBase):
    pass


class SessionInDBBase(ClientPortalSessionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SessionResponse(SessionInDBBase):
    pass
```

```