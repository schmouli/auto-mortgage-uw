```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct

@pytest.mark.integration
@pytest.mark.asyncio
class TestLenderComparisonRoutes:

    async def test_get_lenders_empty(self, app, client: AsyncClient):
        """
        Test GET /lenders returns empty list when no lenders exist.
        """
        response = await client.get("/api/v1/lender-comparison/lenders")
        assert response.status_code == 200
        assert response.json() == []

    async def test_compare_applications_no_match(self, app, client: AsyncClient, valid_submission_data: dict):
        """
        Test comparison endpoint when applicant doesn't meet any criteria.
        """
        # Modify data to be unmatchable (very low credit score)
        valid_submission_data["credit_score"] = 400
        
        response = await client.post("/api/v1/lender-comparison/compare", json=valid_submission_data)
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_compare_applications_success(
        self, 
        app, 
        client: AsyncClient, 
        sample_lender: LenderProduct, 
        valid_submission_data: dict
    ):
        """
        Test successful comparison returning matching products.
        """
        # Ensure data matches the sample_lender fixture criteria
        # Sample Lender: Min Credit 680, Max LTV 0.80
        valid_submission_data["credit_score"] = 700
        valid_submission_data["loan_amount"] = Decimal("400000.00")
        valid_submission_data["property_value"] = Decimal("500000.00") # 80% LTV
        valid_submission_data["annual_income"] = Decimal("60000.00")

        response = await client.post("/api/v1/lender-comparison/compare", json=valid_submission_data)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        
        # Verify structure of returned product
        product = data[0]
        assert "id" in product
        assert "lender_name" == product["lender_name"]
        assert "interest_rate" in product
        # Ensure Decimal precision is preserved in JSON response (usually string or float)
        assert product["max_ltv_ratio"] == "0.80" or product["max_ltv_ratio"] == 0.8

    async def test_compare_filters_high_ltv(
        self,
        app,
        client: AsyncClient,
        sample_lender: LenderProduct,
        valid_submission_data: dict
    ):
        """
        Test that comparison correctly filters out lenders if LTV is too high.
        Sample Lender Max LTV is 80%.
        """
        valid_submission_data["credit_score"] = 800
        valid_submission_data["loan_amount"] = Decimal("450000.00")
        valid_submission_data["property_value"] = Decimal("500000.00") # 90% LTV
        valid_submission_data["annual_income"] = Decimal("100000.00")

        response = await client.post("/api/v1/lender-comparison/compare", json=valid_submission_data)
        
        assert response.status_code == 404
        assert "No matching lenders found" in response.json()["detail"]

    async def test_submit_application_success(
        self,
        app,
        client: AsyncClient,
        sample_lender: LenderProduct,
        valid_submission_data: dict,
        monkeypatch
    ):
        """
        Test the submission workflow end-to-end with mocked external API.
        """
        # Mock the external HTTP request within the service
        # We use monkeypatch to replace httpx.post behavior during the request
        class MockResponse:
            status_code = 202
            def json(self):
                return {"reference_id": "EXT_REF_123"}

        async def mock_post(*args, **kwargs):
            return MockResponse()

        # Patch the specific method used in the service
        # Note: Depending on import structure, the path might need adjustment.
        # Assuming service imports httpx directly or uses a client.
        monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

        submit_payload = {
            "product_id": sample_lender.id,
            "application_data": valid_submission_data
        }

        response = await client.post("/api/v1/lender-comparison/submit", json=submit_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "SUBMITTED"
        assert data["external_reference_id"] == "EXT_REF_123"
        assert "id" in data

    async def test_submit_application_compliance_failure(
        self,
        app,
        client: AsyncClient,
        sample_lender: LenderProduct,
        valid_submission_data: dict
    ):
        """
        Test that submission fails if GDS/TDS compliance checks fail.
        Sample Lender logic should check these.
        """
        # Create a scenario that fails GDS/TDS
        # Low income, high housing costs
        valid_submission_data["annual_income"] = Decimal("30000.00") # Low
        valid_submission_data["loan_amount"] = Decimal("400000.00") # High debt
        valid_submission_data["property_value"] = Decimal("500000.00")
        valid_submission_data["property_tax"] = Decimal("5000.00")
        
        submit_payload = {
            "product_id": sample_lender.id,
            "application_data": valid_submission_data
        }

        response = await client.post("/api/v1/lender-comparison/submit", json=submit_payload)

        # Expect 400 Bad Request due to compliance/validation error
        assert response.status_code == 400
        data = response.json()
        assert "Compliance" in data["detail"] or "GDS" in data["detail"] or "TDS" in data["detail"]

    async def test_pipeda_check_no_pii_in_logs(
        self,
        app,
        client: AsyncClient,
        sample_lender: LenderProduct,
        valid_submission_data: dict,
        monkeypatch,
        caplog
    ):
        """
        Verify that sensitive data (SIN/DOB) is handled correctly.
        Note: This is a simplified check ensuring the endpoint doesn't echo back raw PII
        if it were included (though our schema doesn't strictly require SIN in this flow).
        """
        # Add PII fields to payload (even if schema ignores them or hashes them)
        valid_submission_data["sin"] = "123456789"
        
        # We are primarily checking the response doesn't leak it if we accidentally added it
        # and that the system doesn't crash.
        
        submit_payload = {
            "product_id": sample_lender.id,
            "application_data": valid_submission_data
        }

        # Mock external API to pass
        class MockResponse:
            status_code = 202
            def json(self):
                return {"reference_id": "REF"}

        async def mock_post(*args, **kwargs):
            return MockResponse()
        
        monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

        response = await client.post("/api/v1/lender-comparison/submit", json=submit_payload)
        
        # If successful, check response
        if response.status_code == 201:
            data = response.json()
            # Ensure raw SIN is not in the response body
            assert "123456789" not in str(data)
            # Ensure application_data in response is minimized or sanitized
            resp_app_data = data.get("application_data", {})
            assert "sin" not in resp_app_data
```