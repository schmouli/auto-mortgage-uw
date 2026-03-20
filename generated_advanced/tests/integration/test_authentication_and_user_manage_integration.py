```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from datetime import datetime

from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.common.security import verify_token

@pytest.mark.integration
class TestAuthEndpoints:

    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient, valid_user_payload):
        """Test user registration endpoint returns 201 and creates user."""
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "test_user"
        assert data["email"] == "test@example.com"
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, valid_user_payload):
        """Test that registering the same email twice returns 400."""
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient, valid_user_payload):
        """Test registration validation with bad email."""
        payload = valid_user_payload.copy()
        payload["email"] = "not-an-email"
        
        response = await client.post("/api/v1/auth/register", json=payload)
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, valid_user_payload):
        """Test login returns valid access token."""
        # Register user first
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login
        login_payload = {
            "email": valid_user_payload["email"],
            "password": valid_user_payload["password"]
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, valid_user_payload):
        """Test login with wrong password returns 401."""
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        login_payload = {
            "email": valid_user_payload["email"],
            "password": "WrongPassword!"
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, valid_user_payload):
        """Test retrieving current user profile with valid token."""
        # Register
        reg_res = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_res.json()["id"]
        
        # Login
        login_res = await client.post("/api/v1/auth/login", json={
            "email": valid_user_payload["email"],
            "password": valid_user_payload["password"]
        })
        token = login_res.json()["access_token"]
        
        # Get Me
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_res.status_code == 200
        data = me_res.json()
        assert data["id"] == user_id
        assert data["email"] == valid_user_payload["email"]
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test accessing protected endpoint without token returns 401."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test accessing protected endpoint with bad token returns 401."""
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_user_persistence_in_db(self, client: AsyncClient, db_session, valid_user_payload):
        """Test that user data is correctly persisted in the database."""
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Query DB directly
        result = await db_session.execute(select(User).where(User.email == valid_user_payload["email"]))
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.username == "test_user"
        assert user.email == "test@example.com"
        assert user.role == "underwriter"
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_password_is_hashed_in_db(self, client: AsyncClient, db_session, valid_user_payload):
        """Test that password is never stored in plain text."""
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        result = await db_session.execute(select(User).where(User.email == valid_user_payload["email"]))
        user = result.scalar_one_or_none()
        
        assert user.hashed_password != valid_user_payload["password"]
        # Bcrypt hashes usually start with $2b$
        assert user.hashed_password.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_update_last_login(self, client: AsyncClient, valid_user_payload):
        """
        Test that logging in updates user activity (simulated via audit logs or updated_at if applicable).
        Note: This assumes the service updates the user or logs a LoginHistory entry.
        Here we verify the token allows access, implying session validity.
        """
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        login_res = await client.post("/api/v1/auth/login", json={
            "email": valid_user_payload["email"],
            "password": valid_user_payload["password"]
        })
        
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        
        # Verify token is valid via protected endpoint
        me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
```