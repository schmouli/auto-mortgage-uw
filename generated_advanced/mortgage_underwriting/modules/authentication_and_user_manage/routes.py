from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status, Security

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse, RefreshTokenRequest, UserUpdate
)
from mortgage_underwriting.modules.auth.services import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


async def get_auth_service(db: AsyncSession = Depends(get_async_session)) -> AuthService:
    return AuthService(db)


def get_current_user_id() -> int:
    # TODO: Replace with real JWT token validation
    # This is just a placeholder - in reality you'd decode the JWT here
    return 1


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate,
    service: AuthService = Depends(get_auth_service)
) -> UserResponse:
    """Register a new user account."""
    try:
        return await service.register_user(payload)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"detail": e.detail, "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": "Registration failed", "error_code": "AUTH_001"})


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    try:
        access_token, refresh_token, user = await service.authenticate_user(payload)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user)
        )
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"detail": e.detail, "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": "Login failed", "error_code": "AUTH_007"})


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """Refresh access token using valid refresh token."""
    try:
        access_token, user = await service.refresh_access_token(payload.refresh_token)
        return TokenResponse(
            access_token=access_token,
            refresh_token=service._create_refresh_token(user.id),
            user=UserResponse.model_validate(user)
        )
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"detail": e.detail, "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": "Token refresh failed", "error_code": "AUTH_008"})


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Logout user (placeholder - actual revocation handled by refresh flow)."""
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    service: AuthService = Depends(get_auth_service),
    current_user_id: int = Depends(get_current_user_id)
) -> UserResponse:
    """Get current authenticated user profile."""
    user: Optional[User] = await service.get_current_user(current_user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": "User not found", "error_code": "AUTH_006"})
    return user


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    payload: UserUpdate,
    service: AuthService = Depends(get_auth_service),
    current_user_id: int = Depends(get_current_user_id)
) -> UserResponse:
    """Update current authenticated user profile."""
    try:
        return await service.update_current_user(current_user_id, payload)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": e.detail, "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": "Update failed", "error_code": "AUTH_009"})