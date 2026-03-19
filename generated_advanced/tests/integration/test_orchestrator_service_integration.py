import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from mortgage_underwriting.modules.orchestrator.models import Application
from decimal import Decimal

@pytest.mark.integration
class TestOrchestratorRoutes:

    @pytest.mark.asyncio
    async def test_create_application_and_approve(self, client: AsyncClient, db_session: AsyncSession):
        """
        Full workflow: Submit application -> Orchestrator processes -> Returns Decision
        """
        payload = {
            "borrower_id": "int-bor-1",
            "property_id": "int-prop-1",
            "loan_amount": "500000.00",
            "contract_rate": "4.00",
            "amortization_years": 25,
            "down_payment": "100000.00"
        }

        # Note: This test assumes the orchestrator has access to mockable or real data 
        # for the borrower/property. In a real integration test, we might seed those tables first.
        # Here we test the API contract and the persistence of the Application record.
        
        response = await client.post("/api/v1/orchestrator/apply", json=payload)
        
        # Assert API Response
        assert response.status_code in [201, 202] # Accepted or Created immediately
        
        data = response.json()
        assert "id" in data
        assert "status" in data
        
        # Verify Database Record (FINTRAC: Audit trail)
        stmt = select(Application).where(Application.id == data["id"])
        result = await db_session.execute(stmt)
        app_record = result.scalar_one_or_none()
        
        assert app_record is not None
        assert app_record.borrower_id == "int-bor-1"
        assert app_record.loan_amount == Decimal("500000.00")
        assert app_record.created_at is not None # Audit trail requirement

    @pytest.mark.asyncio
    async def test_get_application_status(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test retrieving a specific application status.
        """
        # Create an application directly in DB
        new_app = Application(
            borrower_id="bor-status",
            property_id="prop-status",
            loan_amount=Decimal("200000.00"),
            contract_rate=Decimal("3.5"),
            amortization_years=20,
            down_payment=Decimal("40000.00"),
            status="Completed",
            decision="Approved"
        )
        db_session.add(new_app)
        await db_session.commit()
        await db_session.refresh(new_app)

        response = await client.get(f"/api/v1/orchestrator/applications/{new_app.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(new_app.id)
        assert data["status"] == "Completed"
        assert data["decision"] == "Approved"
        # Ensure PII is not leaked (SIN/DOB not in response)
        assert "sin" not in data
        assert "date_of_birth" not in data

    @pytest.mark.asyncio
    async def test_create_application_validation_error(self, client: AsyncClient):
        """
        Test input validation: Negative loan amount should be rejected immediately.
        """
        payload = {
            "borrower_id": "bor-1",
            "property_id": "prop-1",
            "loan_amount": "-50000.00", # Invalid
            "contract_rate": "4.00",
            "amortization_years": 25,
            "down_payment": "10000.00"
        }

        response = await client.post("/api/v1/orchestrator/apply", json=payload)
        
        assert response.status_code == 422 # Unprocessable Entity
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_get_non_existent_application(self, client: AsyncClient):
        """
        Test 404 handling.
        """
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/v1/orchestrator/applications/{fake_id}")
        
        assert response.status_code == 404

# Import select for the integration test
from sqlalchemy import select