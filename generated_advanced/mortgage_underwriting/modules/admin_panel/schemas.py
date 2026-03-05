from pydantic import BaseModel, Field, ConfigDict, EmailStr
from decimal import Decimal
from datetime import datetime
from typing import Optional, List


# Role Schemas
class RoleBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(RoleBase):
    name: Optional[str] = Field(None, max_length=100)


class RoleResponse(RoleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


# Admin User Schemas
class AdminUserBase(BaseModel):
    email: EmailStr
    is_active: bool = True
    role_id: Optional[int] = None


class AdminUserCreate(AdminUserBase):
    pass


class AdminUserUpdate(AdminUserBase):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class AdminUserResponse(AdminUserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    roles: Optional[List[RoleResponse]] = None


# Support Agent Schemas
class SupportAgentBase(BaseModel):
    name: str = Field(..., max_length=255)
    hourly_rate: Decimal = Field(..., gt=0, description="Hourly rate in CAD")


class SupportAgentCreate(SupportAgentBase):
    pass


class SupportAgentUpdate(SupportAgentBase):
    name: Optional[str] = Field(None, max_length=255)
    hourly_rate: Optional[Decimal] = Field(None, gt=0)


class SupportAgentResponse(SupportAgentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
```

```