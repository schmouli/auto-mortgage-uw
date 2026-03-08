```python
import pytest
from httpx import AsyncClient

from mortgage_underwriting.modules.authentication.models import User
from sqlalchemy import select

@pytest.mark.integration
class TestAuthenticationRoutes:

    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient, valid_user_payload: dict):
        """
        Integration test: Register a new user via API.
        """
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["username"] == valid_user_payload["username"]
        assert data["email"] == valid_user_payload["email"]
        assert data["role"] == valid_user_payload["role"]
        
        # PII Check: SIN and DOB must NOT be in response
        assert "sin" not in data
        assert "dob" not in data
        assert "password" not in data
        assert "sin_hash" not in data
        assert "encrypted_dob" not in data

    @pytest.mark.asyncio
    async def test_register_user_duplicate(self, client: AsyncClient, valid_user_payload: dict):
        """
        Integration test: Attempt to register duplicate user.
        """
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration (should fail)
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "already exists" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_user_validation_error(self, client: AsyncClient):
        """
        Integration test: Register with invalid data (missing fields).
        """
        invalid_payload = {
            "username": "baduser",
            # Missing email, password, sin, dob
        }
        
        response = await client.post("/api/v1/auth/register", json=invalid_payload)
        assert response.status_code == 422 # Validation Error

    @pytest.mark.asyncio
    async def test_login_user_success(self, client: AsyncClient, seeded_user: User):
        """
        Integration test: Login with valid credentials.
        """
        login_payload = {
            "username": seeded_user.username,
            "password": "SecurePassword123!" # From conftest fixture
        }
        
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_user_invalid_password(self, client: AsyncClient, seeded_user: User):
        """
        Integration test: Login with wrong password.
        """
        login_payload = {
            "username": seeded_user.username,
            "password": "WrongPassword"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_payload)
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_current_user_protected(self, client: AsyncClient, seeded_user: User):
        """
        Integration test: Access protected /me endpoint with valid token.
        """
        # 1. Login to get token
        login_payload = {
            "username": seeded_user.username,
            "password": "SecurePassword123!"
        }
        login_resp = await client.post("/api/v1/auth/login", json=login_payload)
        token = login_resp.json()["access_token"]
        
        # 2. Access /me
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["username"] == seeded_user.username
        assert data["email"] == seeded_user.email
        # Ensure PII is not exposed
        assert "sin" not in data
        assert "dob" not in data

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """
        Integration test: Access protected /me endpoint without token.
        """
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """
        Integration test: Access protected /me endpoint with malformed token.
        """
        headers = {"Authorization": "Bearer invalid_token_string"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_pii_storage_in_db(self, db_session, client: AsyncClient, valid_user_payload: dict):
        """
        Regulatory Check: Verify that SIN is hashed and DOB is encrypted in the DB.
        """
        # Register via API
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Query DB directly
        result = await db_session.execute(select(User).where(User.username == valid_user_payload["username"]))
        db_user = result.scalar_one_or_none()
        
        assert db_user is not None
        
        # Verify raw data is NOT stored
        assert db_user.sin_hash != valid_user_payload["sin"]
        assert db_user.encrypted_dob != valid_user_payload["dob"]
        
        # Verify fields are populated (transformed)
        assert db_user.sin_hash is not None
        assert db_user.encrypted_dob is not None
        
        # Verify raw data is never in the model instance attributes
        assert not hasattr(db_user, 'sin')
        assert not hasattr(db_user, 'raw_dob')

    @pytest.mark.asyncio
    async def test_user_audit_fields(self, db_session, client: AsyncClient, valid_user_payload: dict):
        """
        Regulatory Check: Verify created_at and updated_at are populated.
        """
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        result = await db_session.execute(select(User).where(User.username == valid_user_payload["username"]))
        db_user = result.scalar_one_or_none()
        
        assert db_user.created_at is not None
        assert db_user.updated_at is not None
```