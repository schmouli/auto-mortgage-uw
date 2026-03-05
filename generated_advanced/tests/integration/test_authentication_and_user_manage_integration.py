import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.auth.models import User

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
class TestAuthEndpoints:
    """Integration tests for Authentication API endpoints."""

    async def test_register_user_success(self, client: AsyncClient, valid_user_payload):
        """Test successful user registration."""
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        # PIPEDA Compliance Check: Password must NEVER be in response
        assert "password" not in data
        assert "hashed_password" not in data

    async def test_register_duplicate_user_conflict(self, client: AsyncClient, valid_user_payload):
        """Test that registering a duplicate user returns 409."""
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration with same data
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_register_weak_password_rejected(self, client: AsyncClient, valid_user_payload):
        """Test that weak passwords are rejected by validation."""
        weak_payload = valid_user_payload.copy()
        weak_payload["password"] = "123" # Too short
        
        response = await client.post("/api/v1/auth/register", json=weak_payload)
        
        assert response.status_code == 422 # Validation Error

    async def test_login_success(self, client: AsyncClient, valid_user_payload):
        """Test successful login returns a token."""
        # Register first
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login
        login_data = {
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        }
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials(self, client: AsyncClient, valid_user_payload):
        """Test login with wrong password returns 401."""
        # Register first
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login with wrong password
        login_data = {
            "username": valid_user_payload["username"],
            "password": "WrongPassword123!"
        }
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "access_token" not in response.json()

    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """Test accessing protected route without token returns 401."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    async def test_protected_endpoint_with_valid_token(self, client: AsyncClient, valid_user_payload):
        """Test accessing protected route with valid token."""
        # Register
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login
        login_res = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_res.json()["access_token"]
        
        # Access Protected Route
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_res.status_code == 200
        data = me_res.json()
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        # Ensure no sensitive data leaks
        assert "password" not in data

    async def test_protected_endpoint_with_invalid_token(self, client: AsyncClient):
        """Test accessing protected route with garbage token returns 401."""
        headers = {"Authorization": "Bearer invalid_token_string"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401

    async def test_user_data_persisted_correctly(self, client: AsyncClient, db_session, valid_user_payload):
        """Verify database state after registration."""
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Query DB directly
        result = await db_session.execute(select(User).where(User.username == valid_user_payload["username"]))
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.email == valid_user_payload["email"]
        assert user.role == valid_user_payload["role"]
        assert user.hashed_password is not None
        assert user.hashed_password != valid_user_payload["password"] # Verify hashing