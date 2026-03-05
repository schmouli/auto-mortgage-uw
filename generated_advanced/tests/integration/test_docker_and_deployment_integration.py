import pytest
from httpx import AsyncClient
from sqlalchemy import select
from mortgage_underwriting.modules.docker_deployment.models import DeploymentLog


@pytest.mark.integration
class TestDeploymentRoutes:
    @pytest.mark.asyncio
    async def test_create_deployment_log(self, client: AsyncClient, mock_deployment_payload):
        """Test creating a deployment log via API."""
        response = await client.post("/api/v1/deployment/logs", json=mock_deployment_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["version"] == mock_deployment_payload["version"]
        assert data["id"] is not None
        assert data["created_at"] is not None

    @pytest.mark.asyncio
    async def test_create_deployment_log_invalid_payload(self, client: AsyncClient):
        """Test API validation with missing fields."""
        incomplete_payload = {"environment": "prod"}
        response = await client.post("/api/v1/deployment/logs", json=incomplete_payload)

        assert response.status_code == 422  # Validation Error

    @pytest.mark.asyncio
    async def test_get_deployment_logs(self, client: AsyncClient, db_session, mock_deployment_payload):
        """Test retrieving list of deployment logs."""
        # Seed data
        log1 = DeploymentLog(**mock_deployment_payload)
        log2 = DeploymentLog(**{**mock_deployment_payload, "version": "1.0.6"})
        db_session.add(log1)
        db_session.add(log2)
        await db_session.commit()
        await db_session.refresh(log1)
        await db_session.refresh(log2)

        response = await client.get("/api/v1/deployment/logs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 2
        # Verify newest is first (assuming ordering)
        assert data["items"][0]["version"] == "1.0.6"

    @pytest.mark.asyncio
    async def test_get_deployment_log_by_id(self, client: AsyncClient, db_session, mock_deployment_payload):
        """Test retrieving a specific deployment log."""
        log = DeploymentLog(**mock_deployment_payload)
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        response = await client.get(f"/api/v1/deployment/logs/{log.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == log.id
        assert data["git_commit_sha"] == mock_deployment_payload["git_commit_sha"]


@pytest.mark.integration
class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, client: AsyncClient):
        """Test the liveness/readiness probe endpoint."""
        response = await client.get("/api/v1/deployment/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_version_endpoint(self, client: AsyncClient):
        """Test the version endpoint."""
        response = await client.get("/api/v1/deployment/version")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        # Check format (e.g., 1.0.0)
        assert isinstance(data["version"], str)


@pytest.mark.integration
class TestDeploymentAuditTrail:
    @pytest.mark.asyncio
    async def test_deployment_log_immutability_audit_fields(self, client: AsyncClient, db_session, mock_deployment_payload):
        """
        Test that deployment logs are created with correct audit fields
        and represent an immutable event log.
        """
        response = await client.post("/api/v1/deployment/logs", json=mock_deployment_payload)
        assert response.status_code == 201
        
        log_id = response.json()["id"]
        
        # Verify in DB
        result = await db_session.execute(select(DeploymentLog).where(DeploymentLog.id == log_id))
        log = result.scalar_one()
        
        assert log.created_at is not None
        assert log.updated_at is not None # Usually set by base model
        
        # Attempting to update via API should fail or be restricted depending on implementation
        # Assuming updates are not allowed for audit logs
        update_payload = {"status": "failed"}
        response = await client.patch(f"/api/v1/deployment/logs/{log_id}", json=update_payload)
        
        # Expect 405 Method Not Allowed or 403 Forbidden if strictly immutable
        assert response.status_code in [405, 403, 404] # 404 if endpoint doesn't exist