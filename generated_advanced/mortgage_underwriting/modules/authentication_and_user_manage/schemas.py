from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr, ConfigDict

# Request Schemas

class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=10, description="Min 10 chars, 1 uppercase, 1 number, 1 special char")
    full_name: str = Field(..., description="Full legal name")
    phone: str = Field(..., description="Phone number")
    role: str = Field(default="client", pattern="^(broker|client|admin|underwriter)$", description="User role")

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, description="Updated full name")
    phone: Optional[str] = Field(None, description="Updated phone number")

# Response Schemas

class UserRegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    user_id: int
    email: str
    full_name: str
    phone: str
    role: str
    created_at: datetime
    message: str = "Registration successful. Identity verification required for FINTRAC compliance."

class UserLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class UserMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    email: str
    full_name: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class LogoutResponse(BaseModel):
    detail: str = "Logout successful"