from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.modules.frontend_react_ui.models import FrontendUIModule, UIComponent
from mortgage_underwriting.modules.frontend_react_ui.schemas import (
    FrontendUIModuleCreate,
    FrontendUIModuleUpdate,
    UIComponentCreate,
    UIComponentUpdate
)
from mortgage_underwriting.modules.frontend_react_ui.exceptions import FrontendUIError

logger = structlog.get_logger()


class FrontendUIService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_module(self, payload: FrontendUIModuleCreate) -> FrontendUIModule:
        logger.info("frontend_ui_module_create", name=payload.name)
        try:
            instance = FrontendUIModule(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return instance
        except Exception as e:
            await self.db.rollback()
            logger.error("frontend_ui_module_create_failed", error=str(e))
            raise FrontendUIError(f"Failed to create UI module: {str(e)}") from e

    async def get_module(self, module_id: int) -> Optional[FrontendUIModule]:
        logger.info("frontend_ui_module_fetch", module_id=module_id)
        stmt = select(FrontendUIModule).options(selectinload(FrontendUIModule.ui_components)).where(FrontendUIModule.id == module_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_modules(self, skip: int = 0, limit: int = 100) -> List[FrontendUIModule]:
        logger.info("frontend_ui_modules_list", skip=skip, limit=limit)
        stmt = select(FrontendUIModule).options(selectinload(FrontendUIModule.ui_components)).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_module(self, module_id: int, payload: FrontendUIModuleUpdate) -> Optional[FrontendUIModule]:
        logger.info("frontend_ui_module_update", module_id=module_id)
        instance = await self.get_module(module_id)
        if not instance:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(instance, key, value)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def delete_module(self, module_id: int) -> bool:
        logger.info("frontend_ui_module_delete", module_id=module_id)
        instance = await self.get_module(module_id)
        if not instance:
            return False
        await self.db.delete(instance)
        await self.db.commit()
        return True

    async def create_component(self, payload: UIComponentCreate) -> UIComponent:
        logger.info("ui_component_create", name=payload.name, module_id=payload.module_id)
        # Validate module exists before creating component
        module_exists = await self.get_module(payload.module_id)
        if not module_exists:
            raise FrontendUIError("Parent module does not exist")
        try:
            instance = UIComponent(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return instance
        except Exception as e:
            await self.db.rollback()
            logger.error("ui_component_create_failed", error=str(e))
            raise FrontendUIError(f"Failed to create UI component: {str(e)}") from e

    async def update_component(self, component_id: int, payload: UIComponentUpdate) -> Optional[UIComponent]:
        logger.info("ui_component_update", component_id=component_id)
        stmt = select(UIComponent).where(UIComponent.id == component_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(instance, key, value)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def delete_component(self, component_id: int) -> bool:
        logger.info("ui_component_delete", component_id=component_id)
        stmt = select(UIComponent).where(UIComponent.id == component_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            return False
        await self.db.delete(instance)
        await self.db.commit()
        return True