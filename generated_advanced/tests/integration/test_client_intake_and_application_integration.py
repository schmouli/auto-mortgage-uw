import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.client_intake.models import Applicant, Application

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_applicant_flow(self, client: AsyncClient, valid_applicant_data):
        """
        Test full flow: Create Applicant -> Verify Response -> Verify DB State.
        Ensures PIPEDA compliance (SIN not in response).
        """
        response = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify Response Structure
        assert "id" in data
        assert data["first_name"] == "Jane"
        assert data["last_name"] == "Doe"
        assert data["email"] == "jane.doe@example.com"
        
        # PIPEDA: Ensure raw SIN is NEVER returned
        assert "sin" not in data
        assert "123456782" not in str(data)
        
        # Verify Audit Fields (FINTRAC)
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_applicant_invalid_email(self, client: AsyncClient, valid_applicant_data):
        """
        Test validation error on invalid email.
        """
        invalid_data = valid_applicant_data.copy()
        invalid_data["email"] = "not-an-email"
        
        response = await client.post("/api/v1/client-intake/applicants", json=invalid_data)
        
        assert response.status_code == 422 # Pydantic validation error

    async def test_create_application_flow(self, client: AsyncClient, valid_applicant_data, valid_application_data, db_session):
        """
        Test full flow: Create Applicant -> Create Application -> Verify Calculations.
        """
        # 1. Create Applicant
        app_resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = app_resp.json()["id"]
        
        # 2. Create Application
        app_payload = valid_application_data.copy()
        app_payload["applicant_id"] = applicant_id
        
        resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        
        assert resp.status_code == 201
        data = resp.json()
        
        # Verify Financials are Decimal (represented as strings in JSON)
        assert Decimal(data["loan_amount"]) == Decimal("450000.00")
        assert Decimal(data["annual_income"]) == Decimal("120000.00")
        
        # Verify LTV Calculation
        # 450000 / 600000 = 0.75
        expected_ltv = Decimal("75.00")
        assert Decimal(data["ltv_ratio"]) == expected_ltv
        
        # Verify Insurance Requirement (CMHC Logic)
        # LTV 75% <= 80%, so no insurance required
        assert data["insurance_required"] is False
        assert data["insurance_premium"] == Decimal("0.00")

    async def test_create_application_high_ltv_triggers_insurance(self, client: AsyncClient, valid_applicant_data, db_session):
        """
        Test CMHC Logic: High LTV (>80%) triggers insurance requirement.
        """
        # Create Applicant
        app_resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = app_resp.json()["id"]
        
        # Create Application with 5% down (95% LTV)
        payload = {
            "applicant_id": applicant_id,
            "loan_amount": "475000.00",
            "property_value": "500000.00",
            "down_payment": "25000.00",
            "amortization_years": 25,
            "interest_rate": "5.00",
            "annual_income": "120000.00",
            "property_tax": "3000.00",
            "heating_cost": "1200.00",
            "other_debt": "0.00"
        }
        
        resp = await client.post("/api/v1/client-intake/applications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        
        # LTV = 95%
        assert Decimal(data["ltv_ratio"]) == Decimal("95.00")
        
        # CMHC: 90.01-95% = 4.00% premium
        # Premium is calculated on loan amount usually
        expected_premium = Decimal("475000.00") * Decimal("0.04")
        
        assert data["insurance_required"] is True
        assert Decimal(data["insurance_premium"]) == expected_premium

    async def test_get_application_by_id(self, client: AsyncClient, valid_applicant_data, valid_application_data):
        """
        Test retrieving an application.
        """
        # Setup
        app_resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = app_resp.json()["id"]
        
        app_payload = valid_application_data.copy()
        app_payload["applicant_id"] = applicant_id
        create_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        application_id = create_resp.json()["id"]
        
        # Test Get
        get_resp = await client.get(f"/api/v1/client-intake/applications/{application_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == application_id
        assert data["applicant_id"] == applicant_id

    async def test_get_application_not_found(self, client: AsyncClient):
        """
        Test 404 for non-existent application.
        """
        resp = await client.get("/api/v1/client-intake/applications/99999")
        assert resp.status_code == 404

    async def test_update_applicant_contact_info(self, client: AsyncClient, valid_applicant_data):
        """
        Test updating applicant info (e.g., email change).
        """
        # Create
        create_resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = create_resp.json()["id"]
        
        # Update
        update_payload = {"email": "new.email@example.com"}
        update_resp = await client.patch(f"/api/v1/client-intake/applicants/{applicant_id}", json=update_payload)
        
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["email"] == "new.email@example.com"
        assert data["first_name"] == "Jane" # Other fields unchanged

    async def test_sin_is_hashed_in_db(self, client: AsyncClient, valid_applicant_data, db_session):
        """
        Verify PIPEDA compliance: SIN is hashed in the database, not plain text.
        """
        resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = resp.json()["id"]
        
        # Query DB directly to check storage format
        from sqlalchemy import select
        stmt = select(Applicant).where(Applicant.id == applicant_id)
        result = await db_session.execute(stmt)
        db_applicant = result.scalar_one()
        
        # Ensure the SIN field in DB is NOT the plain text "123456782"
        # It should be a hash (e.g., sha256 hex string length 64)
        assert db_applicant.sin != "123456782"
        assert len(db_applicant.sin) == 64 # Assuming SHA-256 hex output
        assert "123456782" not in db_applicant.sin

    async def test_financial_decimals_precision(self, client: AsyncClient, valid_applicant_data):
        """
        Ensure financial values maintain precision without float conversion errors.
        """
        app_resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = app_resp.json()["id"]
        
        payload = {
            "applicant_id": applicant_id,
            "loan_amount": "123456.78", # High precision cents
            "property_value": "500000.00",
            "down_payment": "376543.22",
            "amortization_years": 25,
            "interest_rate": "3.99",
            "annual_income": "100200.50",
            "property_tax": "3000.01",
            "heating_cost": "1200.12",
            "other_debt": "0.01"
        }
        
        resp = await client.post("/api/v1/client-intake/applications", json=payload)
        assert resp.status_code == 201
        
        data = resp.json()
        # Verify strict decimal equality
        assert Decimal(data["loan_amount"]) == Decimal("123456.78")
        assert Decimal(data["annual_income"]) == Decimal("100200.50")