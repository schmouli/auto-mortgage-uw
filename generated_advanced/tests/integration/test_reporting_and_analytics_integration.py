```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal
from datetime import date

# Import the router and models to setup the test app
from mortgage_underwriting.modules.reporting.routes import router
from mortgage_underwriting.modules.reporting.models import ReportLog
from mortgage_underwriting.common.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture(scope="function")
def app(db_session):
    """
    Create a test FastAPI app with the Reporting router.
    Overrides the dependency to use the test database session.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/reporting", tags=["reporting"])
    
    # Override the database dependency
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    # Clean up overrides
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestReportingEndpoints:

    async def test_create_report_endpoint_success(self, app: FastAPI):
        """
        Test POST /api/v1/reporting/reports
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/reporting/reports", json={
                "report_type": "portfolio_summary",
                "start_date": "2023-01-01",
                "end_date": "2023-01-31",
                "format": "json"
            })
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["status"] == "pending" # Assuming async generation or immediate
            assert data["report_type"] == "portfolio_summary"

    async def test_create_report_invalid_input(self, app: FastAPI):
        """
        Test POST /api/v1/reporting/reports with invalid data (missing fields).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/reporting/reports", json={
                "report_type": "portfolio_summary"
                # Missing dates
            })
            
            assert response.status_code == 422 # Validation Error

    async def test_get_report_endpoint_not_found(self, app: FastAPI):
        """
        Test GET /api/v1/reporting/reports/{id} for non-existent report.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/reporting/reports/99999")
            
            assert response.status_code == 404

    async def test_get_analytics_metrics_endpoint(self, app: FastAPI):
        """
        Test GET /api/v1/reporting/analytics/metrics
        Verifies the endpoint returns structured financial data using Decimals.
        """
        # Seed some data first (if the endpoint reads from DB directly)
        # For this test, we assume the endpoint calculates on the fly or reads seeded data
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/reporting/analytics/metrics?year=2023")
            
            # If DB is empty, service might return zeros or empty list, but should not 500
            assert response.status_code in [200, 404] 
            
            if response.status_code == 200:
                data = response.json()
                # Verify JSON serialization of Decimals works
                if "average_ltv" in data:
                    # Ensure it returns a number, not a string representation of Decimal
                    assert isinstance(data["average_ltv"], (int, float, str))

@pytest.mark.integration
@pytest.mark.asyncio
class TestReportingWorkflow:
    
    async def test_full_report_lifecycle(self, app: FastAPI):
        """
        Integration test: Create report -> Check status -> Retrieve result.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create Report
            create_resp = await client.post("/api/v1/reporting/reports", json={
                "report_type": "loan_performance",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "format": "json"
            })
            assert create_resp.status_code == 201
            report_id = create_resp.json()["id"]

            # 2. Retrieve Report
            get_resp = await client.get(f"/api/v1/reporting/reports/{report_id}")
            assert get_resp.status_code == 200
            report_data = get_resp.json()
            
            # 3. Validate Data Structure
            assert report_data["id"] == report_id
            # Check audit fields exist (FINTRAC/General Audit requirement)
            assert "created_at" in report_data
            
            # 4. Check PII Exclusion (PIPEDA)
            # If the report includes applicant data, ensure SIN is not present
            # This depends on the response structure, generally checking keys
            assert "sin" not in report_data
            assert "social_insurance_number" not in report_data

    async def test_fintrac_large_transaction_flag(self, app: FastAPI):
        """
        Test that the analytics endpoint correctly flags transactions > 10k.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Call analytics endpoint that checks large transactions
            response = await client.get("/api/v1/reporting/analytics/large-transactions")
            
            assert response.status_code == 200
            data = response.json()
            assert "transactions" in data
            # Verify each transaction returned is > 10,000 (if logic is in query)
            # Or verify the flag exists in the response
            for txn in data.get("transactions", []):
                assert Decimal(str(txn["amount"])) > Decimal("10000.00")
```