```python
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
from typing import List, Dict, Any

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.applications.models import Application
from mortgage_underwriting.modules.applications.schemas import ApplicationCreate, ApplicationUpdate


logger = structlog.get_logger()


def application_payload_dict(payload: ApplicationCreate) -> Dict[Any, Any]:  # FIXED: Added return type hint
    """Convert ApplicationCreate payload to dictionary for logging purposes."""
    # Never log sensitive fields like SIN, DOB, or detailed financial info
    return {
        "client_id": payload.client_id,
        "property_value": str(payload.property_value),
        "down_payment": str(payload.down_payment),
        "loan_amount": str(payload.loan_amount),
        "interest_rate": str(payload.interest_rate),
        "amortization_years": payload.amortization_years
    }


class ApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_application(self, payload: ApplicationCreate) -> Application:
        logger.info("creating_application", client_id=payload.client_id)
        try:
            app = Application(**payload.model_dump())
            self.db.add(app)
            await self.db.commit()
            await self.db.refresh(app)
            return app
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("integrity_error_creating_application", exc_info=e)
            raise AppException("CLIENT_NOT_FOUND", "Client does not exist.") from e

    async def get_applications(self, skip: int = 0, limit: int = 100) -> List[Application]:
        # FIXED: Implemented pagination with capped limit
        logger.info("listing_applications", skip=skip, limit=limit)
        stmt = select(Application).offset(skip).limit(min(limit, 100))  # Cap at 100 per page
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_application_by_id(self, application_id: int) -> Application:
        stmt = select(Application).where(Application.id == application_id)
        result = await self.db.execute(stmt)
        app = result.scalar_one_or_none()
        if not app:
            raise AppException("APPLICATION_NOT_FOUND", f"Application {application_id} not found.")
        return app

    async def update_application(self, application_id: int, payload: ApplicationUpdate) -> Application:
        app = await self.get_application_by_id(application_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(app, field, value)
        await self.db.commit()
        await self.db.refresh(app)
        return app
```