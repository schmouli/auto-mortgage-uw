import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from mortgage_underwriting.modules.frontend_react_ui.models import MortgageApplication

@pytest.mark.integration
@pytest.mark.asyncio
class TestFrontendRoutes:

    async def test_submit_application_success(self, client: AsyncClient, valid_applicant_payload):
        """
        Test successful submission of a mortgage application via API
        """
        response = await client.post("/api/v1/frontend/submit", json=valid_applicant_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending_review"
        assert data["loan_amount"] == "400000.00"
        # PIPEDA Check: Ensure SIN is NOT exposed in response
        assert "sin" not in data or data.get("sin") != valid_applicant_payload["sin"]

    async def test_submit_application_invalid_schema(self, client: AsyncClient):
        """
        Test validation error on malformed input (missing required fields)
        """
        invalid_payload = {
            "first_name": "Test",
            # Missing last_name, income, etc.
        }
        
        response = await client.post("/api/v1/frontend/submit", json=invalid_payload)
        
        assert response.status_code == 422
        assert "detail" in response.json()

    async def test_submit_application_osfi_gds_rejection(self, client: AsyncClient, high_gds_payload):
        """
        Integration test: Verify API rejects application failing OSFI GDS limits
        """
        response = await client.post("/api/v1/frontend/submit", json=high_gds_payload)
        
        assert response.status_code == 400 # Bad Request / Validation Error
        data = response.json()
        assert "error_code" in data
        # Verify error message mentions compliance
        assert "GDS" in data["detail"] or "compliance" in data["detail"].lower()

    async def test_get_application_status(self, client: AsyncClient, valid_applicant_payload, db_session):
        """
        Test retrieving application status
        """
        # 1. Create an application first
        create_resp = await client.post("/api/v1/frontend/submit", json=valid_applicant_payload)
        app_id = create_resp.json()["id"]
        
        # 2. Retrieve status
        status_resp = await client.get(f"/api/v1/frontend/status/{app_id}")
        
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["id"] == app_id
        assert data["created_at"] is not None

    async def test_submit_application_high_ltv_triggers_cmhc(self, client: AsyncClient, db_session):
        """
        Test CMHC Insurance logic integration:
        High LTV (e.g., 90%) should result in insurance_required = True
        """
        payload = {
            "first_name": "Bob",
            "last_name": "Builder",
            "sin": "555555555",
            "dob": "1980-01-01",
            "income": Decimal("100000.00"),
            "property_value": Decimal("100000.00"),
            "down_payment": Decimal("5000.00"), # 5% down -> 95% LTV
            "loan_amount": Decimal("95000.00"),
            "contract_rate": Decimal("4.00"),
            "property_tax": Decimal("1000.00"),
            "heating_cost": Decimal("1000.00"),
            "condo_fees": Decimal("0.00"),
            "other_debt": Decimal("0.00")
        }
        
        response = await client.post("/api/v1/frontend/submit", json=payload)
        assert response.status_code == 201
        
        # Verify DB state
        result = await db_session.execute(select(MortgageApplication).where(MortgageApplication.id == response.json()["id"]))
        app = result.scalar_one()
        
        assert app.insurance_required is True
        assert app.ltv_ratio == Decimal("0.95")
        assert app.cmhc_premium_rate == Decimal("0.04") # 90.01-95% tier

    async def test_fintrac_audit_fields_present(self, client: AsyncClient, valid_applicant_payload, db_session):
        """
        FINTRAC: Verify audit fields (created_at, created_by) are immutable and present
        """
        response = await client.post("/api/v1/frontend/submit", json=valid_applicant_payload)
        app_id = response.json()["id"]
        
        result = await db_session.execute(select(MortgageApplication).where(MortgageApplication.id == app_id))
        app = result.scalar_one()
        
        assert app.created_at is not None
        assert app.created_by is not None # Should be 'system' or user ID

    async def test_pipeda_sin_not_logged(self, client: AsyncClient, valid_applicant_payload, caplog):
        """
        PIPEDA: Ensure raw SIN never appears in logs
        """
        # This test assumes the application logs inputs at INFO level for debugging
        # We want to ensure the security middleware/logger scrubs the SIN
        
        with caplog.at_level("INFO"):
            response = await client.post("/api/v1/frontend/submit", json=valid_applicant_payload)
            
        # Gather all log messages
        log_messages = "".join(record.message for record in caplog.records)
        
        # Assert raw SIN is NOT present
        assert valid_applicant_payload["sin"] not in log messages
        # Assert placeholder or hash IS present (optional, but good practice)
        assert "******" in log_messages or "hashed" in log_messages.lower()