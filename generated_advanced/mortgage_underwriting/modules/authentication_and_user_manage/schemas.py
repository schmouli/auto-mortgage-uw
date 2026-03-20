from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    full_name: str = Field(..., min_length=1, max_length=255, description="User's full name")
    phone: Optional[str] = Field(None, max_length=20, description="User's phone number")


class UserRegister(UserBase):
    password: str = Field(..., min_length=10, description="Password (min 10 chars, uppercase, number, special char required)")
    role: str = Field(..., pattern="^(broker|client|admin|underwriter)$", description="User role")


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token string")


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT Access Token")
    refresh_token: str = Field(..., description="JWT Refresh Token")
    token_type: str = Field("bearer", description="Token type")


class TokenPayload(BaseModel):
    sub: int = Field(..., description="Subject (user ID)")
    exp: int = Field(..., description="Expiration timestamp")
    type: str = Field(..., description="Token type (access/refresh)")