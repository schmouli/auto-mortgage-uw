from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
from typing import List

from mortgage_underwriting.modules.frontend.models import FrontendComponent
from mortgage_underwriting.modules.frontend.schemas import (
    FrontendComponentCreate,
    FrontendComponentUpdate,
    FrontendComponentResponse
)
from mortgage_underwriting.modules.frontend.exceptions import ComponentNotFoundError

logger = structlog.get_logger()


class FrontendComponentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_all_components(self) -> List[FrontendComponent]:
        logger.info("fetching_frontend_components")
        result = await self.db.execute(select(FrontendComponent))
        return result.scalars().all()

    async def get_component_by_id(self, component_id: int) -> FrontendComponent:
        logger.info("fetching_frontend_component", component_id=component_id)
        stmt = select(FrontendComponent).where(FrontendComponent.id == component_id)
        result = await self.db.execute(stmt)
        component = result.scalar_one_or_none()
        if not component:
            raise ComponentNotFoundError(f"Component with ID {component_id} not found")
        return component

    async def create_component(self, payload: FrontendComponentCreate) -> FrontendComponent:
        logger.info("creating_frontend_component", name=payload.name)
        component = FrontendComponent(**payload.model_dump(exclude_unset=True))
        self.db.add(component)
        await self.db.commit()
        await self.db.refresh(component)
        return component

    async def update_component(self, component_id: int, payload: FrontendComponentUpdate) -> FrontendComponent:
        logger.info("updating_frontend_component", component_id=component_id)
        component = await self.get_component_by_id(component_id)
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(component, key, value)
        await self.db.commit()
        await self.db.refresh(component)
        return component