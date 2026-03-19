import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from sqlalchemy import select
from structlog import testing

from mortgage_underwriting.modules.background_jobs.services import BackgroundJobService
from mortgage_underwriting.modules.background_jobs.models import BackgroundJob
from mortgage_underwriting.modules.background_jobs.exceptions import JobDispatchError
from mortgage_underwriting.modules.mortgage.models import Mortgage
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.unit
class TestBackgroundJobService:

    @pytest.fixture
    def service(self, mock_celery_app):
        return BackgroundJobService(celery_app=mock_celery_app)

    @pytest.mark.asyncio
    async def test_dispatch_report_generation_success(self, service, mock_celery_app, mock_db):
        """
        Test successfully dispatching a report generation job.
        """
        application_id = 1
        report_type = "mortgage_summary"

        # Mock DB behavior
        mock_db.execute = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None) # No existing job
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Capture logging
        with testing.capture_logs() as cap_logs:
            job_id = await service.dispatch_report_generation(
                db=mock_db, 
                application_id=application_id, 
                report_type=report_type
            )

        # Assertions
        assert job_id == "test-task-id-12345"
        mock_celery_app.send_task.assert_called_once_with(
            "tasks.generate_report",
            args=[application_id, report_type],
            kwargs={}
        )
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

        # Regulatory: Check logs do not contain PII
        for log in cap_logs:
            assert "sin" not in log.lower()
            assert "date_of_birth" not in log.lower()

    @pytest.mark.asyncio
    async def test_dispatch_archive_success(self, service, mock_celery_app, mock_db):
        """
        Test successfully dispatching an archive job (FINTRAC retention).
        """
        application_id = 5
        
        mock_db.execute = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        job_id = await service.dispatch_archive_job(db=mock_db, application_id=application_id)

        assert job_id == "test-task-id-12345"
        mock_celery_app.send_task.assert_called_once_with(
            "tasks.archive_application_data",
            args=[application_id]
        )
        mock_db.add.assert_called_once()
        
        # Verify the job record was added
        added_job = mock_db.add.call_args[0][0]
        assert isinstance(added_job, BackgroundJob)
        assert added_job.status == "PENDING"
        assert added_job.task_name == "tasks.archive_application_data"

    @pytest.mark.asyncio
    async def test_dispatch_job_database_failure(self, service, mock_celery_app, mock_db):
        """
        Test handling of DB errors during job dispatch.
        """
        mock_db.commit = AsyncMock(side_effect=Exception("DB Connection Lost"))

        with pytest.raises(AppException) as exc_info:
            await service.dispatch_report_generation(
                db=mock_db, 
                application_id=1, 
                report_type="stress_test"
            )
        
        assert "Failed to record job" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_job_status_success(self, service, mock_db):
        """
        Test retrieving the status of a background job from the DB.
        """
        job_id = "job-123"
        
        # Create a fake BackgroundJob object
        fake_job = BackgroundJob(
            id=1,
            task_id=job_id,
            task_name="tasks.generate_report",
            status="SUCCESS",
            result={"report_url": "/reports/1.pdf"}
        )
        
        # Mock the DB query to return our fake job
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = fake_job
        mock_db.execute.return_value = mock_result

        status = await service.get_job_status(db=mock_db, job_id=job_id)

        assert status is not None
        assert status["task_id"] == job_id
        assert status["status"] == "SUCCESS"
        assert "report_url" in status["result"]

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, service, mock_db):
        """
        Test retrieving status for a non-existent job ID.
        """
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(AppException) as exc_info:
            await service.get_job_status(db=mock_db, job_id="non-existent")
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_check_pii_not_sent_to_celery(self, service, mock_celery_app, mock_db):
        """
        Ensure PII is not sent as arguments to Celery tasks (PIPEDA compliance).
        """
        mock_db.execute = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        # Attempt to send a job with potentially sensitive data (Service should sanitize)
        # Assuming service takes an application_id and fetches data internally or passes ID only
        await service.dispatch_report_generation(db=mock_db, application_id=99, report_type="full_details")

        call_args = mock_celery_app.send_task.call_args
        args = call_args[1].get('args', [])
        kwargs = call_args[1].get('kwargs', {})

        # Assert only IDs are passed, not raw data
        assert 99 in args
        assert all('sin' not in str(arg) for arg in args)
        assert all('income' not in str(kwarg) for kwarg in kwargs.values())