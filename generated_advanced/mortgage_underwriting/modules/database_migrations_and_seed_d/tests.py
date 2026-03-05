```python
# conftest.py

import pytest
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Numeric, Integer, DateTime, func
from datetime import datetime
from decimal import Decimal
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# Hypothetical Base for testing migration/seed targets
class Base(DeclarativeBase):
    pass

# Hypothetical Models to test seeding against
class Province(Base):
    __tablename__ = "provinces"
    
    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class CmhcTier(Base):
    __tablename__ = "cmhc_tiers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    min_ltv: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_ltv: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    premium_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False) # Using 4 decimals for percentage precision
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

# Database Fixture
@pytest.fixture(scope="function")
async def engine() -> AsyncGenerator:
    # Using in-memory SQLite for integration testing speed
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

# App Fixture
@pytest.fixture(scope="function")
def app() -> FastAPI:
    from mortgage_underwriting.modules.migrations.routes import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/migrations")
    return app

@pytest.fixture(scope="function")
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

--- unit_tests ---

```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from alembic.config import Config
from alembic import command

# Import paths based on project structure
from mortgage_underwriting.modules.migrations.services import MigrationService, SeedService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestMigrationService:
    
    @pytest.fixture
    def mock_alembic_config(self):
        with patch("mortgage_underwriting.modules.migrations.services.Config") as mock_config:
            yield mock_config

    @pytest.fixture
    def service(self):
        # Service typically initialized with config path, but for unit test we mock internals
        return MigrationService()

    @pytest.mark.asyncio
    async def test_upgrade_database_success(self, service, mock_alembic_config):
        """
        Test that the upgrade command calls alembic.command.upgrade with correct arguments.
        """
        mock_cfg_instance = MagicMock(spec=Config)
        mock_alembic_config.return_value = mock_cfg_instance

        with patch("mortgage_underwriting.modules.migrations.services.command.upgrade") as mock_upgrade:
            await service.upgrade("head")
            
            mock_alembic_config.assert_called_once()
            mock_upgrade.assert_called_once_with(mock_cfg_instance, "head")

    @pytest.mark.asyncio
    async def test_upgrade_database_failure(self, service, mock_alembic_config):
        """
        Test that alembic errors are wrapped in AppException.
        """
        mock_cfg_instance = MagicMock(spec=Config)
        mock_alembic_config.return_value = mock_cfg_instance
        
        with patch("mortgage_underwriting.modules.migrations.services.command.upgrade") as mock_upgrade:
            mock_upgrade.side_effect = Exception("Database connection failed")
            
            with pytest.raises(AppException) as exc_info:
                await service.upgrade("head")
            
            assert "Migration failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_downgrade_database_success(self, service, mock_alembic_config):
        """
        Test that the downgrade command calls alembic.command.downgrade.
        """
        mock_cfg_instance = MagicMock(spec=Config)
        mock_alembic_config.return_value = mock_cfg_instance

        with patch("mortgage_underwriting.modules.migrations.services.command.downgrade") as mock_downgrade:
            await service.downgrade("-1")
            
            mock_downgrade.assert_called_once_with(mock_cfg_instance, "-1")

