import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

from mortgage_underwriting.modules.orchestrator.routes import router
from mortgage_underwriting.modules.orchestrator.models import MortgageApplication
from mortgage_underwriting.common.database import get_async_session

# We need to override the dependency for testing
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture
def app(db_session: AsyncSession):
    """Create a test app with the orchestrator router and DB override."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/orchestrator", tags=["orchestrator"])

    # Dependency override
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestOrchestratorRoutes:

    async def test_create_application(self, app: FastAPI, sample_application_payload):
        """Test creating a new mortgage application via API."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/orchestrator/applications",
                json=sample_application_payload
            )
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["status"] == "Pending"
            assert data["loan_amount"] == "400000.00"

    async def test_get_application(self, app: FastAPI, db_session: AsyncSession):
        """Test retrieving an application."""
        # Seed data
        app_obj = MortgageApplication(
            borrower_id="999",
            property_value=Decimal("200000"),
            down_payment=Decimal("40000"),
            loan_amount=Decimal("160000"),
            annual_income=Decimal("60000"),
            property_tax=Decimal("2000"),
            heating_cost=Decimal("100"),
            other_debts=Decimal("0"),
            contract_rate=Decimal("3.0"),
            amortization_years=20
        )
        db_session.add(app_obj)
        await db_session.commit()
        await db_session.refresh(app_obj)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/orchestrator/applications/{app_obj.id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == app_obj.id
            assert data["borrower_id"] == "999"

    async def test_process_application_workflow(self, app: FastAPI, sample_application_payload, db_session: AsyncSession):
        """Full workflow: Create -> Process -> Verify Decision."""
        # 1. Create Application
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/orchestrator/applications",
                json=sample_application_payload
            )
            assert create_resp.status_code == 201
            app_id = create_resp.json()["id"]

            # 2. Process Application (Trigger Orchestrator)
            # NOTE: This endpoint likely triggers the heavy calculation logic
            process_resp = await client.post(f"/api/v1/orchestrator/process/{app_id}")
            assert process_resp.status_code == 200
            
            decision_data = process_resp.json()
            assert "decision" in decision_data
            assert "gds" in decision_data
            assert "tds" in decision_data
            
            # 3. Verify Final State in DB
            get_resp = await client.get(f"/api/v1/orchestrator/applications/{app_id}")
            assert get_resp.status_code == 200
            final_state = get_resp.json()
            
            assert final_state["status"] == decision_data["decision"]
            # Check audit fields are present
            assert "updated_at" in final_state

    async def test_validation_error_on_bad_input(self, app: FastAPI):
        """Test that Pydantic validation catches bad requests."""
        bad_payload = {
            "borrower_id": "123",
            "property_value": "not_a_decimal", # Invalid
            "loan_amount": -500 # Invalid
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/orchestrator/applications",
                json=bad_payload
            )
            
            assert response.status_code == 422

    async def test_not_found_on_processing_invalid_id(self, app: FastAPI):
        """Test processing an application that doesn't exist."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/orchestrator/process/99999")
            assert response.status_code == 404

    async def test_high_ratio_insurance_flag(self, app: FastAPI, db_session: AsyncSession):
        """Test that LTV > 80% triggers insurance requirement in response."""
        # High ratio: 5% down payment
        payload = {
            "borrower_id": "ins_test",
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("25000.00"), # 5% down
            "loan_amount": Decimal("475000.00"),
            "annual_income": Decimal("150000.00"), # High income to pass GDS/TDS
            "property_tax": Decimal("3000.00"),
            "heating_cost": Decimal("150.00"),
            "other_debts": Decimal("0.00"),
            "contract_rate": Decimal("4.50"),
            "amortization_years": 25
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create
            create_resp = await client.post("/api/v1/orchestrator/applications", json=payload)
            app_id = create_resp.json()["id"]
            
            # Process
            proc_resp = await client.post(f"/api/v1/orchestrator/process/{app_id}")
            data = proc_resp.json()
            
            # Assertions
            assert data["ltv"] == Decimal("0.95")
            assert data["insurance_required"] == True
            # Check premium calculation (4.00% of 475000)
            expected_premium = Decimal("475000.00") * Decimal("0.04")
            assert data["insurance_premium"] == str(expected_premium)