import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
from mortgage_underwriting.modules.mortgage.models import MortgageApplication
from mortgage_underwriting.modules.mortgage.schemas import ApplicationCreate

logger = structlog.get_logger()

class MyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: ApplicationCreate) -> MortgageApplication:
        try:
            # FIXED: Add explicit validation for purchase_price maximum limit
            if payload.purchase_price > Decimal('100000000'):
                raise ValueError("Purchase price cannot exceed $100,000,000")
            
            logger.info("creating_item", module="mortgage_application", client_id=payload.client_id)
            instance = MortgageApplication(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return instance
        except ValueError as e:
            logger.warning("validation_failed", error=str(e))
            raise
        except Exception as e:
            logger.error("create_failed", error=str(e))
            raise