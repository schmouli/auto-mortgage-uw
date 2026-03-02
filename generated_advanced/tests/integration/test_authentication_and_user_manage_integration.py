import pytest
from decimal import Decimal
from httpx import AsyncClient

# Import paths based on project conventions
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthEndpoints:

    async def test_register_user_success(self, client: AsyncClient, valid_user_payload):
        """
        Test user registration endpoint ensures:
        1. User is created in DB
        2. Response does not contain PII (SIN)
        3. Response contains audit fields
        """
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        # Validate Response Structure
        assert "id" in data
        assert "username" in data
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert "annual_income" in data
        assert Decimal(data["annual_income"]) == Decimal(valid_user_payload["annual_income"])
        
        # PIPEDA Compliance: SIN must NOT be in response
        assert "sin" not in data
        assert "password" not in data
        assert "hashed_password" not in data
        
        # Audit Fields (FINTRAC/General Audit)
        assert "created_at" in data
        assert "updated_at" in data

    async def test_register_user_duplicate(self, client: AsyncClient, valid_user_payload):
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration with same data
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 400
        assert "detail" in response.json()

    async def test_register_user_invalid_decimal(self, client: AsyncClient, valid_user_payload):
        """
        Test that float or non-decimal strings for financial fields are rejected
        """
        # Violation: Float provided instead of string/decimal
        invalid_payload = valid_user_payload.copy()
        invalid_payload["annual_income"] = 95000.00 
        
        response = await client.post("/api/v1/auth/register", json=invalid_payload)
        
        # Pydantic validation error (422)
        assert response.status_code == 422

    async def test_login_success(self, client: AsyncClient, valid_user_payload):
        # Register user first
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login
        login_payload = {
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials(self, client: AsyncClient, valid_user_payload):
        # Register user
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Login with wrong password
        login_payload = {
            "username": valid_user_payload["username"],
            "password": "WrongPassword123!"
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 401
        assert "detail" in response.json()

    async def test_get_me_protected_route(self, client: AsyncClient, valid_user_payload):
        # 1. Register
        reg_resp = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_resp.json()["id"]

        # 2. Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": valid_user_payload["username"],
            "password": valid_user_payload["password"]
        })
        token = login_resp.json()["access_token"]

        # 3. Access Protected Route /me
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["id"] == user_id
        assert data["username"] == valid_user_payload["username"]
        
        # PIPEDA Compliance Check on /me endpoint
        assert "sin" not in data

    async def test_get_me_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_sin_encrypted_in_db(self, client: AsyncClient, valid_user_payload, db_session):
        """
        Direct DB check to ensure PIPEDA compliance:
        SIN is hashed and not stored in plain text.
        """
        plain_sin = valid_user_payload["sin"]
        
        # Register via API
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Query DB directly
        from sqlalchemy import select
        stmt = select(User).where(User.username == valid_user_payload["username"])
        result = await db_session.execute(stmt)
        user = result.scalar_one()
        
        assert user is not None
        # Assert SIN is NOT stored plainly
        assert user.sin != plain_sin 
        # Assert SIN hash is present
        assert user.sin_hash is not None
        # Assert hash is not the plain text
        assert user.sin_hash != plain_sin
        # Assert hash looks like a hash (length check for SHA256)
        assert len(user.sin_hash) == 64

    async def test_financial_data_precision(self, client: AsyncClient, valid_user_payload):
        """
        Ensure Decimal precision is maintained through the request/response cycle
        """
        # Specific high precision income
        valid_user_payload["annual_income"] = "123456.78"
        
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        assert response.status_code == 201
        
        data = response.json()
        # Verify precision is kept
        assert Decimal(data["annual_income"]) == Decimal("123456.78")