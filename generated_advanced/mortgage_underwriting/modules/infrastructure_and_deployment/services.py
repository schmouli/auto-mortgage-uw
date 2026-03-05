import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from .models import InfrastructureProvider, DeploymentEvent, DeploymentAudit
from .schemas import (
    InfrastructureProviderCreate,
    InfrastructureProviderUpdate,
    DeploymentEventCreate,
    DeploymentEventUpdate,
    DeploymentAuditCreate,
    DeploymentListQueryParams
)

logger = structlog.get_logger()


class InfrastructureService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_provider(self, payload: InfrastructureProviderCreate) -> InfrastructureProvider:
        """
        Create a new infrastructure provider.

        Args:
            payload: InfrastructureProviderCreate schema containing provider data

        Returns:
            Created InfrastructureProvider instance

        Raises:
            Exception: If database operation fails
        """
        logger.info("creating_infrastructure_provider", email=payload.email)
        provider = InfrastructureProvider(**payload.model_dump())
        self.db.add(provider)
        await self.db.commit()
        await self.db.refresh(provider)
        logger.info("infrastructure_provider_created", provider_id=provider.id)
        return provider

    async def get_provider(self, provider_id: int) -> Optional[InfrastructureProvider]:
        """
        Retrieve an infrastructure provider by ID.

        Args:
            provider_id: ID of the provider to retrieve

        Returns:
            InfrastructureProvider instance or None if not found
        """
        logger.info("fetching_infrastructure_provider", provider_id=provider_id)
        stmt = select(InfrastructureProvider).where(InfrastructureProvider.id == provider_id)
        result = await self.db.execute(stmt)
        provider = result.scalar_one_or_none()
        if not provider:
            logger.warning("infrastructure_provider_not_found", provider_id=provider_id)
        return provider

    async def update_provider(self, provider_id: int, payload: InfrastructureProviderUpdate) -> Optional[InfrastructureProvider]:
        """
        Update an infrastructure provider.

        Args:
            provider_id: ID of the provider to update
            payload: InfrastructureProviderUpdate schema containing update data

        Returns:
            Updated InfrastructureProvider instance or None if not found

        Raises:
            Exception: If database operation fails
        """
        logger.info("updating_infrastructure_provider", provider_id=provider_id)
        stmt = select(InfrastructureProvider).where(InfrastructureProvider.id == provider_id)
        result = await self.db.execute(stmt)
        provider = result.scalar_one_or_none()
        
        if not provider:
            logger.warning("infrastructure_provider_not_found_for_update", provider_id=provider_id)
            return None
            
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(provider, field, value)
            
        await self.db.commit()
        await self.db.refresh(provider)
        logger.info("infrastructure_provider_updated", provider_id=provider.id)
        return provider

    async def list_providers(self, skip: int = 0, limit: int = 100) -> List[InfrastructureProvider]:
        """
        List infrastructure providers with pagination.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of InfrastructureProvider instances
        """
        logger.info("listing_infrastructure_providers", skip=skip, limit=limit)
        stmt = select(InfrastructureProvider).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_deployment_event(self, payload: DeploymentEventCreate) -> DeploymentEvent:
        """
        Create a new deployment event.

        Args:
            payload: DeploymentEventCreate schema containing event data

        Returns:
            Created DeploymentEvent instance

        Raises:
            Exception: If database operation fails
        """
        logger.info("creating_deployment_event", provider_id=payload.provider_id, event_type=payload.event_type)
        event = DeploymentEvent(**payload.model_dump())
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        logger.info("deployment_event_created", event_id=event.id)
        return event

    async def get_deployment_event(self, event_id: int) -> Optional[DeploymentEvent]:
        """
        Retrieve a deployment event by ID with provider information.

        Args:
            event_id: ID of the event to retrieve

        Returns:
            DeploymentEvent instance with provider relationship loaded or None if not found
        """
        logger.info("fetching_deployment_event", event_id=event_id)
        stmt = select(DeploymentEvent).options(selectinload(DeploymentEvent.provider)).where(DeploymentEvent.id == event_id)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()
        if not event:
            logger.warning("deployment_event_not_found", event_id=event_id)
        return event

    async def list_deployment_events(self, query_params: DeploymentListQueryParams) -> List[DeploymentEvent]:
        """
        List deployment events with filtering and pagination.

        Args:
            query_params: DeploymentListQueryParams schema containing filters and pagination

        Returns:
            List of DeploymentEvent instances with provider relationships loaded
        """
        logger.info("listing_deployment_events", query_params=query_params.model_dump())
        stmt = select(DeploymentEvent).options(selectinload(DeploymentEvent.provider))
        
        if query_params.provider_id:
            stmt = stmt.where(DeploymentEvent.provider_id == query_params.provider_id)
            
        stmt = stmt.offset(query_params.skip).limit(query_params.limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_deployment_event(self, event_id: int, payload: DeploymentEventUpdate) -> Optional[DeploymentEvent]:
        """
        Update a deployment event.

        Args:
            event_id: ID of the event to update
            payload: DeploymentEventUpdate schema containing update data

        Returns:
            Updated DeploymentEvent instance or None if not found

        Raises:
            Exception: If database operation fails
        """
        logger.info("updating_deployment_event", event_id=event_id)
        stmt = select(DeploymentEvent).where(DeploymentEvent.id == event_id)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()
        
        if not event:
            logger.warning("deployment_event_not_found_for_update", event_id=event_id)
            return None
            
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(event, field, value)
            
        await self.db.commit()
        await self.db.refresh(event)
        logger.info("deployment_event_updated", event_id=event.id)
        return event

    async def create_deployment_audit(self, payload: DeploymentAuditCreate) -> DeploymentAudit:
        """
        Create a new deployment audit record.

        Args:
            payload: DeploymentAuditCreate schema containing audit data

        Returns:
            Created DeploymentAudit instance

        Raises:
            Exception: If database operation fails
        """
        logger.info("creating_deployment_audit", deployment_event_id=payload.deployment_event_id, action=payload.action)
        audit = DeploymentAudit(**payload.model_dump())
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(audit)
        logger.info("deployment_audit_created", audit_id=audit.id)
        return audit

    async def get_deployment_audit(self, audit_id: int) -> Optional[DeploymentAudit]:
        """
        Retrieve a deployment audit record by ID.

        Args:
            audit_id: ID of the audit record to retrieve

        Returns:
            DeploymentAudit instance or None if not found
        """
        logger.info("fetching_deployment_audit", audit_id=audit_id)
        stmt = select(DeploymentAudit).where(DeploymentAudit.id == audit_id)
        result = await self.db.execute(stmt)
        audit = result.scalar_one_or_none()
        if not audit:
            logger.warning("deployment_audit_not_found", audit_id=audit_id)
        return audit
```

```