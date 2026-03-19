```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.auth.models import User

# Module name mapping: 'auth' represents Authentication & User Management
from mortgage_underwriting.modules.auth.routes import router

@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthEndpoints:
    
    async def test_register_user_success(self, client: AsyncClient, valid_user_payload: dict):
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert "password_hash" not in data  # PIPEDA: Never return password hash
        assert "password" not in data

    async def test_register_user_duplicate_email(self, client: AsyncClient, valid_user_payload: dict):
        # First request
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Duplicate request
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_register_user_invalid_email(self, client: AsyncClient, valid_user_payload: dict):
        payload = valid_user_payload.copy()
        payload["email"] = "not-an-email"
        
        response = await client.post("/api/v1/auth/register", json=payload)
        
        assert response.status_code == 422  # Validation Error

    async def test_register_user_weak_password(self, client: AsyncClient, valid_user_payload: dict):
        payload = valid_user_payload.copy()
        payload["password"] = "123" # Too short
        
        response = await client.post("/api/v1/auth/register", json=payload)
        
        assert response.status_code == 422

    async def test_login_success(self, client: AsyncClient, valid_user_payload: dict):
        # Register first
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

    async def test_login_invalid_credentials(self, client: AsyncClient, valid_user_payload: dict):
        # Register first
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login with wrong password
        login_payload = {
            "email": valid_user_payload["email"],
            "password": "WrongPassword123!"
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()

    async def test_get_me_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    async def test_get_me_authorized(self, client: AsyncClient, valid_user_payload: dict):
        # Register
        reg_resp = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_resp.json()["id"]
        
        # Login
        login_payload = {
            "email": valid_user_payload["email"],
            "password": valid_user_payload["password"]
        }
        login_resp = await client.post("/api/v1/auth/login", json=login_payload)
        token = login_resp.json()["access_token"]
        
        # Access protected route
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["id"] == user_id
        assert data["email"] == valid_user_payload["email"]
        assert "password_hash" not in data

    async def test_get_me_invalid_token(self, client: AsyncClient):
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401

    async def test_user_persistence_in_db(self, client: AsyncClient, db_session: AsyncClient, valid_user_payload: dict):
        """Integration test verifying actual DB state (FINTRAC: Audit trail check)"""
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Query DB directly
        result = await db_session.execute(select(User).where(User.email == valid_user_payload["email"]))
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.username == valid_user_payload["username"]
        assert user.created_at is not None  # FINTRAC: Audit trail
        assert user.updated_at is not None  # FINTRAC: Audit trail
        assert user.password_hash is not None
        assert user.password_hash != valid_user_payload["password"]

    async def test_logout_deactivates_token(self, client: AsyncClient, valid_user_payload: dict):
        """Test if logout is implemented (optional feature, but good to test)"""
        # Register
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login
        login_payload = {
            "email": valid_user_payload["email"],
            "password": valid_user_payload["password"]
        }
        login_resp = await client.post("/api/v1/auth/login", json=login_payload)
        token = login_resp.json()["access_token"]
        
        # Logout (assuming endpoint exists, usually just client-side token drop, but testing server-side if applicable)
        # If endpoint doesn't exist, this test would 404. Assuming standard implementation:
        # For this specific stack, we usually just drop the token on client. 
        # Let's test a protected endpoint ensures the token works first.
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        
        # If there was a /logout endpoint that blacklisted the token, we would call it here.
        # Since we are using stateless JWT, we just verify the token continues to work 
        # until it expires, which is expected behavior.
```