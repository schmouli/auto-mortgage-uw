import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, status
from sqlalchemy import select

from mortgage_underwriting.modules.admin_panel.routes import router as admin_router
from mortgage_underwriting.modules.admin_panel.models import SystemConfig, AuditLog
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.security import verify_token

# Mock authentication dependency
async def mock_auth_override():
    return {"user_id": "admin-test", "role": "admin"}


@pytest.mark.integration
@pytest.mark.asyncio
class TestAdminPanelIntegration:
    """
    Integration tests for Admin Panel endpoints.
    Tests full request/response cycle with database interaction.
    """

    @pytest.fixture
    def app(self, db_session):
        """
        Create app with DB session override and Auth override.
        """
        app = FastAPI()
        app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])

        # Override DB dependency
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db
        app.dependency_overrides[verify_token] = mock_auth_override
        
        yield app
        app.dependency_overrides.clear()

    @pytest.fixture
    async def client(self, app):
        """
        Async client for testing endpoints.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_get_dashboard_stats_endpoint(self, client: AsyncClient):
        """
        Test GET /api/v1/admin/stats
        """
        response = await client.get("/api/v1/admin/stats")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_applications" in data
        assert "approved_applications" in data
        # Validate types
        assert isinstance(data["total_applications"], int)

    async def test_update_system_config_endpoint_success(self, client: AsyncClient, db_session):
        """
        Test PATCH /api/v1/admin/config
        Updates OSFI B-20 settings.
        """
        # Setup: Create a default config
        config = SystemConfig(
            min_stress_test_rate=Decimal("5.25"),
            max_gds_ratio=Decimal("39.0"),
            max_tds_ratio=Decimal("44.0")
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)

        update_payload = {
            "min_stress_test_rate": "6.00", # JSON string, converted to Decimal
            "max_gds_ratio": "39.0"
        }

        response = await client.patch(f"/api/v1/admin/config/{config.id}", json=update_payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["min_stress_test_rate"] == "6.00"
        
        # Verify DB update
        await db_session.refresh(config)
        assert config.min_stress_test_rate == Decimal("6.00")

    async def test_update_system_config_endpoint_osfi_validation(self, client: AsyncClient, db_session):
        """
        Test PATCH /api/v1/admin/config with invalid OSFI rate.
        Ensures API returns 400/422 for regulatory violations.
        """
        config = SystemConfig(
            min_stress_test_rate=Decimal("5.25"),
            max_gds_ratio=Decimal("39.0"),
            max_tds_ratio=Decimal("44.0")
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)

        # Attempt to set rate below 5.25%
        invalid_payload = {
            "min_stress_test_rate": "4.00",
            "max_gds_ratio": "39.0"
        }

        response = await client.patch(f"/api/v1/admin/config/{config.id}", json=invalid_payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert "qualifying rate" in data["detail"].lower()

    async def test_get_audit_logs_endpoint(self, client: AsyncClient, db_session):
        """
        Test GET /api/v1/admin/audit
        Verifies FINTRAC audit trail retrieval.
        """
        # Setup: Create an audit log
        log_entry = AuditLog(
            entity_id="app-123",
            action="STATUS_CHANGE",
            actor="admin_user",
            details={"old": "pending", "new": "approved"}
        )
        db_session.add(log_entry)
        await db_session.commit()

        response = await client.get("/api/v1/admin/audit?limit=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1
        
        # Check PII is not exposed
        first_log = data["items"][0]
        assert "sin" not in first_log
        assert "dob" not in first_log
        assert first_log["action"] == "STATUS_CHANGE"

    async def test_unauthorized_access(self, client: AsyncClient, app):
        """
        Test that removing auth override results in 401.
        """
        # Remove override to test actual security (if implemented) or default behavior
        app.dependency_overrides.pop(verify_token, None)

        response = await client.get("/api/v1/admin/stats")
        
        # Assuming default auth requires a token
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_create_config_endpoint_decimal_precision(self, client: AsyncClient):
        """
        Test POST /api/v1/admin/config
        Ensures Decimal precision is maintained for financial thresholds.
        """
        payload = {
            "min_stress_test_rate": "5.75",
            "max_gds_ratio": "35.50",
            "max_tds_ratio": "42.00"
        }

        response = await client.post("/api/v1/admin/config", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        # Ensure we get strings back or decimals, not floats
        assert data["max_gds_ratio"] == "35.50" or Decimal("35.50") == Decimal(data["max_gds_ratio"])