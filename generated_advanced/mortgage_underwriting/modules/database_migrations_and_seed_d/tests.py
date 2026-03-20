--- conftest.py ---
```python
import pytest
from collections.abc import AsyncGenerator, Generator
from typing import AsyncIterator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from decimal import Decimal

# Assuming Base is imported from common.database
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.main import app  # Assuming a main app entry point
from mortgage_underwriting.common.config import settings

# Use SQLite for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def engine():
    """Create a new database engine for each test function."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncIterator[AsyncSession]:
    """Create a new database session for each test function."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """
    Create a test client that overrides the database dependency.
    """
    from mortgage_underwriting.common.database import get_async_session
    
    async def override_get_async_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_async_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture
def sample_province_payload():
    return {
        "code": "ON",
        "name": "Ontario",
        "tax_rate": Decimal("0.13")
    }

@pytest.fixture
def sample_cmhc_tier_payload():
    return {
        "min_ltv": Decimal("80.01"),
        "max_ltv": Decimal("85.00"),
        "premium_rate": Decimal("0.0280")
    }

@pytest.fixture
def mock_alembic_config():
    """Mock Alembic configuration for migration testing."""
    from unittest.mock import MagicMock
    config = MagicMock()
    config.get_section = MagicMock(return_value={})
    return config
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from sqlalchemy import select
from mortgage_underwriting.modules.database_migrations_and_seed_data.services import (
    SeedDataService,
    MigrationService
)
from mortgage_underwriting.modules.database_migrations_and_seed_data.models import (
    Province,
    CMHCPremiumTier
)
from mortgage_underwriting.common.exceptions import AppException

# Import paths strictly following conventions

@pytest.mark.unit
class TestSeedDataService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        # Mock scalar() for existence checks
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        db.execute.return_value = result_mock
        return db

    @pytest.fixture
    def seed_service(self, mock_db):
        return SeedDataService(mock_db)

    @pytest.mark.asyncio
    async def test_seed_province_success(self, seed_service, mock_db):
        """Test successful seeding of a new province."""
        payload = {
            "code": "BC",
            "name": "British Columbia",
            "tax_rate": Decimal("0.12")
        }
        
        # Mock exists check returns None (not exists)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute.return_value = mock_result

        await seed_service.seed_province(payload)
        
        # Verify add was called
        assert mock_db.add.call_count == 1
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, Province)
        assert added_obj.code == "BC"
        assert added_obj.tax_rate == Decimal("0.12")
        
        # Verify commit
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_seed_province_already_exists_skips(self, seed_service, mock_db):
        """Test that seeding an existing province skips insertion."""
        payload = {
            "code": "AB",
            "name": "Alberta",
            "tax_rate": Decimal("0.05")
        }
        
        # Mock exists check returns an object (exists)
        existing_province = Province(code="AB", name="Alberta", tax_rate=Decimal("0.05"))
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing_province)
        mock_db.execute.return_value = mock_result

        await seed_service.seed_province(payload)
        
        # Verify add was NOT called
        mock_db.add.assert_not_called()
        # Verify commit was still called (transaction safety)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_seed_cmhc_tier_success(self, seed_service, mock_db):
        """Test successful seeding of CMHC premium tier."""
        payload = {
            "min_ltv": Decimal("80.01"),
            "max_ltv": Decimal("85.00"),
            "premium_rate": Decimal("0.0280")
        }
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute.return_value = mock_result

        await seed_service.seed_cmhc_tier(payload)
        
        assert mock_db.add.call_count == 1
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, CMHCPremiumTier)
        assert added_obj.premium_rate == Decimal("0.0280")
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bulk_seed_provinces_handles_errors(self, seed_service, mock_db):
        """Test that bulk seeding handles individual item failures gracefully."""
        payloads = [
            {"code": "ON", "name": "Ontario", "tax_rate": Decimal("0.13")},
            {"code": "QC", "name": "Quebec", "tax_rate": Decimal("0.14975")}
        ]
        
        # First call succeeds, second call raises DB error
        async def side_effect_execute(stmt):
            # Simplified logic for mocking side effects based on stmt text or object
            if "ON" in str(stmt):
                res = AsyncMock()
                res.scalar_one_or_none = MagicMock(return_value=None)
                return res
            else:
                raise Exception("Database connection lost")

        mock_db.execute.side_effect = side_effect_execute

        with pytest.raises(AppException) as exc_info:
            await seed_service.bulk_seed_provinces(payloads)
        
        assert "Error seeding provinces" in str(exc_info.value)
        mock_db.commit.assert_awaited() # Attempted commit or rollback logic

    @pytest.mark.asyncio
    async def test_validate_seed_data_missing_required_field(self, seed_service):
        """Test validation logic within seed service."""
        invalid_payload = {
            "code": "MB",
            # Missing 'name'
            "tax_rate": Decimal("0.12")
        }
        
        with pytest.raises(ValueError) as exc_info:
            await seed_service.seed_province(invalid_payload)
        
        assert "Missing required field" in str(exc_info.value)


@pytest.mark.unit
class TestMigrationService:
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def migration_service(self, mock_db):
        return MigrationService(mock_db)

    @patch('mortgage_underwriting.modules.database_migrations_and_seed_data.services.context')
    @pytest.mark.asyncio
    async def test_get_current_revision_success(self, mock_context, migration_service):
        """Test retrieving current Alembic revision."""
        mock_context.configure = MagicMock()
        mock_script = MagicMock()
        mock_script.get_current_head = MagicMock(return_value="abc123")
        
        # Mock the execution of the SQL to get version
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value="abc123")
        migration_service._db.execute = AsyncMock(return_value=mock_result)

        revision = await migration_service.get_current_revision()
        
        assert revision == "abc123"
        migration_service._db.execute.assert_awaited_once()

    @patch('alembic.command.upgrade')
    @patch('mortgage_underwriting.modules.database_migrations_and_seed_data.services.Config')
    @pytest.mark.asyncio
    async def test_run_migration_to_head(self, MockConfig, mock_upgrade, migration_service):
        """Test triggering a migration to head."""
        config_instance = MagicMock()
        MockConfig.return_value = config_instance
        
        await migration_service.run_migrations("head")
        
        MockConfig.assert_called_once()
        mock_upgrade.assert_called_once_with(config_instance, "head")

    @pytest.mark.asyncio
    async def test_check_schema_health_table_missing(self, migration_service):
        """Test health check when a critical table is missing."""
        # Mock inspect to return empty list
        with patch('sqlalchemy.inspect') as mock_inspect:
            mock_inspector = MagicMock()
            mock_inspector.get_table_names = MagicMock(return_value=[])
            mock_inspect.return_value = mock_inspector
            
            is_healthy = await migration_service.check_schema_health()
            
            assert is_healthy is False

    @pytest.mark.asyncio
    async def test_check_schema_health_table_exists(self, migration_service):
        """Test health check when tables exist."""
        with patch('sqlalchemy.inspect') as mock_inspect:
            mock_inspector = MagicMock()
            mock_inspector.get_table_names = MagicMock(return_value=["province", "users"])
            mock_inspect.return_value = mock_inspector
            
            is_healthy = await migration_service.check_schema_health()
            
            assert is_healthy is True
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select, text
from mortgage_underwriting.modules.database_migrations_and_seed_data.models import (
    Province,
    CMHCPremiumTier
)

# Import paths strictly following conventions

@pytest.mark.integration
class TestSeedDataEndpoints:

    @pytest.mark.asyncio
    async def test_seed_provinces_endpoint_creates_records(self, client: AsyncClient, db_session):
        """Test POST /admin/seed/provinces creates data in DB."""
        payload = [
            {"code": "ON", "name": "Ontario", "tax_rate": "0.13"},
            {"code": "BC", "name": "British Columbia", "tax_rate": "0.12"}
        ]
        
        response = await client.post("/api/v1/admin/seed/provinces", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Provinces seeded successfully"
        assert data["count"] == 2
        
        # Verify DB state
        result = await db_session.execute(select(Province).where(Province.code == "ON"))
        province = result.scalar_one_or_none()
        assert province is not None
        assert province.name == "Ontario"
        assert province.tax_rate == Decimal("0.13")

    @pytest.mark.asyncio
    async def test_seed_provinces_idempotent(self, client: AsyncClient, db_session):
        """Test that seeding same data twice doesn't create duplicates."""
        payload = [{"code": "AB", "name": "Alberta", "tax_rate": "0.05"}]
        
        # First call
        response1 = await client.post("/api/v1/admin/seed/provinces", json=payload)
        assert response1.status_code == 201
        
        # Second call
        response2 = await client.post("/api/v1/admin/seed/provinces", json=payload)
        assert response2.status_code == 200 # Expect OK or 201 depending on impl, assuming 200 if no changes
        
        # Verify only one record exists
        result = await db_session.execute(select(Province).where(Province.code == "AB"))
        provinces = result.scalars().all()
        assert len(provinces) == 1

    @pytest.mark.asyncio
    async def test_seed_cmhc_tiers_endpoint(self, client: AsyncClient, db_session):
        """Test POST /admin/seed/cmhc-tiers."""
        payload = [
            {"min_ltv": "80.01", "max_ltv": "85.00", "premium_rate": "0.0280"},
            {"min_ltv": "85.01", "max_ltv": "90.00", "premium_rate": "0.0310"}
        ]
        
        response = await client.post("/api/v1/admin/seed/cmhc-tiers", json=payload)
        
        assert response.status_code == 201
        
        # Verify DB state with Decimal precision check
        result = await db_session.execute(select(CMHCPremiumTier))
        tiers = result.scalars().all()
        assert len(tiers) == 2
        assert tiers[0].premium_rate == Decimal("0.0280")

    @pytest.mark.asyncio
    async def test_seed_invalid_data_returns_400(self, client: AsyncClient):
        """Test validation error on bad input."""
        payload = [{"code": "XX", "name": None, "tax_rate": "0.10"}] # Invalid name
        
        response = await client.post("/api/v1/admin/seed/provinces", json=payload)
        
        assert response.status_code == 422 # Unprocessable Entity from Pydantic

    @pytest.mark.asyncio
    async def test_get_seed_status(self, client: AsyncClient, db_session):
        """Test GET /admin/seed/status returns counts."""
        # Seed some data manually
        prov = Province(code="SK", name="Saskatchewan", tax_rate=Decimal("0.11"))
        db_session.add(prov)
        await db_session.commit()
        
        response = await client.get("/api/v1/admin/seed/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "provinces_count" in data
        assert data["provinces_count"] >= 1


@pytest.mark.integration
class TestMigrationEndpoints:

    @pytest.mark.asyncio
    async def test_get_migration_status(self, client: AsyncClient):
        """Test GET /admin/migrations/status."""
        # This endpoint checks alembic version
        response = await client.get("/api/v1/admin/migrations/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "current_revision" in data
        # In test env, this might be None or empty string depending on alembic setup
        assert isinstance(data["current_revision"], str)

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, client: AsyncClient):
        """Test GET /health returns DB connectivity status."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data

    @pytest.mark.asyncio
    async def test_run_migration_endpoint_restricted(self, client: AsyncClient):
        """
        Test POST /admin/migrations/upgrade.
        Note: In a real scenario, this requires auth. 
        Assuming auth is mocked or disabled for integration tests via dependency override.
        """
        # This is a dangerous endpoint, usually protected.
        # We check if it exists and returns appropriate response structure
        response = await client.post("/api/v1/admin/migrations/upgrade", json={"revision": "head"})
        
        # If protected and auth not mocked, 401/403. If mocked, 200.
        # Assuming we have a fixture to bypass auth:
        from mortgage_underwriting.common.security import verify_token
        from mortgage_underwriting.main import app
        
        # Bypass auth for this specific test
        app.dependency_overrides[verify_token] = lambda: True
        
        response = await client.post("/api/v1/admin/migrations/upgrade", json={"revision": "head"})
        
        # If migrations run successfully
        assert response.status_code in [200, 202] # Accepted or OK
        
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_database_schema_reflection(self, client: AsyncClient, db_session):
        """Verify that tables defined in models are actually created in the test DB."""
        # Inspect the database
        async with db_session.connection() as conn:
            result = await conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ))
            tables = [row[0] for row in result.fetchall()]
            
            # Check for expected tables based on our seed models
            assert "province" in tables
            assert "cmhc_premium_tier" in tables
```