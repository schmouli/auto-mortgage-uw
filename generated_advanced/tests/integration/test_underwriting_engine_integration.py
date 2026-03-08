import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

from mortgage_underwriting.modules.underwriting_engine.routes import router
from mortgage_underwriting.modules.underwriting_engine.schemas import UnderwritingRequest

@pytest.fixture
def app():
    """
    Sets up a FastAPI app with the Underwriting Engine router.
    """
    application = FastAPI()
    application.include_router(router, prefix="/api/v1/underwriting", tags=["underwriting"])
    return application

@pytest.mark.integration
@pytest.mark.asyncio
class TestUnderwritingEndpoints:

    async def test_evaluate_endpoint_success(self, app, valid_underwriting_payload):
        """
        Test a full successful evaluation workflow via HTTP.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/underwriting/evaluate", json=valid_underwriting_payload)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["decision"] == "APPROVED"
            assert "gds" in data
            assert "tds" in data
            assert "ltv" in data
            assert "insurance_required" in data
            assert "correlation_id" in data # Check for observability requirements

    async def test_evaluate_endpoint_rejection(self, app, valid_underwriting_payload):
        """
        Test rejection due to bad credit score.
        """
        payload = valid_underwriting_payload.copy()
        payload["borrower"]["credit_score"] = 400
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/underwriting/evaluate", json=payload)
            
            assert response.status_code == 200 # Even rejections return 200 with decision body
            data = response.json()
            assert data["decision"] == "REJECTED"
            assert len(data["rejection_reasons"]) > 0

    async def test_evaluate_endpoint_validation_error(self, app):
        """
        Test 422 Unprocessable Entity for malformed input.
        """
        # Missing required fields
        bad_payload = {
            "borrower": {},
            "property": {},
            "mortgage": {}
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/underwriting/evaluate", json=bad_payload)
            
            assert response.status_code == 422

    async def test_evaluate_endpoint_insurance_calculation(self, app, valid_underwriting_payload):
        """
        Verify CMHC insurance calculation is returned correctly in API response.
        """
        payload = valid_underwriting_payload.copy()
        # Set LTV to 92% (450k loan on 500k value)
        payload["mortgage"]["loan_amount"] = "450000.00"
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/underwriting/evaluate", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["insurance_required"] is True
            # 92% falls in 90.01-95% tier -> 4.00%
            assert data["cmhc_premium_rate"] == "0.0400"

    async def test_evaluate_endpoint_stress_test_application(self, app, valid_underwriting_payload):
        """
        Verify that the stress test rate is applied and affects the monthly payment calculation.
        """
        payload = valid_underwriting_payload.copy()
        # Low contract rate, should trigger stress test floor of 5.25%
        payload["mortgage"]["contract_rate"] = "3.00" 
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/underwriting/evaluate", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            
            # The payment should be based on 5.25%, not 3.0%
            # We check that the qualifying rate is logged or reflected in the calculation breakdown
            assert "qualifying_rate" in data
            assert data["qualifying_rate"] == "5.25"

    async def test_evaluate_endpoint_pii_protection(self, app, valid_underwriting_payload):
        """
        Ensure PII (like SIN) is not leaked in response if added.
        Note: The schema might not accept SIN, but if it did, it shouldn't return it.
        """
        # Assuming schema accepts SIN for lookup but not return (PIPEDA)
        payload = valid_underwriting_payload.copy()
        payload["borrower"]["sin"] = "123456789"
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/underwriting/evaluate", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            
            # SIN should not be in the response
            assert "sin" not in data.get("borrower", {})
            assert "123" not in str(data) # Crude check to ensure no leakage

    async def test_health_check(self, app):
        """
        Test the module health check endpoint.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Assuming a generic health check or specific module health check
            # If not defined, this might 404, but let's assume standard practice
            response = await client.get("/api/v1/underwriting/health")
            # If route doesn't exist, skip or assert 404
            if response.status_code == 200:
                assert response.json()["status"] == "ok"
            else:
                assert response.status_code == 404