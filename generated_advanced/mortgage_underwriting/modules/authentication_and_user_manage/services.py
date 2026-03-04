```python
from datetime import datetime, timedelta
from typing import Optional, Tuple
import hashlib
import secrets
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.core.config import settings
from app.models.user import User, RefreshToken
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserUpdateRequest,
    AuthTokensResponse,
    TokenRefreshRequest
)
from app.exceptions.auth import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    UserInactiveError,
    RefreshTokenInvalidError
)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, user_data: UserRegisterRequest) -> User:
        # Check if user already exists
        result = await self.db.execute(select(User).where(User.email == user_data.email))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise UserAlreadyExistsError()

        # Hash password
        hashed_password = self._hash_password(user_data.password)

        # Create user
        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            role="client",  # Default role for new registrations
            full_name=user_data.full_name,
            phone=user_data.phone
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate_user(self, credentials: UserLoginRequest) -> Tuple[User, AuthTokensResponse]:
        # Get user by email
        result = await self.db.execute(select(User).where(User.email == credentials.email))
        user = result.scalar_one_or_none()
        
        if not user:
            raise InvalidCredentialsError()
            
        if not user.is_active:
            raise UserInactiveError()
            
        # Verify password
        if not self._verify_password(credentials.password, user.hashed_password):
            raise InvalidCredentialsError()
            
        # Generate tokens
        tokens = self._generate_tokens(user.id)
        
        # Store refresh token
        await self._store_refresh_token(user.id, tokens.refresh_token)
        
        return user, tokens

    async def refresh_access_token(self, data: TokenRefreshRequest) -> AuthTokensResponse:
        try:
            payload = jwt.decode(data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            exp = payload.get("exp")
            
            if not user_id or not exp:
                raise RefreshTokenInvalidError()
                
            if datetime.utcnow() > datetime.fromtimestamp(exp):
                raise RefreshTokenInvalidError()
        except jwt.PyJWTError:
            raise RefreshTokenInvalidError()

        # Verify refresh token exists in database and is not expired
        stmt = select(RefreshToken).where(
            and_(
                RefreshToken.token == self._hash_token(data.refresh_token),
                RefreshToken.expires_at > datetime.utcnow()
            )
        )
        result = await self.db.execute(stmt)
        db_refresh_token = result.scalar_one_or_none()
        
        if not db_refresh_token:
            raise RefreshTokenInvalidError()

        # Generate new tokens
        tokens = self._generate_tokens(user_id)
        
        # Store new refresh token
        await self._store_refresh_token(user_id, tokens.refresh_token)
        
        # Delete old refresh token
        await self.db.delete(db_refresh_token)
        await self.db.commit()
        
        return tokens

    async def get_current_user(self, user_id: int) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise InvalidCredentialsError()
        return user

    async def update_user_profile(self, user_id: int, update_data: UserUpdateRequest) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise InvalidCredentialsError()
            
        if update_data.full_name is not None:
            user.full_name = update_data.full_name
        if update_data.phone is not None:
            user.phone = update_data.phone
            
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def logout_user(self, refresh_token: str) -> None:
        hashed_token = self._hash_token(refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token == hashed_token)
        result = await self.db.execute(stmt)
        db_token = result.scalar_one_or_none()
        
        if db_token:
            await self.db.delete(db_token)
            await self.db.commit()

    def _hash_password(self, password: str) -> str:
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), settings.SALT.encode('utf-8'), 100000).hex()

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self._hash_password(plain_password) == hashed_password

    def _generate_tokens(self, user_id: int) -> AuthTokensResponse:
        access_expires = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        access_token = jwt.encode(
            {"sub": user_id, "exp": access_expires},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        refresh_token = secrets.token_urlsafe(64)
        
        return AuthTokensResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )

    async def _store_refresh_token(self, user_id: int, token: str) -> None:
        hashed_token = self._hash_token(token)
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        refresh_token_obj = RefreshToken(
            user_id=user_id,
            token=hashed_token,
            expires_at=expires_at
        )
        
        self.db.add(refresh_token_obj)
        await self.db.commit()

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode('utf-8')).hexdigest()
```