--- conftest.py ---
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Numeric
from typing import AsyncGenerator

# Using an in-memory SQLite for integration tests to ensure speed and isolation
# In a real CI/CD, this might point to a test Postgres instance.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

class Base(DeclarativeBase):
    pass

# Minimal models representing seed data targets for testing purposes
# In a real scenario, these would be imported from the actual modules
class Province(Base):
    __tablename__ = "provinces"
    
    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

class CMHCTier(Base):
    __tablename__ = "cmhc_tiers"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    min_ltv: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    max_ltv: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    premium_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))

@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def cmhc_seed_data():
    """
    Fixture providing the regulatory compliant CMHC tiers.
    OSFI B-20 / CMHC Requirements:
    - 80.01-85% = 2.80%
    - 85.01-90% = 3.10%
    - 90.01-95% = 4.00%
    """
    return [
        {"min_ltv": Decimal("80.01"), "max_ltv": Decimal("85.00"), "premium_rate": Decimal("2.80")},
        {"min_ltv": Decimal("85.01"), "max_ltv": Decimal("90.00"), "premium_rate": Decimal("3.10")},
        {"min_ltv": Decimal("90.01"), "max_ltv": Decimal("95.00"), "premium_rate": Decimal("4.00")},
    ]

@pytest.fixture
def province_seed_data():
    return [
        {"code": "ON", "name": "Ontario"},
        {"code": "BC", "name": "British Columbia"},
        {"code": "QC", "name": "Quebec"},
    ]

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

# Assuming the module name is 'database_management' based on the request context
from mortgage_underwriting.modules.database_management.services import SeedService, MigrationService
from mortgage_underwriting.modules.database_management.exceptions import MigrationError, SeedDataError

@pytest.mark.unit
class TestMigrationService:
    
    @pytest.fixture
    def mock_alembic_config(self):
        return MagicMock()

    @pytest.fixture
    def migration_service(self, mock_alembic_config):
        return MigrationService(mock_alembic_config)

    @pytest.mark.asyncio
    async def test_upgrade_to_head_success(self, migration_service, mock_alembic_config):
        """Test successful migration execution to 'head'."""
        with patch('alembic.command.upgrade') as mock_upgrade:
            await migration_service.upgrade("head")
            mock_upgrade.assert_called_once_with(mock_alembic_config, "head")

    @pytest.mark.asyncio
    async def test_upgrade_to_specific_revision(self, migration_service, mock_alembic_config):
        """Test successful migration execution to a specific revision."""
        revision_id = "a1b2c3d4"
        with patch('alembic.command.upgrade') as mock_upgrade:
            await migration_service.upgrade(revision_id)
            mock_upgrade.assert_called_once_with(mock_alembic_config, revision_id)

    @pytest.mark.asyncio
    async def test_upgrade_failure_raises_exception(self, migration_service):
        """Test that a database error during migration raises a MigrationError."""
        with patch('alembic.command.upgrade', side_effect=Exception("DB Lock")):
            with pytest.raises(MigrationError) as exc_info:
                await migration_service.upgrade("head")
            assert "Migration failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_current_version(self, migration_service, mock_alembic_config):
        """Test retrieving the current database version."""
        mock_script = MagicMock()
        mock_script.get_current_revision.return_value = "rev123"
        
        with patch('alembic.script.ScriptDirectory.from_config', return_value=mock_script):
            with patch('alembic.runtime.migration.MigrationContext.configure') as mock_context:
                mock_migration_context = AsyncMock()
                mock_migration_context.get_current_revision.return_value = "rev123"
                mock_context.return_value = mock_migration_context
                
                version = await migration_service.get_current_version()
                assert version == "rev123"


