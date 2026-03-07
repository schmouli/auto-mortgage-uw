from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Tuple, Optional
import hashlib
import secrets

from passlib.context import CryptContext
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
import structlog

from mortgage_underwriting.common.config import settings
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.auth.models import User, RefreshToken
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
from mortgage_underwriting.modules.auth.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    RefreshTokenInvalidError,
    PasswordValidationError
)

logger = structlog.get_logger()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, payload: UserRegisterRequest) -> UserRegisterResponse:
        logger.info("auth.register_user.start", email=payload.email)
        
        # Validate password strength
        if not self._is_valid_password(payload.password):
            logger.warning("auth.register_user.password_invalid", email=payload.email)
            raise PasswordValidationError()
        
        # Check if user exists
        stmt = select(User).where(User.email == payload.email)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            logger.warning("auth.register_user.email_exists", email=payload.email)
            raise UserAlreadyExistsError()
        
        # Hash password
        hashed_pw = pwd_context.hash(payload.password)
        
        # Create user
        try:
            user = User(
                email=payload.email,
                hashed_password=hashed_pw,
                full_name=payload.full_name,
                phone=payload.phone,
                role=payload.role
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("auth.register_user.success", user_id=user.id)
            
            return UserRegisterResponse(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                phone=user.phone,
                role=user.role,
                created_at=user.created_at
            )
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("auth.register_user.integrity_error", error=str(e))
            raise UserAlreadyExistsError()

    async def authenticate_user(self, payload: UserLoginRequest) -> UserLoginResponse:
        logger.info("auth.authenticate_user.start", email=payload.email)
        
        # Get user
        stmt = select(User).where(User.email == payload.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not pwd_context.verify(payload.password, user.hashed_password):
            logger.warning("auth.authenticate_user.invalid_credentials", email=payload.email)
            raise InvalidCredentialsError()
        
        # Generate tokens
        access_token, access_exp = self._create_access_token(user.id)
        refresh_token_str, refresh_exp = self._create_refresh_token(user.id)
        
        # Save refresh token
        refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token_str,
            expires_at=refresh_exp
        )
        self.db.add(refresh_token)
        await self.db.commit()
        
        logger.info("auth.authenticate_user.success", user_id=user.id)
        
        return UserLoginResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    async def refresh_access_token(self, refresh_token_str: str) -> TokenRefreshResponse:
        logger.info("auth.refresh_token.start")
        
        # Find refresh token
        stmt = select(RefreshToken).where(
            RefreshToken.token == refresh_token_str,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc)
        )
        result = await self.db.execute(stmt)
        db_refresh_token = result.scalar_one_or_none()
        
        if not db_refresh_token:
            logger.warning("auth.refresh_token.invalid")
            raise RefreshTokenInvalidError()
        
        # Generate new access token
        access_token, _ = self._create_access_token(db_refresh_token.user_id)
        
        logger.info("auth.refresh_token.success", user_id=db_refresh_token.user_id)
        
        return TokenRefreshResponse(
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    async def logout_user(self, refresh_token_str: str) -> LogoutResponse:
        logger.info("auth.logout_user.start")
        
        # Revoke refresh token
        stmt = select(RefreshToken).where(RefreshToken.token == refresh_token_str)
        result = await self.db.execute(stmt)
        db_refresh_token = result.scalar_one_or_none()
        
        if db_refresh_token:
            db_refresh_token.is_revoked = True
            await self.db.commit()
            logger.info("auth.logout_user.success", token_id=db_refresh_token.id)
        else:
            logger.warning("auth.logout_user.token_not_found")
        
        return LogoutResponse()

    def get_current_user_from_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning("auth.get_current_user.invalid_token", error=str(e))
            raise InvalidCredentialsError()

    def _create_access_token(self, user_id: int) -> Tuple[str, datetime]:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {"sub": str(user_id), "exp": expire}
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt, expire

    def _create_refresh_token(self, user_id: int) -> Tuple[str, datetime]:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        token = secrets.token_urlsafe(64)
        return token, expire

    def _is_valid_password(self, password: str) -> bool:
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
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_profile(self, user_id: int) -> UserMeResponse:
        logger.info("user.get_profile.start", user_id=user_id)
        
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning("user.get_profile.not_found", user_id=user_id)
            raise InvalidCredentialsError()
        
        logger.info("user.get_profile.success", user_id=user.id)
        return UserMeResponse.model_validate(user)

    async def update_user_profile(self, user_id: int, payload: UserUpdateRequest) -> UserMeResponse:
        logger.info("user.update_profile.start", user_id=user_id)
        
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning("user.update_profile.not_found", user_id=user_id)
            raise InvalidCredentialsError()
        
        # Update fields if provided
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.phone is not None:
            user.phone = payload.phone
        
        await self.db.commit()  # FIXED: Added missing database commit
        await self.db.refresh(user)  # FIXED: Refreshed user after update
        
        logger.info("user.update_profile.success", user_id=user.id)
        return UserMeResponse.model_validate(user)