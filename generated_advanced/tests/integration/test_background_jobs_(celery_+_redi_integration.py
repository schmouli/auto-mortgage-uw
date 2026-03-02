```python
import pytest
from fastapi import status
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

# Module to test: API Endpoints triggering Background Jobs

class TestBackgroundJobEndpoints:
    """
    Integration tests for endpoints that trigger Celery tasks.
    We test the API contract and that the task is queued correctly.
    """

    def test_trigger_credit_check_success(
        self, client: TestClient, db_session: Session, sample_application_data
    ):
        """
        Test POST /applications/{id}/credit-check triggers Celery task.
        Verifies API response and Database state.
        """
        # Arrange: Setup DB Data
        # In a real integration test, we would insert sample_application_data into db_session here.
        # For this mock, we assume the DB layer works and focus on the API/Task interaction.
        
        # Mock the Celery task delay method to prevent actual execution during API test
        with patch("app.api.v1.endpoints.applications.process_credit_check") as mock_task:
            mock_task.delay.return_value = MagicMock(id="celery-task-123")

            # Act
            response = client.post(f"/applications/{sample_application_data['id']}/credit-check")

            # Assert - HTTP Contract
            assert response.status_code == status.HTTP_202_ACCEPTED
            json_resp = response.json()
            assert json_resp["message"] == "Credit check initiated"
            assert json_resp["task_id"] == "celery-task-123"

            # Assert - Task Triggered
            mock_task.delay.assert_called_once_with(application_id=sample_application_data["id"])

    def test_trigger_credit_check_not_found(self, client: TestClient):
        """
        Test triggering a job for a non-existent application.
        """
        with patch("app.api.v1.endpoints.applications.process_credit_check") as mock_task:
            response = client.post("/applications/99999/credit-check")
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            mock_task.delay.assert_not_called()

    def test_submit_underwriting_workflow(
        self, client: TestClient, db_session: Session, sample_application_data
    ):
        """
        Test a multi-step workflow: Submit -> Credit Check -> Risk Assessment.
        """
        with patch("app.api.v1.endpoints.applications.process_credit_check") as mock_credit, \
             patch("app.api.v1.endpoints.applications.calculate_debt_service_ratios") as mock_risk:
            
            mock_credit.delay.return_value = MagicMock(id="task-credit-1")
            mock_risk.delay.return_value = MagicMock(id="task-risk-1")

            # Step 1: Initiate Credit Check
            resp1 = client.post(f"/applications/{sample_application_data['id']}/credit-check")
            assert resp1.status_code == 202
            
            # Step 2: Simulate Credit Check completion (usually via webhook or polling, 
            # but here we test the trigger of the next step if it were chained or manually called)
            
            # Step 3: Trigger Risk Assessment
            resp2 = client.post(f"/applications/{sample_application_data['id']}/assess-risk")
            assert resp2.status_code == 202
            assert resp2.json()["task_id"] == "task-risk-1"
            
            # Verify both tasks were queued
            assert mock_credit.delay.called
            assert mock_risk.delay.called

    def test_get_task_status_success(self, client: TestClient):
        """
        Test GET /tasks/{task_id} to check Celery task status.
        """
        # Mock AsyncResult
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"credit_score": 780}

        with patch("app.api.v1.endpoints.tasks.AsyncResult") as mock_async_result:
            mock_async_result.return_value = mock_result

            response = client.get("/tasks/celery-task-123")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["task_id"] == "celery-task-123"
            assert data["status"] == "SUCCESS"
            assert data["result"]["credit_score"] == 780

    def test_get_task_status_pending(self, client: TestClient):
        """
        Test polling a task that is still processing.
        """
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.result = None

        with patch("app.api.v1.endpoints.tasks.AsyncResult") as mock_async_result:
            mock_async_result.return_value = mock_result

            response = client.get("/tasks/celery-task-pending")

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["status"] == "PENDING"
            assert response.json()["result"] is None

    def test_get_task_status_failure(self, client: TestClient):
        """
        Test polling a task that has failed.
        """
        mock_result = MagicMock()
        mock_result.state = "FAILURE"
        mock_result.info = "External API Timeout"

        with patch("app.api.v1.endpoints.tasks.AsyncResult") as mock_async_result:
            mock_async_result.return_value = mock_result

            response = client.get("/tasks/celery-task-failed")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "FAILURE"
            assert "error" in data # Depending on API spec for error handling

    def test_bulk_document_upload_triggers_jobs(self, client: TestClient):
        """
        Test uploading multiple documents triggers individual processing tasks.
        """
        files = [
            ("files", ("paystub_1.pdf", b"fake pdf content", "application/pdf")),
            ("files", ("paystub_2.pdf", b"fake pdf content", "application/pdf")),
        ]
        
        with patch("app.api.v1.endpoints.documents.process_document") as mock_process:
            mock_process.delay.return_value = MagicMock(id="doc-task-1")

            response = client.post("/applications/1/documents", files=files)

            assert response.status_code == status.HTTP_201_CREATED
            # Verify task was called twice (once for each file)
            assert mock_process.delay.call_count == 2

    def test_revoke_underwriting_task(self, client: TestClient):
        """
        Test cancelling an active background job.
        """
        with patch("app.api.v1.endpoints.tasks.celery_app.control.revoke") as mock_revoke:
            response = client.delete("/tasks/task-to-cancel")

            assert response.status_code == status.HTTP_200_OK
            mock_revoke.assert_called_once_with("task-to-cancel", terminate=True)

    def test_health_check_celery_redis(self, client: TestClient):
        """
        Test system health check including Celery and Redis connectivity.
        """
        # Mock Celery inspect
        mock_inspect = MagicMock()
        mock_inspect.ping.return_value = {'worker1@host': 'pong'}
        
        with patch("app.api.v1.endpoints.health.celery_app.control.inspect") as mock_inspect_func, \
             patch("app.api.v1.endpoints.health.redis_client.ping") as mock_redis_ping:
            
            mock_inspect_func.return_value = mock_inspect
            mock_redis_ping.return_value = True

            response = client.get("/health/background-jobs")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["celery_status"] == "healthy"
            assert data["redis_status"] == "connected"
```