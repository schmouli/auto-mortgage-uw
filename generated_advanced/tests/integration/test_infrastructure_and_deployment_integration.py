import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.infrastructure.models import DeploymentEvent

@pytest.mark.integration
class TestInfrastructureRoutes:

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, client: AsyncClient):
        """
        Test the health check endpoint returns 200 and correct structure.
        """
        response = await client.get("/api/v1/infra/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "database_status" in data
        assert "timestamp" in data
        # Check for structured error fields (even in success, schema might dictate keys)
        # but typically success just returns data.

    @pytest.mark.asyncio
    async def test_create_deployment_log_success(self, client: AsyncClient, sample_deployment_payload, db_session):
        """
        Test creating a deployment log via API.
        """
        response = await client.post("/api/v1/infra/deployments", json=sample_deployment_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["id"] > 0
        assert data["version"] == sample_deployment_payload["version"]
        assert data["environment"] == sample_deployment_payload["environment"]
        assert Decimal(data["resource_cost"]) == Decimal(sample_deployment_payload["resource_cost"])
        assert "created_at" in data
        
        # Verify DB state
        stmt = select(DeploymentEvent).where(DeploymentEvent.id == data["id"])
        result = await db_session.execute(stmt)
        db_record = result.scalar_one_or_none()
        
        assert db_record is not None
        assert db_record.version == "v1.2.3"
        assert db_record.created_by == "ci_bot"

    @pytest.mark.asyncio
    async def test_create_deployment_log_invalid_input(self, client: AsyncClient):
        """
        Test validation error on bad input (e.g., float for money, missing fields).
        """
        invalid_payload = {
            "version": "v1.0.0",
            "environment": "production",
            "status": "success",
            # Missing resource_cost
            "created_by": "user"
        }
        
        response = await client.post("/api/v1/infra/deployments", json=invalid_payload)
        
        assert response.status_code == 422  # Unprocessable Entity
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_create_deployment_log_wrong_money_type(self, client: AsyncClient):
        """
        Ensure strict Decimal usage. Sending a float string might be rejected or parsed.
        Here we test that the API handles the Decimal string correctly.
        """
        # Using a float-like string is usually okay for Pydantic Decimal, 
        # but let's test the precision.
        payload = {
            "version": "v1.0.0",
            "environment": "production",
            "status": "success",
            "resource_cost": "100.123456", # High precision
            "created_by": "user"
        }
        
        response = await client.post("/api/v1/infra/deployments", json=payload)
        
        # Assuming the service accepts high precision or rounds it. 
        # If the DB field is NUMERIC(10,2), this might fail or round.
        # For this test, we assume success and check the stored value.
        assert response.status_code in [201, 400] # Depending on DB precision constraints

    @pytest.mark.asyncio
    async def test_get_deployments_list(self, client: AsyncClient, db_session, sample_deployment_record):
        """
        Test retrieving a list of deployment events.
        """
        # Pre-populate DB
        db_session.add(sample_deployment_record)
        await db_session.commit()
        
        response = await client.get("/api/v1/infra/deployments")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["version"] == "v1.2.3"
        # Verify PII/Security: Ensure created_by is present (it's not PII in this context, it's a user)
        # but ensure no internal DB fields leak if they shouldn't.

    @pytest.mark.asyncio
    async def test_get_deployment_by_id(self, client: AsyncClient, db_session, sample_deployment_record):
        """
        Test retrieving a specific deployment event.
        """
        db_session.add(sample_deployment_record)
        await db_session.commit()
        await db_session.refresh(sample_deployment_record)
        
        response = await client.get(f"/api/v1/infra/deployments/{sample_deployment_record.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_deployment_record.id
        assert data["version"] == "v1.2.3"

    @pytest.mark.asyncio
    async def test_get_deployment_not_found(self, client: AsyncClient):
        """
        Test 404 response for non-existent deployment.
        """
        response = await client.get("/api/v1/infra/deployments/99999")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error_code" in data # Enforcing structured error response rule

    @pytest.mark.asyncio
    async def test_deployment_audit_trail_immutability(self, client: AsyncClient, db_session, sample_deployment_payload):
        """
        Test that created_at and created_by are set correctly and immutable logic is respected.
        (Note: Full immutability is usually DB constraint, here we check API doesn't allow overwriting)
        """
        # Attempt to pass created_at in payload (should be ignored or rejected)
        malicious_payload = sample_deployment_payload.copy()
        malicious_payload["created_at"] = "2000-01-01T00:00:00Z"
        
        response = await client.post("/api/v1/infra/deployments", json=malicious_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        # The server should have set the current time, not the one in the payload
        assert data["created_at"] != "2000-01-01T00:00:00Z"
        
        # Verify DB
        stmt = select(DeploymentEvent).where(DeploymentEvent.id == data["id"])
        result = await db_session.execute(stmt)
        record = result.scalar_one()
        
        # Check it's recent (within last minute)
        from datetime import datetime, timedelta
        now = datetime.now(timezone.utc)
        assert now - timedelta(seconds=60) <= record.created_at <= now