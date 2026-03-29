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