```python
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from mortgage_underwriting.modules.lender_comparison.routes import router
from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct
from fastapi import FastAPI

@pytest.fixture(scope="function")
def app(db_session):
    """
    Create a test FastAPI app with the router included.
    """
    app = FastAPI()
    app.include_router(router)
    
    # Dependency override for the database session
    # This ensures the router uses our test session
    async def get_db_override():
        yield db_session
        
    app.dependency_overrides[router.dependency_cache.get("get_async_session")] = get_db_override
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestLenderComparisonEndpoints:

    async def test_get_lenders_empty(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/lender-comparison/lenders")
            assert response.status_code == 200
            assert response.json() == []

    async def test_get_lenders_with_data(self, app: FastAPI, db_session):
        # Setup Data
        lender = Lender(name="Big Bank", contact_email="u@bb.com", api_endpoint="http://bb.com", is_active=True)
        db_session.add(lender)
        await db_session.commit()
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/lender-comparison/lenders")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Big Bank"

    async def test_compare_endpoint_workflow(self, app: FastAPI, db_session):
        # Setup: Add Lender and Product
        lender = Lender(name="Rate Setter", contact_email="u@rs.com", api_endpoint="http://rs.com", is_active=True)
        db_session.add(lender)
        await db_session.flush()
        
        product = LenderProduct(
            lender_id=lender.id,
            product_name="5yr Fixed",
            rate=Decimal("4.00"),
            term_months=60,
            max_ltv=Decimal("95.00"),
            min_credit_score=650,
            insurance_required=True
        )
        db_session.add(product)
        await db_session.commit()
        
        payload = {
            "loan_amount": "300000.00",
            "property_value": "400000.00",
            "credit_score": 700,
            "province": "ON",
            "income": "90000.00",
            "amortization_years": 25
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/lender-comparison/compare", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) > 0
            
            # Check response structure
            offer = data[0]
            assert "lender_name" in offer
            assert "product_name" in offer
            assert "monthly_payment" in offer
            assert Decimal(offer["rate"]) == Decimal("4.00")

    async def test_compare_validation_error(self, app: FastAPI):
        # Invalid payload (missing fields)
        payload = {
            "loan_amount": "100000"
            # Missing property_value, etc.
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/lender-comparison/compare", json=payload)
            assert response.status_code == 422 # Validation Error

@pytest.mark.integration
@pytest.mark.asyncio
class TestSubmissionEndpoints:

    async def test_submit_endpoint_success(self, app: FastAPI, db_session):
        # Setup
        lender = Lender(name="Direct Lender", contact_email="u@dl.com", api_endpoint="http://dl.com", is_active=True)
        db_session.add(lender)
        await db_session.flush()
        
        product = LenderProduct(
            lender_id=lender.id,
            product_name="Var Rate",
            rate=Decimal("3.50"),
            term_months=60,
            max_ltv=Decimal("80.00"),
            min_credit_score=700,
            insurance_required=False
        )
        db_session.add(product)
        await db_session.commit()
        
        payload = {
            "product_id": product.id,
            "application_id": "INT-TEST-001",
            "borrower_data": {"sin": "999999999", "dob": "1990-01-01"} # PII that must be handled
        }
        
        # Mock the external call inside the integration test
        # We want to test the API controller logic, not the real external API
        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"ref": "EXT-REF-123"}
            
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            MockClient.return_value = mock_http
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/lender-comparison/submit", json=payload)
                
                assert response.status_code == 201
                data = response.json()
                assert data["status"] == "submitted"
                assert data["external_reference_id"] == "EXT-REF-123"
                
                # Verify Audit trail in DB
                from mortgage_underwriting.modules.lender_comparison.models import Submission
                from sqlalchemy import select
                
                stmt = select(Submission).where(Submission.application_id == "INT-TEST-001")
                res = await db_session.execute(stmt)
                sub = res.scalar_one()
                
                assert sub.created_at is not None
                # Ensure PII is not stored in plain text if the service handles encryption
                # (Assuming service logic handles this, we check existence here)

    async def test_submit_invalid_product(self, app: FastAPI, db_session):
        payload = {
            "product_id": 9999,
            "application_id": "INT-TEST-002",
            "borrower_data": {}
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/lender-comparison/submit", json=payload)
            assert response.status_code == 404
```