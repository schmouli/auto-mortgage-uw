```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.authentication.models import User

@pytest.mark.integration
class TestAuthenticationRoutes:

    @pytest.mark.asyncio
    async def test_register_user_creates_encrypted_record(self, client: AsyncClient, db_session):
        """
        Test registration endpoint ensures data is stored and PII is encrypted.
        """
        payload = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "ComplexPass123!",
            "sin": "987654321",
            "dob": "1992-12-12",
            "annual_income": "95000.00" # String representation of Decimal
        }

        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert "id" in data
        # PIPEDA Check: Ensure SIN and DOB are NOT in the response
        assert "sin" not in data
        assert "dob" not in data
        assert "hashed_password" not in data

        # Verify Database State
        result = await db_session.execute(
            f"SELECT sin_encrypted, dob_encrypted, hashed_password FROM users WHERE username = 'newuser'"
        )
        db_record = result.one()

        # Verify encryption happened (value is not the raw input)
        assert db_record.sin_encrypted != "987654321"
        assert db_record.dob_encrypted != "1992-12-12"
        # Verify password hashing happened
        assert db_record.hashed_password != "ComplexPass123!"
        assert db_record.hashed_password.startswith("$2b$") # Bcrypt hash prefix

    @pytest.mark.asyncio
    async def test_register_duplicate_username_returns_400(self, client: AsyncClient, async_existing_user: User):
        """
        Test that registering a duplicate username returns a structured error.
        """
        payload = {
            "username": "existinguser", # Duplicate
            "email": "another@example.com",
            "password": "ComplexPass123!",
            "sin": "111111111",
            "dob": "1990-01-01",
            "annual_income": "50000.00"
        }

        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 400
        # Check structured error response
        assert "detail" in response.json()
        assert "error_code" in response.json()

    @pytest.mark.asyncio
    async def test_login_success_returns_token(self, client: AsyncClient, async_existing_user: User):
        """
        Test login with valid credentials returns a JWT token.
        """
        payload = {
            "username": "existinguser",
            "password": "Password123!"
        }

        response = await client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_returns_401(self, client: AsyncClient, async_existing_user: User):
        """
        Test login with wrong password returns 401.
        """
        payload = {
            "username": "existinguser",
            "password": "WrongPassword"
        }

        response = await client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 401
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_get_me_returns_user_without_pii(self, client: AsyncClient, async_existing_user: User):
        """
        Test retrieving the current user profile.
        1. Login to get token.
        2. Use token to hit /me.
        3. Verify PII is absent from response.
        """
        # Step 1: Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "existinguser",
            "password": "Password123!"
        })
        token = login_resp.json()["access_token"]

        # Step 2: Get /me
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)

        assert me_resp.status_code == 200
        user_data = me_resp.json()
        
        assert user_data["username"] == "existinguser"
        
        # PIPEDA Compliance: Strict check that sensitive fields are never exposed
        assert "sin" not in user_data
        assert "dob" not in user_data
        assert "sin_encrypted" not in user_data
        assert "dob_encrypted" not in user_data
        assert "hashed_password" not in user_data

    @pytest.mark.asyncio
    async def test_get_me_without_token_returns_401(self, client: AsyncClient):
        """
        Test that accessing protected endpoint without token fails.
        """
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        # FastAPI default detail for unauthorized
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_invalid_income_format_returns_422(self, client: AsyncClient):
        """
        Test validation of financial fields (Decimal requirement).
        Sending a float or garbage string should trigger validation error.
        """
        payload = {
            "username": "moneyuser",
            "email": "money@example.com",
            "password": "Pass123!",
            "sin": "123456789",
            "dob": "1990-01-01",
            "annual_income": "not_a_decimal" # Invalid format
        }

        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 422 # Unprocessable Entity
```