```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from mortgage_underwriting.modules.decision_service.models import Decision
from mortgage_underwriting.common.database import get_async_session

# Dependency override for testing
async def override_get_db():
    try:
        # This relies on the db_session fixture from conftest
        # However, in integration tests we often need to bind the override manually
        # or use the fixture directly within the test if the app allows.
        # Here we assume a global override or a mechanism to inject the session.
        # For simplicity in this pattern, we will assume the test client 
        # interacts with the app which uses the override_get_db.
        yield None 
    finally:
        pass

@pytest.mark.integration
@pytest.mark.asyncio
class TestDecisionEndpoints:

    async def test_create_decision_approve(self, client: AsyncClient, valid_application_payload):
        response = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["decision"] == "Approved"
        assert "id" in data
        assert "gds_ratio" in data
        assert "tds_ratio" in data
        assert "ltv_ratio" in data
        assert data["insurance_required"] == False
        # Verify Decimal precision is preserved (returned as string in JSON usually)
        assert data["ltv_ratio"] == "80.00"

    async def test_create_decision_decline_gds(self, client: AsyncClient, high_gds_payload):
        response = await client.post("/api/v1/decision/evaluate", json=high_gds_payload)
        
        assert response.status_code == 200 # Business logic decline, not HTTP error
        data = response.json()
        
        assert data["decision"] == "Declined"
        assert "GDS" in data["decline_reason"]
        assert float(data["gds_ratio"]) > 39.0

    async def test_create_decision_decline_ltv(self, client: AsyncClient, high_ltv_payload):
        response = await client.post("/api/v1/decision/evaluate", json=high_ltv_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["decision"] == "Declined"
        assert "LTV" in data["decline_reason"]

    async def test_create_decision_insurance_required(self, client: AsyncClient, valid_application_payload):
        # Modify payload slightly to trigger insurance tier 1
        payload = valid_application_payload.copy()
        payload["loan_amount"] = "405000.00" # 81% LTV
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["decision"] == "Approved"
        assert data["insurance_required"] == True
        assert data["insurance_premium_rate"] == "2.80"

    async def test_invalid_input_missing_field(self, client: AsyncClient):
        invalid_payload = {
            "applicant_id": "test",
            # Missing loan_amount
            "property_value": "500000.00"
        }
        
        response = await client.post("/api/v1/decision/evaluate", json=invalid_payload)
        
        assert response.status_code == 422 # Validation Error
        assert "detail" in response.json()

    async def test_invalid_input_wrong_type(self, client: AsyncClient, valid_application_payload):
        payload = valid_application_payload.copy()
        payload["annual_income"] = "not_a_number"
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        
        assert response.status_code == 422

    async def test_get_decision_history(self, client: AsyncClient, valid_application_payload):
        # First, create a decision
        post_resp = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        assert post_resp.status_code == 200
        app_id = post_resp.json()["applicant_id"]
        
        # Then, retrieve history
        get_resp = await client.get(f"/api/v1/decision/applicant/{app_id}")
        
        assert get_resp.status_code == 200
        history = get_resp.json()
        assert len(history) >= 1
        assert history[0]["applicant_id"] == app_id

    async def test_pii_not_exposed_in_response(self, client: AsyncClient, valid_application_payload):
        response = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        data = response.json()
        
        # Ensure raw SIN and DOB are not in the response
        assert "sin" not in data
        assert "dob" not in data
        
        # If they exist, they should be masked or hashed
        # (e.g. "***-***-***" or a hash string, but never the raw input)
        assert data.get("sin_masked") != valid_application_payload["sin"]

    async def test_stress_test_logic_endpoint(self, client: AsyncClient):
        # Low rate (3%) should trigger floor (5.25%)
        payload = {
            "applicant_id": "stress-test-1",
            "loan_amount": "400000.00",
            "property_value": "500000.00",
            "annual_income": "120000.00",
            "monthly_property_tax": "300.00",
            "monthly_heating_cost": "150.00",
            "monthly_strata_fees": "0.00",
            "other_debt_obligations": "0.00",
            "contract_rate": "3.0", # Low rate
            "amortization_years": 25,
            "sin": "000000000",
            "dob": "1990-01-01"
        }
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        data = response.json()
        
        # 3.0 + 2 = 5.0. Floor is 5.25. Qualifying rate must be 5.25.
        assert data["qualifying_rate"] == "5.25"

    async def test_concurrent_requests_handling(self, client: AsyncClient, valid_application_payload):
        # Simple check to ensure the app handles async requests without crashing
        # (Detailed concurrency testing would require more setup)
        import asyncio
        
        async def make_request():
            return await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        
        results = await asyncio.gather(make_request(), make_request(), make_request())
        
        for r in results:
            assert r.status_code == 200
```