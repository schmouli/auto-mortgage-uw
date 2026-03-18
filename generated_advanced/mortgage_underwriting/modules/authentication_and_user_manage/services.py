from datetime import datetime, timedelta, timezone
from typing import Tuple
import hashlib

from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt
import structlog

from mortgage_underwriting.common.config import settings
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.auth.models import User, RefreshToken
from mortgage_underwriting.modules.auth.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    TokenRefreshRequest,
)
from mortgage_underwriting.modules.auth.exceptions import (
    UserAlreadyExistsException,
    InvalidCredentialsException,
    InvalidRefreshTokenException,
    UserNotFoundException
)

logger = structlog.get_logger()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register_user(self, user_data: UserCreate) -> UserResponse:
        # Check if email exists
        stmt = select(User).where(User.email == user_data.email)
        result = await self.db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            logger.info("registration_failed_email_exists", email=user_data.email)
            raise UserAlreadyExistsException()
        
        # Hash password
        hashed_pw = bcrypt.hashpw(user_data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create user
        db_user = User(
            email=user_data.email,
            hashed_password=hashed_pw,
            role=user_data.role,
            full_name=user_data.full_name,
            phone=user_data.phone
        )
        
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        
        logger.info("user_registered", user_id=db_user.id, email=db_user.email)
        
        return UserResponse.model_validate(db_user)

    async def authenticate_user(self, credentials: UserLogin) -> Tuple[User, str, str]:
        # Find user
        stmt = select(User).where(User.email == credentials.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not bcrypt.checkpw(credentials.password.encode('utf-8'), user.hashed_password.encode('utf-8')):
            logger.info("authentication_failed", email=credentials.email)
            raise InvalidCredentialsException()
        
        # Generate tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        access_token = self._create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role},
            expires_delta=access_token_expires
        )
        
        refresh_token = self._create_refresh_token(
            data={"sub": str(user.id)},
            expires_delta=refresh_token_expires
        )
        
        # Store refresh token
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + refresh_token_expires
        
        db_refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        
        self.db.add(db_refresh_token)
        await self.db.commit()
        
        logger.info("user_authenticated", user_id=user.id)
        
        return user, access_token, refresh_token

    async def refresh_access_token(self, token_request: TokenRefreshRequest) -> TokenResponse:
        try:
            payload = jwt.decode(
                token_request.refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            user_id: str = payload.get("sub")
            
            if user_id is None:
                logger.info("refresh_token_invalid_payload", reason="missing_sub_claim")
                raise InvalidRefreshTokenException()
                
        except JWTError as e:
            logger.info("refresh_token_decode_error", error=str(e))
            raise InvalidRefreshTokenException()
        
        # Verify token in DB and not expired/revoked
        token_hash = hashlib.sha256(token_request.refresh_token.encode()).hexdigest()
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.db.execute(stmt)
        db_token = result.scalar_one_or_none()
        
        if not db_token or db_token.is_revoked or db_token.expires_at < datetime.now(timezone.utc):
            logger.info("refresh_token_invalid", 
                       revoked=db_token.is_revoked if db_token else None,
                       expired=db_token.expires_at < datetime.now(timezone.utc) if db_token else None)
            raise InvalidRefreshTokenException()
        
        # Get user
        stmt = select(User).where(User.id == db_token.user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error("user_not_found_for_refresh_token", user_id=db_token.user_id)
            raise UserNotFoundException()
        
        # Generate new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access_token = self._create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role},
            expires_delta=access_token_expires
        )
        
        logger.info("access_token_refreshed", user_id=user.id)
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=token_request.refresh_token
        )

    async def logout_user(self, token: str) -> None:
        # Revoke refresh token
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.db.execute(stmt)
        db_token = result.scalar_one_or_none()
        
        if db_token:
            db_token.is_revoked = True
            await self.db.commit()
            logger.info("user_logged_out", user_id=db_token.user_id)

    def _create_access_token(self, data: dict, expires_delta: timedelta) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    def _create_refresh_token(self, data: dict, expires_delta: timedelta) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt