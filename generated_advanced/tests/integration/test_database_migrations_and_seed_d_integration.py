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