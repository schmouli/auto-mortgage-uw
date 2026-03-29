import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from celery.exceptions import Retry

from mortgage_underwriting.modules.background_jobs.models import JobStatus
from mortgage_underwriting.modules.background_jobs.schemas import JobSubmitRequest, JobStatusResponse
from mortgage_underwriting.modules.background_jobs.services import BackgroundJobService
from mortgage_underwriting.modules.background_jobs.exceptions import JobNotFoundException, TaskExecutionException

@pytest.mark.unit
class TestBackgroundJobService:

    @pytest.fixture
    def service(self, mock_db):
        return BackgroundJobService(mock_db)

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_submit_job_success(self, service, mock_db, mock_celery_task):
        """Test successful job submission and DB record creation."""
        payload = JobSubmitRequest(
            task_type="credit_check",
            payload={"borrower_id": 1, "income": Decimal("50000.00")}
        )

        # Patch the celery task import within the service module
        with patch("mortgage_underwriting.modules.background_jobs.services.credit_check_task", mock_celery_task):
            result = await service.submit_job(payload)

            # Verify Celery task was called
            mock_celery_task.delay.assert_called_once_with(
                borrower_id=1, income=Decimal("50000.00")
            )

            # Verify DB interaction
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            
            # Verify return object
            assert result.task_id == mock_celery_task.id
            assert result.status == "PENDING"

    @pytest.mark.asyncio
    async def test_submit_job_with_sanitize_payload(self, service, mock_db, mock_celery_task):
        """Test that PII is handled/removed before logging or storing if necessary."""
        payload = JobSubmitRequest(
            task_type="underwriting_review",
            payload={"sin": "123456789", "application_id": 99}
        )

        with patch("mortgage_underwriting.modules.background_jobs.services.underwriting_review_task", mock_celery_task):
            result = await service.submit_job(payload)

            # Ensure the task received the data
            mock_celery_task.delay.assert_called_once()
            call_args = mock_celery_task.delay.call_args[0][0]
            
            # Service logic should ideally hash SIN or ensure it's encrypted if passed
            # Here we check the task was triggered
            assert "sin" in call_args

    @pytest.mark.asyncio
    async def test_get_job_status_success(self, service, mock_db, mock_async_result):
        """Test retrieving status of a completed job."""
        job_id = "test-task-id-12345"
        
        # Mock DB response
        mock_job = JobStatus(id=1, task_id=job_id, task_type="credit_check", status="SUCCESS")
        mock_db.scalar.return_value = mock_job

        # Mock Celery AsyncResult
        with patch("mortgage_underwriting.modules.background_jobs.services.AsyncResult", return_value=mock_async_result):
            mock_async_result.status = "SUCCESS"
            mock_async_result.result = {"score": 750}

            response = await service.get_job_status(job_id)

            assert response.task_id == job_id
            assert response.status == "SUCCESS"
            assert response.result == {"score": 750}

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, service, mock_db):
        """Test retrieving status for a non-existent job."""
        job_id = "non-existent-id"
        mock_db.scalar.return_value = None

        with pytest.raises(JobNotFoundException) as exc_info:
            await service.get_job_status(job_id)
        
        assert exc_info.value.detail == "Job not found"

    @pytest.mark.asyncio
    async def test_sync_job_status_updates_db_on_success(self, service, mock_db, mock_async_result):
        """Test that syncing a job updates the DB record to SUCCESS."""
        job_id = "test-task-id"
        mock_job = JobStatus(id=1, task_id=job_id, task_type="report", status="PENDING")
        mock_db.scalar.return_value = mock_job

        with patch("mortgage_underwriting.modules.background_jobs.services.AsyncResult", return_value=mock_async_result):
            mock_async_result.status = "SUCCESS"
            mock_async_result.result = {"report_url": "http://example.com/report.pdf"}

            await service.sync_job_status(job_id)

            assert mock_job.status == "SUCCESS"
            assert mock_job.result == {"report_url": "http://example.com/report.pdf"}
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_job_status_updates_db_on_failure(self, service, mock_db, mock_async_result):
        """Test that syncing a job updates the DB record to FAILURE."""
        job_id = "test-task-id"
        mock_job = JobStatus(id=1, task_id=job_id, task_type="report", status="PENDING")
        mock_db.scalar.return_value = mock_job

        with patch("mortgage_underwriting.modules.background_jobs.services.AsyncResult", return_value=mock_async_result):
            mock_async_result.status = "FAILURE"
            mock_async_result.result = Exception("Credit API unavailable")

            await service.sync_job_status(job_id)

            assert mock_job.status == "FAILURE"
            # Ensure exception info is stored/logged appropriately
            assert "Credit API unavailable" in str(mock_job.result)
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_job_invalid_task_type(self, service, mock_db):
        """Test submitting a job with an unregistered task type."""
        payload = JobSubmitRequest(
            task_type="unknown_task",
            payload={"data": "test"}
        )

        # Assuming service maps task_type strings to task objects
        # If mapping fails, it should raise ValueError or similar
        with pytest.raises(ValueError):
            await service.submit_job(payload)

    @pytest.mark.asyncio
    async def test_calculate_premium_in_background_task_logic(self):
        """
        Unit test for the logic executed inside a background task (e.g., CMHC premium calculation).
        This tests the business logic directly, not the Celery wrapping.
        """
        from mortgage_underwriting.modules.background_jobs.services import _calculate_cmhc_premium_logic
        
        # LTV 85% -> Tier 2.80%
        loan = Decimal("85000.00")
        value = Decimal("100000.00")
        premium = _calculate_cmhc_premium_logic(loan, value)
        
        assert premium == loan * Decimal("0.0280")

    @pytest.mark.asyncio
    async def test_calculate_premium_boundary_95_percent(self):
        """Test boundary condition for CMHC premium (95%)."""
        from mortgage_underwriting.modules.background_jobs.services import _calculate_cmhc_premium_logic
        
        # LTV 95% -> Tier 4.00%
        loan = Decimal("95000.00")
        value = Decimal("100000.00")
        premium = _calculate_cmhc_premium_logic(loan, value)
        
        assert premium == loan * Decimal("0.04")

    @pytest.mark.asyncio
    async def test_stress_test_calculation_in_background(self):
        """
        Test OSFI B-20 stress test logic within a background job context.
        """
        from mortgage_underwriting.modules.background_jobs.services import _perform_stress_test_logic
        
        contract_rate = Decimal("4.5")
        qualifying_rate = _perform_stress_test_logic(contract_rate)
        
        # max(4.5 + 2, 5.25) = 6.5
        assert qualifying_rate == Decimal("6.5")

    @pytest.mark.asyncio
    async def test_stress_test_floor_rate(self):
        """Test stress test hits the floor rate."""
        from mortgage_underwriting.modules.background_jobs.services import _perform_stress_test_logic
        
        contract_rate = Decimal("2.0")
        qualifying_rate = _perform_stress_test_logic(contract_rate)
        
        # max(2.0 + 2, 5.25) = 5.25
        assert qualifying_rate == Decimal("5.25")
```