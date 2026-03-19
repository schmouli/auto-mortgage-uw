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
        logger.info("creating_item", module="mortgage_application")
        try:
            # FIXED: Validate purchase_price is positive
            if payload.purchase_price <= 0:
                raise ValueError("Purchase price must be greater than zero.")
            instance = MortgageApplication(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return instance
        except Exception as e:
            logger.error("item_creation_failed", error=str(e))
            raise

    # FIXED: Added missing type hints on function signatures
    async def get_application_by_id(self, app_id: int) -> MortgageApplication | None:
        stmt = select(MortgageApplication).where(MortgageApplication.id == app_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()