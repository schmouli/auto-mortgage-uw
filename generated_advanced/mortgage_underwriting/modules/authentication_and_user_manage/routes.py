from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, Request

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    TokenResponse,
    TokenRefreshRequest,
    LogoutResponse,
)
from mortgage_underwriting.modules.auth.services import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> UserResponse:
    """Register a new user account."""
    auth_service = AuthService(db)
    return await auth_service.register_user(user_data)


@router.post("/login", response_model=TokenResponse)
async def login_user(
    credentials: UserLogin,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> TokenResponse:
    """Authenticate user and issue JWT tokens."""
    auth_service = AuthService(db)
    try:
        user, access_token, refresh_token = await auth_service.authenticate_user(credentials)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except Exception as e:
        raise HTTPException(
            status_code=getattr(e, 'status_code', status.HTTP_401_UNAUTHORIZED),
            detail={"detail": getattr(e, 'detail', 'Authentication failed'), "error_code": getattr(e, 'error_code', 'AUTH_007')}
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_request: TokenRefreshRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> TokenResponse:
    """Refresh access token using refresh token."""
    auth_service = AuthService(db)
    return await auth_service.refresh_access_token(token_request)


@router.post("/logout", response_model=LogoutResponse)
async def logout_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> LogoutResponse:
    """Logout user by revoking refresh token."""
    auth_service = AuthService(db)
    authorization: str = request.headers.get("Authorization")
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token")
        
    token = authorization.split(" ")[1]
    await auth_service.logout_user(token)
    return LogoutResponse()


@router.get("/users/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> UserResponse:
    """Get current authenticated user details."""
    # Extract user info from request (would come from middleware in real impl)
    # This is simplified for example purposes
    pass


@router.put("/users/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> UserResponse:
    """Update current authenticated user details."""
    # Extract user info from request (would come from middleware in real impl)
    # This is simplified for example purposes
    pass