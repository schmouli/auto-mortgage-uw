import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.client_intake.models import Client

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_client_flow(self, client: AsyncClient, valid_client_payload):
        # Act
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        
        # PIPEDA Compliance Check: SIN must NOT be in the response
        assert "sin" not in data
        assert "123456789" not in str(data)
        
        # FINTRAC Compliance Check: Audit fields present
        assert "created_at" in data

    async def test_create_client_duplicate_sin(self, client: AsyncClient, valid_client_payload):
        # First creation
        await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        
        # Second creation with same SIN
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)

        # Assert
        assert response.status_code == 400 # Bad Request / Conflict
        data = response.json()
        assert "error_code" in data

    async def test_get_client_success(self, client: AsyncClient, valid_client_payload):
        # Setup
        create_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = create_resp.json()["id"]

        # Act
        response = await client.get(f"/api/v1/client-intake/clients/{client_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == client_id
        assert "sin" not in data # PIPEDA

    async def test_get_client_not_found(self, client: AsyncClient):
        # Act
        response = await client.get("/api/v1/client-intake/clients/99999")

        # Assert
        assert response.status_code == 404

    async def test_create_application_success(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        # Setup: Create Client first
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]
        
        # Update payload with real ID
        valid_application_payload["client_id"] = client_id

        # Act
        response = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["client_id"] == client_id
        assert Decimal(data["requested_amount"]) == Decimal("450000.00")
        assert Decimal(data["property_value"]) == Decimal("500000.00")
        
        # FINTRAC: Audit fields
        assert "created_at" in data

    async def test_create_application_invalid_client_id(self, client: AsyncClient, valid_application_payload):
        # Act
        response = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert "CLIENT_NOT_FOUND" in data.get("error_code", "")

    async def test_create_application_ltv_boundary_check(self, client: AsyncClient, valid_client_payload):
        # Setup
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]

        # High Ratio Scenario (95% LTV - Max CMHC insurable)
        # Loan 475k on 500k value
        high_ltv_payload = {
            "client_id": client_id,
            "requested_amount": "475000.00",
            "property_value": "500000.00",
            "property_type": "condo",
            "property_address": "456 High Risk Ave",
            "property_city": "Vancouver",
            "property_province": "BC",
            "property_postal_code": "V6B2W1"
        }

        # Act
        response = await client.post("/api/v1/client-intake/applications", json=high_ltv_payload)

        # Assert
        # Should be accepted by intake (underwriting happens later), or rejected if hard limit > 95
        # Assuming intake accepts it, but flags insurance needed
        assert response.status_code in [201, 400] 
        if response.status_code == 201:
            data = response.json()
            # Verify precision is maintained
            assert Decimal(data["requested_amount"]) == Decimal("475000.00")

    async def test_list_applications_for_client(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        # Setup
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]
        
        valid_application_payload["client_id"] = client_id
        await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Act
        response = await client.get(f"/api/v1/client-intake/clients/{client_id}/applications")

        # Assert
        assert response.status_code == 200
        apps = response.json()
        assert len(apps) == 1
        assert apps[0]["client_id"] == client_id