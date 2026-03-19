import pytest
from httpx import AsyncClient
from sqlalchemy import select
from datetime import datetime

from mortgage_underwriting.modules.deployment.models import DeploymentLog

@pytest.mark.integration
@pytest.mark.asyncio
class TestDeploymentRoutes:

    async def test_create_deployment_log(self, client: AsyncClient, db_session, sample_deployment_payload):
        """
        Test the endpoint to create a deployment log.
        """
        response = await client.post("/api/v1/deployment/log", json=sample_deployment_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["environment"] == "production"
        assert data["version"] == "1.2.3"
        assert "id" in data
        assert "created_at" in data

        # Verify persistence in DB
        stmt = select(DeploymentLog).where(DeploymentLog.version == "1.2.3")
        result = await db_session.execute(stmt)
        log = result.scalar_one_or_none()
        
        assert log is not None
        assert log.commit_hash == "a1b2c3d4"
        assert log.status == "success"

    async def test_create_deployment_log_invalid_version(self, client: AsyncClient, sample_deployment_payload):
        """
        Test validation rejection for bad version format via API.
        """
        sample_deployment_payload["version"] = "bad_version"
        response = await client.post("/api/v1/deployment/log", json=sample_deployment_payload)
        
        assert response.status_code == 422  # Validation Error

    async def test_get_deployment_history(self, client: AsyncClient, db_session):
        """
        Test retrieving history of deployments for an environment.
        """
        # Seed data
        log1 = DeploymentLog(
            environment="production",
            version="1.0.0",
            commit_hash="hash1",
            deployed_by="user1",
            status="success",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        log2 = DeploymentLog(
            environment="production",
            version="1.0.1",
            commit_hash="hash2",
            deployed_by="user1",
            status="success",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(log1)
        db_session.add(log2)
        await db_session.commit()

        response = await client.get("/api/v1/deployment/history?environment=production")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        versions = [item["version"] for item in data]
        assert "1.0.0" in versions
        assert "1.0.1" in versions

    async def test_get_deployment_history_empty(self, client: AsyncClient):
        """
        Test retrieving history when no records exist.
        """
        response = await client.get("/api/v1/deployment/history?environment=staging")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    async def test_health_check_endpoint(self, client: AsyncClient):
        """
        Test the public health check endpoint.
        """
        response = await client.get("/api/v1/deployment/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        # Check structure matches expected health schema
        assert data["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_get_latest_deployment_endpoint(self, client: AsyncClient, db_session):
        """
        Test getting the single latest deployment record.
        """
        log = DeploymentLog(
            environment="production",
            version="2.0.0",
            commit_hash="latest_hash",
            deployed_by="admin",
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(log)
        await db_session.commit()

        response = await client.get("/api/v1/deployment/latest?environment=production")
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "2.0.0"
        assert data["commit_hash"] == "latest_hash"

    async def test_get_latest_deployment_not_found_endpoint(self, client: AsyncClient):
        """
        Test 404 when requesting latest for non-existent environment.
        """
        response = await client.get("/api/v1/deployment/latest?environment=nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    async def test_update_deployment_status(self, client: AsyncClient, db_session):
        """
        Test updating the status of a deployment (e.g., rollback).
        """
        # Create initial log
        log = DeploymentLog(
            environment="production",
            version="3.0.0",
            commit_hash="hash3",
            deployed_by="admin",
            status="deploying",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        # Update via API
        update_payload = {"status": "failed", "notes": "Health check failed"}
        response = await client.patch(f"/api/v1/deployment/{log.id}", json=update_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        
        # Verify DB update
        await db_session.refresh(log)
        assert log.status == "failed"
        assert log.updated_at > log.created_at

    async def test_security_no_secrets_in_response(self, client: AsyncClient, db_session):
        """
        Ensure sensitive fields (if any existed) are not leaked.
        Here we ensure internal IDs or tokens are not exposed unnecessarily.
        """
        log = DeploymentLog(
            environment="production",
            version="1.0.0",
            commit_hash="secret_hash",
            deployed_by="admin",
            status="success",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(log)
        await db_session.commit()

        response = await client.get("/api/v1/deployment/latest?environment=production")
        assert response.status_code == 200
        data = response.json()
        # Ensure response does not contain internal fields not defined in schema
        # (e.g. internal_notes if they existed in model but not schema)
        assert "deployed_by" in data # This is allowed
        # Verify no unexpected keys
        allowed_keys = {"id", "environment", "version", "commit_hash", "deployed_by", "status", "created_at", "updated_at"}
        assert set(data.keys()).issubset(allowed_keys)