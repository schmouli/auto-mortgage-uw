from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Tuple

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import jwt
import structlog

from mortgage_underwriting.common.config import settings
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.auth.models import User, RefreshToken
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin, UserUpdate

logger = structlog.get_logger()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, payload: UserCreate) -> User:
        """Register a new user with proper password hashing and validation."""
        logger.info("register_user", email=payload.email, role=payload.role)
        
        # Hash password
        hashed_pw: str = pwd_context.hash(payload.password)
        
        # Create user
        user = User(
            email=payload.email,
            hashed_password=hashed_pw,
            full_name=payload.full_name,
            phone=payload.phone,
            role=payload.role
        )
        
        try:
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("user_registered", user_id=user.id)
            return user
        except IntegrityError as e:
            await self.db.rollback()
            if "unique constraint" in str(e.orig).lower():
                raise AppException(detail="User with this email already exists", error_code="AUTH_003")
            raise AppException(detail="Registration failed", error_code="AUTH_001")

    async def authenticate_user(self, payload: UserLogin) -> Tuple[str, str, User]:
        """Authenticate user credentials and generate JWT tokens."""
        logger.info("authenticate_user", email=payload.email)
        
        stmt = select(User).where(User.email == payload.email, User.is_active.is_(True))
        result = await self.db.execute(stmt)
        user: Optional[User] = result.scalar_one_or_none()
        
        if not user or not pwd_context.verify(payload.password, user.hashed_password):
            raise AppException(detail="Invalid credentials", error_code="AUTH_004")
            
        # Generate tokens
        access_token: str = self._create_access_token(user.id)
        refresh_token: str = self._create_refresh_token(user.id)
        
        # Store refresh token
        refresh_obj = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        self.db.add(refresh_obj)
        await self.db.commit()
        
        logger.info("user_authenticated", user_id=user.id)
        return access_token, refresh_token, user

    async def refresh_access_token(self, refresh_token: str) -> Tuple[str, User]:
        """Refresh access token using valid refresh token."""
        logger.info("refresh_access_token")
        
        stmt = select(RefreshToken).join(User).where(
            RefreshToken.token == refresh_token,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.utcnow(),
            User.is_active.is_(True)
        )
        result = await self.db.execute(stmt)
        db_refresh: Optional[RefreshToken] = result.scalar_one_or_none()
        
        if not db_refresh:
            raise AppException(detail="Invalid refresh token", error_code="AUTH_005")
            
        # Revoke current refresh token
        db_refresh.revoked_at = datetime.utcnow()
        
        # Create new tokens
        access_token: str = self._create_access_token(db_refresh.user_id)
        new_refresh_token: str = self._create_refresh_token(db_refresh.user_id)
        
        # Store new refresh token
        new_refresh_obj = RefreshToken(
            user_id=db_refresh.user_id,
            token=new_refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        self.db.add(new_refresh_obj)
        self.db.add(db_refresh)  # Update revoked_at
        await self.db.commit()
        
        logger.info("token_refreshed", user_id=db_refresh.user_id)
        return access_token, db_refresh.user

    async def get_current_user(self, user_id: int) -> Optional[User]:
        """Get active user by ID."""
        stmt = select(User).where(User.id == user_id, User.is_active.is_(True))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_current_user(self, user_id: int, payload: UserUpdate) -> User:
        """Update current user profile information."""
        logger.info("update_current_user", user_id=user_id)
        
        stmt = select(User).where(User.id == user_id, User.is_active.is_(True))
        result = await self.db.execute(stmt)
        user: Optional[User] = result.scalar_one_or_none()
        
        if not user:
            raise AppException(detail="User not found", error_code="AUTH_006")
            
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.phone is not None:
            user.phone = payload.phone
            
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info("user_updated", user_id=user.id)
        return user

    def _create_access_token(self, user_id: int) -> str:
        """Create JWT access token for user."""
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {"exp": expire, "sub": str(user_id)}
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def _create_refresh_token(self, user_id: int) -> str:
        """Create JWT refresh token for user."""
        expire = datetime.utcnow() + timedelta(days=7)
        to_encode = {"exp": expire, "sub": str(user_id), "type": "refresh"}
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)