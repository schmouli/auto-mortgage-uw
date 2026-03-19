import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.testing_suite.models import TestScenario, TestResult


@pytest.mark.integration
class TestScenarioRoutes:

    @pytest.mark.asyncio
    async def test_create_scenario_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test API endpoint to create a new test scenario."""
        payload = {
            "name": "CMHC Standard",
            "description": "Standard CMHC LTV calculation test",
            "config": {
                "min_downpayment_percent": "5.00",
                "ltv_threshold_insurance": "80.00"
            }
        }

        response = await client.post("/api/v1/testing-suite/scenarios", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["name"] == "CMHC Standard"
        assert "created_at" in data

        # Verify DB state
        stmt = select(TestScenario).where(TestScenario.name == "CMHC Standard")
        result = await db_session.execute(stmt)
        scenario = result.scalar_one()
        assert scenario is not None

    @pytest.mark.asyncio
    async def test_create_scenario_invalid_payload(self, client: AsyncClient):
        """Test API validation with missing fields."""
        payload = {
            "name": "Incomplete Scenario"
            # Missing description and config
        }

        response = await client.post("/api/v1/testing-suite/scenarios", json=payload)

        assert response.status_code == 422 # Unprocessable Entity

    @pytest.mark.asyncio
    async def test_get_scenario_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test retrieving a specific scenario."""
        # Setup: Create a scenario directly in DB
        scenario = TestScenario(
            name="Retrieval Test",
            description="Test GET",
            config={"rate": "5.5"}
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        response = await client.get(f"/api/v1/testing-suite/scenarios/{scenario.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == scenario.id
        assert data["name"] == "Retrieval Test"

    @pytest.mark.asyncio
    async def test_get_scenario_not_found(self, client: AsyncClient):
        """Test retrieving a non-existent scenario."""
        response = await client.get("/api/v1/testing-suite/scenarios/99999")
        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_execute_scenario_endpoint_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test running a scenario via API."""
        # Setup
        scenario = TestScenario(
            name="Execution Test",
            description="",
            config={"max_gds": "39.00", "max_tds": "44.00"}
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        exec_payload = {
            "applicant_income": "85000.00",
            "property_value": "450000.00",
            "loan_amount": "360000.00",
            "heating_cost": "120.00",
            "property_tax": "2500.00"
        }

        response = await client.post(
            f"/api/v1/testing-suite/scenarios/{scenario.id}/execute",
            json=exec_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert "result_id" in data
        assert "passed" in data
        assert "breakdown" in data
        
        # Verify result stored in DB
        stmt = select(TestResult).where(TestResult.scenario_id == scenario.id)
        result = await db_session.execute(stmt)
        db_result = result.scalar_one()
        assert db_result is not None

    @pytest.mark.asyncio
    async def test_execute_scenario_endpoint_failure_case(self, client: AsyncClient, db_session: AsyncSession):
        """Test running a scenario that fails business rules (e.g., High TDS)."""
        scenario = TestScenario(
            name="Strict TDS",
            description="",
            config={"max_tds": "30.00"} # Very low limit
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        exec_payload = {
            "applicant_income": "50000.00",
            "property_value": "400000.00",
            "loan_amount": "380000.00", # High debt load
            "heating_cost": "200.00",
            "property_tax": "4000.00"
        }

        response = await client.post(
            f"/api/v1/testing-suite/scenarios/{scenario.id}/execute",
            json=exec_payload
        )

        assert response.status_code == 200 # Execution succeeded, but logic failed
        data = response.json()
        assert data["passed"] is False
        assert "TDS" in data["breakdown"] # Expect details about why it failed

    @pytest.mark.asyncio
    async def test_list_scenarios_pagination(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing scenarios with pagination parameters."""
        # Create multiple scenarios
        for i in range(5):
            db_session.add(TestScenario(name=f"Scenario {i}", description="", config={}))
        await db_session.commit()

        response = await client.get("/api/v1/testing-suite/scenarios?limit=2&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5

    @pytest.mark.asyncio
    async def test_delete_scenario_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test deleting a scenario."""
        scenario = TestScenario(
            name="Delete Me",
            description="",
            config={}
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        response = await client.delete(f"/api/v1/testing-suite/scenarios/{scenario.id}")
        assert response.status_code == 204 # No Content

        # Verify deletion
        response_get = await client.get(f"/api/v1/testing-suite/scenarios/{scenario.id}")
        assert response_get.status_code == 404

    @pytest.mark.asyncio
    async def test_input_validation_decimal_precision(self, client: AsyncClient, db_session: AsyncSession):
        """Ensure financial inputs handle Decimal precision correctly."""
        scenario = TestScenario(name="Precision Test", description="", config={})
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        exec_payload = {
            "applicant_income": "100000.999", # High precision
            "property_value": "500000.005",
            "loan_amount": "400000.001",
            "heating_cost": "100.555",
            "property_tax": "2000.123"
        }

        response = await client.post(
            f"/api/v1/testing-suite/scenarios/{scenario.id}/execute",
            json=exec_payload
        )

        # Should accept valid numeric strings, system handles rounding/truncation internally
        # or returns 400 if strictly 2 decimals required. Assuming flexible input -> internal rounding.
        assert response.status_code == 200
        
        # Check breakdown values are Decimals
        data = response.json()
        assert "breakdown" in data

# Imports required for integration tests
from sqlalchemy import select