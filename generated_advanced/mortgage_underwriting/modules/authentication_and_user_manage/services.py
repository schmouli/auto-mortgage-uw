--- services.py ---
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Tuple
from mortgage_underwriting.modules.auth.models import User, UserSession
from mortgage_underwriting.modules.auth.schemas import UserCreate, UserUpdate, SessionCreate
from mortgage_underwriting.modules.auth.exceptions import AuthException, UserNotFoundException

logger = structlog.get_logger()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, payload: UserCreate) -> User:
        """
        Creates a new user with hashed password.
        
        Args:
            payload (UserCreate): The user creation schema containing email and plain-text password.
        Returns:
            User: The newly created user object.
        Raises:
            IntegrityError: If email already exists in database.
        """
        logger.info("creating_new_user", email=payload.email)
        hashed_pw = pwd_context.hash(payload.password)
        user = User(email=payload.email, hashed_password=hashed_pw)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_user_with_sessions(self, user_id: int) -> User:
        """
        Retrieves a user along with their active sessions.
        
        Args:
            user_id (int): The ID of the user to retrieve.
        Returns:
            User: The requested user object with loaded sessions.
        Raises:
            UserNotFoundException: If no user is found with given ID.
        """
        stmt = select(User).options(selectinload(User.sessions)).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundException(f"User with ID {user_id} not found.")
        return user

    async def update_user(self, user_id: int, payload: UserUpdate) -> User:
        """
        Updates an existing user's information.
        
        Args:
            user_id (int): The ID of the user to update.
            payload (UserUpdate): Schema containing fields to update.
        Returns:
            User: Updated user object.
        """
        user = await self.get_user_with_sessions(user_id)
        logger.info("updating_user", user_id=user_id)
        for key, value in payload.dict(exclude_unset=True).items():
            setattr(user, key, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate_and_create_session(self, email: str, password: str) -> Tuple[User, UserSession]:
        """
        Authenticates a user and creates a new session upon successful authentication.
        
        Args:
            email (str): User's registered email address.
            password (str): Plain-text password for verification.
        Returns:
            tuple[User, UserSession]: Authenticated user and created session objects.
        Raises:
            AuthException: On invalid credentials.
        """
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not pwd_context.verify(password, user.hashed_password):
            raise AuthException("Invalid credentials provided.")
        
        session_payload = SessionCreate(
            user_id=user.id,
            token=str(uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        session = UserSession(**session_payload.dict())
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return user, session