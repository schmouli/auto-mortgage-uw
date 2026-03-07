import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal

from mortgage_underwriting.modules.orchestrator.models import UnderwritingResult
from mortgage_underwriting.modules.orchestrator.schemas import UnderwritingDecision

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_application_success(client: AsyncClient, valid_application_payload):
    """
    Integration test: Submit a valid application and verify DB state.
    """
    response = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert "application_id" in data
    assert data["decision"] == "APPROVED"
    assert data["ltv_ratio"] == "0.90" # 450k / 500k
    
    # Verify Audit fields (FINTRAC)
    assert "created_at" in data
    assert "correlation_id" in data
    
    # Verify Insurance Calculation (CMHC)
    assert data["insurance_required"] is True
    assert data["insurance_premium_rate"] == "0.031" # 80.01-90% tier


@pytest.mark.asyncio
async def test_create_application_rejected_high_gds(client: AsyncClient, high_risk_payload):
    """
    Integration test: Submit high-risk application and verify rejection logic.
    """
    response = await client.post("/api/v1/orchestrator/applications", json=high_risk_payload)
    
    assert response.status_code == 201 # Request accepted, but decision is REJECTED
    data = response.json()
    
    assert data["decision"] == "REJECTED"
    assert "GDS" in data["rejection_reason"] or "TDS" in data["rejection_reason"]
    assert data["gds"] > Decimal("0.39") or data["tds"] > Decimal("0.44")


@pytest.mark.asyncio
async def test_get_application_status(client: AsyncClient, db_session, valid_application_payload):
    """
    Integration test: Create an application, then retrieve it by ID.
    """
    # 1. Create
    create_resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
    app_id = create_resp.json()["application_id"]
    
    # 2. Retrieve
    get_resp = await client.get(f"/api/v1/orchestrator/applications/{app_id}")
    
    assert get_resp.status_code == 200
    data = get_resp.json()
    
    assert data["application_id"] == app_id
    # Ensure PIPEDA compliance: SIN/DOB should not be in response
    assert "sin" not in data
    assert "date_of_birth" not in data
    # Ensure financials are present
    assert "loan_amount" in data


@pytest.mark.asyncio
async def test_stress_test_endpoint_logic(client: AsyncClient, db_session):
    """
    Integration test: Verify the stress rate used in calculation via the API response.
    """
    payload = {
        "borrower_id": "stress-test-user",
        "property_id": "stress-prop",
        "loan_amount": "400000.00",
        "purchase_price": "500000.00",
        "amortization_years": 25,
        "contract_rate": "3.00", # Low rate
        "annual_income": "100000.00",
        "annual_property_tax": "3000.00",
        "annual_heating": "1200.00",
        "monthly_debt_payments": "0.00"
    }
    
    response = await client.post("/api/v1/orchestrator/applications", json=payload)
    data = response.json()
    
    # OSFI B-20: Qualifying rate must be at least 5.25%
    # We verify this by checking the monthly_payment calculated in the response
    # If 3.00% was used: Payment ~ $1896
    # If 5.25% was used: Payment ~ $2392
    # This is an indirect check of the logic
    assert Decimal(data["monthly_payment"]) > Decimal("2300.00")


@pytest.mark.asyncio
async def test_input_validation_missing_fields(client: AsyncClient):
    """
    Integration test: Verify 422 Unprocessable Entity on bad input.
    """
    incomplete_payload = {
        "borrower_id": "test"
        # Missing all other required fields
    }
    
    response = await client.post("/api/v1/orchestrator/applications", json=incomplete_payload)
    
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_cmhc_premium_tier_95(client: AsyncClient, db_session):
    """
    Integration test: Verify correct CMHC premium tier for high LTV (90-95%).
    """
    # LTV = 95%
    payload = {
        "borrower_id": "high-ltv-user",
        "property_id": "high-ltv-prop",
        "loan_amount": "475000.00",
        "purchase_price": "500000.00",
        "amortization_years": 25,
        "contract_rate": "4.50",
        "annual_income": "150000.00", # High income to ensure approval
        "annual_property_tax": "3000.00",
        "annual_heating": "1200.00",
        "monthly_debt_payments": "0.00"
    }
    
    response = await client.post("/api/v1/orchestrator/applications", json=payload)
    data = response.json()
    
    assert data["decision"] == "APPROVED"
    assert data["insurance_required"] is True
    assert data["ltv_ratio"] == Decimal("0.95")
    # Tier 90.01-95% = 4.00%
    assert data["insurance_premium_rate"] == Decimal("0.040")