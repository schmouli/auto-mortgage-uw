--- schemas.py ---
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User's email address")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128, description="Plain text password (will be hashed)")


class UserUpdate(BaseModel):
    is_active: bool | None = Field(None, description="Activate or deactivate user account")


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    user_id: int = Field(..., gt=0, description="ID of the associated user")
    token: str = Field(..., min_length=1, max_length=255, description="Authentication token string")
    expires_at: datetime = Field(..., description="Token expiration timestamp")


class SessionResponse(SessionCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True