import pytest
from httpx import AsyncClient
from decimal import Decimal

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_create_underwriting_decision_success(client: AsyncClient, valid_application_payload):
    """
    Integration Test: Successful underwriting flow.
    """
    response = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert "id" in data
    assert data["decision"] == "APPROVED"
    assert data["applicant_id"] == "test-user-123"
    
    # Verify Regulatory Compliance fields are present
    assert "gds" in data
    assert "tds" in data
    assert "qualifying_rate" in data
    assert "insurance_required" in data
    assert "created_at" in data # Audit trail
    
    # Check math roughly
    assert Decimal(data["gds"]) <= Decimal("0.39")
    assert Decimal(data["tds"]) <= Decimal("0.44")

@pytest.mark.asyncio
async def test_create_underwriting_decision_declined(client: AsyncClient, high_risk_payload):
    """
    Integration Test: Application declined due to high TDS.
    API should return 400 Bad Request or specific rejection status with details.
    """
    response = await client.post("/api/v1/underwriting/evaluate", json=high_risk_payload)
    
    # Assuming the API returns 400 when regulatory limits are hit during evaluation
    assert response.status_code == 400
    
    data = response.json()
    assert "detail" in data
    assert "TDS" in data["detail"] or "limit" in data["detail"].lower()

@pytest.mark.asyncio
async def test_create_underwriting_validation_error(client: AsyncClient):
    """
    Integration Test: Input validation failure (Pydantic).
    """
    invalid_payload = {
        "applicant_id": "bad-user",
        "loan_amount": "-50000", # Negative money
        "property_value": "not_a_number"
    }
    
    response = await client.post("/api/v1/underwriting/evaluate", json=invalid_payload)
    
    assert response.status_code == 422 # Unprocessable Entity
    
    errors = response.json()["detail"]
    # Check that field errors are reported
    error_fields = [e["loc"][1] for e in errors]
    assert "loan_amount" in error_fields
    assert "property_value" in error_fields

@pytest.mark.asyncio
async def test_get_underwriting_decision(client: AsyncClient, valid_application_payload):
    """
    Integration Test: Retrieve a stored decision.
    """
    # 1. Create a decision
    create_resp = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
    assert create_resp.status_code == 201
    decision_id = create_resp.json()["id"]
    
    # 2. Retrieve the decision
    get_resp = await client.get(f"/api/v1/underwriting/decisions/{decision_id}")
    
    assert get_resp.status_code == 200
    data = get_resp.json()
    
    assert data["id"] == decision_id
    assert data["applicant_id"] == "test-user-123"
    # Ensure PII is not leaked (SIN/DOB should not be in response if model had them)
    assert "sin" not in data
    assert "date_of_birth" not in data

@pytest.mark.asyncio
async def test_stress_test_logic_endpoint(client: AsyncClient):
    """
    Verify the endpoint returns the correct qualifying rate based on OSFI rules.
    """
    # Low rate case
    payload_low = {
        **valid_application_payload, # defined in conftest, but we redefine here for clarity if needed
        "contract_rate": "3.5", # 3.5 + 2 = 5.5 < 5.25 is False, 5.5 > 5.25. 
                                # Wait, 3.5 + 2 = 5.5. 5.5 > 5.25. Qualifying = 5.5.
    }
    # Correct low case: 3.0 + 2 = 5.0. 5.0 < 5.25. Qualifying = 5.25.
    payload_low["contract_rate"] = "3.0"
    
    resp = await client.post("/api/v1/underwriting/evaluate", json=payload_low)
    assert resp.status_code == 201
    assert Decimal(resp.json()["qualifying_rate"]) == Decimal("0.0525")

    # High rate case
    payload_high = payload_low.copy()
    payload_high["applicant_id"] = "new-user" # unique constraint
    payload_high["contract_rate"] = "6.0" # 6.0 + 2 = 8.0. Qualifying = 8.0.
    
    resp = await client.post("/api/v1/underwriting/evaluate", json=payload_high)
    assert resp.status_code == 201
    assert Decimal(resp.json()["qualifying_rate"]) == Decimal("0.08")

@pytest.mark.asyncio
async def test_cmhc_insurance_tier_endpoint(client: AsyncClient, high_ltv_payload):
    """
    Verify CMHC premium calculation is persisted correctly via API.
    """
    resp = await client.post("/api/v1/underwriting/evaluate", json=high_ltv_payload)
    assert resp.status_code == 201
    
    data = resp.json()
    assert data["insurance_required"] is True
    assert data["ltv"] == "0.95" # 475k / 500k
    assert data["cmhc_premium_rate"] == "0.0400" # 4.00%
    
    # Check total loan amount includes premium
    # 475000 * 1.04 = 494000
    expected_total = Decimal("475000.00") * (Decimal("1.00") + Decimal("0.04"))
    assert Decimal(data["total_loan_amount"]) == expected_total

@pytest.mark.asyncio
async test test_audit_fields_populated(client: AsyncClient, valid_application_payload):
    """
    Verify audit fields (created_at, updated_at) are populated automatically.
    """
    resp = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
    assert resp.status_code == 201
    
    data = resp.json()
    assert "created_at" in data
    assert "updated_at" in data
    # Assuming ISO format strings
    assert data["created_at"] is not None
    assert data["updated_at"] is not None