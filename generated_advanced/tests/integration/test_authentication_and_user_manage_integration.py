import pytest
from httpx import AsyncClient
from sqlalchemy import select
from mortgage_underwriting.modules.authentication.models import User
from mortgage_underwriting.common.security import verify_password

@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthenticationEndpoints:

    async def test_register_user_creates_record_in_db(self, client: AsyncClient, db_session, valid_user_payload):
        """
        Test the registration endpoint creates a user record with encrypted PII and hashed password.
        """
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["username"] == "jdoe"
        assert data["email"] == "john.doe@example.com"
        
        # PIPEDA Compliance: PII must NOT be in the response
        assert "sin" not in data
        assert "dob" not in data
        assert "password" not in data
        assert "hashed_password" not in data

        # Verify Database State
        stmt = select(User).where(User.username == "jdoe")
        result = await db_session.execute(stmt)
        db_user = result.scalar_one_or_none()

        assert db_user is not None
        assert db_user.username == "jdoe"
        
        # Verify password hashing
        assert verify_password("SecurePass123!", db_user.hashed_password) is True
        
        # Verify PII is encrypted in DB (PIPEDA Compliance)
        assert db_user.sin_encrypted != "123456789"
        assert db_user.dob_encrypted != "1980-01-01"
        assert db_user.sin_encrypted is not None
        assert db_user.dob_encrypted is not None

        # FINTRAC Compliance: Audit fields exist
        assert db_user.created_at is not None
        assert db_user.updated_at is not None

    async def test_register_duplicate_user_returns_400(self, client: AsyncClient, valid_user_payload):
        """
        Test that registering a duplicate user returns a 400 error.
        """
        # First registration
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Second registration (duplicate)
        response = await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    async def test_login_valid_credentials_returns_token(self, client: AsyncClient, valid_user_payload, login_payload):
        """
        Test logging in with valid credentials returns a JWT token.
        """
        # Setup: Register user first
        await client.post("/api/v1/auth/register", json=valid_user_payload)

        # Action: Login
        response = await client.post("/api/v1/auth/login", json=login_payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials_returns_401(self, client: AsyncClient, valid_user_payload):
        """
        Test logging in with invalid credentials returns 401 Unauthorized.
        """
        # Setup: Register user
        await client.post("/api/v1/auth/register", json=valid_user_payload)

        # Action: Login with wrong password
        response = await client.post("/api/v1/auth/login", json={
            "username": "jdoe",
            "password": "WrongPassword!"
        })

        assert response.status_code == 401
        # Ensure error code is present for structured error handling
        assert "error_code" in response.json()

    async def test_get_user_profile_returns_sanitized_data(self, client: AsyncClient, valid_user_payload, db_session):
        """
        Test retrieving a user profile via API excludes sensitive PII.
        """
        # Setup: Register user
        reg_resp = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_resp.json()["id"]

        # Login to get token
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "jdoe",
            "password": "SecurePass123!"
        })
        token = login_resp.json()["access_token"]

        # Action: Get User Profile
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get(f"/api/v1/auth/users/{user_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        
        # Verify non-sensitive fields
        assert data["id"] == user_id
        assert data["username"] == "jdoe"
        assert data["email"] == "john.doe@example.com"
        
        # PIPEDA Compliance: Strict check that PII is absent
        assert "sin" not in data
        assert "dob" not in data
        assert "hashed_password" not in data
        assert "sin_encrypted" not in data
        assert "dob_encrypted" not in data

    async def test_get_user_profile_unauthorized_without_token(self, client: AsyncClient, valid_user_payload):
        """
        Test accessing profile without token returns 401.
        """
        reg_resp = await client.post("/api/v1/auth/register", json=valid_user_payload)
        user_id = reg_resp.json()["id"]

        response = await client.get(f"/api/v1/auth/users/{user_id}")
        assert response.status_code == 401

    async def test_update_user_last_login(self, client: AsyncClient, valid_user_payload, db_session):
        """
        Test that login updates the audit trail (last_login_at).
        """
        # Setup
        await client.post("/api/v1/auth/register", json=valid_user_payload)
        
        # Check initial state
        stmt = select(User).where(User.username == "jdoe")
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()
        initial_last_login = user.last_login_at

        # Action
        await client.post("/api/v1/auth/login", json={
            "username": "jdoe",
            "password": "SecurePass123!"
        })

        # Verify update
        await db_session.refresh(user)
        # Assuming the service updates last_login_at on successful auth
        # If the field exists in model, it should be updated
        if hasattr(user, 'last_login_at'):
            assert user.last_login_at is not None
            if initial_last_login:
                assert user.last_login_at > initial_last_login