@pytest.mark.unit
class TestSeedService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def seed_service(self):
        return SeedService()

    @pytest.mark.asyncio
    async def test_seed_cmhc_tiers_success(self, seed_service, mock_db):
        """Test seeding CMHC tiers with correct Decimal values (Regulatory Check)."""
        # Mock result to simulate empty table (no existing data)
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        await seed_service.seed_cmhc_tiers(mock_db)

        # Verify 3 tiers were added
        assert mock_db.add.call_count == 3
        assert mock_db.commit.call_count == 1
        
        # Verify Decimal precision in the calls (CMHC Requirement)
        # Extracting the objects passed to add
        added_objects = [call.args[0] for call in mock_db.add.call_args_list]
        premiums = [obj.premium_rate for obj in added_objects]
        
        assert Decimal("2.80") in premiums
        assert Decimal("3.10") in premiums
        assert Decimal("4.00") in premiums

    @pytest.mark.asyncio
    async def test_seed_cmhc_tiers_idempotent(self, seed_service, mock_db):
        """Test that seeding does not duplicate data if it already exists."""
        # Mock result to simulate data already exists
        mock_result = AsyncMock()
        mock_existing_tier = MagicMock()
        mock_existing_tier.min_ltv = Decimal("80.01")
        mock_result.scalars.return_value.all.return_value = [mock_existing_tier]
        mock_db.execute.return_value = mock_result

        await seed_service.seed_cmhc_tiers(mock_db)

        # Should not add anything if data exists
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_seed_provinces_success(self, seed_service, mock_db):
        """Test seeding standard Canadian provinces."""
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        await seed_service.seed_provinces(mock_db)

        # Verify standard provinces
        assert mock_db.add.call_count >= 13 # At least the main provinces/territories
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_seed_provinces_invalid_data(self, seed_service, mock_db):
        """Test handling of corrupted or missing seed data files."""
        # Simulate a scenario where the seed data loader returns invalid data
        with patch.object(seed_service, '_load_province_data', return_value=[{"code": None, "name": "Invalid"}]):
            with pytest.raises(SeedDataError) as exc_info:
                await seed_service.seed_provinces(mock_db)
            assert "Invalid province data" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_seed_osfi_config(self, seed_service, mock_db):
        """Test seeding OSFI B-20 default configuration (e.g., Qualifying Rate)."""
        mock_result = AsyncMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        await seed_service.seed_osfi_defaults(mock_db)

        # Verify config was added
        mock_db.add.assert_called_once()
        added_obj = mock_db.add.call_args.args[0]
        
        # Check for the mandatory 5.25% floor rate logic
        assert hasattr(added_obj, 'min_qualifying_rate')
        # Assuming the service sets the default floor
        assert added_obj.min_qualifying_rate == Decimal("5.25")

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from fastapi import FastAPI

from mortgage_underwriting.modules.database_management.routes import router
from mortgage_underwriting.modules.database_management.models import CMHCTier, Province, OSFIConfig

# Import the conftest models for the test DB setup
from conftest import Base, engine, db_session

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/system")
    return app

@pytest.mark.integration
@pytest.mark.asyncio
class TestDatabaseMigrationAndSeedAPI:

    async def test_seed_cmhc_endpoint_creates_records(self, app: FastAPI, db_session: AsyncSession):
        """
        Integration Test: Verify the seed endpoint correctly populates CMHC tiers
        and respects Decimal precision requirements.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act: Trigger seed
            response = await client.post("/api/v1/system/seed/cmhc")
            
            # Assert: Endpoint success
            assert response.status_code == 201
            json_resp = response.json()
            assert json_resp["message"] == "CMHC tiers seeded successfully"
            assert json_resp["count"] == 3

            # Assert: Database State
            result = await db_session.execute(select(CMHCTier))
            tiers = result.scalars().all()
            
            assert len(tiers) == 3
            
            # Verify Regulatory Values (CMHC)
            tier_80_85 = next((t for t in tiers if t.min_ltv == Decimal("80.01")), None)
            assert tier_80_85 is not None
            assert tier_80_85.premium_rate == Decimal("2.80")
            
            tier_90_95 = next((t for t in tiers if t.min_ltv == Decimal("90.01")), None)
            assert tier_90_95 is not None
            assert tier_90_95.premium_rate == Decimal("4.00")

    async def test_seed_provinces_endpoint(self, app: FastAPI, db_session: AsyncSession):
        """Integration Test: Verify province seeding."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/system/seed/provinces")
            
            assert response.status_code == 201
            
            result = await db_session.execute(select(Province))
            provinces = result.scalars().all()
            
            # Check specific provinces exist
            province_codes = [p.code for p in provinces]
            assert "ON" in province_codes
            assert "BC" in province_codes
            assert "QC" in province_codes

    async def test_seed_idempotency(self, app: FastAPI, db_session: AsyncSession):
        """
        Integration Test: Ensure running seed twice does not create duplicates.
        Important for maintaining data integrity in multi-stage deployments.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First seed
            await client.post("/api/v1/system/seed/provinces")
            
            # Second seed
            response = await client.post("/api/v1/system/seed/provinces")
            
            assert response.status_code == 200 # 200 OK implies no changes, 201 implies created
            # Or check message depending on implementation. Assuming 200 if exists.
            
            result = await db_session.execute(select(Province))
            count = len(result.scalars().all())
            
            # Assuming standard 13 provinces/territories
            assert count == 13 

    async def test_get_migration_status(self, app: FastAPI):
        """Integration Test: Check migration status endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/system/migrations/status")
            
            assert response.status_code == 200
            data = response.json()
            assert "current_revision" in data
            assert "is_head" in data

    async def test_seed_osfi_defaults(self, app: FastAPI, db_session: AsyncSession):
        """
        Integration Test: Verify OSFI B-20 defaults are seeded.
        Specifically the Qualifying Rate floor.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/system/seed/osfi")
            
            assert response.status_code == 201
            
            result = await db_session.execute(select(OSFIConfig))
            config = result.scalar_one_or_none()
            
            assert config is not None
            # Verify the mandatory stress test floor rate
            assert config.min_qualifying_rate == Decimal("5.25")
            # Verify GDS/TDS limits are present
            assert config.max_gds == Decimal("39.00")
            assert config.max_tds == Decimal("44.00")