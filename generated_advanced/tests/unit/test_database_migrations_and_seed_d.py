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