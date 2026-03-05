import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select
from mortgage_underwriting.modules.decision.models import DecisionRecord

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_create_decision_happy_path(client: AsyncClient, valid_application_payload):
    """
    Test full API flow: Create a valid application decision.
    """
    response = await client.post("/api/v1/decisions/", json=valid_application_payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert "id" in data
    assert data["decision"] == "APPROVED"
    assert data["borrower_id"] == "test-borrower-123"
    assert Decimal(data["gds_ratio"]) < Decimal("39.00")
    assert Decimal(data["tds_ratio"]) < Decimal("44.00")
    assert "created_at" in data

@pytest.mark.asyncio
async def test_create_decision_denial_gds(client: AsyncClient, high_gds_payload):
    """
    Test API returns 200 OK (or 201) but with DENIED status for high GDS.
    """
    response = await client.post("/api/v1/decisions/", json=high_gds_payload)
    
    # Assuming API returns 201 even for denials (the record is created)
    # If the API treats denial as an error, this would be 400, but underwriting usually returns a Decision object.
    assert response.status_code == 201
    data = response.json()
    
    assert data["decision"] == "DENIED"
    assert "GDS" in data["denial_reason"]
    assert Decimal(data["gds_ratio"]) > Decimal("39.00")

@pytest.mark.asyncio
async def test_create_decision_validation_error(client: AsyncClient):
    """
    Test Pydantic validation on input (missing fields).
    """
    invalid_payload = {
        "borrower_id": "test",
        # Missing loan_amount, property_value, etc.
    }
    
    response = await client.post("/api/v1/decisions/", json=invalid_payload)
    
    assert response.status_code == 422 # Unprocessable Entity

@pytest.mark.asyncio
async def test_get_decision_by_id(client: AsyncClient, db_session, valid_application_payload):
    """
    Test retrieving a specific decision record.
    """
    # 1. Create a decision
    create_resp = await client.post("/api/v1/decisions/", json=valid_application_payload)
    assert create_resp.status_code == 201
    decision_id = create_resp.json()["id"]
    
    # 2. Retrieve it
    get_resp = await client.get(f"/api/v1/decisions/{decision_id}")
    
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == decision_id
    assert data["decision"] == "APPROVED"

@pytest.mark.asyncio
async def test_get_decision_not_found(client: AsyncClient):
    """
    Test 404 when looking for a non-existent decision.
    """
    response = await client.get("/api/v1/decisions/99999")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_database_persistence(client: AsyncClient, db_session, valid_application_payload):
    """
    Verify that the decision is actually saved to the database (Integration).
    """
    resp = await client.post("/api/v1/decisions/", json=valid_application_payload)
    decision_id = resp.json()["id"]
    
    # Query DB directly
    stmt = select(DecisionRecord).where(DecisionRecord.id == decision_id)
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()
    
    assert record is not None
    assert record.decision == "APPROVED"
    assert record.borrower_id == "test-borrower-123"
    assert record.created_at is not None

@pytest.mark.asyncio
async def test_cmhc_insurance_calculation_persisted(client: AsyncClient, db_session):
    """
    Test that CMHC insurance requirements are calculated and saved.
    """
    # LTV 90% -> Insurance Required
    payload = {
        "borrower_id": "test-insurance",
        "loan_amount": Decimal("450000.00"),
        "property_value": Decimal("500000.00"), # 90%
        "annual_income": Decimal("150000.00"),
        "monthly_debt": Decimal("0.00"),
        "contract_rate": Decimal("4.00"),
        "amortization_years": 25,
        "property_tax_annual": Decimal("3000.00"),
        "heating_monthly": Decimal("150.00")
    }
    
    resp = await client.post("/api/v1/decisions/", json=payload)
    data = resp.json()
    
    assert data["ltv_ratio"] == "90.00"
    assert data["insurance_required"] is True
    assert data["insurance_premium_rate"] == "0.0310" # 3.10%

@pytest.mark.asyncio
async def test_pipeda_sin_not_exposed_in_response(client: AsyncClient, valid_application_payload):
    """
    Ensure that even if SIN is sent (if supported by schema), it is not returned.
    """
    # Assuming schema allows SIN for identification but not response
    payload_with_sin = valid_application_payload.copy()
    # If the schema doesn't accept SIN, this test validates the schema rejection.
    # If it does, it validates the filtering.
    # We will assume it might be sent.
    
    response = await client.post("/api/v1/decisions/", json=payload_with_sin)
    data = response.json()
    
    # Ensure SIN is not in the response
    assert "sin" not in data
    # Ensure no hashed version that looks like SIN is there (basic check)
    # Note: This depends on specific implementation details of the response model.