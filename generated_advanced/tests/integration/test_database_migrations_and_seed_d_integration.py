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