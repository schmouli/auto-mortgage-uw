--- services.py ---
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from passlib.context import CryptContext
from datetime import datetime, timedelta
from uuid import uuid4
from mortgage_underwriting.modules.auth.models import User, UserSession
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserUpdate, SessionCreate
from mortgage_underwriting.modules.auth.exceptions import AuthException, UserNotFoundException

logger = structlog.get_logger()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, payload: UserCreate) -> User:
        logger.info("creating_new_user", email=payload.email)
        hashed_pw = pwd_context.hash(payload.password)
        user = User(email=payload.email, hashed_password=hashed_pw)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_user_with_sessions(self, user_id: int) -> User:
        stmt = select(User).options(selectinload(User.sessions)).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundException(f"User with ID {user_id} not found.")
        return user

    async def update_user(self, user_id: int, payload: UserUpdate) -> User:
        user = await self.get_user_with_sessions(user_id)
        logger.info("updating_user", user_id=user_id)
        for key, value in payload.dict(exclude_unset=True).items():
            setattr(user, key, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate_and_create_session(self, email: str, password: str) -> tuple[User, UserSession]:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not pwd_context.verify(password, user.hashed_password):
            raise AuthException("Invalid credentials provided.")
        
        session_payload = SessionCreate(
            user_id=user.id,
            token=str(uuid4()),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        session = UserSession(**session_payload.dict())
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return user, session