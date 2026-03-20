from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Tuple, Optional
import hashlib

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.common.security import verify_password, hash_password, create_access_token, decode_jwt_token
from mortgage_underwriting.modules.auth.models import User, RefreshToken
from mortgage_underwriting.modules.auth.schemas import UserRegister, UserLogin, TokenRefreshRequest

logger = structlog.get_logger()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register_user(self, payload: UserRegister) -> User:
        logger.info("register_user", email=payload.email, role=payload.role)
        
        # Hash password
        hashed_pw = hash_password(payload.password)
        
        # Create user
        user = User(
            email=payload.email.lower(),
            hashed_password=hashed_pw,
            role=payload.role,
            full_name=payload.full_name,
            phone=payload.phone
        )
        
        try:
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("user_registered", user_id=user.id)
            return user
        except IntegrityError as e:
            await self.db.rollback()
            if 'email' in str(e.orig).lower():
                raise AppException("Email already registered", "EMAIL_EXISTS")
            raise AppException("Registration failed", "REGISTRATION_ERROR")

    async def authenticate_user(self, payload: UserLogin) -> Tuple[User, str, str]:
        logger.info("authenticate_user", email=payload.email)
        
        stmt = select(User).where(User.email == payload.email.lower(), User.is_active == True)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(payload.password, user.hashed_password):
            raise AppException("Invalid credentials", "INVALID_CREDENTIALS")
            
        # Generate tokens
        access_token = create_access_token({"sub": user.id, "type": "access"})
        refresh_token_str = self._generate_refresh_token()
        
        # Store refresh token
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=self._hash_token(refresh_token_str),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        self.db.add(refresh_token)
        await self.db.commit()
        
        logger.info("user_authenticated", user_id=user.id)
        return user, access_token, refresh_token_str

    async def refresh_access_token(self, payload: TokenRefreshRequest) -> Tuple[str, str]:
        logger.info("refresh_access_token")
        
        token_hash = self._hash_token(payload.refresh_token)
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.expires_at > datetime.now(timezone.utc),
            RefreshToken.revoked_at.is_(None)
        )
        result = await self.db.execute(stmt)
        db_refresh_token = result.scalar_one_or_none()
        
        if not db_refresh_token:
            raise AppException("Invalid refresh token", "INVALID_REFRESH_TOKEN")
            
        # Revoke current token
        db_refresh_token.revoked_at = datetime.now(timezone.utc)
        
        # Generate new tokens
        access_token = create_access_token({"sub": db_refresh_token.user_id, "type": "access"})
        new_refresh_token_str = self._generate_refresh_token()
        
        # Store new refresh token
        new_refresh_token = RefreshToken(
            user_id=db_refresh_token.user_id,
            token_hash=self._hash_token(new_refresh_token_str),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        self.db.add(new_refresh_token)
        await self.db.commit()
        
        logger.info("token_refreshed", user_id=db_refresh_token.user_id)
        return access_token, new_refresh_token_str

    async def logout_user(self, refresh_token_str: str) -> None:
        logger.info("logout_user")
        
        token_hash = self._hash_token(refresh_token_str)
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.expires_at > datetime.now(timezone.utc),
            RefreshToken.revoked_at.is_(None)
        )
        result = await self.db.execute(stmt)
        db_refresh_token = result.scalar_one_or_none()
        
        if db_refresh_token:
            db_refresh_token.revoked_at = datetime.now(timezone.utc)
            await self.db.commit()
            logger.info("user_logged_out", user_id=db_refresh_token.user_id)

    def _generate_refresh_token(self) -> str:
        import secrets
        return secrets.token_urlsafe(32)

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_current_user(self, user_id: int) -> User:
        logger.info("get_current_user", user_id=user_id)
        stmt = select(User).where(User.id == user_id, User.is_active == True)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise AppException("User not found", "USER_NOT_FOUND")
        return user

    async def update_current_user(self, user_id: int, payload: dict) -> User:
        logger.info("update_current_user", user_id=user_id)
        user = await self.get_current_user(user_id)
        
        for field, value in payload.items():
            if hasattr(user, field) and value is not None:
                setattr(user, field, value)
                
        await self.db.commit()
        await self.db.refresh(user)
        logger.info("user_updated", user_id=user.id)
        return user


async def get_current_user_from_token(credentials: dict, user_service: UserService) -> User:
    try:
        payload = decode_jwt_token(credentials['token'])
        user_id = payload.get('sub')
        if not user_id:
            raise AppException("Invalid token", "INVALID_TOKEN")
        return await user_service.get_current_user(int(user_id))
    except Exception as e:
        raise AppException("Could not validate credentials", "CREDENTIALS_INVALID") from e