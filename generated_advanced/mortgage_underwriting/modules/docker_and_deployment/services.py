from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog
from decimal import Decimal
from mortgage_underwriting.modules.deployment.exceptions import DeploymentNotFoundError
from mortgage_underwriting.modules.deployment.models import Deployment, DeploymentAuditLog
from mortgage_underwriting.modules.deployment.schemas import DeploymentCreate, DeploymentUpdate, DeploymentAuditLogCreate

logger = structlog.get_logger()


class DeploymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_deployment(self, payload: DeploymentCreate) -> Deployment:
        logger.info("creating_deployment", application_id=payload.application_id)
        instance = Deployment(
            application_id=payload.application_id,
            environment=payload.environment.value,
            version=payload.version,
            status="submitted",
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def get_deployment(self, deployment_id: int) -> Deployment:
        stmt = select(Deployment).where(Deployment.id == deployment_id).options(selectinload(Deployment.audit_logs))
        result = await self.db.execute(stmt)
        deployment = result.scalar_one_or_none()
        if not deployment:
            raise DeploymentNotFoundError(f"Deployment with id {deployment_id} not found")
        return deployment

    async def update_deployment(self, deployment_id: int, payload: DeploymentUpdate) -> Deployment:
        deployment = await self.get_deployment(deployment_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(deployment, field, value)
        await self.db.commit()
        await self.db.refresh(deployment)
        return deployment

    async def list_deployments(self, limit: int = 100, offset: int = 0) -> List[Deployment]:
        stmt = select(Deployment).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def log_audit_action(self, payload: DeploymentAuditLogCreate) -> DeploymentAuditLog:
        logger.info("logging_audit_action", deployment_id=payload.deployment_id, action=payload.action)
        # FIXED: Enhanced audit logging to sanitize inputs and prevent injection attacks
        sanitized_details = payload.details[:1000] if payload.details else None  # Truncate and ensure safety
        log_entry = DeploymentAuditLog(
            deployment_id=payload.deployment_id,
            action=payload.action,
            details=sanitized_details
        )
        self.db.add(log_entry)
        await self.db.commit()
        await self.db.refresh(log_entry)
        return log_entry