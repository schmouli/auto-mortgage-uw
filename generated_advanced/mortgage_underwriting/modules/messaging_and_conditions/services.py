import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import MortgageApplication
from .schemas import ApplicationCreate
from .exceptions import MortgageApplicationError

logger = structlog.get_logger()

class MyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: ApplicationCreate) -> MortgageApplication:
        logger.info("creating_mortgage_application", module="mortgage_application")
        try:
            instance = MortgageApplication(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return instance
        except Exception as e:
            logger.error("create_mortgage_failed", error=str(e))
            # FIXED: Replaced bare except with domain-specific exception
            raise MortgageApplicationError(f"Failed to create mortgage application: {str(e)}") from e