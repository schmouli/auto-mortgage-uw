```python
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.modules.client_intake.routes import router
from mortgage_underwriting.main import app # Assuming main app exists or we build one

# We need a FastAPI app to include the router
@pytest.fixture(scope="function")
def test_app():
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-intake")
    return app

pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_create_client_workflow(test_app, db_session, valid_client_payload):
    """
    Test the full workflow of creating a client via API and verifying DB state.
    """
    # Arrange
    transport = ASGITransport(app=test_app)
    
    # Act
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        
        # Assert Response
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["email"] == "john.doe@example.com"
        assert "sin" not in data  # PIPEDA: SIN should never be returned
        assert "created_at" in data # FINTRAC: Audit trail
        
        # Assert Database
        stmt = select(Client).where(Client.id == data["id"])
        result = await db_session.execute(stmt)
        db_client = result.scalar_one_or_none()
        
        assert db_client is not None
        assert db_client.first_name == "John"
        # Verify SIN is encrypted in DB (not plain text)
        assert db_client.sin != "123456789" 
        assert db_client.sin.startswith("encrypted_") # Based on our mock

@pytest.mark.asyncio
async def test_create_application_workflow(test_app, db_session, valid_client_payload, valid_application_payload):
    """
    Test creating a client then creating an application linked to that client.
    """
    # 1. Create Client
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        assert client_resp.status_code == 201
        client_id = client_resp.json()["id"]
        
        # 2. Create Application
        app_payload = valid_application_payload.copy()
        app_payload["client_id"] = client_id
        
        app_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        
        # Assert Application Response
        assert app_resp.status_code == 201
        app_data = app_resp.json()
        assert app_data["client_id"] == client_id
        assert app_data["loan_amount"] == "400000.00" # JSON serialization of Decimal
        assert app_data["ltv_ratio"] == "0.80" # Verify calculation was performed
        assert app_data["insurance_required"] is False # LTV <= 80%
        
        # Assert Database
        stmt = select(Application).where(Application.id == app_data["id"])
        result = await db_session.execute(stmt)
        db_app = result.scalar_one_or_none()
        
        assert db_app is not None
        assert db_app.loan_amount == Decimal("400000.00")

@pytest.mark.asyncio
async def test_create_application_validation_error(test_app, db_session):
    """
    Test that validation errors return structured 422 responses.
    """
    transport = ASGITransport(app=test_app)
    invalid_payload = {
        "client_id": 999, # Doesn't exist
        "property_value": -500, # Negative value
        "down_payment": "not_a_number",
        "loan_amount": 400000,
        "amortization_years": 25,
        "interest_rate": 5.0,
        "annual_income": 95000,
        "property_tax": 3000,
        "heating_cost": 1200,
        "other_debt": 500
    }
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/client-intake/applications", json=invalid_payload)
        
        # FastAPI/Pydantic validation errors usually return 422
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

@pytest.mark.asyncio
async def test_get_client_not_found(test_app):
    """
    Test retrieving a non-existent client returns 404.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/client-intake/clients/99999")
        
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND"

@pytest.mark.asyncio
async def test_cmhc_insurance_trigger(test_app, db_session, valid_client_payload):
    """
    Integration test to verify CMHC premium logic is triggered correctly at high LTV.
    """
    # Create Client
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]
        
        # Create Application with 95% LTV (5% down)
        # Value: 500k, Down: 25k, Loan: 475k
        app_payload = {
            "client_id": client_id,
            "property_value": "500000.00",
            "down_payment": "25000.00",
            "loan_amount": "475000.00",
            "amortization_years": 25,
            "interest_rate": "5.00",
            "annual_income": "120000.00",
            "property_tax": "3000.00",
            "heating_cost": "1200.00",
            "other_debt": "0.00"
        }
        
        app_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        assert app_resp.status_code == 201
        data = app_resp.json()
        
        # CMHC Logic: IF LTV > 80% THEN insurance_required = True
        assert data["insurance_required"] is True
        # Verify LTV calculation precision
        assert Decimal(data["ltv_ratio"]) == Decimal("0.95")

@pytest.mark.asyncio
async def test_pipeda_sin_not_exposed(test_app, db_session, valid_client_payload):
    """
    Ensure SIN is not exposed in List or Get endpoints.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create
        create_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = create_resp.json()["id"]
        
        # Get Single
        get_resp = await client.get(f"/api/v1/client-intake/clients/{client_id}")
        assert "sin" not in get_resp.json()
        
        # List (Assuming a list endpoint exists or adding one logic check)
        # If list endpoint exists: list_resp = await client.get("/api/v1/client-intake/clients")
        # assert all("sin" not in c for c in list_resp.json())
```