```python
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.api.deps import get_db, get_current_user
from app.services.auth import AuthService
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserUpdateRequest,
    UserResponse,
    AuthTokensResponse,
    MessageResponse,
    TokenRefreshRequest
)
from app.models.user import User
from app.core.config import settings
from app.exceptions.auth import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    UserInactiveError,
    RefreshTokenInvalidError
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
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
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

@router.post("/login", response_model=AuthTokensResponse)
async def login_user(
    credentials: UserLoginRequest,
    db: AsyncSession = Depends(get_db)
) -> AuthTokensResponse:
    """
    Authenticate user and provide access/refresh tokens.
    
    Args:
        credentials: User login credentials (email and password)
        
    Returns:
        AuthTokensResponse: Access and refresh tokens for authentication
        
    Raises:
        HTTPException: If credentials are invalid or user is inactive
    """
    try:
        auth_service = AuthService(db)
        user, tokens = await auth_service.authenticate_user(credentials)
        return tokens
    except (InvalidCredentialsError, UserInactiveError) as e:
        if isinstance(e, UserInactiveError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

@router.post("/refresh", response_model=AuthTokensResponse)
async def refresh_token(
    data: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db)
) -> AuthTokensResponse:
    """
    Obtain new access token using refresh token.
    
    Args:
        data: Contains the refresh token
        
    Returns:
        AuthTokensResponse: New access and refresh tokens
        
    Raises:
        HTTPException: If refresh token is invalid or expired
    """
    try:
        auth_service = AuthService(db)
        tokens = await auth_service.refresh_access_token(data)
        return tokens
    except RefreshTokenInvalidError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

@router.post("/logout", response_model=MessageResponse)
async def logout_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Invalidate refresh token to log out user.
    
    Args:
        request: HTTP request containing Authorization header
        
    Returns:
        MessageResponse: Success message
        
    Raises:
        HTTPException: If token extraction fails
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization header"
        )
        
    refresh_token = auth_header.split(" ")[1]
    auth_service = AuthService(db)
    await auth_service.logout_user(refresh_token)
    
    return MessageResponse(message="Successfully logged out")

# User profile endpoints
user_router = APIRouter(prefix="/users", tags=["User Management"])

@user_router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """
    Get current authenticated user's profile information.
    
    Returns:
        UserResponse: Current user's information (without password)
    """
    return current_user

@user_router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Update current authenticated user's profile information.
    
    Args:
        update_data: Fields to update (full_name, phone)
        
    Returns:
        UserResponse: Updated user information
    """
    auth_service = AuthService(db)
    updated_user = await auth_service.update_user_profile(current_user.id, update_data)
    return updated_user
```