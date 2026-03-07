from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from . import schemas
from .models import UiComponent, UiPage, PageComponent

logger = structlog.get_logger()


class UiComponentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_component(self, payload: schemas.UiComponentCreate) -> UiComponent:
        logger.info("ui_component_create", name=payload.name)
        try:
            instance = UiComponent(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return instance
        except Exception as e:
            await self.db.rollback()
            logger.error("ui_component_create_failed", error=str(e))
            raise AppException(f"Failed to create UI component: {str(e)}") from e

    async def get_component(self, component_id: int) -> UiComponent:
        logger.debug("ui_component_get", component_id=component_id)
        stmt = select(UiComponent).where(UiComponent.id == component_id)
        result = await self.db.execute(stmt)
        component = result.scalar_one_or_none()
        if not component:
            raise NotFoundError(f"UI Component with ID {component_id} not found.")
        return component

    async def update_component(self, component_id: int, payload: schemas.UiComponentUpdate) -> UiComponent:
        logger.info("ui_component_update", component_id=component_id)
        component = await self.get_component(component_id)
        try:
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(component, key, value)
            await self.db.commit()
            await self.db.refresh(component)
            return component
        except Exception as e:
            await self.db.rollback()
            logger.error("ui_component_update_failed", component_id=component_id, error=str(e))
            raise AppException(f"Failed to update UI component: {str(e)}") from e

    async def delete_component(self, component_id: int) -> None:
        logger.info("ui_component_delete", component_id=component_id)
        component = await self.get_component(component_id)
        try:
            await self.db.delete(component)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error("ui_component_delete_failed", component_id=component_id, error=str(e))
            raise AppException(f"Failed to delete UI component: {str(e)}") from e


class UiPageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_page(self, payload: schemas.UiPageCreate) -> UiPage:
        logger.info("ui_page_create", route_path=payload.route_path)
        try:
            # Create the page first
            page_data = payload.model_dump(exclude={'components'})
            page_instance = UiPage(**page_data)
            self.db.add(page_instance)
            await self.db.flush()  # Get the page ID without committing
            
            # Then create associated components
            for comp_data in payload.components:
                comp_instance = PageComponent(
                    page_id=page_instance.id,
                    component_id=comp_data.component_id,
                    display_order=comp_data.display_order,
                    config_override_json=comp_data.config_override_json
                )
                self.db.add(comp_instance)
            
            await self.db.commit()
            await self.db.refresh(page_instance)
            return await self.get_page_with_components(page_instance.id)
        except Exception as e:
            await self.db.rollback()
            logger.error("ui_page_create_failed", route_path=payload.route_path, error=str(e))
            raise AppException(f"Failed to create UI page: {str(e)}") from e

    async def get_page_with_components(self, page_id: int) -> UiPage:
        logger.debug("ui_page_get_with_components", page_id=page_id)
        stmt = (
            select(UiPage)
            .options(selectinload(UiPage.components).selectinload(PageComponent.component))
            .where(UiPage.id == page_id)
        )
        result = await self.db.execute(stmt)
        page = result.scalar_one_or_none()
        if not page:
            raise NotFoundError(f"UI Page with ID {page_id} not found.")
        return page

    async def get_page_by_route(self, route_path: str) -> UiPage:
        logger.debug("ui_page_get_by_route", route_path=route_path)
        stmt = (
            select(UiPage)
            .options(selectinload(UiPage.components).selectinload(PageComponent.component))
            .where(UiPage.route_path == route_path)
        )
        result = await self.db.execute(stmt)
        page = result.scalar_one_or_none()
        if not page:
            raise NotFoundError(f"UI Page with route {route_path} not found.")
        return page

    async def list_pages(self, skip: int = 0, limit: int = 100) -> Tuple[List[UiPage], int]:
        logger.debug("ui_page_list", skip=skip, limit=limit)
        if limit > 100:
            limit = 100
        
        count_query = select(func.count(UiPage.id))
        total_count_result = await self.db.execute(count_query)
        total_count = total_count_result.scalar_one()
        
        stmt = (
            select(UiPage)
            .offset(skip)
            .limit(limit)
            .order_by(UiPage.id)
        )
        result = await self.db.execute(stmt)
        pages = list(result.scalars().all())
        
        return pages, total_count

    async def update_page(self, page_id: int, payload: schemas.UiPageUpdate) -> UiPage:
        logger.info("ui_page_update", page_id=page_id)
        page = await self.get_page_with_components(page_id)
        try:
            update_data = payload.model_dump(exclude_unset=True, exclude={'components'})
            for key, value in update_data.items():
                setattr(page, key, value)
            await self.db.commit()
            await self.db.refresh(page)
            return await self.get_page_with_components(page_id)
        except Exception as e:
            await self.db.rollback()
            logger.error("ui_page_update_failed", page_id=page_id, error=str(e))
            raise AppException(f"Failed to update UI page: {str(e)}") from e

    async def delete_page(self, page_id: int) -> None:
        logger.info("ui_page_delete", page_id=page_id)
        page = await self.get_page_with_components(page_id)
        try:
            await self.db.delete(page)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error("ui_page_delete_failed", page_id=page_id, error=str(e))
            raise AppException(f"Failed to delete UI page: {str(e)}") from e