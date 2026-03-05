```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

from mortgage_underwriting.modules.xml_policy_service.routes import router
from mortgage_underwriting.modules.xml_policy_service.models import XmlPolicy
from mortgage_underwriting.common.database import get_async_session, Base

# We use an in-memory SQLite for integration tests to ensure speed and isolation
# but still test the DB interaction logic.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def app():
    """Sets up a test FastAPI app with a test database."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    
    # Create engine
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Dependency override
    async def override_get_db():
        async with async_session_maker() as session:
            yield session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/xml-policies", tags=["xml-policies"])
    app.dependency_overrides[get_async_session] = override_get_db

    yield app

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestXmlPolicyEndpoints:

    async def test_create_policy_endpoint_success(self, app: FastAPI, valid_policy_xml):
        """Test full workflow: POST request -> DB Save -> Response"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policies",
                json={"xml_content": valid_policy_xml}
            )
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["policy_name"] == "StandardResidential"
            assert data["min_credit_score"] == 680
            assert data["max_ltv"] == "80.00" # JSON serialization converts Decimal to string
            assert "created_at" in data

    async def test_create_policy_endpoint_malformed_xml(self, app: FastAPI, invalid_policy_xml):
        """Test endpoint rejection of malformed XML."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policies",
                json={"xml_content": invalid_policy_xml}
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "XmlParseError" in data["detail"] or "Failed to parse" in data["detail"]

    async def test_create_policy_endpoint_missing_content(self, app: FastAPI):
        """Test endpoint validation for missing payload."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policies",
                json={}
            )
            
            assert response.status_code == 422  # Validation Error

    async def test_get_policy_endpoint_success(self, app: FastAPI, valid_policy_xml):
        """Test retrieving a previously created policy."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create
            create_resp = await client.post(
                "/api/v1/xml-policies",
                json={"xml_content": valid_policy_xml}
            )
            policy_id = create_resp.json()["id"]

            # 2. Get
            get_resp = await client.get(f"/api/v1/xml-policies/{policy_id}")
            
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["id"] == policy_id
            assert data["content"] == valid_policy_xml

    async def test_get_policy_endpoint_not_found(self, app: FastAPI):
        """Test 404 when policy does not exist."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/xml-policies/99999")
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()

    async def test_list_policies_endpoint(self, app: FastAPI, valid_policy_xml):
        """Test listing all policies."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create a couple
            await client.post("/api/v1/xml-policies", json={"xml_content": valid_policy_xml})
            await client.post("/api/v1/xml-policies", json={"xml_content": valid_policy_xml})

            # List
            response = await client.get("/api/v1/xml-policies")
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert len(data["items"]) >= 2

    async def test_update_policy_endpoint(self, app: FastAPI, valid_policy_xml):
        """Test updating an existing policy."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create
            create_resp = await client.post(
                "/api/v1/xml-policies",
                json={"xml_content": valid_policy_xml}
            )
            policy_id = create_resp.json()["id"]

            # Update
            updated_xml = valid_policy_xml.replace("StandardResidential", "UpdatedPolicy")
            update_resp = await client.put(
                f"/api/v1/xml-policies/{policy_id}",
                json={"xml_content": updated_xml}
            )

            assert update_resp.status_code == 200
            data = update_resp.json()
            assert data["policy_name"] == "UpdatedPolicy"
            # Check audit field
            assert data["updated_at"] != create_resp.json()["updated_at"]
```