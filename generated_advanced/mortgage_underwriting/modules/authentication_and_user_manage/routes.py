"""
Authentication and User Management Module

This module provides secure authentication services including user registration,
login, token management, and user session handling. It implements industry-standard
security practices for credential storage, token generation, and session management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.authentication.services import AuthService
from mortgage_underwriting.modules.authentication.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserUpdateRequest,
    UserResponse,
    AuthTokensResponse,
    MessageResponse,
    TokenRefreshRequest
)
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.common.config import settings
from mortgage_underwriting.modules.authentication.dependencies import get_current_user_from_token, get_token_from_header

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegisterRequest,
    db: AsyncSession = Depends(get_async_session)
) -> UserResponse:
    """
    Register a new user account.
    
    Args:
        user_data: User registration information including email, password, full name and optional phone
        
    Returns:
        UserResponse: Registered user information (without password)
        
    Raises:
        HTTPException: If user already exists or validation fails
    """
    try:
        auth_service = AuthService(db)
        user = await auth_service.register_user(user_data)
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login", response_model=AuthTokensResponse)
async def login_user(
    credentials: UserLoginRequest,
    db: AsyncSession = Depends(get_async_session)
) -> AuthTokensResponse:
    """
    Authenticate user and generate access/refresh tokens.
    
    Args:
        credentials: User login credentials (email and password)
        
    Returns:
        AuthTokensResponse: Access and refresh tokens
        
    Raises:
        HTTPException: If credentials are invalid
    """
    try:
        auth_service = AuthService(db)
        user, access_token, refresh_token = await auth_service.authenticate_user(credentials)
        return AuthTokensResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )

@router.post("/refresh", response_model=AuthTokensResponse)
async def refresh_token(
    token_data: TokenRefreshRequest,
    db: AsyncSession = Depends(get_async_session)
) -> AuthTokensResponse:
    """
    Refresh access token using valid refresh token.
    
    Args:
        token_data: Contains the refresh token
        
    Returns:
        AuthTokensResponse: New access and refresh tokens
        
    Raises:
        HTTPException: If refresh token is invalid or expired
    """
    try:
        auth_service = AuthService(db)
        return await auth_service.refresh_access_token(token_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )

@router.post("/logout", response_model=MessageResponse)
async def logout_user(
    token: str = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_async_session)
) -> MessageResponse:
    """
    Invalidate refresh token to log out user.
    
    Args:
        token: Refresh token extracted from Authorization header
        
    Returns:
        MessageResponse: Confirmation of successful logout
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        auth_service = AuthService(db)
        success = await auth_service.logout_user(token)
        if success:
            return MessageResponse(message="Successfully logged out")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user_from_token)
) -> UserResponse:
    """
    Get current authenticated user's profile information.
    
    Args:
        current_user: Current authenticated user from token
        
    Returns:
        UserResponse: Current user's profile information
    """
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_async_session)
) -> UserResponse:
    """
    Update current authenticated user's profile information.
    
    Args:
        update_data: Fields to update in user profile
        current_user: Current authenticated user from token
        db: Database session
        
    Returns:
        UserResponse: Updated user profile information
    """
    auth_service = AuthService(db)
    return await auth_service.update_user(current_user.id, update_data)

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_async_session)
) -> List[UserResponse]:
    """
    Get paginated list of all users (admin only).
    
    Args:
        skip: Number of records to skip
        limit: Number of records to return (max 100)
        current_user: Current authenticated user from token
        db: Database session
        
    Returns:
        List[UserResponse]: List of users
    """
    # Check if user has admin privileges
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
        
    auth_service = AuthService(db)
    users = await auth_service.get_users(skip=skip, limit=limit)
    return users
```

```