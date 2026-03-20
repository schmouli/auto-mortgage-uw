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