import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.frontend_react_ui.models import UIConfig
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
class TestFrontendRoutes:

    async def test_calculate_prequalification_endpoint(self, client: AsyncClient):
        """
        Integration test for the prequalification calculator endpoint.
        Verifies request/response contract and OSFI B-20 compliance.
        """
        response = await client.post(
            "/api/v1/frontend/calculate",
            json={
                "annual_income": "85000.00",
                "property_tax": "2400.00",
                "heating_cost": "1200.00",
                "condo_fees": "0.00",
                "debt_payments": "300.00",
                "mortgage_rate": "3.5",
                "amortization_years": 25,
                "down_payment": "40000.00"
            }
        )

        assert response.status_code == 200
        data = response.json()
        
        assert "max_mortgage_amount" in data
        assert "qualifying_rate" in data
        assert "gds_ratio" in data
        assert "tds_ratio" in data
        assert "insurance_required" in data
        
        # Verify Decimal precision is maintained in JSON response (string representation)
        assert isinstance(data["max_mortgage_amount"], str)
        assert Decimal(data["max_mortgage_amount"]) > 0
        
        # Verify qualifying rate logic (Contract 3.5 + 2 = 5.5 > 5.25)
        assert Decimal(data["qualifying_rate"]) == Decimal("5.50")

    async def test_calculate_prequalification_invalid_input(self, client: AsyncClient):
        """
        Test validation error handling for malformed requests.
        """
        response = await client.post(
            "/api/v1/frontend/calculate",
            json={
                "annual_income": "-50000", # Negative income
                "mortgage_rate": "3.5",
                "amortization_years": 30
            }
        )

        assert response.status_code == 422 # Unprocessable Entity

    async def test_get_ui_config_default(self, client: AsyncClient):
        """
        Test retrieving default UI configuration when no user-specific config exists.
        """
        response = await client.get(
            "/api/v1/frontend/config",
            params={"user_id": "new_user_999"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "light" # Default
        assert data["language"] == "en-CA" # Default

    async def test_save_and_retrieve_ui_config(self, client: AsyncClient, db_session):
        """
        Multi-step workflow: Save config, then retrieve it to verify persistence.
        """
        user_id = "integration_test_user"
        
        # Step 1: Save Config
        save_response = await client.post(
            "/api/v1/frontend/config",
            json={
                "user_id": user_id,
                "theme": "dark",
                "language": "fr-CA",
                "notifications_enabled": False
            }
        )
        assert save_response.status_code == 201

        # Step 2: Retrieve Config
        get_response = await client.get(
            "/api/v1/frontend/config",
            params={"user_id": user_id}
        )
        assert get_response.status_code == 200
        data = get_response.json()
        
        assert data["theme"] == "dark"
        assert data["language"] == "fr-CA"
        assert data["notifications_enabled"] is False

    async def test_update_existing_config(self, client: AsyncClient, db_session):
        """
        Test updating an existing configuration record.
        """
        user_id = "update_test_user"
        
        # Initial creation
        await client.post(
            "/api/v1/frontend/config",
            json={"user_id": user_id, "theme": "light", "language": "en-CA"}
        )

        # Update
        update_response = await client.put(
            f"/api/v1/frontend/config/{user_id}",
            json={"theme": "high_contrast", "language": "en-CA"}
        )
        assert update_response.status_code == 200
        
        # Verify update
        get_response = await client.get(
            "/api/v1/frontend/config",
            params={"user_id": user_id}
        )
        data = get_response.json()
        assert data["theme"] == "high_contrast"

    async def test_health_check_endpoint(self, client: AsyncClient):
        """
        Test the health check endpoint used by the React frontend.
        """
        response = await client.get("/api/v1/frontend/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "frontend-adapter"}

    async def test_get_provinces_list(self, client: AsyncClient):
        """
        Test retrieval of static data (Provinces) for dropdowns.
        Ensures data minimization (only code and name).
        """
        response = await client.get("/api/v1/frontend/static-data/provinces")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify structure
        assert "code" in data[0]
        assert "name" in data[0]
        # Ensure no sensitive data is leaked
        assert "tax_rate" not in data[0] 

    async def test_calculate_with_high_ltv_triggers_insurance(self, client: AsyncClient):
        """
        Test CMHC logic: Low down payment (High LTV) should trigger insurance requirement.
        """
        response = await client.post(
            "/api/v1/frontend/calculate",
            json={
                "annual_income": "100000.00",
                "property_tax": "3000.00",
                "heating_cost": "1000.00",
                "condo_fees": "0.00",
                "debt_payments": "0.00",
                "mortgage_rate": "4.0",
                "amortization_years": 25,
                "down_payment": "5000.00" # Very low down payment
            }
        )

        assert response.status_code == 200
        data = response.json()
        # LTV > 80% logic check
        assert data["insurance_required"] is True
        # Check if premium rate is applied (approximate check)
        assert Decimal(data["insurance_premium"]) > Decimal("0.00")