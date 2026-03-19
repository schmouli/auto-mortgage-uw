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