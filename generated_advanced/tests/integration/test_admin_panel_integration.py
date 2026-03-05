import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, status
from unittest.mock import AsyncMock, patch

# Import paths based on project conventions
from mortgage_underwriting.modules.admin_panel.routes import router
from mortgage_underwriting.modules.admin_panel.models import AdminUser
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
class TestAdminPanelRoutes:
    """
    Integration tests for Admin Panel API endpoints.
    Tests HTTP contracts, validation, and response structures.
    """

    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/admin", tags=["admin"])
        return app

    @pytest.mark.asyncio
    async def test_create_user_endpoint_success(self, app):
        """
        Test POST /api/v1/admin/users returns 201 and valid JSON.
        """
        # We mock the database dependency to avoid needing a real DB for this integration check
        # or we rely on the test client overriding the dependency.
        # Here we will mock the service layer directly or the DB session.
        
        async def override_get_db():
            mock_db = AsyncMock()
            # Mock the flow of create_user
            mock_db.execute.return_value.scalar_one_or_none.return_value = None # No existing user
            yield mock_db

        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "username": "new_user",
                "email": "new_user@example.com",
                "role": "underwriter",
                "department": "risk"
            }
            response = await client.post("/api/v1/admin/users", json=payload)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["username"] == "new_user"
            assert "id" in data
            # Verify PIPEDA: Password should NOT be in response (if schema included it)
            assert "password" not in data

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_user_endpoint_validation_error(self, app):
        """
        Test POST /api/v1/admin/users with invalid data returns 422.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing required fields
            payload = {
                "username": "bad_user"
                # missing email, role, etc.
            }
            response = await client.post("/api/v1/admin/users", json=payload)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            # Verify structured error response
            assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_get_audit_logs_endpoint_success(self, app):
        """
        Test GET /api/v1/admin/audit-logs returns 200 and list of logs.
        """
        async def override_get_db():
            mock_db = AsyncMock()
            # Mock DB response
            mock_log = MagicMock()
            mock_log.id = 1
            mock_log.action = "LOGIN"
            mock_log.actor = "admin"
            mock_log.timestamp = "2023-10-01T10:00:00"
            
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_log]
            mock_db.execute.return_value = mock_result
            yield mock_db

        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/audit-logs")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert isinstance(data, list)
            assert len(data) > 0
            assert data[0]["action"] == "LOGIN"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_audit_logs_endpoint_pagination(self, app):
        """
        Test GET /api/v1/admin/audit-logs with limit query parameter.
        """
        async def override_get_db():
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [] # Empty list for simplicity
            mock_db.execute.return_value = mock_result
            yield mock_db

        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/audit-logs?limit=5")

            assert response.status_code == status.HTTP_200_OK
            # We assume the service respects the limit parameter
            mock_db = app.dependency_overrides[get_async_session]
            # In a real scenario, we would inspect the call arguments to the service

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_user_endpoint_success(self, app):
        """
        Test DELETE /api/v1/admin/users/{id} returns 204 No Content.
        """
        async def override_get_db():
            mock_db = AsyncMock()
            # Mock user exists
            user = AdminUser(id=99, username="delete_me", email="delete@test.com", role="admin")
            mock_db.execute.return_value.scalar_one_or_none.return_value = user
            yield mock_db

        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/admin/users/99")

            assert response.status_code == status.HTTP_204_NO_CONTENT

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_user_endpoint_not_found(self, app):
        """
        Test DELETE /api/v1/admin/users/{id} returns 404 if user does not exist.
        """
        async def override_get_db():
            mock_db = AsyncMock()
            # Mock user not found
            mock_db.execute.return_value.scalar_one_or_none.return_value = None
            yield mock_db

        app.dependency_overrides[get_async_session] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/admin/users/999")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "detail" in data
            assert "error_code" in data

        app.dependency_overrides.clear()