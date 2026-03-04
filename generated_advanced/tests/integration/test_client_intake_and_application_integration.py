import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.client_intake.models import Client

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeAPI:

    async def test_create_client_success(self, client: AsyncClient, valid_client_payload):
        """Test creating a client via API."""
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["id"] == 1
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert "sin" not in data  # PIPEDA: SIN must not be exposed
        assert "dob" not in data  # PIPEDA: DOB must not be exposed
        assert data["email"] == "john.doe@example.com"

    async def test_create_client_validation_error(self, client: AsyncClient):
        """Test validation error on invalid input."""
        invalid_payload = {
            "first_name": "", # Invalid
            "last_name": "Doe",
            "sin": "123",
            "email": "not-an-email"
        }
        
        response = await client.post("/api/v1/client-intake/clients", json=invalid_payload)
        assert response.status_code == 422

    async def test_create_application_workflow(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        """
        Test multi-step workflow:
        1. Create Client
        2. Create Application for that Client
        3. Verify OSFI B-20 and CMHC logic in response
        """
        # Step 1: Create Client
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        assert client_resp.status_code == 201
        client_id = client_resp.json()["id"]

        # Step 2: Create Application
        # Adjust payload to use the new client_id
        app_payload = valid_application_payload.copy()
        app_payload["client_id"] = client_id
        
        app_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        assert app_resp.status_code == 201
        app_data = app_resp.json()

        # Step 3: Verify Response Data
        assert app_data["id"] > 0
        assert app_data["client_id"] == client_id
        assert app_data["status"] == "SUBMITTED"
        
        # Verify LTV Calculation (CMHC)
        # Loan 450k / Value 500k = 90%
        assert app_data["ltv_ratio"] == "90.00"
        assert app_data["insurance_required"] is True
        assert app_data["insurance_premium_rate"] == "0.0310" # 3.10% tier
        
        # Verify Ratios (OSFI B-20)
        # These are calculated in service, here we check they exist and are formatted
        assert "gds_ratio" in app_data
        assert "tds_ratio" in app_data
        assert Decimal(app_data["gds_ratio"]) <= Decimal("39.00")
        assert Decimal(app_data["tds_ratio"]) <= Decimal("44.00")

    async def test_create_application_gds_rejection(self, client: AsyncClient, valid_client_payload):
        """Test that application fails if GDS > 39%."""
        # Create Client
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]

        # Create Application with low income to trigger GDS failure
        # High Loan, Low Income
        payload = {
            "client_id": client_id,
            "loan_amount": "800000.00",
            "property_value": "850000.00",
            "annual_income": "50000.00", # Too low for 800k loan
            "property_tax": "5000.00",
            "heating_cost": "2000.00",
            "condo_fees": "500.00",
            "other_debts": "0.00",
            "contract_rate": "5.00"
        }

        response = await client.post("/api/v1/client-intake/applications", json=payload)
        
        # Expecting 400 Bad Request or 422 depending on implementation detail
        # Service raises GDSLimitExceededError -> handled by exception handler -> 400
        assert response.status_code == 400
        assert "GDS" in response.json()["detail"]

    async def test_get_application_by_id(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        """Test retrieving an application."""
        # Setup
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]
        
        app_payload = valid_application_payload.copy()
        app_payload["client_id"] = client_id
        app_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        app_id = app_resp.json()["id"]

        # Test Get
        get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
        assert get_resp.status_code == 200
        
        data = get_resp.json()
        assert data["id"] == app_id
        assert data["loan_amount"] == "450000.00"

    async def test_get_application_not_found(self, client: AsyncClient):
        """Test 404 when application does not exist."""
        response = await client.get("/api/v1/client-intake/applications/99999")
        assert response.status_code == 404

    async def test_fintrac_audit_fields_present(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        """Test that created_at/updated_at are present for audit trail."""
        # Create Client
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]

        # Create Application
        app_payload = valid_application_payload.copy()
        app_payload["client_id"] = client_id
        app_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        
        data = app_resp.json()
        assert "created_at" in data
        assert "updated_at" in data
        # ISO 8601 format check roughly
        assert "T" in data["created_at"]