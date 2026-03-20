```python
import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

# Import models to verify DB state
from mortgage_underwriting.modules.testing_suite.models import StressTestResult

@pytest.mark.integration
class TestStressTestEndpoints:
    """
    Integration tests for the Testing Suite API endpoints.
    Tests the full request/response cycle and database persistence.
    """

    @pytest.mark.asyncio
    async def test_post_stress_test_success(self, client: AsyncClient, valid_stress_test_payload, db_session):
        """
        Test a successful stress test submission via API.
        Verifies HTTP 201, response structure, and DB insertion.
        """
        response = await client.post("/api/v1/testing-suite/run", json=valid_stress_test_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["applicant_id"] == "test-app-001"
        assert data["is_passed"] is True
        assert Decimal(data["qualifying_rate"]) == Decimal("6.50")
        assert Decimal(data["gds_ratio"]) <= Decimal("39.00")
        assert Decimal(data["tds_ratio"]) <= Decimal("44.00")
        assert "created_at" in data

        # Verify Database Persistence
        stmt = select(StressTestResult).where(StressTestResult.id == data["id"])
        result = await db_session.execute(stmt)
        db_record = result.scalar_one()
        
        assert db_record is not None
        assert db_record.applicant_id == "test-app-001"
        assert db_record.is_passed is True

    @pytest.mark.asyncio
    async def test_post_stress_test_fail_gds(self, client: AsyncClient, high_gds_payload, db_session):
        """
        Test stress test resulting in failure due to high GDS.
        """
        response = await client.post("/api/v1/testing-suite/run", json=high_gds_payload)
        
        assert response.status_code == 201 # We accept the result even if failed
        data = response.json()
        
        assert data["is_passed"] is False
        assert Decimal(data["gds_ratio"]) > Decimal("39.00")

    @pytest.mark.asyncio
    async def test_post_stress_test_validation_error(self, client: AsyncClient):
        """
        Test API validation with malformed payload (missing fields).
        """
        incomplete_payload = {
            "applicant_id": "test"
            # Missing all required financial fields
        }
        
        response = await client.post("/api/v1/testing-suite/run", json=incomplete_payload)
        
        assert response.status_code == 422
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_post_stress_test_invalid_type(self, client: AsyncClient, valid_stress_test_payload):
        """
        Test API validation with incorrect data types (string instead of number).
        """
        bad_payload = valid_stress_test_payload.copy()
        bad_payload["loan_amount"] = "not-a-number"
        
        response = await client.post("/api/v1/testing-suite/run", json=bad_payload)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_stress_test_history(self, client: AsyncClient, valid_stress_test_payload, db_session):
        """
        Test retrieving history for a specific applicant.
        """
        # 1. Create a record
        post_resp = await client.post("/api/v1/testing-suite/run", json=valid_stress_test_payload)
        assert post_resp.status_code == 201
        applicant_id = post_resp.json()["applicant_id"]

        # 2. Retrieve history
        get_resp = await client.get(f"/api/v1/testing-suite/history/{applicant_id}")
        
        assert get_resp.status_code == 200
        history = get_resp.json()
        assert isinstance(history, list)
        assert len(history) >= 1
        assert history[0]["applicant_id"] == applicant_id

    @pytest.mark.asyncio
    async def test_get_stress_test_result_by_id(self, client: AsyncClient, valid_stress_test_payload):
        """
        Test retrieving a specific stress test result by ID.
        """
        # 1. Create
        post_resp = await client.post("/api/v1/testing-suite/run", json=valid_stress_test_payload)
        result_id = post_resp.json()["id"]

        # 2. Get by ID
        get_resp = await client.get(f"/api/v1/testing-suite/{result_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == result_id
        assert "qualifying_rate" in data

    @pytest.mark.asyncio
    async def test_get_stress_test_not_found(self, client: AsyncClient):
        """
        Test retrieving a non-existent result returns 404.
        """
        get_resp = await client.get("/api/v1/testing-suite/99999")
        assert get_resp.status_code == 404
        assert "detail" in get_resp.json()

    @pytest.mark.asyncio
    async def test_osfi_compliance_logging(self, client: AsyncClient, valid_stress_test_payload, caplog):
        """
        Test that the calculation breakdown is logged for audit purposes (OSFI B-20).
        Note: This depends on the implementation using structlog/logger.
        """
        # Assuming the endpoint logs the calculation details
        with caplog.at_level("INFO"):
            response = await client.post("/api/v1/testing-suite/run", json=valid_stress_test_payload)
            assert response.status_code == 201
            
            # Check if any log contains calculation keywords
            # This is a basic check; real implementation might check specific JSON log output
            logs = [record.message for record in caplog.records]
            assert any("qualifying_rate" in msg.lower() for msg in logs) or \
                   any("gds" in msg.lower() for msg in logs)

    @pytest.mark.asyncio
    async def test_security_no_pii_in_response(self, client: AsyncClient, valid_stress_test_payload):
        """
        Ensure PII (SIN, DOB) is not leaked in the response.
        Assuming the payload might contain PII (though schema minimizes it),
        ensure it doesn't echo back if it wasn't explicitly requested or if handled securely.
        """
        # Add a hypothetical SIN field (if schema allowed it, though PIPEDA says minimize)
        # Since our defined schema in conftest doesn't have SIN, we check existing fields.
        response = await client.post("/api/v1/testing-suite/run", json=valid_stress_test_payload)
        data = response.json()
        
        # Ensure no sensitive internal IDs or raw data leaks
        # Just a structural check for this example
        assert "sin" not in data
        assert "dob" not in data
```