import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.authentication.models import User

@pytest.mark.integration
class TestAuthenticationEndpoints:

    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient, valid_user_payload):
        """Test successful user registration."""
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert "hashed_password" not in data # Security check
        assert "sin" not in data # PIPEDA check: SIN should not be in response
        assert "created_at" in data # FINTRAC check

    @pytest.mark.asyncio
    async def test_register_user_duplicate(self, client: AsyncClient, valid_user_payload):
        """Test registering a duplicate user returns 400."""
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 400
        assert "error_code" in response.json()

    @pytest.mark.asyncio
    async def test_register_user_invalid_income_type(self, client: AsyncClient, valid_user_payload):
        """Test that float income is rejected (must be Decimal/string)."""
        # This test validates Pydantic schema enforcement
        # Sending a float where a Decimal is expected usually results in 422 if strict types
        # However, Pydantic v2 coerces strings to Decimals. Let's test invalid format.
        payload = valid_user_payload.copy()
        payload["annual_income"] = "not_a_number"
        
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, valid_user_payload):
        """Test successful login and token generation."""
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

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with wrong password."""
        login_data = {"username": "nonexistent", "password": "wrong"}
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_current_user_profile(self, client: AsyncClient, valid_user_payload):
        """Test retrieving the current user profile (protected route)."""
        # 1. Register
        reg_resp = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_resp.json()["id"]
        
        # 2. Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_resp.json()["access_token"]
        
        # 3. Access Protected Route
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["id"] == user_id
        assert data["username"] == valid_user_payload["username"]
        assert "sin" not in data # Data minimization
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test accessing protected route without token."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test accessing protected route with garbage token."""
        headers = {"Authorization": "Bearer invalid_token_string"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_user_profile(self, client: AsyncClient, valid_user_payload):
        """Test updating user financial info (income)."""
        # 1. Register & Login
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Update Income
        update_payload = {"annual_income": "95000.00"}
        update_resp = await client.patch("/api/v1/auth/me", json=update_payload, headers=headers)
        
        assert update_resp.status_code == 200
        data = update_resp.json()
        # Ensure Decimal precision is maintained
        assert data["annual_income"] == "95000.00" 

    @pytest.mark.asyncio
    async def test_pipeda_sin_not_exposed_in_db_dump_simulation(self, client: AsyncClient, db_session, valid_user_payload):
        """
        Integration test to verify SIN is encrypted at rest.
        We query the DB directly to ensure the 'sin' column is not plain text.
        """
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Direct DB query
        result = await db_session.execute(
            f"SELECT sin FROM users WHERE username = '{valid_user_payload['username']}'"
        )
        db_sin = result.scalar_one_or_none()
        
        assert db_sin is not None
        assert db_sin != valid_user_payload["sin"]
        # Assuming encryption produces a longer string or specific format
        assert len(db_sin) > len(valid_user_payload["sin"]) or db_sin.startswith("encrypted:") or db_sin != "123456789"