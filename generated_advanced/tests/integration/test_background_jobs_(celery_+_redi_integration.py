```python
import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.background_jobs.models import TaskExecutionLog

@pytest.mark.integration
@pytest.mark.asyncio
class TestBackgroundJobsAPI:

    async def test_trigger_job_endpoint_202_accepted(self, client: AsyncClient, valid_mortgage_payload):
        """
        Test API contract for triggering a job.
        Expect 202 Accepted and a task_id in response.
        """
        response = await client.post("/api/v1/background-jobs/trigger", json=valid_mortgage_payload)
        
        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "PENDING"

    async def test_trigger_job_persists_log(self, client: AsyncClient, db_session, valid_mortgage_payload):
        """
        Test that triggering a job creates an immutable audit record in DB.
        """
        response = await client.post("/api/v1/background-jobs/trigger", json=valid_mortgage_payload)
        task_id = response.json()["task_id"]

        # Verify DB state
        stmt = select(TaskExecutionLog).where(TaskExecutionLog.id == task_id)
        result = await db_session.execute(stmt)
        log_entry = result.scalar_one_or_none()

        assert log_entry is not None
        assert log_entry.task_name == "mortgage_underwriting_task"
        assert log_entry.status == "PENDING"
        assert log_entry.created_at is not None # FINTRAC: Audit timestamp

    async def test_get_status_endpoint(self, client: AsyncClient, valid_mortgage_payload):
        """
        Test retrieving status of a submitted job.
        """
        # 1. Trigger job
        trigger_resp = await client.post("/api/v1/background-jobs/trigger", json=valid_mortgage_payload)
        task_id = trigger_resp.json()["task_id"]

        # 2. Get status
        status_resp = await client.get(f"/api/v1/background-jobs/status/{task_id}")
        
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["task_id"] == task_id
        # Status might be PENDING or SUCCESS depending on mocked worker speed in real env,
        # but in integration test without worker, usually PENDING unless mocked.
        assert "status" in data

    async def test_get_status_404_if_not_found(self, client: AsyncClient):
        """Test structured error response for missing task."""
        fake_id = "non-existent-id-999"
        response = await client.get(f"/api/v1/background-jobs/status/{fake_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error_code" in data

    async def test_batch_workflow_integration(self, client: AsyncClient, valid_batch_payload):
        """
        Test multi-step workflow: Trigger Batch -> Check Status -> Verify Logs.
        """
        # Step 1: Trigger Batch
        batch_resp = await client.post("/api/v1/background-jobs/batch", json=valid_batch_payload)
        assert batch_resp.status_code == 202
        batch_id = batch_resp.json()["batch_id"]

        # Step 2: Verify individual task triggers (simulated via audit logs if available)
        # For this test, we verify the batch initiation record exists
        status_resp = await client.get(f"/api/v1/background-jobs/batch/{batch_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "PROCESSING"

    async def test_input_validation_422(self, client: AsyncClient):
        """Test API rejects invalid payloads (e.g., negative amounts)."""
        invalid_payload = {
            "application_id": "app-001",
            "loan_amount": "-100.00", # Invalid
            "property_value": "500000.00"
        }
        
        response = await client.post("/api/v1/background-jobs/trigger", json=invalid_payload)
        assert response.status_code == 422

    async def test_pii_not_exposed_in_response(self, client: AsyncClient, valid_mortgage_payload):
        """
        Test PIPEDA compliance: Ensure SIN/PII is not returned in API responses.
        """
        # Trigger job
        response = await client.post("/api/v1/background-jobs/trigger", json=valid_mortgage_payload)
        assert response.status_code == 202
        
        # Check status response
        task_id = response.json()["task_id"]
        status_resp = await client.get(f"/api/v1/background-jobs/status/{task_id}")
        data = status_resp.json()
        
        # Ensure raw SIN is not in the response
        assert "123456789" not in str(data)
        assert "sin" not in data

    async def test_fintrac_retention_simulation(self, client: AsyncClient, db_session):
        """
        Test that audit logs are created correctly for retention requirements.
        """
        payload = {
            "task_name": "fintrac_report",
            "params": {"transaction_id": "txn_999"}
        }
        
        await client.post("/api/v1/background-jobs/trigger", json=payload)
        
        # Query logs
        stmt = select(TaskExecutionLog).where(TaskExecutionLog.task_name == "fintrac_report")
        result = await db_session.execute(stmt)
        logs = result.scalars().all()
        
        assert len(logs) > 0
        # Verify immutable fields are present
        for log in logs:
            assert log.id is not None
            assert log.created_at is not None
```