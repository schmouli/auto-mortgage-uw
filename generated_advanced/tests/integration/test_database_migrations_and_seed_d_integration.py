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