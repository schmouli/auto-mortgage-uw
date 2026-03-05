"""Client portal services for mortgage underwriting system."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from uuid import uuid4
from datetime import datetime, timedelta
from decimal import Decimal

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.client_portal.models import Client, ClientPortalSession
from mortgage_underwriting.modules.client_portal.schemas import ClientCreate, ClientUpdate, SessionCreate

logger = structlog.get_logger()


class ClientPortalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_client(self, payload: ClientCreate) -> Client:
        """
        Create a new client.
        
        Args:
            payload: Client creation data
            
        Returns:
            Created client object
            
        Raises:
            AppException: If client creation fails
        """
        logger.info("creating_client", email=payload.email)
        try:
            client = Client(**payload.model_dump())
            self.db.add(client)
            await self.db.commit()
            await self.db.refresh(client)
            return client
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("client_creation_failed", error=str(e))
            raise AppException("CLIENT_CREATION_FAILED", "Failed to create client") from e

    async def get_client(self, client_id: int) -> Optional[Client]:
        """
        Get a specific client by ID.
        
        Args:
            client_id: Client ID to fetch
            
        Returns:
            Client object or None if not found
        """
        logger.info("fetching_client", client_id=client_id)
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_clients(self, skip: int = 0, limit: int = 100) -> List[Client]:
        """
        Get a list of clients with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of client objects
        """
        logger.info("fetching_clients", skip=skip, limit=limit)
        stmt = select(Client).offset(skip).limit(min(limit, 100))  # FIXED: Applied pagination with offset/limit
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_client(self, client_id: int, payload: ClientUpdate) -> Optional[Client]:
        """
        Update an existing client.
        
        Args:
            client_id: Client ID to update
            payload: Client update data
            
        Returns:
            Updated client object or None if not found
        """
        logger.info("updating_client", client_id=client_id)
        client = await self.get_client(client_id)
        if not client:
            return None
        
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(client, field, value)
            
        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def create_session(self, payload: SessionCreate) -> ClientPortalSession:
        """
        Create a new client portal session.
        
        Args:
            payload: Session creation data
            
        Returns:
            Created session object
        """
        logger.info("creating_session", client_id=payload.client_id)
        session = ClientPortalSession(
            id=str(uuid4()),
            **payload.model_dump()
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_session(self, session_id: str) -> Optional[ClientPortalSession]:
        """
        Get a specific session by ID.
        
        Args:
            session_id: Session ID to fetch
            
        Returns:
            Session object or None if not found
        """
        logger.info("fetching_session", session_id=session_id)
        stmt = select(ClientPortalSession).where(ClientPortalSession.id == session_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_sessions(self, skip: int = 0, limit: int = 100) -> List[ClientPortalSession]:
        """
        Get a list of sessions with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of session objects
        """
        logger.info("fetching_sessions", skip=skip, limit=limit)
        stmt = select(ClientPortalSession).offset(skip).limit(min(limit, 100))  # FIXED: Applied pagination with offset/limit
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate a client portal session.
        
        Args:
            session_id: Session ID to invalidate
            
        Returns:
            True if session was invalidated, False if not found
        """
        logger.info("invalidating_session", session_id=session_id)
        session = await self.get_session(session_id)
        if not session:
            return False
            
        session.is_active = False
        await self.db.commit()
        return True
```

```