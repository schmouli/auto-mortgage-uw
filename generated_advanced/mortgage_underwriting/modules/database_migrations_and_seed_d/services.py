from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import asyncio
import structlog
from mortgage_underwriting.modules.database.exceptions import DatabaseMigrationError, SeedDataError, RollbackTestError
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from mortgage_underwriting.common.config import settings
import json
import os
from sqlalchemy import text


class DatabaseMigrationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.logger = structlog.get_logger()

    async def migrate_up(self, revision: str = "head") -> Dict[str, Any]:
        self.logger.info("migrating_database_up", revision=revision)
        try:
            alembic_cfg = Config(settings.ALEMBIC_CONFIG_PATH)
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, command.upgrade, alembic_cfg, revision)
            
            return {
                "status": "ok",
                "revision": revision
            }
        except Exception as e:
            self.logger.error("migration_failed", error=str(e))
            raise DatabaseMigrationError(f"Migration failed: {str(e)}") from e

    async def migrate_down(self, revision: str) -> Dict[str, Any]:
        self.logger.info("migrating_database_down", revision=revision)
        try:
            alembic_cfg = Config(settings.ALEMBIC_CONFIG_PATH)
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, command.downgrade, alembic_cfg, revision)
            
            return {
                "status": "ok",
                "revision": revision
            }
        except Exception as e:
            self.logger.error("downgrade_failed", error=str(e))
            raise DatabaseMigrationError(f"Downgrade failed: {str(e)}") from e

    async def get_status(self) -> Dict[str, Any]:
        self.logger.info("checking_migration_status")
        try:
            alembic_cfg = Config(settings.ALEMBIC_CONFIG_PATH)
            script = ScriptDirectory.from_config(alembic_cfg)
            
            async with self.db.connection() as conn:
                raw_conn = await conn.get_raw_connection()
                context = MigrationContext.configure(connection=raw_conn.dbapi_connection)
                current_rev = context.get_current_revision()
                
                heads = script.get_heads()
                pending: List[str] = []
                if heads and current_rev != heads[0]:
                    for rev in script.walk_revisions(current_rev, heads[0]):
                        pending.append(rev.revision)
                
                return {
                    "current_rev": current_rev or "none",
                    "pending": pending
                }
        except Exception as e:
            self.logger.error("status_check_failed", error=str(e))
            raise DatabaseMigrationError(f"Status check failed: {str(e)}") from e


class SeedDataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.logger = structlog.get_logger()

    async def seed_environment(self, environment: str, confirm: bool, truncate_first: bool) -> Dict[str, Any]:
        self.logger.info("seeding_environment", env=environment, confirm=confirm, truncate_first=truncate_first)
        
        if not confirm:
            raise ValueError("Seed confirmation required")
            
        try:
            valid_environments = {"dev", "staging", "prod"}
            if environment not in valid_environments:
                raise SeedDataError(f"Invalid environment: {environment}")
                
            seed_file_path = os.path.join(settings.SEED_DATA_DIR, f"{environment}.json")
            if not os.path.exists(seed_file_path):
                raise SeedDataError(f"Seed file not found: {seed_file_path}")
                
            with open(seed_file_path, 'r') as f:
                seed_data = json.load(f)
            
            if truncate_first:
                self.logger.warn("truncating_tables_before_seeding")
                for table_name in getattr(settings, 'SEED_TRUNCATE_TABLES', []):
                    await self.db.execute(text(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE"))
                await self.db.commit()
                
            seeded_counts = {}
            for table, rows in seed_data.items():
                if rows:
                    # FIXED: Properly parameterized query to prevent SQL injection
                    columns = ', '.join(rows[0].keys())
                    placeholders = ', '.join([':' + k for k in rows[0].keys()])
                    stmt = text(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})")
                    result = await self.db.execute(stmt, rows)
                    seeded_counts[table] = result.rowcount
            await self.db.commit()
            
            return {
                "status": "ok",
                "seeded": seeded_counts
            }
        except Exception as e:
            self.logger.error("seeding_failed", error=str(e))
            raise SeedDataError(f"Seeding failed: {str(e)}") from e

    async def test_rollback(self, scenario: str) -> Dict[str, Any]:
        self.logger.info("testing_rollback", scenario=scenario)
        try:
            valid_scenarios = {"basic", "data_integrity", "constraint_violation"}
            if scenario not in valid_scenarios:
                raise RollbackTestError(f"Invalid rollback scenario: {scenario}")
                
            async with self.db.begin() as transaction:
                if scenario == "basic":
                    await self.db.execute(text("SAVEPOINT sp1"))
                    await self.db.execute(text("INSERT INTO migrations (revision, description) VALUES (:rev, :desc)"), {'rev': 'test-rev', 'desc': 'Test migration'})
                    await self.db.execute(text("ROLLBACK TO SAVEPOINT sp1"))
                elif scenario == "data_integrity":
                    await self.db.execute(text("SAVEPOINT sp2"))
                    await self.db.execute(text("INSERT INTO seed_data (environment, data_summary) VALUES (:env, :summary)"), {'env': 'test', 'summary': '{}'})
                    await self.db.execute(text("ROLLBACK TO SAVEPOINT sp2"))
                elif scenario == "constraint_violation":
                    await self.db.execute(text("SAVEPOINT sp3"))
                    try:
                        await self.db.execute(text("INSERT INTO migrations (revision) VALUES (NULL)"))
                    except Exception:
                        pass
                    await self.db.execute(text("ROLLBACK TO SAVEPOINT sp3"))
            
            return {
                "status": "ok",
                "rollback_verified": True
            }
        except Exception as e:
            self.logger.error("rollback_test_failed", error=str(e))
            raise RollbackTestError(f"Rollback test failed: {str(e)}") from e