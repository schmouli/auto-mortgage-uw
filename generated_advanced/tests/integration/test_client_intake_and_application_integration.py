```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_create_application_endpoint_success(client: AsyncClient, valid_application_payload: dict):
    """Test full workflow of creating an application via API."""
    response = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert "id" in data
    assert data["status"] == "DRAFT"
    assert data["borrower_first_name"] == "John"
    assert data["borrower_last_name"] == "Doe"
    
    # PII Checks (PIPEDA Compliance)
    # SIN must NOT be returned in plain text
    assert "borrower_sin" not in data
    # DOB must NOT be returned in plain text
    assert "borrower_dob" not in data
    
    # Financial checks
    assert Decimal(data["property_value"]) == Decimal("750000.00")
    assert Decimal(data["loan_amount"]) == Decimal("600000.00")

@pytest.mark.asyncio
async def test_create_application_endpoint_validation_error(client: AsyncClient, invalid_application_payload_missing_sin: dict):
    """Test API validation when required fields are missing."""
    response = await client.post("/api/v1/client-intake/applications", json=invalid_application_payload_missing_sin)
    
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data

@pytest.mark.asyncio
async def test_create_application_endpoint_negative_income(client: AsyncClient, invalid_application_payload_negative_income: dict):
    """Test API validation for negative income."""
    response = await client.post("/api/v1/client-intake/applications", json=invalid_application_payload_negative_income)
    
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_get_application_endpoint_success(client: AsyncClient, valid_application_payload: dict):
    """Test retrieving an application after creation."""
    # 1. Create
    create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    app_id = create_resp.json()["id"]
    
    # 2. Retrieve
    get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
    
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == app_id
    assert data["borrower_email"] == "john.doe@example.com"
    
    # Verify PII is still masked on GET
    assert "borrower_sin" not in data

@pytest.mark.asyncio
async def test_get_application_not_found(client: AsyncClient):
    """Test retrieving a non-existent application."""
    response = await client.get("/api/v1/client-intake/applications/99999")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_submit_application_workflow(client: AsyncClient, valid_application_payload: dict):
    """Test the workflow of creating and then submitting an application."""
    # 1. Create Application
    create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "DRAFT"
    
    # 2. Submit Application
    submit_payload = {"status": "SUBMITTED"}
    submit_resp = await client.patch(f"/api/v1/client-intake/applications/{app_id}", json=submit_payload)
    
    assert submit_resp.status_code == 200
    data = submit_resp.json()
    assert data["status"] == "SUBMITTED"
    
    # 3. Verify status persistence
    get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
    assert get_resp.json()["status"] == "SUBMITTED"

@pytest.mark.asyncio
async def test_update_property_value(client: AsyncClient, valid_application_payload: dict):
    """Test updating financial details (property value)."""
    # 1. Create
    create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    app_id = create_resp.json()["id"]
    
    # 2. Update Property Value
    update_payload = {
        "property_value": "800000.00",
        "down_payment": "160000.00",
        "loan_amount": "640000.00"
    }
    update_resp = await client.patch(f"/api/v1/client-intake/applications/{app_id}", json=update_payload)
    
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert Decimal(data["property_value"]) == Decimal("800000.00")
    assert Decimal(data["loan_amount"]) == Decimal("640000.00")

@pytest.mark.asyncio
async def test_list_applications(client: AsyncClient, valid_application_payload: dict):
    """Test listing multiple applications."""
    # Create two apps
    await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    payload_2 = valid_application_payload.copy()
    payload_2["borrower_email"] = "second@example.com"
    await client.post("/api/v1/client-intake/applications", json=payload_2)
    
    # List
    list_resp = await client.get("/api/v1/client-intake/applications")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) >= 2
    
    # Ensure PII is not in list view
    for app in data:
        assert "borrower_sin" not in app

@pytest.mark.asyncio
async def test_duplicate_sin_prevention(client: AsyncClient, valid_application_payload: dict):
    """Test that submitting an application with an existing SIN is handled (FINTRAC/Audit)."""
    # 1. Create first app
    resp1 = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    assert resp1.status_code == 201
    
    # 2. Try to create second app with same SIN
    # Assuming business logic or DB constraint prevents this
    # If unique constraint on hashed_sin exists:
    resp2 = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    
    # Expecting 409 Conflict or 400 Bad Request depending on implementation
    assert resp2.status_code in [409, 400]

@pytest.mark.asyncio
async def test_invalid_status_transition(client: AsyncClient, valid_application_payload: dict):
    """Test API guard against invalid status changes."""
    # Create
    create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
    app_id = create_resp.json()["id"]
    
    # Try to jump directly to APPROVED (skipping underwriting)
    invalid_payload = {"status": "APPROVED"}
    resp = await client.patch(f"/api/v1/client-intake/applications/{app_id}", json=invalid_payload)
    
    # Should fail validation or business rule
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_decimal_precision_preservation(client: AsyncClient, valid_application_payload: dict):
    """Test that financial values retain precision (no float conversion)."""
    # Use high precision values
    precise_payload = valid_application_payload.copy()
    precise_payload["property_value"] = "1234567.89"
    precise_payload["down_payment"] = "234567.88"
    
    resp = await client.post("/api/v1/client-intake/applications", json=precise_payload)
    assert resp.status_code == 201
    
    data = resp.json()
    # Verify exact string match or Decimal equality
    assert data["property_value"] == "1234567.89"
    assert data["down_payment"] == "234567.88"
```