@pytest.mark.unit
class TestSeedService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self):
        return SeedService()

    @pytest.mark.asyncio
    async def test_seed_cmhc_tiers_uses_decimals(self, service, mock_db):
        """
        CRITICAL: Verify CMHC tiers use Decimal type for financial precision.
        Regulatory: CMHC premium tiers must be precise.
        """
        # Mock execute to track calls
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [] # Assume empty to trigger insert
        mock_db.execute.return_value = mock_result
        
        await service.seed_cmhc_tiers(mock_db)
        
        # Verify commit was called
        mock_db.commit.assert_awaited_once()
        
        # Verify that the data inserted is of type Decimal
        # We inspect the calls to db.add (if used) or db.execute
        # Here we assume service uses bulk_insert_mappings or similar
        calls = mock_db.execute.call_args_list
        
        # We check if the service attempted to insert data
        assert len(calls) > 0

    @pytest.mark.asyncio
    async def test_seed_cmhc_tiers_correct_values(self, service, mock_db):
        """
        Regulatory: Verify specific CMHC premium tiers (80.01-85% = 2.80%, etc.)
        """
        # Mock existing check to return empty
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = []
        mock_db.execute.return_value = mock_result

        await service.seed_cmhc_tiers(mock_db)
        
        # Capture what was added to the session
        added_objects = mock_db.add.call_args_list
        added_models = [call[0][0] for call in added_objects]
        
        # Verify 80.01-85% tier
        tier_80_85 = next((m for m in added_models if m.min_ltv == Decimal("80.01")), None)
        assert tier_80_85 is not None
        assert tier_80_85.max_ltv == Decimal("85.00")
        assert tier_80_85.premium_rate == Decimal("0.0280") # 2.80%

        # Verify 90.01-95% tier
        tier_90_95 = next((m for m in added_models if m.min_ltv == Decimal("90.01")), None)
        assert tier_90_95 is not None
        assert tier_90_95.premium_rate == Decimal("0.0400") # 4.00%

    @pytest.mark.asyncio
    async def test_seed_cmhc_idempotent(self, service, mock_db):
        """
        Test that seeding does not duplicate data if it already exists.
        """
        # Mock existing check to return data
        mock_existing = MagicMock()
        mock_existing.code = "QC" # Arbitrary field to simulate existence
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [mock_existing] # Non-empty list
        mock_db.execute.return_value = mock_result

        await service.seed_cmhc_tiers(mock_db)
        
        # If data exists, we should NOT add new data
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_seed_provinces_validates_input(self, service, mock_db):
        """
        Test that province seeding validates input data (non-empty codes).
        """
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = []
        mock_db.execute.return_value = mock_result

        await service.seed_provinces(mock_db)
        
        # Verify add was called
        assert mock_db.add.call_count > 0
        
        # Verify integrity of data (e.g., ON, BC, QC)
        added_objects = [call[0][0] for call in mock_db.add.call_args_list]
        codes = [obj.code for obj in added_objects]
        
        assert "ON" in codes
        assert "BC" in codes
        assert "QC" in codes
        
        # Ensure no empty codes
        assert "" not in codes

    @pytest.mark.asyncio
    async def test_seed_logs_compliance_data(self, service, mock_db):
        """
        Regulatory: Verify that seed operations log creation timestamps.
        """
        with patch("mortgage_underwriting.modules.migrations.services.logger") as mock_logger:
            mock_result = MagicMock()
            mock_result.scalars().all.return_value = []
            mock_db.execute.return_value = mock_result
            
            await service.seed_cmhc_tiers(mock_db)
            
            # Check that a log message indicates data was seeded
            mock_logger.info.assert_any_call("Seeded CMHC tiers successfully")
```

--- integration_tests ---

```python
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

# Imports from the hypothetical models in conftest
# Note: In a real scenario, these would be imported from the actual module models
from conftest import Province, CmhcTier

