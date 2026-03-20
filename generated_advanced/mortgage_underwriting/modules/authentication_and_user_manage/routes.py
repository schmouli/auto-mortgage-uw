from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.auth.schemas import (
    UserRegister, UserLogin, UserResponse, 
    TokenResponse, TokenRefreshRequest, UserUpdate
)
from mortgage_underwriting.modules.auth.services import AuthService, UserService, get_current_user_from_token

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
security = HTTPBearer()

async def get_auth_service(db: AsyncSession = Depends(get_async_session)) -> AuthService:
    return AuthService(db)

async def get_user_service(db: AsyncSession = Depends(get_async_session)) -> UserService:
    return UserService(db)

async def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service)
) -> User:
    return await get_current_user_from_token({"token": credentials.credentials}, user_service)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegister,
    auth_service: AuthService = Depends(get_auth_service)
) -> UserResponse:
    try:
        user = await auth_service.register_user(payload)
        return UserResponse.model_validate(user)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"})

@router.post("/login", response_model=TokenResponse)
async def login_user(
    payload: UserLogin,
    auth_service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    try:
        user, access_token, refresh_token = await auth_service.authenticate_user(payload)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"})

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: TokenRefreshRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    try:
        access_token, refresh_token = await auth_service.refresh_access_token(payload)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"})

@router.post("/logout")
async def logout_user(
    payload: TokenRefreshRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> dict:
    try:
        await auth_service.logout_user(payload.refresh_token)
        return {"message": "Successfully logged out"}
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"})

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_user_dependency)
) -> UserResponse:
    try:
        return UserResponse.model_validate(current_user)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"})

@router.put("/me", response_model=UserResponse)
async def update_user_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user_dependency),
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    try:
        user = await user_service.update_current_user(current_user.id, payload.model_dump(exclude_unset=True))
        return UserResponse.model_validate(user)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"})