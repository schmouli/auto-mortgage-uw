import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from mortgage_underwriting.modules.background_jobs.services import (
    BackgroundService,
    generate_mortgage_statement_task,
    send_notification_task
)
from mortgage_underwriting.modules.background_jobs.models import JobLog
from mortgage_underwriting.modules.background_jobs.exceptions import TaskExecutionError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestBackgroundService:
    
    @pytest.fixture
    def service(self, mock_db):
        return BackgroundService(mock_db)

    @pytest.mark.asyncio
    async def test_create_job_log_success(self, service, mock_db):
        # Arrange
        task_name = "test_task"
        payload = {"key": "value"}
        
        # Act
        job_log = await service.create_job_log(task_name, payload)
        
        # Assert
        assert job_log.id is not None
        assert job_log.task_name == task_name
        assert job_log.status == "PENDING"
        assert job_log.payload == payload
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(job_log)

    @pytest.mark.asyncio
    async def test_update_job_status_success(self, service, mock_db):
        # Arrange
        job_log = JobLog(id=1, task_name="test", payload={}, status="PENDING")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = job_log
        
        # We need to mock the execute chain on the session
        mock_db.execute.return_value = result_mock
        
        # Act
        updated_job = await service.update_job_status(1, "SUCCESS", {"result": "done"})
        
        # Assert
        assert updated_job.status == "SUCCESS"
        assert updated_job.result == {"result": "done"}
        assert updated_job.completed_at is not None
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_job_status_not_found(self, service, mock_db):
        # Arrange
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.update_job_status(999, "SUCCESS", {})
        assert exc_info.value.status_code == 404


@pytest.mark.unit
class TestCeleryTasks:

    @pytest.fixture
    def mock_db_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_generate_mortgage_statement_task_success(self, mock_db_session, mock_pdf_generator):
        # Arrange
        application_id = "app-123"
        format_type = "pdf"
        
        # Mock the service layer within the task
        with patch('mortgage_underwriting.modules.background_jobs.services.BackgroundService') as MockService:
            mock_service_instance = AsyncMock()
            MockService.return_value = mock_service_instance
            
            # Act
            await generate_mortgage_statement_task(application_id, format_type)
            
            # Assert
            mock_pdf_generator.assert_called_once()
            mock_service_instance.create_job_log.assert_awaited()
            # Check that update was called with success
            update_call = mock_service_instance.update_job_status.call_args
            assert update_call[0][1] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_generate_mortgage_statement_task_pdf_failure(self, mock_db_session, mock_pdf_generator):
        # Arrange
        application_id = "app-123"
        mock_pdf_generator.side_effect = Exception("PDF Lib crashed")
        
        with patch('mortgage_underwriting.modules.background_jobs.services.BackgroundService') as MockService:
            mock_service_instance = AsyncMock()
            MockService.return_value = mock_service_instance
            
            # Act
            await generate_mortgage_statement_task(application_id, "pdf")
            
            # Assert
            update_call = mock_service_instance.update_job_status.call_args
            assert update_call[0][1] == "FAILURE"
            assert "PDF Lib crashed" in update_call[0][2]["error_message"]

    @pytest.mark.asyncio
    async def test_send_notification_task_success(self, mock_db_session, mock_email_client):
        # Arrange
        recipient = "applicant@example.com"
        subject = "Mortgage Update"
        body = "Your application is approved."
        
        with patch('mortgage_underwriting.modules.background_jobs.services.BackgroundService') as MockService:
            mock_service_instance = AsyncMock()
            MockService.return_value = mock_service_instance
            
            # Act
            await send_notification_task(recipient, subject, body)
            
            # Assert
            mock_email_client.send.assert_awaited_once_with(
                to=recipient, 
                subject=subject, 
                content=body
            )
            mock_service_instance.update_job_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_notification_task_sanitizes_pii(self, mock_db_session, mock_email_client):
        # Arrange
        # Ensure PII is not passed to logging or stored in plain text in result
        recipient = "user@test.com"
        sin = "123-456-789" # Should not appear in DB result
        body = f"Your SIN {sin} is verified."
        
        with patch('mortgage_underwriting.modules.background_jobs.services.BackgroundService') as MockService:
            mock_service_instance = AsyncMock()
            MockService.return_value = mock_service_instance
            
            # Act
            await send_notification_task(recipient, "Notification", body)
            
            # Assert
            # Verify email sent (it contains the body)
            mock_email_client.send.assert_awaited_once()
            
            # Verify DB status update does NOT contain raw SIN in result (PIPEDA compliance)
            update_call = mock_service_instance.update_job_status.call_args
            result_data = update_call[0][2]
            # The result should be generic, not contain the email body
            assert "sent_at" in result_data
            assert "123-456-789" not in str(result_data)

    @pytest.mark.asyncio
    async def test_calculate_gds_in_background_task_compliance(self, mock_db_session):
        # Arrange
        income = Decimal("5000.00")
        housing_costs = Decimal("2000.00")
        qualifying_rate = Decimal("5.25") # OSFI B-20
        
        # Simulate a calculation task
        with patch('mortgage_underwriting.modules.background_jobs.services.BackgroundService') as MockService:
            mock_service_instance = AsyncMock()
            MockService.return_value = mock_service_instance
            
            # Act
            # Importing the hypothetical calculation function
            from mortgage_underwriting.modules.background_jobs.services import calculate_gds_task
            
            await calculate_gds_task(income, housing_costs, qualifying_rate)
            
            # Assert
            # Check update was called
            mock_service_instance.update_job_status.assert_awaited()
            
            # Extract the result passed to the DB
            update_args = mock_service_instance.update_job_status.call_args[0]
            result = update_args[2] # The result dict
            
            # Verify calculation logic (GDS = (2000 / 5000) * 100 = 40.0%)
            assert "gds_ratio" in result
            assert result["gds_ratio"] == Decimal("40.00")
            assert "qualifying_rate" in result # Audit trail requirement
            assert result["qualifying_rate"] == Decimal("5.25")
            
            # Verify warning if GDS > 39% (OSFI Limit)
            assert "warning" in result
            assert "GDS exceeds 39%" in result["warning"]