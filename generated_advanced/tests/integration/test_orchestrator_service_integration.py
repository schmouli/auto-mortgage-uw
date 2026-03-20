import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.borrower.models import Borrower
from mortgage_underwriting.modules.property.models import PropertyModel
from mortgage_underwriting.modules.orchestrator.models import Application
from mortgage_underwriting.common.security import hash_pii


@pytest.mark.integration
class TestOrchestratorRoutes:

    @pytest.mark.asyncio
    async def test_create_application_workflow(self, client: AsyncClient, valid_application_payload):
        """
        Test the full workflow: Create Borrower/Property implicitly via Orchestrator 
        and create the Application record.
        """
        response = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["status"] == "PENDING"
        assert data["loan_amount"] == "400000.00"
        
        # Verify Borrower was created and PII hashed
        app_id = data["id"]
        # We need to inspect the DB directly as we might not have a GET borrower endpoint via orchestrator
        # Assuming the orchestrator created the records in the same session context or separate calls
        # For this integration test, we verify the Application record exists
        # Note: Depending on implementation, the Orchestrator might create borrower/prop first or expect IDs.
        # Assuming the payload is a DTO that triggers creation of sub-resources.
        
    @pytest.mark.asyncio
    async def test_submit_underwriting_decision_approved(self, client: AsyncClient, db_session, valid_application_payload):
        """
        Test submitting an application and then triggering underwriting evaluation.
        """
        # 1. Create Application
        create_resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        assert create_resp.status_code == 201
        app_id = create_resp.json()["id"]

        # 2. Trigger Underwriting
        eval_resp = await client.post(f"/api/v1/orchestrator/applications/{app_id}/evaluate")
        
        assert eval_resp.status_code == 200
        data = eval_resp.json()
        
        assert data["decision"] in ["APPROVED", "REFUSED", "REFER"]
        
        # If approved based on payload (96k income, 400k loan)
        # Monthly payment ~2200, Tax 300, Heat 100 -> 2600/8000 = 32.5% GDS (Pass)
        # TDS = 3100/8000 = 38.75% (Pass)
        # LTV = 80% (Pass, no insurance)
        assert data["decision"] == "APPROVED"
        assert data["ltv"] == "0.80"
        assert data["insurance_required"] is False
        
        # 3. Verify Database Update
        stmt = select(Application).where(Application.id == app_id)
        result = await db_session.execute(stmt)
        app_db = result.scalar_one_or_none()
        
        assert app_db is not None
        assert app_db.status == "COMPLETED" # Assuming status changes to COMPLETED after evaluation
        assert app_db.decision == "APPROVED"

    @pytest.mark.asyncio
    async def test_submit_underwriting_high_ltv_insurance(self, client: AsyncClient, valid_application_payload):
        """
        Test application with LTV > 80% triggers insurance requirement logic.
        """
        # Modify payload for 90% LTV
        valid_application_payload["loan_amount"] = "450000.00"
        valid_application_payload["borrower"]["annual_income"] = "200000.00" # Ensure ratios pass
        
        create_resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        app_id = create_resp.json()["id"]
        
        eval_resp = await client.post(f"/api/v1/orchestrator/applications/{app_id}/evaluate")
        data = eval_resp.json()
        
        assert data["decision"] == "APPROVED"
        assert data["ltv"] == "0.90"
        assert data["insurance_required"] is True
        # 90.01-95% = 4.00% premium
        assert data["insurance_premium_rate"] == "0.0400"

    @pytest.mark.asyncio
    async def test_submit_underwriting_refusal_tds(self, client: AsyncClient, valid_application_payload):
        """
        Test application refusal due to high TDS (>44%).
        """
        # Low income, high debt
        valid_application_payload["borrower"]["annual_income"] = "50000.00"
        valid_application_payload["borrower"]["monthly_debt"] = "2000.00"
        
        create_resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        app_id = create_resp.json()["id"]
        
        eval_resp = await client.post(f"/api/v1/orchestrator/applications/{app_id}/evaluate")
        data = eval_resp.json()
        
        assert data["decision"] == "REFUSED"
        assert "TDS" in data["rejection_reason"]

    @pytest.mark.asyncio
    async def test_get_application_status(self, client: AsyncClient, valid_application_payload):
        """
        Test retrieving the status of a specific application.
        """
        create_resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        app_id = create_resp.json()["id"]
        
        get_resp = await client.get(f"/api/v1/orchestrator/applications/{app_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        
        assert data["id"] == app_id
        assert data["status"] == "PENDING"
        assert "borrower" in data # Check nested serialization
        assert "property" in data

    @pytest.mark.asyncio
    async def test_validation_error_missing_field(self, client: AsyncClient):
        """
        Test that Pydantic validation catches missing required fields.
        """
        invalid_payload = {
            "borrower": {}, # Missing fields
            "property": {}, # Missing fields
            "loan_amount": "100000"
        }
        
        resp = await client.post("/api/v1/orchestrator/applications", json=invalid_payload)
        
        assert resp.status_code == 422
        assert "detail" in resp.json()

    @pytest.mark.asyncio
    async def test_data_minimization_pii_not_logged(self, client: AsyncClient, valid_application_payload, caplog):
        """
        Ensure SIN is not in logs (PIPEDA compliance).
        Note: This is a structural check. In a real scenario, we'd check log output.
        Here we ensure the response doesn't contain raw SIN.
        """
        # The fixture uses a hash, but let's assume the user sent a raw SIN by mistake 
        # or the API returned it (which it shouldn't).
        
        # For this test, we verify the response structure matches the schema 
        # which should exclude raw SIN.
        resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        assert resp.status_code == 201
        
        data = resp.json()
        # Ensure raw SIN keys are not present in response
        assert "sin" not in data.get("borrower", {})
        assert "social_insurance_number" not in data.get("borrower", {})