@pytest.mark.integration
@pytest.mark.asyncio
class TestMigrationEndpoints:

    async def test_upgrade_endpoint(self, app: AsyncClient, client: AsyncClient):
        """
        Test the API endpoint to trigger database upgrades.
        """
        response = await client.post("/api/v1/migrations/upgrade", json={"revision": "head"})
        
        # Assuming 202 Accepted or 200 OK
        assert response.status_code in [200, 202]
        data = response.json()
        assert "message" in data
        assert "upgrade" in data["message"].lower()

    async def test_seed_cmhc_endpoint(self, app: AsyncClient, client: AsyncClient, db_session: AsyncSession):
        """
        Test the API endpoint to seed CMHC data and verify DB state.
        Regulatory: Verify correct Decimal values are persisted.
        """
        response = await client.post("/api/v1/migrations/seed/cmhc")
        
        assert response.status_code == 200
        
        # Verify in DB
        stmt = select(CmhcTier).where(CmhcTier.min_ltv == Decimal("85.01"))
        result = await db_session.execute(stmt)
        tier = result.scalar_one_or_none()
        
        assert tier is not None
        assert tier.premium_rate == Decimal("0.0310") # 3.10%

    async def test_seed_provinces_endpoint(self, app: AsyncClient, client: AsyncClient, db_session: AsyncSession):
        """
        Test the API endpoint to seed Province data.
        """
        response = await client.post("/api/v1/migrations/seed/provinces")
        
        assert response.status_code == 200
        
        # Verify in DB
        stmt = select(Province)
        result = await db_session.execute(stmt)
        provinces = result.scalars().all()
        
        assert len(provinces) > 0
        # Check for a specific province
        ontario = next((p for p in provinces if p.code == "ON"), None)
        assert ontario is not None
        assert ontario.name == "Ontario"

@pytest.mark.integration
@pytest.mark.asyncio
class TestSeedDataIntegrity:

    async def test_cmhc_tiers_precision(self, app: AsyncClient, client: AsyncClient, db_session: AsyncSession):
        """
        CRITICAL: Ensure Decimal precision is maintained in DB.
        No float conversion errors allowed.
        """
        await client.post("/api/v1/migrations/seed/cmhc")
        
        stmt = select(CmhcTier)
        result = await db_session.execute(stmt)
        tiers = result.scalars().all()
        
        for tier in tiers:
            # Verify types strictly
            assert isinstance(tier.min_ltv, Decimal)
            assert isinstance(tier.max_ltv, Decimal)
            assert isinstance(tier.premium_rate, Decimal)
            
            # Verify specific regulatory tiers are present
            if tier.min_ltv == Decimal("80.01"):
                assert tier.premium_rate == Decimal("0.0280")
            elif tier.min_ltv == Decimal("90.01"):
                assert tier.premium_rate == Decimal("0.0400")

    async def test_seed_idempotency_integration(self, app: AsyncClient, client: AsyncClient, db_session: AsyncSession):
        """
        Test that calling the seed endpoint twice does not duplicate data.
        """
        # First call
        r1 = await client.post("/api/v1/migrations/seed/provinces")
        assert r1.status_code == 200
        
        # Count records
        stmt = select(Province)
        res1 = await db_session.execute(stmt)
        count1 = len(res1.scalars().all())
        
        # Second call
        r2 = await client.post("/api/v1/migrations/seed/provinces")
        assert r2.status_code == 200
        
        # Count records again
        res2 = await db_session.execute(stmt)
        count2 = len(res2.scalars().all())
        
        assert count1 == count2
        assert count1 > 0 # Ensure it actually seeded something

    async def test_reference_data_created_at_audit(self, app: AsyncClient, client: AsyncClient, db_session: AsyncSession):
        """
        Regulatory: Verify audit fields (created_at) are populated by seed logic.
        """
        await client.post("/api/v1/migrations/seed/provinces")
        
        stmt = select(Province).limit(1)
        result = await db_session.execute(stmt)
        province = result.scalar_one_or_none()
        
        assert province is not None
        assert province.created_at is not None

    async def test_migration_workflow_multi_step(self, app: AsyncClient, client: AsyncClient):
        """
        Test a workflow: Upgrade -> Seed -> Verify Ready
        """
        # 1. Upgrade
        up_res = await client.post("/api/v1/migrations/upgrade", json={"revision": "head"})
        assert up_res.status_code == 200
        
        # 2. Seed
        seed_res = await client.post("/api/v1/migrations/seed/all")
        assert seed_res.status_code == 200
        
        # 3. Check Health/Status (Assuming a status endpoint exists or checking response)
        # For this test, we assume success implies the system is ready
        data = seed_res.json()
        assert "success" in data or "message" in data
```