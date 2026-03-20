import pytest
from httpx import AsyncClient
from decimal import Decimal

from mortgage_underwriting.modules.decision_service.models import MortgageApplication
from sqlalchemy import select

@pytest.mark.integration
@pytest.mark.asyncio
class TestDecisionEndpoints:

    async def test_evaluate_application_success(self, client: AsyncClient, valid_application_payload):
        response = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["decision"] in ["Approved", "Rejected", "Refer"]
        assert "id" in data
        assert "gds" in data
        assert "tds" in data
        assert "ltv" in data
        assert "created_at" in data
        assert "updated_at" in data
        
        # Verify Decimal precision is preserved in JSON (usually string or float, checking type conversion)
        # Pydantic/FastAPI converts Decimals to floats in JSON by default, but logic uses Decimals.
        assert isinstance(data["gds"], float) or isinstance(data["gds"], str)

    async def test_evaluate_application_rejection_high_ltv(self, client: AsyncClient):
        # LTV > 95%
        payload = {
            "applicant_id": "high-ltv",
            "loan_amount": "480000.00",
            "property_value": "500000.00",
            "annual_income": "200000.00",
            "annual_property_tax": "3000.00",
            "annual_heating_cost": "1200.00",
            "other_debts": "0.00",
            "contract_rate": "4.00",
            "amortization_years": 25
        }
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "Rejected"
        assert "LTV" in data["rejection_reasons"]

    async def test_evaluate_application_validation_error_missing_field(self, client: AsyncClient):
        payload = {
            "applicant_id": "missing-data",
            "loan_amount": "400000.00",
            # Missing property_value
            "annual_income": "100000.00",
            "contract_rate": "4.00",
            "amortization_years": 25
        }
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        
        assert response.status_code == 422
        assert "detail" in response.json()

    async def test_evaluate_application_creates_db_record(self, client: AsyncClient, valid_application_payload, db_session):
        response = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        assert response.status_code == 200
        
        app_id = response.json()["id"]
        
        # Verify in DB
        result = await db_session.execute(select(MortgageApplication).where(MortgageApplication.id == app_id))
        db_record = result.scalar_one_or_none()
        
        assert db_record is not None
        assert db_record.applicant_id == valid_application_payload["applicant_id"]
        assert db_record.loan_amount == Decimal(valid_application_payload["loan_amount"])
        assert db_record.created_at is not None

    async def test_evaluate_application_osfi_stress_test_compliance(self, client: AsyncClient, db_session):
        # Scenario: Low contract rate (3%), but must qualify at 5.25%
        # Income is tight at 5.25%
        payload = {
            "applicant_id": "stress-test",
            "loan_amount": "400000.00",
            "property_value": "500000.00",
            "annual_income": "84000.00", # ~$7000/mo income
            "annual_property_tax": "3000.00",
            "annual_heating_cost": "1200.00",
            "other_debts": "0.00",
            "contract_rate": "3.00", # Actual payment would be ~$1896
            "amortization_years": 25
        }
        
        # Logic check:
        # Payment @ 3%: ~1896. GDS = (1896+250+100)*12 / 84000 = 30.8% (Pass)
        # Payment @ 5.25%: ~2400. GDS = (2400+250+100)*12 / 84000 = 39.1% (Fail)
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        data = response.json()
        
        # If the service correctly implements OSFI B-20, this should be rejected or referred
        # because the GDS at the qualifying rate (5.25%) exceeds 39%.
        assert data["decision"] in ["Rejected", "Refer"]
        assert "GDS" in data["rejection_reasons"]

    async def test_evaluate_application_cmhc_insurance_calculation(self, client: AsyncClient):
        # LTV 90% -> Premium 3.10%
        payload = {
            "applicant_id": "ins-test",
            "loan_amount": "450000.00",
            "property_value": "500000.00",
            "annual_income": "150000.00",
            "annual_property_tax": "3000.00",
            "annual_heating_cost": "1200.00",
            "other_debts": "0.00",
            "contract_rate": "4.00",
            "amortization_years": 25
        }
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        data = response.json()
        
        assert data["decision"] == "Approved" # Income is high
        assert data["insurance_required"] is True
        assert data["insurance_premium_rate"] == 0.031 # 3.10%

    async def test_get_application_history(self, client: AsyncClient, valid_application_payload, db_session):
        # Create one first
        post_resp = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        app_id = post_resp.json()["id"]
        
        # Get history
        get_resp = await client.get(f"/api/v1/decision/applications/{valid_application_payload['applicant_id']}")
        
        assert get_resp.status_code == 200
        apps = get_resp.json()
        assert len(apps) >= 1
        assert any(a["id"] == app_id for a in apps)

    async def test_fintrac_audit_trail_fields_present(self, client: AsyncClient, valid_application_payload):
        # FINTRAC: Immutable audit trail (created_at)
        response = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        data = response.json()
        
        assert "created_at" in data
        assert "updated_at" in data
        # Ensure we aren't logging PII (SIN) - verified by absence in response keys
        assert "sin" not in data
        assert "dob" not in data