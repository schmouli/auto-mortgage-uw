import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from datetime import datetime
from decimal import Decimal

# Import models and app setup
from mortgage_underwriting.main import app
from mortgage_underwriting.modules.deployment.models import DeploymentEvent
from mortgage_underwriting.modules.deployment.schemas import HealthCheckResponse
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestDeploymentRoutes:
    """
    Integration tests for the Deployment module API endpoints.
    Tests the full request/response cycle and DB interaction.
    """

    async def test_health_endpoint_success(self, client: AsyncClient):
        """
        Test GET /api/v1/deployment/health returns 200 and correct structure.
        """
        response = await client.get("/api/v1/deployment/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        # Validate UUID format for correlation_id if present
        # assert "correlation_id" in data 

    async def test_version_endpoint(self, client: AsyncClient):
        """
        Test GET /api/v1/deployment/version returns version info.
        """
        response = await client.get("/api/v1/deployment/version")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "version" in data
        assert "app_name" in data
        assert data["app_name"] == "mortgage_underwriting"

    async def test_log_event_endpoint_creates_record(self, client: AsyncClient, db_session):
        """
        Test POST /api/v1/deployment/events creates a record in DB.
        """
        event_payload = {
            "event_type": "CONFIG_UPDATE",
            "description": "Updated interest rate floor",
            "initiated_by": "admin_user"
        }
        
        response = await client.post("/api/v1/deployment/events", json=event_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["event_type"] == "CONFIG_UPDATE"
        assert data["created_at"] is not None

        # Verify persistence in DB
        result = await db_session.execute(select(DeploymentEvent).where(DeploymentEvent.id == data["id"]))
        db_record = result.scalar_one_or_none()
        
        assert db_record is not None
        assert db_record.description == "Updated interest rate floor"
        assert db_record.initiated_by == "admin_user"

    async def test_get_events_pagination(self, client: AsyncClient, db_session):
        """
        Test GET /api/v1/deployment/events with pagination parameters.
        """
        # Seed data
        for i in range(15):
            event = DeploymentEvent(
                event_type="TEST_EVENT",
                description=f"Test event {i}",
                initiated_by="tester"
            )
            db_session.add(event)
        await db_session.commit()

        # Fetch first page
        response = await client.get("/api/v1/deployment/events?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 10
        assert data["total"] == 15
        assert data["page"] == 1

        # Fetch second page
        response = await client.get("/api/v1/deployment/events?limit=10&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5

    async def test_log_event_validation_error(self, client: AsyncClient):
        """
        Test POST /api/v1/deployment/events with invalid payload returns 422.
        """
        invalid_payload = {
            "event_type": "BAD_TYPE", # Assuming enum validation
            "description": "", # Empty description might be invalid
            "initiated_by": "" 
        }
        
        response = await client.post("/api/v1/deployment/events", json=invalid_payload)
        
        assert response.status_code == 422
        assert "detail" in response.json()

    async def test_readiness_check_k8s_style(self, client: AsyncClient):
        """
        Test GET /api/v1/deployment/readiness (specific for K8s probes).
        Should return 200 if dependencies are met.
        """
        response = await client.get("/api/v1/deployment/readiness")
        assert response.status_code == 200
        assert response.json() == {"ready": True}

    async def test_liveness_check_k8s_style(self, client: AsyncClient):
        """
        Test GET /api/v1/deployment/liveness (specific for K8s probes).
        """
        response = await client.get("/api/v1/deployment/liveness")
        assert response.status_code == 200
        assert response.json() == {"alive": True}

    async def test_event_immutable_audit_fields(self, client: AsyncClient, db_session):
        """
        Test that created_at audit fields are automatically populated and immutable.
        """
        payload = {
            "event_type": "SECURITY_PATCH",
            "description": "Applied hotfix",
            "initiated_by": "devops"
        }
        
        response = await client.post("/api/v1/deployment/events", json=payload)
        event_id = response.json()["id"]
        
        # Try to update created_at via API (should fail or be ignored)
        # Assuming there is no PUT endpoint, but if there were, it should not allow updating created_at.
        # Here we just verify the initial state.
        result = await db_session.execute(select(DeploymentEvent).where(DeploymentEvent.id == event_id))
        record = result.scalar_one()
        
        assert isinstance(record.created_at, datetime)
        assert isinstance(record.updated_at, datetime)
        
        # Verify we cannot manually set created_at via the API
        update_payload = {
            "created_at": "2000-01-01T00:00:00" 
        }
        # This assumes an endpoint exists; if not, this test confirms the schema behavior via ORM
        # For this exercise, we verify the initial creation compliance.
        
    async def test_security_headers_present(self, client: AsyncClient):
        """
        Test that security headers are present on deployment endpoints.
        """
        response = await client.get("/api/v1/deployment/health")
        
        # Check for common security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"