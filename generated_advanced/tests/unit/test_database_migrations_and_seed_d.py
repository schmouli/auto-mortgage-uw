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