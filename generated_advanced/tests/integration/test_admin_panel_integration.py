```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.admin_panel.routes import router
from mortgage_underwriting.modules.admin_panel.models import AdminUser, SystemConfiguration
from mortgage_underwriting.common.database import get_async_session

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

@pytest.fixture
def app(db_session):
    """
    Create a test FastAPI app with the Admin router and overridden DB dependency.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin", tags=["Admin"])

    # Override the database dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_admin_user_endpoint(app):
    """
    Integration test: Create a new admin user via API.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "username": "new_admin",
            "email": "new_admin@test.com",
            "role": "admin",
            "password": "ComplexPassword123!"
        }
        
        response = await client.post("/api/v1/admin/users", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "new_admin"
        assert data["email"] == "new_admin@test.com"
        assert "id" in data
        assert "password" not in data  # Ensure password is not in response

@pytest.mark.asyncio
async def test_create_admin_user_validation_error(app):
    """
    Integration test: Create user with invalid data (missing password).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "username": "bad_admin",
            "email": "bad@test.com",
            "role": "admin"
            # Missing password
        }
        
        response = await client.post("/api/v1/admin/users", json=payload)
        
        assert response.status_code == 422  # Unprocessable Entity

@pytest.mark.asyncio
async def test_get_audit_logs_endpoint(app, db_session):
    """
    Integration test: Retrieve audit logs.
    """
    # Seed data
    log = AuditLog(
        id="log-1",
        user_id="admin-1",
        action="LOGIN",
        details={"ip": "127.0.0.1"},
        timestamp="2023-01-01T12:00:00"
    )
    db_session.add(log)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/admin/audit-logs")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1
        assert data["items"][0]["action"] == "LOGIN"

@pytest.mark.asyncio
async def test_update_config_endpoint_osfi_validation(app):
    """
    Integration test: Attempt to update config with invalid OSFI limits.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Attempt to set GDS to 50% (Violates OSFI B-20)
        payload = {
            "gds_limit": "50.00",
            "tds_limit": "44.00",
            "stress_test_rate": "5.25"
        }
        
        response = await client.put("/api/v1/admin/config", json=payload)
        
        # Expecting 400 Bad Request or 422 from validation logic
        assert response.status_code in [400, 422]
        assert "GDS" in response.json()["detail"]

@pytest.mark.asyncio
async def test_update_config_endpoint_success(app, db_session):
    """
    Integration test: Successfully update system configuration.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "min_beacon_score": 680,
            "gds_limit": "35.00", # Valid
            "tds_limit": "42.00", # Valid
            "stress_test_rate": "5.50",
            "max_ltv_uninsured": "80.00"
        }
        
        response = await client.put("/api/v1/admin/config", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["gds_limit"] == "35.00"
        
        # Verify persistence in DB
        stmt = select(SystemConfiguration).limit(1)
        result = await db_session.execute(stmt)
        config = result.scalar_one_or_none()
        assert config is not None
        assert config.gds_limit == Decimal("35.00")

@pytest.mark.asyncio
async def test_lock_user_endpoint(app, db_session):
    """
    Integration test: Lock a user account via API.
    """
    # Create a user first
    user = AdminUser(
        id="user-to-lock",
        username="victim",
        email="victim@test.com",
        role="underwriter",
        hashed_password="hash",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/api/v1/admin/users/{user.id}/lock", json={
            "reason": "Security violation",
            "locked_by": "superadmin"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_locked"] is True
        assert data["locked_reason"] == "Security violation"

        # Verify DB state
        await db_session.refresh(user)
        assert user.is_locked is True

@pytest.mark.asyncio
async def test_get_metrics_dashboard(app, db_session):
    """
    Integration test: Fetch dashboard metrics.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/admin/metrics")
        
        assert response.status_code == 200
        data = response.json()
        # Check structure exists
        assert "total_users" in data
        assert "active_sessions" in data
        assert "system_health" in data
```