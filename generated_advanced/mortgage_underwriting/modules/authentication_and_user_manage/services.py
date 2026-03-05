import structlog
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
import hashlib
import secrets
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from mortgage_underwriting.common.config import settings
from mortgage_underwriting.modules.authentication.models import User, RefreshToken
from mortgage_underwriting.modules.authentication.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserUpdateRequest,
    AuthTokensResponse,
    TokenRefreshRequest
)
from mortgage_underwriting.modules.authentication.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    UserInactiveError,
    RefreshTokenInvalidError
)

logger = structlog.get_logger()

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, user_data: UserRegisterRequest) -> User:
        logger.info("registering_new_user", email=user_data.email)
        
        # Check if user already exists
        result = await self.db.execute(select(User).where(User.email == user_data.email))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            logger.warning("user_registration_failed", reason="email_already_exists", email=user_data.email)
            raise UserAlreadyExistsError()

        # Hash password with per-user salt
        salt = secrets.token_hex(32)
        hashed_password = self._hash_password(user_data.password, salt)

        # Create user
        user = User(
            email=user_data.email,
            hashed_password=f"{salt}:{hashed_password}",  # Store salt with hash
            role="client",  # Default role for new registrations
            full_name=user_data.full_name,
            phone=user_data.phone
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info("user_registered_successfully", user_id=user.id)
        return user

    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password with salt using SHA-256"""
        return hashlib.sha256((password + salt).encode()).hexdigest()

    async def authenticate_user(self, credentials: UserLoginRequest) -> Tuple[User, str, str]:
        logger.info("authenticating_user", email=credentials.email)
        
        # Find user by email
        result = await self.db.execute(select(User).where(User.email == credentials.email))
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning("authentication_failed", reason="user_not_found", email=credentials.email)
            raise InvalidCredentialsError()
            
        if not user.is_active:
            logger.warning("authentication_failed", reason="user_inactive", user_id=user.id)
            raise UserInactiveError()

        # Extract salt and hash from stored password
        try:
            salt, stored_hash = user.hashed_password.split(':')
        except ValueError as e:
            logger.error("authentication_failed", reason="invalid_password_format", user_id=user.id, exc_info=True)
            raise InvalidCredentialsError()
            
        # Verify password
        provided_hash = self._hash_password(credentials.password, salt)
        if provided_hash != stored_hash:
            logger.warning("authentication_failed", reason="invalid_password", user_id=user.id)
            raise InvalidCredentialsError()
            
        # Generate tokens
        access_token = self._create_access_token(user.id)
        refresh_token = self._create_refresh_token(user.id)
        
        # Store refresh token
        refresh_token_obj = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        self.db.add(refresh_token_obj)
        await self.db.commit()
        
        logger.info("user_authenticated_successfully", user_id=user.id)
        return user, access_token, refresh_token

    def _create_access_token(self, user_id: int) -> str:
        """
        Create JWT access token for authenticated user.
        
        Args:
            user_id: ID of the authenticated user
            
        Returns:
            str: Encoded JWT access token
        """
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            "type": "access"
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def _create_refresh_token(self, user_id: int) -> str:
        """Create refresh token for user session management."""
        return secrets.token_urlsafe(64)

    async def refresh_access_token(self, token_data: TokenRefreshRequest) -> AuthTokensResponse:
        logger.info("refreshing_access_token")
        
        # Find refresh token
        result = await self.db.execute(
            select(RefreshToken).where(
                and_(
                    RefreshToken.token == token_data.refresh_token,
                    RefreshToken.expires_at > datetime.utcnow()
                )
            )
        )
        refresh_token_obj = result.scalar_one_or_none()
        
        if not refresh_token_obj:
            logger.warning("token_refresh_failed", reason="invalid_refresh_token")
            raise RefreshTokenInvalidError()
            
        # Get user
        result = await self.db.execute(select(User).where(User.id == refresh_token_obj.user_id))
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            logger.warning("token_refresh_failed", reason="user_inactive_or_not_found")
            raise RefreshTokenInvalidError()
            
        # Generate new tokens
        access_token = self._create_access_token(user.id)
        new_refresh_token = self._create_refresh_token(user.id)
        
        # Update refresh token
        refresh_token_obj.token = new_refresh_token
        refresh_token_obj.expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        await self.db.commit()
        
        logger.info("access_token_refreshed_successfully", user_id=user.id)
        return AuthTokensResponse(
            access_token=access_token,
            refresh_token=new_refresh_token
        )

    async def get_user(self, user_id: int) -> User:
        """Get user by ID"""
        logger.info("fetching_user", user_id=user_id)
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            logger.warning("user_fetch_failed", reason="user_not_found", user_id=user_id)
            raise InvalidCredentialsError()
        return user

    async def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get paginated list of users"""
        logger.info("fetching_users_list", skip=skip, limit=min(limit, 100))
        # Ensure limit doesn't exceed maximum allowed value
        safe_limit = min(limit, 100)
        result = await self.db.execute(select(User).offset(skip).limit(safe_limit))
        return list(result.scalars().all())

    async def update_user(self, user_id: int, update_data: UserUpdateRequest) -> User:
        """Update user profile information"""
        logger.info("updating_user", user_id=user_id)
        user = await self.get_user(user_id)
        
        if update_data.full_name is not None:
            user.full_name = update_data.full_name
        if update_data.phone is not None:
            user.phone = update_data.phone
            
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info("user_updated_successfully", user_id=user.id)
        return user

    async def logout_user(self, refresh_token: str) -> bool:
        """Invalidate refresh token to log out user"""
        logger.info("logging_out_user")
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        token_obj = result.scalar_one_or_none()
        
        if not token_obj:
            logger.warning("logout_failed", reason="token_not_found")
            return False
            
        await self.db.delete(token_obj)
        await self.db.commit()
        logger.info("user_logged_out_successfully")
        return True
```