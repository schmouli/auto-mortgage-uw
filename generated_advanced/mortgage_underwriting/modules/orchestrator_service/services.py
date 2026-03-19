import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
from .models import MortgageApplication
from .schemas import ApplicationCreate
from .exceptions import MortgageCreationError
from mortgage_underwriting.common.config import Settings

logger = structlog.get_logger()

class MyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: ApplicationCreate) -> MortgageApplication:
        """Create a new mortgage application with comprehensive validation."""
        logger.info("creating_mortgage_application", client_id=payload.client_id)
        try:
            # Validate purchase price is reasonable (not negative or zero)
            if payload.purchase_price <= Decimal('0'):
                raise MortgageCreationError("Purchase price must be greater than zero")
            
            # Validate against maximum allowable purchase price from settings
            settings = Settings()
            if payload.purchase_price > settings.max_purchase_price:
                raise MortgageCreationError(f"Purchase price exceeds maximum allowed: {settings.max_purchase_price}")
            
            # Check if client exists (example validation)
            # This would normally query the Client model
            
            instance = MortgageApplication(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return instance
        except Exception as e:
            logger.error("mortgage_creation_failed", error=str(e))
            raise MortgageCreationError(f"Failed to create mortgage application: {str(e)}")