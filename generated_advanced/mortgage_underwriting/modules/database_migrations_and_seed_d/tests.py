--- conftest.py ---
```python
import pytest
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool
from decimal import Decimal

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.main import app
from mortgage_underwriting.modules.db_admin.models import CMHCTier, Province
from mortgage_underwriting.common.config import settings

# Use an in-memory SQLite database for integration tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def engine() -> AsyncGenerator:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a test client that overrides the database dependency.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture
def mock_alembic_config():
    """Mock Alembic Config object for migration tests."""
    from unittest.mock import MagicMock
    config = MagicMock()
    config.set_main_option = MagicMock()
    config.get_section_option = MagicMock(return_value="mock")
    return config

@pytest.fixture
def sample_cmhc_payload():
    return [
        {"min_ltv": Decimal("80.01"), "max_ltv": Decimal("85.00"), "premium_rate": Decimal("0.0280")},
        {"min_ltv": Decimal("85.01"), "max_ltv": Decimal("90.00"), "premium_rate": Decimal("0.0310")},
        {"min_ltv": Decimal("90.01"), "max_ltv": Decimal("95.00"), "premium_rate": Decimal("0.0400")},
    ]

@pytest.fixture
def sample_provinces():
    return [
        {"code": "ON", "name": "Ontario", "tax_rate": Decimal("0.13")},
        {"code": "BC", "name": "British Columbia", "tax_rate": Decimal("0.12")},
        {"code": "AB", "name": "Alberta", "tax_rate": Decimal("0.05")},
    ]
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from alembic.config import Config
from alembic.script import ScriptDirectory

from mortgage_underwriting.modules.db_admin.services import (
    SeedService, 
    MigrationService,
)
from mortgage_underwriting.modules.db_admin.models import CMHCTier, Province
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestMigrationService:
    
    @pytest.fixture
    def mock_config(self):
        return MagicMock(spec=Config)

    @pytest.mark.asyncio
    async def test_get_current_revision_success(self, mock_config):
        """Test retrieving current revision from Alembic."""
        mock_script = MagicMock(spec=ScriptDirectory)
        mock_script.get_current_revision.return_value = "abc123"
        
        with patch("alembic.script.ScriptDirectory.from_config", return_value=mock_script):
            service = MigrationService(mock_config)
            revision = await service.get_current_revision()
            
            assert revision == "abc123"
            mock_script.get_current_revision.assert_called_once()

    @pytest.mark.asyncio
    async def test_upgrade_database_success(self, mock_config):
        """Test successful database upgrade command."""
        with patch("alembic.command.upgrade") as mock_upgrade:
            service = MigrationService(mock_config)
            await service.upgrade("head")
            
            mock_upgrade.assert_called_once_with(mock_config, "head")

    @pytest.mark.asyncio
    async def test_upgrade_database_failure(self, mock_config):
        """Test handling of Alembic upgrade failure."""
        with patch("alembic.command.upgrade", side_effect=Exception("Migration failed")):
            service = MigrationService(mock_config)
            
            with pytest.raises(AppException) as exc_info:
                await service.upgrade("head")
            
            assert "Migration failed" in str(exc_info.value.detail)

@pytest.mark.unit
class TestSeedService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_seed_provinces_empty_db(self, mock_db):
        """Test seeding provinces when database is empty."""
        # Mock result proxy for execute check
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 0
        mock_db.execute.return_value = mock_result

        service = SeedService(mock_db)
        data = [
            {"code": "ON", "name": "Ontario", "tax_rate": Decimal("0.13")},
            {"code": "QC", "name": "Quebec", "tax_rate": Decimal("0.14975")}
        ]
        
        await service.seed_provinces(data)
        
        # Verify check was called
        assert mock_db.execute.call_count >= 1
        # Verify all provinces added
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_seed_provinces_already_seeded(self, mock_db):
        """Test that seeding is idempotent and skips existing data."""
        # Mock result proxy indicating data exists
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 10 # > 0
        mock_db.execute.return_value = mock_result

        service = SeedService(mock_db)
        data = [{"code": "ON", "name": "Ontario", "tax_rate": Decimal("0.13")}]
        
        await service.seed_provinces(data)
        
        # Should not add anything
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_seed_cmhc_tiers_compliance(self, mock_db):
        """
        Test seeding CMHC tiers with strict Decimal precision and regulatory ranges.
        Ensures OSFI/CMHC compliance: 80.01-85% = 2.80%, etc.
        """
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 0
        mock_db.execute.return_value = mock_result

        service = SeedService(mock_db)
        
        # Regulatory data from requirements
        tiers = [
            {"min_ltv": Decimal("80.01"), "max_ltv": Decimal("85.00"), "premium_rate": Decimal("0.0280")},
            {"min_ltv": Decimal("85.01"), "max_ltv": Decimal("90.00"), "premium_rate": Decimal("0.0310")},
            {"min_ltv": Decimal("90.01"), "max_ltv": Decimal("95.00"), "premium_rate": Decimal("0.0400")},
        ]
        
        await service.seed_cmhc_tiers(tiers)
        
        assert mock_db.add.call_count == 3
        
        # Verify the first call (Tier 1)
        first_tier_arg = mock_db.add.call_args_list[0][0][0]
        assert isinstance(first_tier_arg, CMHCTier)
        assert first_tier_arg.min_ltv == Decimal("80.01")
        assert first_tier_arg.premium_rate == Decimal("0.0280")

    @pytest.mark.asyncio
    async def test_seed_cmhc_invalid_data_raises(self, mock_db):
        """Test that invalid LTV ranges (e.g., min > max) raise ValueError."""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 0
        mock_db.execute.return_value = mock_result

        service = SeedService(mock_db)
        
        invalid_tiers = [
            {"min_ltv": Decimal("90.00"), "max_ltv": Decimal("80.00"), "premium_rate": Decimal("0.04")}
        ]
        
        with pytest.raises(ValueError) as exc_info:
            await service.seed_cmhc_tiers(invalid_tiers)
        
        assert "Invalid LTV range" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_seed_cmhc_boundary_check(self, mock_db):
        """Test boundary conditions for LTV calculations."""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 0
        mock_db.execute.return_value = mock_result

        service = SeedService(mock_db)
        
        # Boundary: Exactly 80%
        boundary_tiers = [
            {"min_ltv": Decimal("80.00"), "max_ltv": Decimal("80.00"), "premium_rate": Decimal("0.00")}
        ]
        
        # Logic should handle exact boundaries
        await service.seed_cmhc_tiers(boundary_tiers)
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_seed_service_rollback_on_error(self, mock_db):
        """Test that DB session is rolled back if an error occurs during seeding."""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 0
        mock_db.execute.return_value = mock_result
        
        # Force an error during object creation
        service = SeedService(mock_db)
        
        with patch.object(service, "_create_province_model", side_effect=Exception("DB Error")):
            with pytest.raises(Exception):
                await service.seed_provinces([{"bad": "data"}])
        
        mock_db.rollback.assert_awaited_once()
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.db_admin.models import CMHCTier, Province
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
class TestDatabaseSeedIntegration:

    async def test_seed_provinces_endpoint(self, client: AsyncClient):
        """Test the API endpoint to seed provinces."""
        payload = {
            "provinces": [
                {"code": "ON", "name": "Ontario", "tax_rate": "0.13"},
                {"code": "BC", "name": "British Columbia", "tax_rate": "0.12"}
            ]
        }
        
        response = await client.post("/api/v1/db-admin/seed/provinces", json=payload)
        
        assert response.status_code == 201
        json_resp = response.json()
        assert json_resp["message"] == "Provinces seeded successfully"
        assert json_resp["count"] == 2

    async def test_seed_provinces_idempotency(self, client: AsyncClient, db_session):
        """Test that calling seed endpoint twice does not duplicate data."""
        payload = {
            "provinces": [
                {"code": "AB", "name": "Alberta", "tax_rate": "0.05"}
            ]
        }
        
        # First call
        r1 = await client.post("/api/v1/db-admin/seed/provinces", json=payload)
        assert r1.status_code == 201
        
        # Verify count
        stmt = select(Province)
        result = await db_session.execute(stmt)
        provinces = result.scalars().all()
        assert len(provinces) == 1
        
        # Second call (should not add more)
        r2 = await client.post("/api/v1/db-admin/seed/provinces", json=payload)
        # Depending on implementation, might return 200 OK (skipped) or 201 (no-op success)
        # Here we assume it returns 200 if skipped or 201 if successful check passed
        assert r2.status_code in [200, 201]
        
        # Verify count still 1
        result = await db_session.execute(stmt)
        provinces = result.scalars().all()
        assert len(provinces) == 1

    async def test_seed_cmhc_tiers_endpoint_contract(self, client: AsyncClient, db_session):
        """Test CMHC seeding with accurate Decimal storage and retrieval."""
        payload = {
            "tiers": [
                {"min_ltv": "80.01", "max_ltv": "85.00", "premium_rate": "0.0280"},
                {"min_ltv": "85.01", "max_ltv": "90.00", "premium_rate": "0.0310"},
                {"min_ltv": "90.01", "max_ltv": "95.00", "premium_rate": "0.0400"}
            ]
        }
        
        response = await client.post("/api/v1/db-admin/seed/cmhc", json=payload)
        assert response.status_code == 201
        
        # Verify Database Content
        stmt = select(CMHCTier).order_by(CMHCTier.min_ltv)
        result = await db_session.execute(stmt)
        tiers = result.scalars().all()
        
        assert len(tiers) == 3
        
        # Verify Regulatory Tiers (CMHC Requirements)
        # Tier 1: 80.01 - 85.00 @ 2.80%
        t1 = tiers[0]
        assert t1.min_ltv == Decimal("80.01")
        assert t1.max_ltv == Decimal("85.00")
        assert t1.premium_rate == Decimal("0.0280") # 2.80%
        
        # Tier 3: 90.01 - 95.00 @ 4.00%
        t3 = tiers[2]
        assert t3.min_ltv == Decimal("90.01")
        assert t3.premium_rate == Decimal("0.0400") # 4.00%

    async def test_seed_cmhc_invalid_ltv_range(self, client: AsyncClient):
        """Test API validation for invalid LTV ranges (min > max)."""
        payload = {
            "tiers": [
                {"min_ltv": "95.00", "max_ltv": "80.00", "premium_rate": "0.04"}
            ]
        }
        
        response = await client.post("/api/v1/db-admin/seed/cmhc", json=payload)
        
        assert response.status_code == 422 # Unprocessable Entity

    async def test_migration_status_endpoint(self, client: AsyncClient):
        """Test retrieving migration status."""
        response = await client.get("/api/v1/db-admin/migrations/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "current_revision" in data
        # In test environment, this might be None or a specific hash depending on setup
        # We just check the contract structure
        assert isinstance(data["current_revision"], (str, type(None)))

@pytest.mark.integration
class TestDatabaseConstraints:
    """Test database level constraints for seeded data."""

    async def test_province_code_unique_constraint(self, client: AsyncClient, db_session):
        """Test that duplicate province codes are rejected by DB."""
        payload = {
            "provinces": [
                {"code": "ON", "name": "Ontario", "tax_rate": "0.13"}
            ]
        }
        
        # Seed first
        await client.post("/api/v1/db-admin/seed/provinces", json=payload)
        
        # Try to insert duplicate manually via DB session to test constraint
        dup_province = Province(code="ON", name="Ontario 2", tax_rate=Decimal("0.10"))
        db_session.add(dup_province)
        
        with pytest.raises(Exception): # Raises IntegrityError
            await db_session.commit()
        await db_session.rollback()

    async def test_cmhc_decimals_precision(self, client: AsyncClient, db_session):
        """Ensure Decimal precision is maintained without float conversion errors."""
        payload = {
            "tiers": [
                {"min_ltv": "80.005", "max_ltv": "85.005", "premium_rate": "0.0125"}
            ]
        }
        
        await client.post("/api/v1/db-admin/seed/cmhc", json=payload)
        
        stmt = select(CMHCTier)
        result = await db_session.execute(stmt)
        tier = result.scalar_one()
        
        # Critical: Verify exact precision, not approximation
        assert tier.min_ltv == Decimal("80.005")
        assert tier.premium_rate == Decimal("0.0125")
        # Ensure it is not a float
        assert isinstance(tier.min_ltv, Decimal)
```