```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy import select

from mortgage_underwriting.modules.auth_user.models import User
from mortgage_underwriting.modules.auth_user.routes import router
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.security import get_password_hash

# Import test session fixture
from conftest import test_session

@pytest.fixture
def app(test_session):
    """Create a test FastAPI app with the auth router."""
    app = FastAPI()
    
    # Dependency override to use the test session
    async def override_get_async_session():
        yield test_session

    app.include_router(router, prefix="/api/v1/auth", tags=["auth"])
    app.dependency_overrides[get_async_session] = override_get_async_session
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_user_integration(app, user_payload):
    # Arrange
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Act
        response = await client.post("/api/v1/auth/register", json=user_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_payload["email"]
        assert "id" in data
        assert "password" not in data
        
        # PIPEDA Check: SIN must NOT be in the response
        assert "sin" not in data
        assert "encrypted_sin" not in data
        
        # Verify in DB
        # Note: We need the session from the fixture, but the fixture is in conftest.py
        # In a real setup, we would inject the session or query via a separate client.
        # Here we verify the response contract primarily.

@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_user_duplicate_email_integration(app, user_payload, test_session):
    # Arrange - Pre-seed DB
    existing_user = User(
        email=user_payload["email"],
        hashed_password="hash",
        first_name="Existing",
        last_name="User",
        encrypted_sin="hash",
        dob="1990-01-01",
        role="underwriter"
    )
    test_session.add(existing_user)
    await test_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Act
        response = await client.post("/api/v1/auth/register", json=user_payload)

        # Assert
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_user_integration(app, user_payload, test_session):
    # Arrange - Create user first
    # We manually hash to simulate what the registration endpoint would do
    hashed_pw = get_password_hash(user_payload["password"])
    new_user = User(
        email=user_payload["email"],
        hashed_password=hashed_pw,
        first_name=user_payload["first_name"],
        last_name=user_payload["last_name"],
        encrypted_sin="dummy_encrypted_sin",
        dob=user_payload["dob"],
        role=user_payload["role"]
    )
    test_session.add(new_user)
    await test_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Act
        login_data = {"email": user_payload["email"], "password": user_payload["password"]}
        response = await client.post("/api/v1/auth/login", json=login_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_user_wrong_password_integration(app, user_payload, test_session):
    # Arrange
    hashed_pw = get_password_hash(user_payload["password"])
    new_user = User(
        email=user_payload["email"],
        hashed_password=hashed_pw,
        first_name="Test",
        last_name="User",
        encrypted_sin="hash",
        dob="1980-01-01",
        role="underwriter"
    )
    test_session.add(new_user)
    await test_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Act
        login_data = {"email": user_payload["email"], "password": "WrongPassword"}
        response = await client.post("/api/v1/auth/login", json=login_data)

        # Assert
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_me_protected_route_integration(app, user_payload, test_session):
    # Arrange - Create User
    hashed_pw = get_password_hash(user_payload["password"])
    new_user = User(
        email=user_payload["email"],
        hashed_password=hashed_pw,
        first_name=user_payload["first_name"],
        last_name=user_payload["last_name"],
        encrypted_sin="hash",
        dob=user_payload["dob"],
        role=user_payload["role"]
    )
    test_session.add(new_user)
    await test_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login to get token
        login_resp = await client.post("/api/v1/auth/login", json={"email": user_payload["email"], "password": user_payload["password"]})
        token = login_resp.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}

        # Act - Access protected route
        # Assuming a /me endpoint exists in the auth router
        me_resp = await client.get("/api/v1/auth/me", headers=headers)

        # Assert
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["email"] == user_payload["email"]
        # PIPEDA Check: Ensure SIN is not exposed
        assert "sin" not in data
        assert "encrypted_sin" not in data

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_me_unauthorized_integration(app):
    # Arrange
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Act - Access protected route without token
        me_resp = await client.get("/api/v1/auth/me")

        # Assert
        assert me_resp.status_code == 401
```