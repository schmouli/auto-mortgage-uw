import pytest
from httpx import AsyncClient, ASGITransport
from decimal import Decimal

from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.common.database import get_async_session

# Helper to override DB dependency in tests
async def override_get_db(session):
    yield session

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_and_retrieve_client_workflow(self, app: FastAPI, test_db_session: AsyncSession):
        # Setup Override
        app.dependency_overrides[get_async_session] = lambda: override_get_db(test_db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 1: Create Client
            payload = {
                "first_name": "Alice",
                "last_name": "Wonderland",
                "email": "alice@test.com",
                "phone_number": "4165551234",
                "date_of_birth": "1992-02-02",
                "sin": "987654321",
                "address": {
                    "street": "456 Wonderland Rd",
                    "city": "Mississauga",
                    "province": "ON",
                    "postal_code": "L5B1C2"
                }
            }
            
            response = await client.post("/api/v1/client-intake/clients", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["email"] == "alice@test.com"
            assert data["created_at"] is not None
            # PIPEDA Compliance: SIN must NOT be in response
            assert "sin" not in data
            assert "987654321" not in str(data)
            
            client_id = data["id"]

            # Step 2: Retrieve Client
            response = await client.get(f"/api/v1/client-intake/clients/{client_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["first_name"] == "Alice"
            assert "sin" not in data # PIPEDA check again

        # Cleanup
        app.dependency_overrides.clear()

    async def test_create_application_workflow(self, app: FastAPI, test_db_session: AsyncSession):
        app.dependency_overrides[get_async_session] = lambda: override_get_db(test_db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Seed a client manually (or via endpoint, let's do endpoint for realism)
            client_payload = {
                "first_name": "Bob", "last_name": "Builder", "email": "bob@test.com",
                "phone_number": "9055559876", "date_of_birth": "1980-03-03", "sin": "111222333",
                "address": {"street": "789 Construction Way", "city": "Brampton", "province": "ON", "postal_code": "L6Y0E1"}
            }
            create_resp = await client.post("/api/v1/client-intake/clients", json=client_payload)
            client_id = create_resp.json()["id"]

            # 2. Create Application
            app_payload = {
                "client_id": client_id,
                "property_address": "789 Construction Way",
                "property_value": "500000.00",
                "down_payment": "100000.00",
                "loan_amount": "400000.00",
                "employment": [
                    {
                        "employer_name": "Self Employed",
                        "position": "Contractor",
                        "years_employed": 10,
                        "annual_income": "95000.00"
                    }
                ],
                "assets": []
            }
            
            response = await client.post("/api/v1/client-intake/applications", json=app_payload)
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["status"] == "submitted" # Default status
            assert Decimal(data["loan_amount"]) == Decimal("400000.00")
            assert data["created_at"] is not None # FINTRAC Audit trail

            # 3. Verify Application Retrieval
            app_id = data["id"]
            get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
            assert get_resp.status_code == 200
            app_data = get_resp.json()
            assert app_data["client_id"] == client_id

        app.dependency_overrides.clear()

    async def test_create_application_invalid_client_id(self, app: FastAPI, test_db_session: AsyncSession):
        app.dependency_overrides[get_async_session] = lambda: override_get_db(test_db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            app_payload = {
                "client_id": 9999, # Non-existent
                "property_address": "Nowhere",
                "property_value": "100.00",
                "down_payment": "10.00",
                "loan_amount": "90.00",
                "employment": [],
                "assets": []
            }
            
            response = await client.post("/api/v1/client-intake/applications", json=app_payload)
            
            assert response.status_code == 404
            assert "client" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    async def test_validation_error_missing_fields(self, app: FastAPI, test_db_session: AsyncSession):
        app.dependency_overrides[get_async_session] = lambda: override_get_db(test_db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing email and sin
            payload = {
                "first_name": "Incomplete",
                "last_name": "Data"
            }
            
            response = await client.post("/api/v1/client-intake/clients", json=payload)
            
            assert response.status_code == 422 # Validation Error
            
            errors = response.json()["detail"]
            error_fields = [e["loc"][1] for e in errors]
            assert "email" in error_fields
            assert "sin" in error_fields

        app.dependency_overrides.clear()