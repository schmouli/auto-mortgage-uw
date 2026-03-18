from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    email: str = Field(..., max_length=255)
    role: str = Field(default="client", pattern="^(broker|client|admin|underwriter)$")
    full_name: str = Field(..., max_length=100)
    phone: str = Field(..., pattern=r"^\+[1-9]\d{1,14}$")  # E.164 format
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=10, pattern="^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]+$")


class UserLogin(BaseModel):
    email: str = Field(...)
    password: str = Field(...)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, pattern=r"^\+[1-9]\d{1,14}$")


class UserResponse(UserBase):
    id: int
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class LogoutResponse(BaseModel):
    message: str = "Successfully logged out"