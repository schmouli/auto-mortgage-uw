from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
import re


# Request Schemas
class UserRegisterRequest(BaseModel):
    """
    Schema for user registration requests.
    
    Validates and structures user registration data including email, password,
    full name, and optional phone number. Password must meet security requirements.
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ..., 
        min_length=10,
        description="Password must be at least 10 characters long and contain uppercase letter, number, and special character"
    )
    full_name: str = Field(..., description="User's full name")
    phone: Optional[str] = Field(None, description="User's phone number")

    @staticmethod
    def validate_password(v: str) -> str:
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[^A-Za-z0-9]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, description="User's full name")
    phone: Optional[str] = Field(None, description="User's phone number")


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token for obtaining new access token")


# Response Schemas
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    full_name: Optional[str]
    phone: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AuthTokensResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str
```

```