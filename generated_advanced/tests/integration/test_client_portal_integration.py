import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.client_portal.models import Client, MortgageApplication
from mortgage_underwriting.modules.client_portal.schemas import ApplicationStatus

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_create_client_endpoint(client: AsyncClient):
    """
    Test creating a client via the API.
    PIPEDA Check: Ensure SIN is not returned in the response.
    """
    response = await client.post("/api/v1/portal/clients", json={
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice.smith@example.com",
        "phone_number": "+14155552672",
        "date_of_birth": "1990-05-20",
        "sin": "987654321",
        "address": "456 Oak Ave",
        "city": "Vancouver",
        "province": "BC",
        "postal_code": "V6C1G1"
    })

    assert response.status_code == 201
    data = response.json()
    
    assert data["id"] > 0
    assert data["first_name"] == "Alice"
    assert data["email"] == "alice.smith@example.com"
    
    # CRITICAL: PIPEDA Compliance - SIN must never be returned
    assert "sin" not in data
    assert "sin_hash" not in data # Internal field should not leak


async def test_create_duplicate_client_returns_error(client: AsyncClient):
    payload = {
        "first_name": "Bob",
        "last_name": "Jones",
        "email": "bob@example.com",
        "phone_number": "+14155552673",
        "date_of_birth": "1980-01-01",
        "sin": "111222333",
        "address": "789 Pine St",
        "city": "Montreal",
        "province": "QC",
        "postal_code": "H2X1Y1"
    }

    # First request
    response1 = await client.post("/api/v1/portal/clients", json=payload)
    assert response1.status_code == 201

    # Second request (Duplicate)
    response2 = await client.post("/api/v1/portal/clients", json=payload)
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"].lower()


async def test_submit_application_workflow(client: AsyncClient, valid_client_payload, valid_application_payload):
    """
    Full workflow: Create Client -> Submit Application -> Verify Calculations.
    """
    # 1. Create Client
    client_resp = await client.post("/api/v1/portal/clients", json=valid_client_payload)
    assert client_resp.status_code == 201
    client_id = client_resp.json()["id"]

    # 2. Submit Application linked to client
    app_payload = valid_application_payload.copy()
    app_payload["client_id"] = client_id
    
    app_resp = await client.post("/api/v1/portal/applications", json=app_payload)
    assert app_resp.status_code == 201
    app_data = app_resp.json()

    # 3. Verify Response Data
    assert app_data["client_id"] == client_id
    assert app_data["status"] == "SUBMITTED"
    
    # Verify OSFI B-20 Stress Test Calculation
    # Contract 4.5 + 2 = 6.5 vs 5.25 -> 6.5
    assert app_data["qualifying_rate"] == "6.50"
    
    # Verify LTV
    assert app_data["ltv_ratio"] == "80.00"
    
    # Verify CMHC Insurance Logic (80% LTV usually doesn't require insurance depending on exact cut off, 
    # but logic says > 80%. Here it is exactly 80, so False)
    assert app_data["insurance_required"] is False

    # Verify Audit Trail (FINTRAC)
    assert "created_at" in app_data
    assert "updated_at" in app_data


async def test_get_application_status(client: AsyncClient, valid_client_payload, valid_application_payload):
    # Setup
    client_resp = await client.post("/api/v1/portal/clients", json=valid_client_payload)
    client_id = client_resp.json()["id"]
    
    app_payload = valid_application_payload.copy()
    app_payload["client_id"] = client_id
    app_resp = await client.post("/api/v1/portal/applications", json=app_payload)
    app_id = app_resp.json()["id"]

    # Get Status
    status_resp = await client.get(f"/api/v1/portal/applications/{app_id}")
    
    assert status_resp.status_code == 200
    data = status_resp.json()
    
    # Ensure financial precision is maintained
    assert Decimal(data["loan_amount"]) == Decimal("400000.00")
    assert data["status"] == "SUBMITTED"


async def test_submit_application_compliance_validation_gds(client: AsyncClient, valid_client_payload):
    """
    Test that the API rejects applications violating GDS > 39% rule.
    """
    # Create Client
    client_resp = await client.post("/api/v1/portal/clients", json=valid_client_payload)
    client_id = client_resp.json()["id"]

    # Submit High Risk Application (Low Income)
    bad_payload = {
        "client_id": client_id,
        "property_value": "600000.00",
        "down_payment": "120000.00",
        "loan_amount": "480000.00",
        "contract_rate": "5.00",
        "amortization_years": 25,
        "annual_income": "30000.00", # Very low
        "monthly_property_tax": "400.00",
        "monthly_heating": "200.00",
        "monthly_debts": "100.00"
    }

    response = await client.post("/api/v1/portal/applications", json=bad_payload)
    
    # Should return 400 or 422 depending on how exception is mapped
    assert response.status_code == 400
    assert "GDS" in response.json()["detail"]


async def test_piipa_data_leak_prevention(client: AsyncClient, db_session):
    """
    Verify that even if we query the DB directly or via API, PII fields are handled.
    This is a safety check for the API layer.
    """
    # Create a client directly in DB for testing retrieval
    new_client = Client(
        first_name="Test",
        last_name="User",
        email="test@test.com",
        sin="encrypted_sin_value", # Mocked encrypted value
        sin_hash="hash123",
        date_of_birth="1990-01-01"
    )
    db_session.add(new_client)
    await db_session.commit()
    await db_session.refresh(new_client)

    # Fetch via API
    response = await client.get(f"/api/v1/portal/clients/{new_client.id}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Explicitly check that raw SIN is absent
    assert "sin" not in data
    # Check that raw DOB is absent (PIPEDA minimization/logging risk)
    # Note: Depending on business requirement, DOB might be needed for verification, 
    # but usually masked. Assuming strict PIPEDA here.
    assert "date_of_birth" not in data or data["date_of_birth"] != "1990-01-01"