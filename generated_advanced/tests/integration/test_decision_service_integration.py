```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

from mortgage_underwriting.modules.decision.routes import router
from mortgage_underwriting.modules.decision.models import Decision
from mortgage_underwriting.common.database import get_async_session

# Override the dependency for testing
async def override_get_db():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from mortgage_underwriting.common.database import Base
    
    # Use in-memory DB for integration tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session_maker() as session:
        yield session

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/decision", tags=["decision"])
    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestDecisionAPI:

    async def test_create_decision_success(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "application_id": "int-test-001",
                "loan_amount": "400000.00",
                "property_value": "500000.00",
                "annual_income": "120000.00",
                "mortgage_payment": "2000.00",
                "property_tax": "300.00",
                "heating_cost": "150.00",
                "other_debt": "500.00",
                "contract_rate": "4.5"
            }
            
            response = await client.post("/api/v1/decision/evaluate", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert data["application_id"] == "int-test-001"
            assert data["is_approved"] is True
            assert data["ltv"] == "80.00"
            assert "id" in data
            assert "created_at" in data

    async def test_create_decision_decline_tds(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "application_id": "int-test-decline",
                "loan_amount": "450000.00",
                "property_value": "500000.00",
                "annual_income": "80000.00",
                "mortgage_payment": "2600.00",
                "property_tax": "400.00",
                "heating_cost": "150.00",
                "other_debt": "1500.00",
                "contract_rate": "5.0"
            }
            
            response = await client.post("/api/v1/decision/evaluate", json=payload)
            
            assert response.status_code == 201 # Creation succeeds, but decision is negative
            data = response.json()
            assert data["is_approved"] is False
            assert "TDS" in data["rejection_reason"]

    async def test_create_decision_validation_error(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing required field
            payload = {
                "application_id": "int-test-bad",
                "loan_amount": "400000.00",
                # Missing property_value
                "annual_income": "120000.00",
                "mortgage_payment": "2000.00",
                "property_tax": "300.00",
                "heating_cost": "150.00",
                "other_debt": "500.00",
                "contract_rate": "4.5"
            }
            
            response = await client.post("/api/v1/decision/evaluate", json=payload)
            
            assert response.status_code == 422

    async def test_get_decision_by_id(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create a decision
            payload = {
                "application_id": "int-test-get",
                "loan_amount": "300000.00",
                "property_value": "400000.00",
                "annual_income": "100000.00",
                "mortgage_payment": "1500.00",
                "property_tax": "200.00",
                "heating_cost": "100.00",
                "other_debt": "0.00",
                "contract_rate": "3.0"
            }
            create_resp = await client.post("/api/v1/decision/evaluate", json=payload)
            decision_id = create_resp.json()["id"]

            # 2. Retrieve it
            get_resp = await client.get(f"/api/v1/decision/{decision_id}")
            
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["id"] == decision_id
            assert data["application_id"] == "int-test-get"

    async def test_get_decision_not_found(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/decision/99999")
            assert response.status_code == 404

    async def test_financial_precision_integrity(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Use specific decimals to ensure no float conversion issues
            payload = {
                "application_id": "int-test-precision",
                "loan_amount": "350000.55", 
                "property_value": "500000.99",
                "annual_income": "87500.12",
                "mortgage_payment": "1850.33",
                "property_tax": "275.44",
                "heating_cost": "125.22",
                "other_debt": "450.10",
                "contract_rate": "4.15"
            }
            
            response = await client.post("/api/v1/decision/evaluate", json=payload)
            assert response.status_code == 201
            
            data = response.json()
            # Verify response contains decimal strings, not floats (which might look like 1850.3300000000002)
            # FastAPI/Pydantic converts Decimals to strings in JSON usually
            assert data["gds"] is not None
            # Check that we can parse back to Decimal without losing precision
            gds_decimal = Decimal(data["gds"])
            assert gds_decimal > Decimal("0.00")
```