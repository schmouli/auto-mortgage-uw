from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, Request
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.auth.schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse, RefreshTokenRequest, UserUpdate
)
from mortgage_underwriting.modules.auth.services import AuthService, UserService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

def get_current_user(request: Request) -> dict:
    # In real implementation, extract user info from JWT token here
    # This is a placeholder - actual logic would decode the token
    user_info = getattr(request.state, "user", None)
    if not user_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user_info


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    auth_service = AuthService(db)
    try:
        user = await auth_service.register_user(payload)
        return user
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": e.detail, "error_code": e.error_code})


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid credentials", "error_code": "INVALID_CREDENTIALS"}
        )
    
    tokens = await auth_service.create_tokens(user)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    auth_service = AuthService(db)
    tokens = await auth_service.refresh_access_token(payload.refresh_token)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid or expired refresh token", "error_code": "INVALID_REFRESH_TOKEN"}
        )
    return tokens


@router.post("/logout")
async def logout(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    auth_service = AuthService(db)
    success = await auth_service.logout(payload.refresh_token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Logout failed", "error_code": "LOGOUT_FAILED"}
        )
    return {"message": "Successfully logged out"}


@router.get("/users/me", response_model=UserResponse)
async def get_me(
    user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    user_service = UserService(db)
    user = await user_service.get_current_user(int(user_info["sub"]))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "User not found", "error_code": "USER_NOT_FOUND"}
        )
    return user


@router.put("/users/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    user_info: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    user_service = UserService(db)
    user = await user_service.update_current_user(int(user_info["sub"]), payload)
    return user