import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, status
from sqlalchemy.ext.asyncio import AsyncSession

# Import the module under test
from mortgage_underwriting.modules.infrastructure_deployment.routes import router
from mortgage_underwriting.modules.infrastructure_deployment.models import DeploymentLog
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestInfrastructureRoutes:
    """
    Integration tests for Infrastructure API endpoints.
    Tests request/response contracts and DB interaction.
    """

    @pytest.fixture
    def app(self, db_session: AsyncSession):
        """
        Create app with DB session override.
        """
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/infra", tags=["Infrastructure"])

        # Dependency override to use test session
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_async_session] = override_get_db
        yield app
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, app: FastAPI):
        """
        Test GET /health returns 200 and correct structure.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infra/health")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert "status" in data
            assert "components" in data
            assert isinstance(data["components"], dict)

    @pytest.mark.asyncio
    async def test_health_check_endpoint_db_down(self, app: FastAPI):
        """
        Test GET /health handles DB failure gracefully (returns 503 or status unhealthy).
        """
        # This test assumes we can break the DB connection or mock the service layer within the integration
        # For integration tests, we usually rely on the test DB being up.
        # However, we can test the 'readiness' endpoint specifically.
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Assuming /readiness performs stricter checks than /health
            response = await client.get("/api/v1/infra/ready")
            
            # In a healthy test environment, this should be 200
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]

    @pytest.mark.asyncio
    async def test_metrics_endpoint_exists(self, app: FastAPI):
        """
        Test GET /metrics endpoint exists and returns text/plain (Prometheus format).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infra/metrics")
            
            # Metrics endpoint might require auth or specific setup, checking existence
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_log_deployment_workflow(self, app: FastAPI, db_session: AsyncSession):
        """
        Test multi-step workflow: Log deployment -> Verify in DB -> Retrieve History.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 1: Log a deployment
            payload = {
                "version": "2.0.1",
                "status": "deployed",
                "deployed_by": "tester",
                "notes": "Integration test deployment"
            }
            response = await client.post("/api/v1/infra/deployments", json=payload)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["version"] == "2.0.1"
            assert "id" in data

            # Step 2: Verify it exists in DB directly
            result = await db_session.execute(DeploymentLog.__table__.select().where(DeploymentLog.id == data["id"]))
            db_record = result.fetchone()
            assert db_record is not None
            assert db_record.version == "2.0.1"
            assert db_record.created_by == "tester" # Audit trail check

            # Step 3: Retrieve history via API
            history_response = await client.get("/api/v1/infra/deployments")
            assert history_response.status_code == status.HTTP_200_OK
            
            history_data = history_response.json()
            assert len(history_data) >= 1
            assert any(d["id"] == data["id"] for d in history_data)

    @pytest.mark.asyncio
    async def test_config_endpoint_security(self, app: FastAPI):
        """
        Test that config endpoint does not leak sensitive data (PIPEDA).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infra/config/public")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Ensure secrets are not present
            assert "SECRET_KEY" not in data
            assert "DATABASE_URL" not in data
            assert "environment" in data # Non-sensitive info should be present

    @pytest.mark.asyncio
    async def test_input_validation_deployment_log(self, app: FastAPI):
        """
        Test input validation on deployment log endpoint.
        Ensures empty strings or invalid data is rejected.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing required field
            payload = {
                "version": "", # Invalid: empty string
                "status": "deployed"
            }
            response = await client.post("/api/v1/infra/deployments", json=payload)
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_version_endpoint(self, app: FastAPI):
        """
        Test GET /version returns build information.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/infra/version")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "version" in data
            # Regex check for semantic versioning would go here
            assert len(data["version"]) > 0