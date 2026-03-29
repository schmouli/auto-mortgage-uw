from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.migrations.models import MigrationRecord
from mortgage_underwriting.modules.migrations.schemas import MigrationRecordCreate, MigrationRecordUpdate

logger = structlog.get_logger()


class MigrationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_migration(self, payload: MigrationRecordCreate) -> MigrationRecord:
        logger.info("recording_migration", version=payload.version)
        try:
            instance = MigrationRecord(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return instance
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("migration_record_failed", error=str(e))
            raise AppException("Migration recording failed") from e

    async def update_migration_status(self, version: str, payload: MigrationRecordUpdate) -> Optional[MigrationRecord]:
        logger.info("updating_migration_status", version=version)
        stmt = select(MigrationRecord).where(MigrationRecord.version == version)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            return None
        
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(instance, key, value)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def get_all_migrations(self) -> List[MigrationRecord]:
        logger.info("fetching_all_migrations")
        stmt = select(MigrationRecord).order_by(MigrationRecord.applied_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())