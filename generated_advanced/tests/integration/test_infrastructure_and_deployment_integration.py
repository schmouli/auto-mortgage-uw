import pytest
from httpx import AsyncClient, ASGITransport
from decimal import Decimal

from mortgage_underwriting.modules.infrastructure.models import SystemHealth, DeploymentRecord

@pytest.mark.integration
@pytest.mark.asyncio
class TestInfrastructureRoutes:

    async def test_health_check_endpoint_returns_200(self, app):
        """
        Test the GET /health endpoint returns 200 OK and status.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert data["status"] in ["healthy", "degraded", "unhealthy"]
            assert "timestamp" in data

    async def test_create_deployment_record_success(self, app, db_session, mock_deployment_data):
        """
        Test POST /deployments creates a record in DB.
        """
        transport = ASGITransport(app=app)
        
        # We need to override the dependency for the DB session in the route
        # This is typically done in conftest or via app.dependency_overrides
        from mortgage_underwriting.common.database import get_async_session
        
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/infrastructure/deployments", json=mock_deployment_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] > 0
            assert data["version"] == mock_deployment_data["version"]
            assert data["environment"] == mock_deployment_data["environment"]
            assert Decimal(str(data["resource_cost"])) == mock_deployment_data["resource_cost"]
            assert "created_at" in data

        # Cleanup overrides
        app.dependency_overrides = {}

    async def test_create_deployment_record_validates_cost(self, app, db_session, mock_deployment_data):
        """
        Test that negative costs are rejected at the API level.
        """
        transport = ASGITransport(app=app)
        from mortgage_underwriting.common.database import get_async_session
        
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db

        invalid_data = mock_deployment_data.copy()
        invalid_data["resource_cost"] = "-100.00"

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/infrastructure/deployments", json=invalid_data)
            
            # Expecting 422 Unprocessable Entity due to Pydantic validation
            # or 400 if service logic handles it and raises HTTPException
            assert response.status_code in [400, 422]

        app.dependency_overrides = {}

    async def test_list_deployments_pagination(self, app, db_session):
        """
        Test GET /deployments returns a list and handles pagination.
        """
        from mortgage_underwriting.common.database import get_async_session
        
        # Seed data
        deploy1 = DeploymentRecord(
            version="v1.0.0", environment="prod", deployer_id="admin", resource_cost=Decimal("100.00")
        )
        deploy2 = DeploymentRecord(
            version="v1.0.1", environment="prod", deployer_id="admin", resource_cost=Decimal("105.00")
        )
        
        db_session.add(deploy1)
        db_session.add(deploy2)
        await db_session.commit()

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/deployments?limit=10&offset=0")
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert len(data["items"]) >= 2
            assert data["total"] >= 2

        app.dependency_overrides = {}

    async def test_config_endpoint_sanitizes_secrets(self, app):
        """
        Test GET /config returns config but masks sensitive values.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infrastructure/config")
            
            assert response.status_code == 200
            data = response.json()
            
            # Ensure sensitive keys are present but masked
            if "database_url" in data:
                assert "password" not in data["database_url"]
            
            if "secret_key" in data:
                assert data["secret_key"] == "*****"

    async def test_maintenance_mode_toggle(self, app, db_session):
        """
        Test POST /maintenance toggles maintenance mode.
        """
        from mortgage_underwriting.common.database import get_async_session
        
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Turn on
            response_on = await client.post("/api/v1/infrastructure/maintenance", json={"enabled": True})
            assert response_on.status_code == 200
            assert response_on.json()["maintenance_mode"] is True

            # Turn off
            response_off = await client.post("/api/v1/infrastructure/maintenance", json={"enabled": False})
            assert response_off.status_code == 200
            assert response_off.json()["maintenance_mode"] is False

        app.dependency_overrides = {}
```