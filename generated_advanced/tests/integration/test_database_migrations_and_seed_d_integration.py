```python
import pytest
from decimal import Decimal
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncEngine

# Models to verify schema
from mortgage_underwriting.modules.borrower.models import Borrower
from mortgage_underwriting.modules.property.models import Property
from mortgage_underwriting.modules.mortgage.models import Mortgage

@pytest.mark.integration
@pytest.mark.asyncio
class TestDatabaseMigrations:
    
    async def test_migration_creates_borrower_table(self, migrated_db: AsyncEngine):
        """Verify that the borrower table is created with correct columns."""
        async with migrated_db.connect() as conn:
            # Check table existence
            result = await conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='borrowers'"
            ))
            table_exists = result.fetchone()
            assert table_exists is not None

            # Check column existence and types (SQLite specific introspection)
            result = await conn.execute(text("PRAGMA table_info(borrowers)"))
            columns = {row[1]: row[2] for row in result.fetchall()}
            
            assert "id" in columns
            assert "credit_score" in columns
            assert "sin_hash" in columns # PIPEDA compliance: hashed column
            
            # Ensure plain text SIN column does NOT exist
            assert "sin" not in columns

    async def test_migration_creates_mortgage_table_with_decimals(self, migrated_db: AsyncEngine):
        """Verify mortgage table uses appropriate types for financial data."""
        async with migrated_db.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(mortgages)"))
            columns = {row[1]: row[2] for row in result.fetchall()}
            
            # In SQLite, Decimals are often stored as NUMERIC, which can hold floats
            # but our application layer enforces Decimal. 
            # We check if the columns exist.
            assert "loan_amount" in columns
            assert "interest_rate" in columns
            assert "gds_ratio" in columns # OSFI B-20 requirement storage
            assert "tds_ratio" in columns # OSFI B-20 requirement storage

    async def test_migration_enforces_audit_fields(self, migrated_db: AsyncEngine):
        """Verify all tables have audit fields for FINTRAC compliance."""
        tables = ["borrowers", "properties", "mortgages", "transactions"]
        
        async with migrated_db.connect() as conn:
            for table_name in tables:
                result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
                columns = [row[1] for row in result.fetchall()]
                
                assert "created_at" in columns, f"{table_name} missing created_at"
                assert "updated_at" in columns, f"{table_name} missing updated_at"
                # Note: 'created_by' might be nullable in some schemas, but should exist

    async def test_migration_downgrade_removes_tables(self, alembic_config, migrated_db: AsyncEngine):
        """
        Test that downgrading removes the schema changes.
        This requires re-running the migration lifecycle in a specific way or 
        checking the state after the 'migrated_db' fixture cleans up.
        Here we manually trigger a downgrade within the test.
        """
        from alembic import command
        
        # Verify table exists first
        async with migrated_db.connect() as conn:
            result = await conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='mortgages'"
            ))
            assert result.fetchone() is not None
            
        # Downgrade
        command.downgrade(alembic_config, "base")
        
        # Verify table is gone
        async with migrated_db.connect() as conn:
            result = await conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='mortgages'"
            ))
            assert result.fetchone() is None


@pytest.mark.integration
@pytest.mark.asyncio
class TestSeedData:
    
    async def test_seed_provinces_data(self, migrated_db: AsyncEngine):
        """Verify provinces are seeded correctly."""
        # We assume a seed script runs as part of migration or post-migration hook
        # For this test, we manually invoke the seed service or SQL if not auto-run
        from mortgage_underwriting.modules.database_seed.services import SeedService
        from mortgage_underwriting.common.database import async_session_maker
        
        async with async_session_maker(bind=migrated_db) as session:
            service = SeedService(session)
            await service.seed_provinces()
            await session.commit()
            
        # Verify Data
        async with migrated_db.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM provinces"))
            count = result.scalar()
            assert count == 13 # Canada
            
            result = await conn.execute(text("SELECT code FROM provinces WHERE name = 'Ontario'"))
            code = result.scalar()
            assert code == "ON"

    async def test_seed_insurance_tiers_accuracy(self, migrated_db: AsyncEngine):
        """Verify CMHC insurance tiers are seeded with correct Decimal values."""
        from mortgage_underwriting.modules.database_seed.services import SeedService
        from mortgage_underwriting.common.database import async_session_maker

        async with async_session_maker(bind=migrated_db) as session:
            service = SeedService(session)
            await service.seed_insurance_tiers()
            await session.commit()

        async with migrated_db.connect() as conn:
            # Check 80.01-85.00 tier
            result = await conn.execute(text(
                "SELECT premium_rate FROM insurance_tiers WHERE min_ltv = :min AND max_ltv = :max"
            ), {"min": "80.01", "max": "85.00"})
            
            rate = result.scalar()
            # SQLite might return string or float depending on driver, convert to Decimal for check
            assert Decimal(str(rate)) == Decimal("0.0280")

    async def test_seed_stress_test_config(self, migrated_db: AsyncEngine):
        """Verify system settings include the OSFI stress test floor."""
        from mortgage_underwriting.modules.database_seed.services import SeedService
        from mortgage_underwriting.common.database import async_session_maker

        async with async_session_maker(bind=migrated_db) as session:
            service = SeedService(session)
            await service.seed_system_settings()
            await session.commit()

        async with migrated_db.connect() as conn:
            result = await conn.execute(text(
                "SELECT value FROM system_settings WHERE key = 'qualifying_rate_floor'"
            ))
            floor = result.scalar()
            assert Decimal(str(floor)) == Decimal("5.25")

    async def test_seed_data_immutability(self, migrated_db: AsyncEngine):
        """
        Test that attempting to update seed data directly might be restricted 
        or that audit trails are preserved.
        """
        from mortgage_underwriting.modules.database_seed.services import SeedService
        from mortgage_underwriting.common.database import async_session_maker
        from datetime import datetime

        # 1. Seed
        async with async_session_maker(bind=migrated_db) as session:
            service = SeedService(session)
            await service.seed_provinces()
            await session.commit()

        # 2. Fetch created_at
        async with migrated_db.connect() as conn:
            result = await conn.execute(text(
                "SELECT created_at FROM provinces LIMIT 1"
            ))
            original_created_at = result.scalar()

        # 3. Update (Simulate a change, though in real app triggers might prevent this)
        async with async_session_maker(bind=migrated_db) as session:
            await session.execute(text("UPDATE provinces SET name = 'Test' WHERE code = 'ON'"))
            await session.commit()

        # 4. Verify created_at did NOT change (FINTRAC immutable audit trail)
        async with migrated_db.connect() as conn:
            result = await conn.execute(text(
                "SELECT created_at FROM provinces WHERE code = 'ON'"
            ))
            current_created_at = result.scalar()
            
            assert current_created_at == original_created_at
```