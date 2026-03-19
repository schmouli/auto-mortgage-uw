```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

from mortgage_underwriting.modules.client_intake.routes import router
from mortgage_underwriting.modules.client_intake.models import ClientApplication
from mortgage_underwriting.common.database import get_async_session

# Import shared fixtures from conftest are available automatically

@pytest.fixture(scope="function")
def app(db_session):
    """Create a test FastAPI app with the module router and overridden DB dependency."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-intake", tags=["Client Intake"])
    
    # Override the dependency to use the test session
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_application_endpoint_success(self, app: FastAPI):
        """Test full workflow: POST application -> 201 Created -> DB Record."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "loan_amount": "500000.00",
                "down_payment": "100000.00",
                "amortization_period": 25,
                "interest_rate": "4.5",
                "term_years": 5,
                "monthly_property_tax": "300.00",
                "monthly_heating_cost": "120.00",
                "other_debt_payments": "0.00",
                "applicant": {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "date_of_birth": "1985-05-15",
                    "sin": "987654321",
                    "email": "jane@example.com",
                    "phone_number": "4165551234",
                    "employment_status": "employed",
                    "annual_income": "85000.00"
                },
                "property": {
                    "address": "456 Oak Ave",
                    "city": "Vancouver",
                    "province": "BC",
                    "postal_code": "V6K1A1",
                    "property_type": "condo",
                    "property_value": "600000.00",
                    "year_built": 2015
                }
            }
            
            response = await client.post("/api/v1/client-intake/applications", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["loan_amount"] == "500000.00"
            assert data["status"] == "pending_review"
            # PIPEDA Check: SIN should NOT be in response
            assert "sin" not in data["applicant"]
            assert "sin_hash" not in data["applicant"] # Internal field usually hidden from DTO
            assert data["applicant"]["email"] == "jane@example.com"

    async def test_create_application_validation_error_missing_field(self, app: FastAPI):
        """Test input validation enforcement."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing SIN
            payload = {
                "loan_amount": "500000.00",
                "down_payment": "100000.00",
                "amortization_period": 25,
                "interest_rate": "4.5",
                "term_years": 5,
                "monthly_property_tax": "300.00",
                "monthly_heating_cost": "120.00",
                "other_debt_payments": "0.00",
                "applicant": {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "email": "jane@example.com",
                    # Missing SIN, DOB, etc
                },
                "property": {
                    "address": "456 Oak Ave",
                    "city": "Vancouver",
                    "province": "BC",
                    "postal_code": "V6K1A1",
                    "property_type": "condo",
                    "property_value": "600000.00",
                    "year_built": 2015
                }
            }
            
            response = await client.post("/api/v1/client-intake/applications", json=payload)
            
            assert response.status_code == 422
            assert "detail" in response.json()

    async def test_get_application_retrieval(self, app: FastAPI, valid_application_data):
        """Test retrieving a created application."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create
            create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_data)
            assert create_resp.status_code == 201
            app_id = create_resp.json()["id"]
            
            # 2. Retrieve
            get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
            assert get_resp.status_code == 200
            
            data = get_resp.json()
            assert data["id"] == app_id
            # Verify financial precision is maintained in response
            assert Decimal(data["loan_amount"]) == Decimal("600000.00")

    async def test_osfi_compliance_integration_high_gds(self, app: FastAPI, db_session):
        """
        Integration test for OSFI B-20.
        Attempt to create an application that mathematically fails GDS/TDS.
        The endpoint should return a 400 or specific compliance error.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Low income, high house cost
            payload = {
                "loan_amount": "800000.00",
                "down_payment": "5000.00", # Very high LTV
                "amortization_period": 30,
                "interest_rate": "5.0",
                "term_years": 5,
                "monthly_property_tax": "600.00",
                "monthly_heating_cost": "200.00",
                "other_debt_payments": "1000.00",
                "applicant": {
                    "first_name": "Risk",
                    "last_name": "Applicant",
                    "date_of_birth": "1990-01-01",
                    "sin": "111111111",
                    "email": "risk@test.com",
                    "phone_number": "4165550000",
                    "employment_status": "employed",
                    "annual_income": "40000.00" # Too low for this loan
                },
                "property": {
                    "address": "1 Expensive Way",
                    "city": "Toronto",
                    "province": "ON",
                    "postal_code": "M5H1A1",
                    "property_type": "detached",
                    "property_value": "805000.00",
                    "year_built": 2020
                }
            }
            
            response = await client.post("/api/v1/client-intake/applications", json=payload)
            
            # Expect rejection due to OSFI compliance rules
            assert response.status_code == 400
            data = response.json()
            assert "error_code" in data
            # Verify it's a compliance error, not a generic server error
            assert "compliance" in data["detail"].lower() or "gds" in data["detail"].lower() or "tds" in data["detail"].lower()

    async def test_list_applications_empty(self, app: FastAPI):
        """Test listing applications when none exist."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/client-intake/applications")
            assert response.status_code == 200
            assert response.json() == []

    async def test_list_applications_pagination(self, app: FastAPI, valid_application_data):
        """Test listing applications with limit/offset (if implemented) or basic listing."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create 2 apps
            await client.post("/api/v1/client-intake/applications", json=valid_application_data)
            await client.post("/api/v1/client-intake/applications", json=valid_application_data)
            
            response = await client.get("/api/v1/client-intake/applications")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    async def test_fintrac_audit_trail_immutability(self, app: FastAPI, valid_application_data):
        """
        Test that created_at and created_by are present and immutable.
        Note: Testing immutability strictly requires trying to update via ORM or API 
        and verifying it fails or is ignored. Here we verify presence.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_data)
            data = create_resp.json()
            
            assert "created_at" in data
            assert "updated_at" in data
            assert "created_by" in data # Assuming system or user ID
            
            # Verify format (ISO 8601)
            assert "T" in data["created_at"]
```