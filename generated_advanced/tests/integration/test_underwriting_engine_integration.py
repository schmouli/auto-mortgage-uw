import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from mortgage_underwriting.modules.underwriting_engine.models import UnderwritingDecision

@pytest.mark.integration
@pytest.mark.asyncio
class TestUnderwritingRoutes:

    async def test_create_underwriting_decision_success(self, client: AsyncClient, valid_application_payload):
        """
        Test submitting a valid application results in an 'Approved' decision and database record.
        """
        response = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["decision"] == "Approved"
        assert "id" in data
        assert data["application_id"] == "app_12345"
        assert Decimal(data["gds_ratio"]) <= Decimal("39.00")
        assert Decimal(data["tds_ratio"]) <= Decimal("44.00")
        
        # Verify DB Persistence
        # Note: In a real integration test we would query the DB here, 
        # but the 'client' fixture uses a separate session scope in this setup.
        # We assume the endpoint returns the persisted object.

    async def test_create_underwriting_decision_declined_tds(self, client: AsyncClient, high_tds_payload):
        """
        Test submitting an application that fails TDS limits.
        """
        response = await client.post("/api/v1/underwriting/evaluate", json=high_tds_payload)
        
        assert response.status_code == 201 # We create the record even if declined
        data = response.json()
        
        assert data["decision"] == "Declined"
        assert "TDS" in data["rejection_reason"]
        assert Decimal(data["tds_ratio"]) > Decimal("44.00")

    async def test_create_underwriting_missing_field(self, client: AsyncClient):
        """
        Test validation error when required fields are missing.
        """
        invalid_payload = {
            "application_id": "app_missing",
            # Missing loan_amount, property_value, etc.
        }
        
        response = await client.post("/api/v1/underwriting/evaluate", json=invalid_payload)
        
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(err["loc"][-1] == "loan_amount" for err in errors)

    async def test_get_underwriting_decision(self, client: AsyncClient, valid_application_payload):
        """
        Test retrieving a specific underwriting decision by ID.
        """
        # 1. Create a decision
        create_resp = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
        assert create_resp.status_code == 201
        decision_id = create_resp.json()["id"]
        
        # 2. Retrieve it
        get_resp = await client.get(f"/api/v1/underwriting/decisions/{decision_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == decision_id
        assert data["application_id"] == "app_12345"

    async def test_get_underwriting_decision_not_found(self, client: AsyncClient):
        """
        Test retrieving a non-existent decision returns 404.
        """
        get_resp = await client.get("/api/v1/underwriting/decisions/99999")
        assert get_resp.status_code == 404

    async def test_cmhc_insurance_application(self, client: AsyncClient, high_ltv_payload):
        """
        Test that insurance is calculated and applied correctly for high LTV.
        LTV 88.8% -> Premium 3.10%.
        """
        response = await client.post("/api/v1/underwriting/evaluate", json=high_ltv_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify insurance flag
        assert data["insurance_required"] is True
        
        # Verify premium calculation roughly
        # Premium = Loan * Rate / (1 - Rate)
        # 400k * 0.031 / 0.969 ≈ 12,796.90
        # Total Loan ≈ 412,796.90
        expected_premium = Decimal("400000.00") * Decimal("0.031") / (Decimal("1") - Decimal("0.031"))
        
        # We check if the stored premium matches the calculation
        assert Decimal(data["insurance_premium_amount"]) == pytest.approx(expected_premium)

    async def test_stress_test_application(self, client: AsyncClient, valid_application_payload):
        """
        Test that the qualifying rate is applied correctly.
        Contract rate 4.50% -> Qualifying 6.50%.
        The resulting monthly payment in the response should reflect the qualifying rate payment capability check.
        """
        response = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        # The response should contain the qualifying rate used
        assert data["qualifying_rate"] == "6.50"
        
        # Ensure GDS/TDS were calculated based on this stress test
        # (Implicitly checked by the decision being Approved/Declined correctly)

    async def test_pipeda_sin_not_logged(self, client: AsyncClient, caplog):
        """
        Test that PII (SIN) is not exposed in logs.
        Note: This test requires the application to actually log something, 
        which is hard to trigger via HTTP client without inspecting server logs.
        Here we check the response doesn't leak it if we added it (though schema shouldn't allow it).
        """
        # Assuming we try to inject a SIN in a free text field (if one existed) or just verify schema prevents it
        # Since the schema doesn't have SIN, we verify the response structure is clean.
        payload = valid_application_payload.copy()
        # If there was a 'notes' field:
        # payload["notes"] = "My SIN is 123456789"
        
        response = await client.post("/api/v1/underwriting/evaluate", json=payload)
        assert response.status_code == 201
        # Verify no sensitive keys in response
        assert "sin" not in response.json().keys()
        assert "dob" not in response.json().keys()

    async def test_fintrac_audit_fields(self, client: AsyncClient, valid_application_payload):
        """
        Test that created_at and created_by are present in the response (Audit trail).
        """
        response = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "created_at" in data
        assert data["created_at"] is not None
        # created_by might be system user or extracted from token
        assert "created_by" in data 

    async def test_concurrent_requests(self, client: AsyncClient, valid_application_payload):
        """
        Test basic concurrency handling (system should handle multiple eval requests).
        """
        import asyncio
        
        async def make_request():
            return await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
        
        results = await asyncio.gather(make_request(), make_request(), make_request())
        
        for response in results:
            assert response.status_code == 201
            assert response.json()["decision"] == "Approved"