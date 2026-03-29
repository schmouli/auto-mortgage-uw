```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy import select

from mortgage_underwriting.modules.deployment.routes import router
from mortgage_underwriting.modules.deployment.models import DeploymentAudit
from mortgage_underwriting.common.database import get_async_session

@pytest.fixture
def app(db_session):
    """
    Creates a test FastAPI app with the deployment router.
    Overrides the database dependency with the test session.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/deployment", tags=["Deployment"])

    # Dependency override
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestDeploymentEndpoints:

    async def test_create_deployment_audit(self, app: FastAPI):
        """
        Test POST /api/v1/deployment/audit
        Ensures audit trail is created correctly (FINTRAC compliance).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "version": "v1.4.5",
                "deployed_by": "devops_user",
                "environment": "production",
                "notes": "Hotfix for security patch"
            }
            
            response = await client.post("/api/v1/deployment/audit", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] > 0
            assert data["version"] == "v1.4.5"
            assert data["status"] == "success"
            assert "created_at" in data
            
            # Verify immutability: response should not allow updating via this endpoint
            # (Implicitly tested as we only have a POST endpoint)

    async def test_create_deployment_invalid_input(self, app: FastAPI):
        """
        Test POST /api/v1/deployment/audit with missing required fields.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing 'version'
            payload = {
                "deployed_by": "user",
                "environment": "dev"
            }
            
            response = await client.post("/api/v1/deployment/audit", json=payload)
            
            assert response.status_code == 422  # Validation Error

    async def test_get_deployment_history(self, app: FastAPI, db_session: AsyncSession):
        """
        Test GET /api/v1/deployment/audit
        Verifies retrieval of audit logs.
        """
        # Seed data
        audit1 = DeploymentAudit(
            version="v1.0.0",
            deployed_by="alice",
            environment="staging",
            status="success"
        )
        audit2 = DeploymentAudit(
            version="v1.1.0",
            deployed_by="bob",
            environment="production",
            status="success"
        )
        db_session.add_all([audit1, audit2])
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/deployment/audit")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            # Verify order (usually newest first, check logic implementation)
            # Assuming default order by created_at desc
            assert data[0]["version"] == "v1.1.0"
            assert data[1]["version"] == "v1.0.0"

    async def test_get_health_endpoint(self, app: FastAPI, mock_redis):
        """
        Test GET /api/v1/deployment/health
        Checks system status aggregation.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/deployment/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "database" in data
            assert "cache" in data
            assert "timestamp" in data

    async def test_get_deployment_by_id(self, app: FastAPI, db_session: AsyncSession):
        """
        Test GET /api/v1/deployment/audit/{id}
        """
        audit = DeploymentAudit(
            version="v3.0.0",
            deployed_by="tester",
            environment="dev",
            status="success"
        )
        db_session.add(audit)
        await db_session.commit()
        await db_session.refresh(audit)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/deployment/audit/{audit.id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["version"] == "v3.0.0"

    async def test_get_deployment_not_found(self, app: FastAPI):
        """
        Test GET /api/v1/deployment/audit/{id} with non-existent ID.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/deployment/audit/99999")
            
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data

    async def test_environment_config_endpoint(self, app: FastAPI):
        """
        Test GET /api/v1/deployment/config
        Ensure sensitive secrets are NOT exposed (PIPEDA/Security).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/deployment/config")
            
            assert response.status_code == 200
            data = response.json()
            assert "environment" in data
            assert "version" in data
            # Ensure secrets are absent
            assert "database_url" not in data
            assert "secret_key" not in data
            assert "api_keys" not in data
```