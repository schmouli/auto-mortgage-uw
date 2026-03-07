from datetime import datetime, timedelta, timezone
from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserUpdateRequest,
    UserRegisterResponse,
    UserLoginResponse,
    UserMeResponse,
    TokenRefreshResponse,
    LogoutResponse
)
from mortgage_underwriting.modules.auth.services import AuthService, UserService
from mortgage_underwriting.modules.auth.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    RefreshTokenInvalidError,
    PasswordValidationError
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
security = HTTPBearer()  # FIXED: Implemented actual JWT dependency

# Dependency
def get_auth_service(db: AsyncSession = Depends(get_async_session)) -> AuthService:
    return AuthService(db)

def get_user_service(db: AsyncSession = Depends(get_async_session)) -> UserService:
    return UserService(db)

# Helper to extract token from Authorization header
async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    token = credentials.credentials
    auth_service = AuthService(None)  # We'll only use the method that doesn't need db
    try:
        payload = auth_service.get_current_user_from_token(token)
        user_id = int(payload.get("sub"))
        return user_id
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")

# Auth Routes

@router.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> UserRegisterResponse:
    try:
        return await auth_service.register_user(payload)
    except PasswordValidationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Password does not meet complexity requirements", "error_code": "AUTH_001"}
        )
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Email already registered", "error_code": "AUTH_002"}
        )

@router.post("/login", response_model=UserLoginResponse)
async def login_user(
    payload: UserLoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> UserLoginResponse:
    try:
        return await auth_service.authenticate_user(payload)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid credentials", "error_code": "AUTH_005"}
        )

@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    refresh_token: str,
    auth_service: AuthService = Depends(get_auth_service)
) -> TokenRefreshResponse:
    try:
        return await auth_service.refresh_access_token(refresh_token)
    except RefreshTokenInvalidError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid refresh token", "error_code": "AUTH_006"}
        )

@router.post("/logout", response_model=LogoutResponse)
async def logout_user(
    refresh_token: str,
    auth_service: AuthService = Depends(get_auth_service)
) -> LogoutResponse:
    return await auth_service.logout_user(refresh_token)

# User Profile Routes

@router.get("/me", response_model=UserMeResponse)
async def get_my_profile(
    user_id: int = Depends(get_current_user_id),
    user_service: UserService = Depends(get_user_service)
) -> UserMeResponse:
    try:
        return await user_service.get_user_profile(user_id)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "User not found", "error_code": "AUTH_007"}
        )

@router.put("/me", response_model=UserMeResponse)
async def update_my_profile(
    payload: UserUpdateRequest,
    user_id: int = Depends(get_current_user_id),
    user_service: UserService = Depends(get_user_service)
) -> UserMeResponse:
    try:
        return await user_service.update_user_profile(user_id, payload)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "User not found", "error_code": "AUTH_007"}
        )