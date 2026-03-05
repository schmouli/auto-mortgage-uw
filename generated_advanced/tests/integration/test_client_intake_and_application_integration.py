import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.client_intake.models import Client, Application

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_client_endpoint_success(self, client: AsyncClient, valid_client_payload):
        # Act
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        # PIPEDA Compliance Check: SIN must NOT be in response
        assert "sin" not in data
        assert "date_of_birth" not in data # Usually PII, check requirements
        assert "created_at" in data

    async def test_create_client_validation_error(self, client: AsyncClient):
        # Arrange - Invalid Email
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "not-an-email",
            "sin": "123"
        }

        # Act
        response = await client.post("/api/v1/client-intake/clients", json=payload)

        # Assert
        assert response.status_code == 422 # Unprocessable Entity

    async def test_get_client_endpoint_success(self, client: AsyncClient, valid_client_payload):
        # Arrange - Create a client first
        create_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = create_resp.json()["id"]

        # Act
        get_resp = await client.get(f"/api/v1/client-intake/clients/{client_id}")

        # Assert
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == client_id
        assert "sin" not in data

    async def test_get_client_not_found(self, client: AsyncClient):
        # Act
        response = await client.get("/api/v1/client-intake/clients/99999")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_create_application_endpoint_success(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        # Arrange - Create a client first
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]
        
        # Update application payload with the new client ID
        valid_application_payload["client_id"] = client_id

        # Act
        app_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Assert
        assert app_resp.status_code == 201
        data = app_resp.json()
        assert "id" in data
        assert data["client_id"] == client_id
        # Financial fields should be strings in JSON
        assert data["loan_amount"] == "400000.00"
        assert data["property_value"] == "500000.00"
        # Check LTV calculation (100k / 500k = 20%)
        assert data["ltv_percentage"] == "20.00"

    async def test_create_application_non_existent_client(self, client: AsyncClient, valid_application_payload):
        # Arrange
        valid_application_payload["client_id"] = 99999

        # Act
        response = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Assert
        assert response.status_code == 404
        assert "client" in response.json()["detail"].lower()

    async def test_create_application_high_ltv_rejection(self, client: AsyncClient, valid_client_payload):
        # Arrange
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]

        # Create payload with 0 down payment (100% LTV) - should be rejected
        payload = {
            "client_id": client_id,
            "property_value": "500000.00",
            "down_payment": "0.00", # Invalid
            "loan_amount": "500000.00",
            "amortization_years": 25,
            "interest_rate": "5.00",
            "income_monthly": "10000.00",
            "property_tax_monthly": "300.00",
            "heating_monthly": "150.00"
        }

        # Act
        response = await client.post("/api/v1/client-intake/applications", json=payload)

        # Assert
        # Depending on implementation, could be 422 (validation) or 400 (business logic)
        assert response.status_code in [400, 422]

    async def test_workflow_intake_to_application(self, client: AsyncClient):
        # Full workflow test
        
        # 1. Create Client
        client_payload = {
            "first_name": "Alice",
            "last_name": "Smith",
            "date_of_birth": "1985-05-15",
            "sin": "987654321",
            "email": "alice@example.com",
            "phone_number": "+14155552672",
            "address": {
                "street": "456 Elm St",
                "city": "Vancouver",
                "province": "BC",
                "postal_code": "V6A1A1"
            }
        }
        c_resp = await client.post("/api/v1/client-intake/clients", json=client_payload)
        assert c_resp.status_code == 201
        client_id = c_resp.json()["id"]

        # 2. Submit Application
        app_payload = {
            "client_id": client_id,
            "property_value": "800000.00",
            "down_payment": "160000.00", # 20% down
            "loan_amount": "640000.00",
            "amortization_years": 30,
            "interest_rate": "4.5",
            "income_monthly": "12000.00",
            "property_tax_monthly": "400.00",
            "heating_monthly": "200.00"
        }
        a_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        assert a_resp.status_code == 201
        app_data = a_resp.json()
        
        # 3. Verify Calculations
        # LTV: 640k / 800k = 80%
        assert app_data["ltv_percentage"] == "80.00"
        
        # 4. Retrieve Client's Applications (Assuming endpoint exists or check via DB)
        # For now, we verify the application ID exists
        app_id = app_data["id"]
        
        get_app = await client.get(f"/api/v1/client-intake/applications/{app_id}")
        assert get_app.status_code == 200
        assert get_app.json()["status"] == "SUBMITTED" # Default status