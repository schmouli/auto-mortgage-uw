from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.exceptions import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from mortgage_underwriting.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UserResponse,
    UserUpdateRequest,
)
from mortgage_underwriting.modules.auth.services import AuthService, UserService

router = APIRouter(prefix="/api/v1", tags=["Authentication & User Management"])


def get_auth_service(db: AsyncSession = Depends(get_async_session)) -> AuthService:
    return AuthService(db)


def get_user_service(db: AsyncSession = Depends(get_async_session)) -> UserService:
    return UserService(db)


def get_current_user_id(request: Request) -> int:
    # This would extract user ID from JWT token in practice
    # Simplified for this example
    return 1


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service)
) -> UserResponse:
    try:
        return await service.register(payload)
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "User with this email already exists", "error_code": "AUTH_003"}
        )


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service)
) -> LoginResponse:
    try:
        return await service.login(payload)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid credentials", "error_code": "AUTH_001"}
        )


@router.post("/auth/refresh", response_model=LoginResponse)
async def refresh(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service)
) -> LoginResponse:
    try:
        return await service.refresh(payload)
    except InvalidRefreshTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid refresh token", "error_code": "AUTH_004"}
        )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    service: AuthService = Depends(get_auth_service)
) -> None:
    try:
        await service.logout(payload)
    except InvalidRefreshTokenError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Refresh token not found", "error_code": "AUTH_005"}
        )


@router.get("/users/me", response_model=UserResponse)
async def get_me(
    user_id: Annotated[int, Depends(get_current_user_id)],
    service: UserService = Depends(get_user_service)
) -> UserResponse:
    try:
        return await service.get_current_user(user_id)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "User not found", "error_code": "AUTH_001"}
        )


@router.put("/users/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdateRequest,
    user_id: Annotated[int, Depends(get_current_user_id)],
    service: UserService = Depends(get_user_service)
) -> UserResponse:
    try:
        return await service.update_current_user(user_id, payload)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "User not found", "error_code": "AUTH_001"}
        )