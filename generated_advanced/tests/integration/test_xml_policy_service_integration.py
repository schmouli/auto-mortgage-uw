import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, status
from mortgage_underwriting.modules.xml_policy.routes import router
from mortgage_underwriting.common.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture(scope="function")
def app(db_session: AsyncSession):
    """
    Create a test FastAPI app with the XML Policy router.
    Overrides the DB dependency with the test fixture.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/xml-policy", tags=["XML Policy"])
    
    # Dependency Override
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestXmlPolicyEndpoints:

    async def test_upload_and_parse_xml_success(self, app: FastAPI, valid_policy_xml):
        """
        Test full workflow: Upload XML -> Parse -> Validate -> Store -> 201 Response
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": valid_policy_xml}
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            
            assert data["policy_id"] == "POL-2023-001"
            assert data["premium"] == "8750.00" # JSON serialization of Decimal
            assert data["insurance_required"] is True
            assert "id" in data
            assert "created_at" in data

    async def test_upload_invalid_xml_returns_400(self, app: FastAPI, invalid_malformed_xml):
        """
        Test that malformed XML returns a structured 400 error.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": invalid_malformed_xml}
            )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            
            assert "detail" in data
            assert "error_code" in data
            assert "XML parsing failed" in data["detail"]

    async def test_upload_validation_error_returns_422(self, app: FastAPI, high_risk_policy_xml):
        """
        Test that business rule violations (e.g., LTV too high) return 422.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": high_risk_policy_xml}
            )
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            data = response.json()
            
            assert "LTV exceeds maximum limit" in data["detail"]

    async def test_get_policy_by_id(self, app: FastAPI, db_session: AsyncSession, valid_policy_xml):
        """
        Test retrieving a created policy by ID.
        """
        # First, create a policy
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": valid_policy_xml}
            )
            policy_id = create_resp.json()["id"]
            
            # Now retrieve it
            get_resp = await client.get(f"/api/v1/xml-policy/{policy_id}")
            
            assert get_resp.status_code == status.HTTP_200_OK
            data = get_resp.json()
            
            assert data["id"] == policy_id
            assert data["policy_id"] == "POL-2023-001"

    async def test_get_policy_not_found(self, app: FastAPI):
        """
        Test retrieving a non-existent policy returns 404.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/xml-policy/99999")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "not found" in data["detail"].lower()

    async def test_financial_data_integrity_check(self, app: FastAPI, xml_with_float_precision_error):
        """
        Integration test to ensure financial data is stored with Decimal precision
        and not truncated/rounded by the DB or API layer.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": xml_with_float_precision_error}
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            
            # Verify the API returns the exact string representation
            assert data["loan_amount"] == "100000.999"
            assert data["property_value"] == "200000.001"

    async def test_empty_xml_content_rejected(self, app: FastAPI):
        """
        Test that empty or missing XML content is rejected early.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/xml-policy/upload",
                json={"xml_content": ""}
            )
            
            # Depending on validation layer, could be 422 (Pydantic) or 400 (Logic)
            assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]