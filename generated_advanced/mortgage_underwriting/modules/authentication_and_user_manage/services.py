from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import bcrypt
import structlog
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.config import settings
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.modules.auth.exceptions import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from mortgage_underwriting.modules.auth.models import RefreshToken, User
from mortgage_underwriting.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UserResponse,
    UserUpdateRequest,
)

logger = structlog.get_logger()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, payload: RegisterRequest) -> UserResponse:
        logger.info("auth_register", email=payload.email)
        
        # Check if user already exists
        existing_user_result = await self.db.execute(select(User).where(User.email == payload.email))
        existing_user = existing_user_result.scalars().first()
        if existing_user:
            raise UserAlreadyExistsError()

        # Hash password
        hashed_pw = bcrypt.hashpw(payload.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Encrypt PII
        encrypted_phone = encrypt_pii(payload.phone)
        
        # Create user
        user = User(
            email=payload.email,
            hashed_password=hashed_pw,
            full_name=payload.full_name,
            phone=encrypted_phone,
            role=payload.role
        )
        
        self.db.add(user)
        try:
            await self.db.commit()
            await self.db.refresh(user)
        except IntegrityError:
            await self.db.rollback()
            raise UserAlreadyExistsError()
            
        logger.info("user_registered", user_id=user.id)
        return UserResponse.model_validate(user)

    async def login(self, payload: LoginRequest) -> LoginResponse:
        logger.info("auth_login", email=payload.email)
        
        result = await self.db.execute(select(User).where(User.email == payload.email))
        user = result.scalars().first()
        
        if not user or not bcrypt.checkpw(payload.password.encode('utf-8'), user.hashed_password.encode('utf-8')):
            raise InvalidCredentialsError()
            
        # Generate tokens
        access_expires = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        access_token = jwt.encode(
            {"sub": str(user.id), "exp": access_expires},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        refresh_token_str = jwt.encode(
            {"sub": str(user.id), "exp": refresh_expires},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        # Store refresh token
        refresh_token_obj = RefreshToken(
            user_id=user.id,
            token=refresh_token_str,
            expires_at=refresh_expires
        )
        
        self.db.add(refresh_token_obj)
        await self.db.commit()
        
        logger.info("user_logged_in", user_id=user.id)
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    async def refresh(self, payload: RefreshRequest) -> LoginResponse:
        logger.info("auth_refresh")
        
        try:
            payload_data = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = int(payload_data.get("sub"))
        except JWTError:
            raise InvalidRefreshTokenError()
            
        # Verify token exists and is not expired
        result = await self.db.execute(
            select(RefreshToken)
            .where(RefreshToken.token == payload.refresh_token)
            .where(RefreshToken.expires_at > datetime.now(timezone.utc))
        )
        refresh_token_obj = result.scalars().first()
        
        if not refresh_token_obj:
            raise InvalidRefreshTokenError()
            
        # Generate new access token
        access_expires = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = jwt.encode(
            {"sub": str(user_id), "exp": access_expires},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        logger.info("token_refreshed", user_id=user_id)
        return LoginResponse(
            access_token=access_token,
            refresh_token=payload.refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    async def logout(self, payload: LogoutRequest) -> None:
        logger.info("auth_logout")
        
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == payload.refresh_token)
        )
        refresh_token_obj = result.scalars().first()
        
        if not refresh_token_obj:
            raise InvalidRefreshTokenError()
            
        await self.db.delete(refresh_token_obj)
        await self.db.commit()
        
        logger.info("user_logged_out", token_id=refresh_token_obj.id)


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_current_user(self, user_id: int) -> UserResponse:
        logger.info("get_current_user", user_id=user_id)
        
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        
        if not user:
            raise UserNotFoundError()
            
        return UserResponse.model_validate(user)

    async def update_current_user(self, user_id: int, payload: UserUpdateRequest) -> UserResponse:
        logger.info("update_current_user", user_id=user_id)
        
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        
        if not user:
            raise UserNotFoundError()
            
        if payload.full_name is not None:
            user.full_name = payload.full_name
            
        if payload.phone is not None:
            user.phone = encrypt_pii(payload.phone)
            
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info("user_updated", user_id=user.id)
        return UserResponse.model_validate(user)