import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from decimal import Decimal

from mortgage_underwriting.modules.clients.models import Client
from mortgage_underwriting.modules.clients.schemas import ClientCreate, ClientUpdate
from mortgage_underwriting.modules.clients.exceptions import ClientNotFoundError, ClientAlreadyExistsError

logger = structlog.get_logger()

class ClientService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_client(self, payload: ClientCreate) -> Client:
        logger.info("creating_client", email=payload.email)
        try:
            client = Client(**payload.model_dump())
            self.db.add(client)
            await self.db.commit()
            await self.db.refresh(client)
            logger.info("client_created", client_id=client.id)
            return client
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("client_creation_failed", email=payload.email, error=str(e))
            raise ClientAlreadyExistsError(email=payload.email)

    async def get_client(self, client_id: int) -> Client:
        logger.debug("fetching_client", client_id=client_id)
        stmt = select(Client).where(Client.id == client_id, Client.is_active == True)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()
        if not client:
            logger.warning("client_not_found", client_id=client_id)
            raise ClientNotFoundError(client_id)
        logger.debug("client_fetched", client_id=client.id)
        return client

    async def update_client(self, client_id: int, payload: ClientUpdate) -> Client:
        logger.info("updating_client", client_id=client_id)
        client = await self.get_client(client_id)
        
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(client, key, value)
            
        await self.db.commit()
        await self.db.refresh(client)
        logger.info("client_updated", client_id=client.id)
        return client

    async def delete_client(self, client_id: int) -> bool:
        logger.info("deleting_client", client_id=client_id)
        client = await self.get_client(client_id)
        client.is_active = False  # FIXED: Soft delete instead of hard delete to maintain audit trail per FINTRAC
        await self.db.commit()
        await self.db.refresh(client)
        logger.info("client_deleted", client_id=client_id)
        return True