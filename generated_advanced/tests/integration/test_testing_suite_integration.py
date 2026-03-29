```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.testing_suite.models import TestScenario

@pytest.mark.integration
@pytest.mark.asyncio
class TestScenarioEndpoints:
    """Tests for the API endpoints of the Testing Suite module."""

    async def test_create_scenario_endpoint_success(self, client: AsyncClient, valid_scenario_payload):
        response = await client.post("/api/v1/testing-suite/scenarios", json=valid_scenario_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == valid_scenario_payload["name"]
        assert data["borrower_annual_income"] == valid_scenario_payload["borrower_annual_income"]
        assert "created_at" in data

    async def test_create_scenario_endpoint_invalid_data(self, client: AsyncClient):
        invalid_payload = {
            "name": "Bad Data",
            "borrower_annual_income": "not_a_number"
        }
        
        response = await client.post("/api/v1/testing-suite/scenarios", json=invalid_payload)
        
        assert response.status_code == 422 # Unprocessable Entity

    async def test_get_scenario_endpoint(self, client: AsyncClient, valid_scenario_payload, db_session):
        # Create a scenario directly in DB to test GET
        scenario = TestScenario(
            name=valid_scenario_payload["name"],
            description=valid_scenario_payload["description"],
            borrower_annual_income=Decimal(valid_scenario_payload["borrower_annual_income"]),
            property_value=Decimal(valid_scenario_payload["property_value"]),
            loan_amount=Decimal(valid_scenario_payload["loan_amount"]),
            contract_rate=Decimal(valid_scenario_payload["contract_rate"]),
            property_tax_annual=Decimal(valid_scenario_payload["property_tax_annual"]),
            heating_cost_monthly=Decimal(valid_scenario_payload["heating_cost_monthly"]),
            other_debt_monthly=Decimal(valid_scenario_payload["other_debt_monthly"])
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        response = await client.get(f"/api/v1/testing-suite/scenarios/{scenario.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == scenario.id
        assert Decimal(data["loan_amount"]) == scenario.loan_amount

    async def test_get_scenario_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/testing-suite/scenarios/99999")
        assert response.status_code == 404

    async def test_run_stress_test_workflow(self, client: AsyncClient, valid_scenario_payload):
        # 1. Create Scenario
        create_resp = await client.post("/api/v1/testing-suite/scenarios", json=valid_scenario_payload)
        assert create_resp.status_code == 201
        scenario_id = create_resp.json()["id"]

        # 2. Run Stress Test
        run_resp = await client.post(f"/api/v1/testing-suite/scenarios/{scenario_id}/run")
        assert run_resp.status_code == 200
        
        result = run_resp.json()
        assert "gds_ratio" in result
        assert "tds_ratio" in result
        assert "qualifying_rate" in result
        assert "is_approved" in result
        
        # Verify OSFI B-20 logic result (should pass with valid payload)
        assert result["is_approved"] is True
        
        # Verify qualifying rate logic (Contract 4.5 + 2 = 6.5 > 5.25)
        assert Decimal(result["qualifying_rate"]) == Decimal("6.50")

    async def test_run_stress_test_fails_regulatory_check(self, client: AsyncClient, high_risk_scenario_payload):
        # 1. Create High Risk Scenario
        create_resp = await client.post("/api/v1/testing-suite/scenarios", json=high_risk_scenario_payload)
        assert create_resp.status_code == 201
        scenario_id = create_resp.json()["id"]

        # 2. Run Stress Test
        run_resp = await client.post(f"/api/v1/testing-suite/scenarios/{scenario_id}/run")
        
        # Expecting a 400 or specific error code for regulatory failure
        assert run_resp.status_code == 400
        data = run_resp.json()
        assert "detail" in data
        assert "limit" in data["detail"].lower()

    async def test_list_scenarios_pagination(self, client: AsyncClient, valid_scenario_payload, db_session):
        # Create multiple scenarios
        for i in range(3):
            scenario = TestScenario(
                name=f"Scenario {i}",
                description="Batch test",
                borrower_annual_income=Decimal("100000.00"),
                property_value=Decimal("400000.00"),
                loan_amount=Decimal("300000.00"),
                contract_rate=Decimal("3.00"),
                property_tax_annual=Decimal("2000.00"),
                heating_cost_monthly=Decimal("100.00"),
                other_debt_monthly=Decimal("0.00")
            )
            db_session.add(scenario)
        await db_session.commit()

        response = await client.get("/api/v1/testing-suite/scenarios?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 3
```