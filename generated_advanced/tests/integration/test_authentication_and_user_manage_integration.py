import pytest
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.authentication.models import User

@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthenticationFlow:

    async def test_register_user_creates_record(self, client: AsyncClient, db_session: AsyncSession, valid_user_payload):
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert "id" in data
        
        # PIPEDA Check: Ensure password is NOT in response
        assert "password" not in data
        assert "hashed_password" not in data
        
        # Verify Database State
        stmt = select(User).where(User.username == valid_user_payload["username"])
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()
        
        assert user is not None
        assert user.email == valid_user_payload["email"]
        assert user.hashed_password is not None
        assert user.hashed_password != valid_user_payload["password"]
        
        # FINTRAC/OSFI: Audit fields exist
        assert user.created_at is not None

    async def test_register_duplicate_fails_409(self, client: AsyncClient, valid_user_payload):
        # First request
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Duplicate request
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 409
        assert "detail" in response.json()

    async def test_login_success_returns_token(self, client: AsyncClient, seeded_user):
        login_payload = {
            "username": seeded_user.username,
            "password": "ExistingPass123!"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials_401(self, client: AsyncClient, seeded_user):
        login_payload = {
            "username": seeded_user.username,
            "password": "WrongPassword"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 401
        # Ensure error structure matches standard
        assert "detail" in response.json()

    async def test_protected_endpoint_with_valid_token(self, client: AsyncClient, seeded_user):
        # 1. Login to get token
        login_res = await client.post("/api/v1/auth/login", json={
            "username": seeded_user.username,
            "password": "ExistingPass123!"
        })
        token = login_res.json()["access_token"]
        
        # 2. Access protected endpoint (e.g., /users/me)
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/users/me", headers=headers)
        
        assert me_res.status_code == 200
        data = me_res.json()
        assert data["username"] == seeded_user.username
        assert "id" in data
        # PIPEDA: No sensitive audit logs or hashes in response
        assert "hashed_password" not in data

    async def test_protected_endpoint_without_token_401(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/users/me")
        
        assert response.status_code == 401

    async def test_protected_endpoint_with_invalid_token_401(self, client: AsyncClient):
        headers = {"Authorization": "Bearer invalid_token_string"}
        response = await client.get("/api/v1/auth/users/me", headers=headers)
        
        assert response.status_code == 401

    async def test_user_role_assignment(self, client: AsyncClient, admin_user_payload, db_session: AsyncSession):
        # Create an admin user
        res = await client.post("/api/v1/auth/register", json=admin_user_payload)
        assert res.status_code == 201
        
        # Verify role in DB
        stmt = select(User).where(User.username == admin_user_payload["username"])
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()
        
        assert user.role == admin_user_payload["role"]

    async def test_input_validation_missing_fields(self, client: AsyncClient):
        # Missing password
        payload = {
            "username": "incomplete",
            "email": "incomplete@example.com"
        }
        
        response = await client.post("/api/v1/auth/register", json=payload)
        
        assert response.status_code == 422  # Validation Error
        
    async def test_weak_password_rejection(self, client: AsyncClient):
        # Assuming the schema enforces strong passwords (length, complexity)
        # If not handled by Pydantic, this might pass, but let's test the contract
        payload = {
            "username": "weak_user",
            "email": "weak@example.com",
            "password": "123" # Too short/weak
        }
        
        response = await client.post("/api/v1/auth/register", json=payload)
        
        # If Pydantic regex is set in schemas.py, this is 422
        # If handled by service logic, might be 400
        # We expect validation to catch this
        assert response.status_code == 422