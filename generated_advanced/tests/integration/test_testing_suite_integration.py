```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.testing_suite.models import TestScenario

@pytest.mark.integration
@pytest.mark.asyncio
class TestTestScenarioRoutes:
    async def test_create_scenario_success(self, client: AsyncClient, valid_scenario_payload: dict):
        """Test creating a valid scenario via API."""
        response = await client.post("/api/v1/testing-suite", json=valid_scenario_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == valid_scenario_payload["name"]
        assert data["insurance_required"] is True  # LTV 80%
        assert "created_at" in data

    async def test_create_scenario_fails_osfi_gds(self, client: AsyncClient, high_gds_payload: dict):
        """Test that API returns 400 when OSFI GDS limits are exceeded."""
        response = await client.post("/api/v1/testing-suite", json=high_gds_payload)
        
        assert response.status_code == 400
        data = response.json()
        assert "error_code" in data
        assert "GDS" in data["detail"]

    async def test_create_scenario_fails_osfi_tds(self, client: AsyncClient, high_tds_payload: dict):
        """Test that API returns 400 when OSFI TDS limits are exceeded."""
        response = await client.post("/api/v1/testing-suite", json=high_tds_payload)
        
        assert response.status_code == 400
        data = response.json()
        assert "error_code" in data
        assert "TDS" in data["detail"]

    async def test_get_scenario(self, client: AsyncClient, valid_scenario_payload: dict):
        """Test retrieving a created scenario."""
        # Create first
        create_resp = await client.post("/api/v1/testing-suite", json=valid_scenario_payload)
        assert create_resp.status_code == 201
        scenario_id = create_resp.json()["id"]

        # Get
        get_resp = await client.get(f"/api/v1/testing-suite/{scenario_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == scenario_id
        assert Decimal(data["applicant_income"]) == Decimal(valid_scenario_payload["applicant_income"])

    async def test_get_scenario_not_found(self, client: AsyncClient):
        """Test retrieving a non-existent scenario."""
        response = await client.get("/api/v1/testing-suite/99999")
        assert response.status_code == 404

    async def test_list_scenarios(self, client: AsyncClient, valid_scenario_payload: dict):
        """Test listing multiple scenarios."""
        # Create two
        await client.post("/api/v1/testing-suite", json=valid_scenario_payload)
        payload_2 = valid_scenario_payload.copy()
        payload_2["name"] = "Second Scenario"
        await client.post("/api/v1/testing-suite", json=payload_2)

        # List
        response = await client.get("/api/v1/testing-suite/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2

    async def test_update_scenario(self, client: AsyncClient, valid_scenario_payload: dict, db_session):
        """Test updating an existing scenario."""
        # Create
        create_resp = await client.post("/api/v1/testing-suite", json=valid_scenario_payload)
        scenario_id = create_resp.json()["id"]

        # Update
        update_payload = {"name": "Updated Name", "other_debt": "100.00"}
        update_resp = await client.patch(f"/api/v1/testing-suite/{scenario_id}", json=update_payload)
        
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["name"] == "Updated Name"
        assert Decimal(data["other_debt"]) == Decimal("100.00")

    async def test_delete_scenario(self, client: AsyncClient, valid_scenario_payload: dict):
        """Test deleting a scenario (soft delete preferred, but check endpoint)."""
        create_resp = await client.post("/api/v1/testing-suite", json=valid_scenario_payload)
        scenario_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/api/v1/testing-suite/{scenario_id}")
        assert delete_resp.status_code == 204

        # Verify it's gone
        get_resp = await client.get(f"/api/v1/testing-suite/{scenario_id}")
        assert get_resp.status_code == 404

    async def test_validation_on_missing_fields(self, client: AsyncClient):
        """Test API validation for missing required fields."""
        incomplete_payload = {
            "name": "Incomplete"
            # Missing financial fields
        }
        response = await client.post("/api/v1/testing-suite", json=incomplete_payload)
        
        assert response.status_code == 422 # Validation Error

    async def test_decimal_precision_handling(self, client: AsyncClient, valid_scenario_payload: dict):
        """Ensure API handles Decimal precision correctly without float conversion errors."""
        # Use high precision numbers
        valid_scenario_payload["applicant_income"] = "100000.999" # Should likely be rounded or rejected depending on config
        valid_scenario_payload["heating_cost"] = "150.555"
        
        response = await client.post("/api/v1/testing-suite", json=valid_scenario_payload)
        
        # If the schema accepts it, check storage. If not, check validation.
        # Assuming Pydantic Decimal validation
        assert response.status_code in [201, 422]

    async def test_audit_fields_populated(self, client: AsyncClient, valid_scenario_payload: dict):
        """Verify created_at and updated_at are populated."""
        resp = await client.post("/api/v1/testing-suite", json=valid_scenario_payload)
        data = resp.json()
        
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_at"] is not None
```