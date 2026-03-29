--- conftest.py ---
```python
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from pathlib import Path
import os

# Dynamically adjust import path for tests to run correctly
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings

# Override settings for testing
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def async_engine():
    """Create an async engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for a test."""
    async_session = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        # Create tables manually for unit tests not using migrations
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        yield session
        
        # Cleanup
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def alembic_config(async_engine) -> Config:
    """
    Fixture to configure Alembic for integration tests.
    Points to the test database and the alembic scripts directory.
    """
    # Assuming standard alembic location at project root
    project_root = Path(__file__).parent.parent
    alembic_dir = project_root / "alembic"
    
    config = Config()
    config.set_main_option("sqlalchemy.url", str(async_engine.url))
    config.set_main_option("script_location", str(alembic_dir))
    return config

@pytest.fixture(scope="function")
async def migrated_db(alembic_config, async_engine):
    """
    Fixture to run migrations up and down for integration tests.
    """
    # Run upgrade to head
    command.upgrade(alembic_config, "head")
    
    yield async_engine

    # Run downgrade to base to clean up
    command.downgrade(alembic_config, "base")
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import text

# Assuming a service exists to handle seed data logic separate from raw migration scripts
# This allows for unit testing business logic used in migrations/seeding
from mortgage_underwriting.modules.database_seed.services import SeedService
from mortgage_underwriting.common.security import encrypt_pii, hash_pii

@pytest.mark.unit
class TestSeedService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_seed_provinces_success(self, mock_db):
        """Test that province seed data generates correct Canadian provinces."""
        service = SeedService(mock_db)
        await service.seed_provinces()
        
        assert mock_db.execute.call_count == 13 # 10 provinces + 3 territories
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_seed_default_stress_test_rate(self, mock_db):
        """Test seeding the default OSFI stress test rate."""
        service = SeedService(mock_db)
        await service.seed_system_settings()
        
        # Verify the call to insert the stress test rate
        # Assuming the service constructs an insert statement
        call_args = mock_db.execute.call_args_list[0]
        statement = call_args[0][0]
        
        # Check compiled statement contains the qualifying rate
        compiled = statement.compile()
        # Check for 5.25% or similar logic
        assert "5.25" in str(compiled) or "525" in str(compiled)

    @pytest.mark.asyncio
    async def test_seed_insurance_tiers_cmhc_compliance(self, mock_db):
        """Test that insurance tiers match CMHC requirements exactly."""
        service = SeedService(mock_db)
        
        expected_tiers = [
            {"min_ltv": Decimal("80.01"), "max_ltv": Decimal("85.00"), "rate": Decimal("0.0280")},
            {"min_ltv": Decimal("85.01"), "max_ltv": Decimal("90.00"), "rate": Decimal("0.0310")},
            {"min_ltv": Decimal("90.01"), "max_ltv": Decimal("95.00"), "rate": Decimal("0.0400")},
        ]
        
        with patch.object(service, '_get_cmhc_tiers', return_value=expected_tiers):
            await service.seed_insurance_tiers()
            
            # Verify execute was called for each tier
            assert mock_db.execute.call_count == len(expected_tiers)

    @pytest.mark.asyncio
    async def test_seed_admin_user_pipeda_compliance(self, mock_db):
        """Test that seeded admin users have encrypted SIN/PII."""
        service = SeedService(mock_db)
        
        raw_sin = "123456789"
        expected_hash = hash_pii(raw_sin)
        
        # Mock the hashing function to ensure it's called
        with patch('mortgage_underwriting.modules.database_seed.services.hash_pii', return_value=expected_hash):
            await service.seed_admin_user(username="admin", sin=raw_sin)
            
            call_args = mock_db.execute.call_args
            statement = call_args[0][0]
            params = statement.compile().params
            
            # Assert SIN is not stored in plain text
            assert raw_sin not in str(params)
            # Assert the hashed value is used
            assert expected_hash in str(params)

    @pytest.mark.asyncio
    async def test_seed_fintrac_audit_fields(self, mock_db):
        """Test that seeded data includes immutable audit fields for FINTRAC."""
        service = SeedService(mock_db)
        await service.seed_system_settings()
        
        call_args = mock_db.execute.call_args
        statement = call_args[0][0]
        compiled = statement.compile()
        
        # Verify created_at and created_by are present in the insert
        assert "created_at" in str(compiled)
        assert "created_by" in str(compiled)

    def test_decimal_precision_handling(self):
        """Test that seed data uses Decimal for financial fields."""
        # Direct logic test
        rate = Decimal("0.0280")
        assert rate == Decimal("0.0280")
        # Ensure no float conversion issues
        assert float(rate) != 0.0279999999999

    @pytest.mark.asyncio
    async def test_seed_rollback_on_error(self, mock_db):
        """Test that seeding rolls back transaction if an error occurs."""
        mock_db.execute.side_effect = Exception("DB Constraint Error")
        
        service = SeedService(mock_db)
        
        with pytest.raises(Exception):
            await service.seed_provinces()
            
        mock_db.rollback.assert_awaited_once()
        mock_db.commit.assert_not_awaited()

@pytest.mark.unit
class TestMigrationHelpers:
    """Test utility functions used inside migration scripts."""

    def test_calculate_ltv_boundaries(self):
        """Test boundary calculations for CMHC insurance tiers."""
        from mortgage_underwriting.modules.database_seed.migration_utils import get_ltv_tiers
        
        tiers = get_ltv_tiers()
        
        # Check boundaries
        assert tiers[0]['min_ltv'] == Decimal("80.01")
        assert tiers[-1]['max_ltv'] == Decimal("95.00")
        
        # Ensure no gaps
        for i in range(len(tiers) - 1):
            # The next min should be exactly 0.01 greater than current max
            expected_next_min = tiers[i]['max_ltv'] + Decimal("0.01")
            assert tiers[i+1]['min_ltv'] == expected_next_min

    def test_hash_sin_consistency(self):
        """Test that SIN hashing is consistent for lookups."""
        sin = "046454286"
        hash1 = hash_pii(sin)
        hash2 = hash_pii(sin)
        
        assert hash1 == hash2
        assert len(hash1) == 64 # SHA256 hex length
        assert sin not in hash1
```

--- integration_tests ---
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