from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=10)
    full_name: str = Field(..., max_length=255)
    phone: str = Field(..., max_length=255)
    role: str = Field(default="client", pattern="^(broker|client|admin|underwriter)$")


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=255)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str
    role: str
    is_active: bool
    # FIXED: Removed extra fields per schema parity review (created_at removed)