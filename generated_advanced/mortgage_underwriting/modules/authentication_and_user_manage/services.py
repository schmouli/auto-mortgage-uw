from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import secrets
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import bcrypt
import jwt
import structlog
from mortgage_underwriting.common.config import settings
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.auth.models import User, RefreshToken
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserLogin, UserUpdate, TokenResponse

logger = structlog.get_logger()

class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register_user(self, payload: UserCreate) -> User:
        logger.info("registering_new_user", email=payload.email)

        # Validate password strength
        if not self._is_password_strong(payload.password):
            raise AppException(
                detail="Password must be at least 10 characters long and contain an uppercase letter, a number, and a special character.",
                error_code="WEAK_PASSWORD"
            )

        # Hash password
        hashed_pw = bcrypt.hashpw(payload.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Create user
        user = User(
            email=payload.email,
            hashed_password=hashed_pw,
            full_name=payload.full_name,
            phone=payload.phone,
            role="client",
            is_active=True
        )

        try:
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
        except IntegrityError as e:
            await self.db.rollback()
            if "email" in str(e.orig).lower():
                raise AppException(detail="Email already registered.", error_code="EMAIL_EXISTS")
            raise AppException(detail="Registration failed due to conflict.", error_code="REGISTRATION_CONFLICT")

        logger.info("user_registered_successfully", user_id=user.id)
        return user

    async def authenticate_user(self, credentials: UserLogin) -> Optional[User]:
        logger.info("authenticating_user", email=credentials.email)
        stmt = select(User).where(User.email == credentials.email, User.is_active.is_(True))
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not bcrypt.checkpw(credentials.password.encode('utf-8'), user.hashed_password.encode('utf-8')):
            logger.warning("authentication_failed", email=credentials.email)
            return None

        logger.info("user_authenticated", user_id=user.id)
        return user

    async def create_tokens(self, user: User) -> TokenResponse:
        logger.info("creating_jwt_tokens", user_id=user.id)

        # Generate access token
        access_payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES)
        }
        access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        # Generate refresh token
        refresh_token_str = secrets.token_urlsafe(64)
        refresh_expires_at = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
        
        refresh_token_obj = RefreshToken(
            user_id=user.id,
            token=refresh_token_str,
            expires_at=refresh_expires_at
        )
        
        self.db.add(refresh_token_obj)
        await self.db.commit()
        await self.db.refresh(refresh_token_obj)

        logger.info("jwt_tokens_created", user_id=user.id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer"
        )

    async def refresh_access_token(self, refresh_token_str: str) -> Optional[TokenResponse]:
        logger.info("refreshing_access_token")
        
        stmt = select(RefreshToken).where(
            RefreshToken.token == refresh_token_str,
            RefreshToken.expires_at > datetime.now(timezone.utc)
        )
        result = await self.db.execute(stmt)
        refresh_token_obj = result.scalar_one_or_none()

        if not refresh_token_obj:
            logger.warning("invalid_or_expired_refresh_token")
            return None

        user = refresh_token_obj.user
        return await self.create_tokens(user)

    async def logout(self, refresh_token_str: str) -> bool:
        logger.info("logging_out_user")
        stmt = select(RefreshToken).where(RefreshToken.token == refresh_token_str)
        result = await self.db.execute(stmt)
        refresh_token_obj = result.scalar_one_or_none()

        if not refresh_token_obj:
            logger.warning("refresh_token_not_found_for_logout")
            return False

        await self.db.delete(refresh_token_obj)
        await self.db.commit()
        logger.info("user_logged_out_successfully")
        return True

    def _is_password_strong(self, password: str) -> bool:
        if len(password) < 10:
            return False
        if not any(c.isupper() for c in password):
            return False
        if not any(c.isdigit() for c in password):
            return False
        if not any(not c.isalnum() for c in password):
            return False
        return True

class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_current_user(self, user_id: int) -> Optional[User]:
        logger.info("fetching_current_user", user_id=user_id)
        stmt = select(User).where(User.id == user_id, User.is_active.is_(True))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_current_user(self, user_id: int, payload: UserUpdate) -> User:
        logger.info("updating_current_user", user_id=user_id)
        stmt = select(User).where(User.id == user_id, User.is_active.is_(True))
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise AppException(detail="User not found.", error_code="USER_NOT_FOUND")

        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.phone is not None:
            user.phone = payload.phone

        await self.db.commit()
        await self.db.refresh(user)
        logger.info("user_updated_successfully", user_id=user.id)
        return user