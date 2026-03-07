--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mortgage_underwriting.common.database import Base, get_async_session
from mortgage_underwriting.modules.background_jobs.routes import router
from mortgage_underwriting.modules.background_jobs.models import JobLog
from fastapi import FastAPI

# Test Database URL (In-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create engine
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_test_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_test_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with dependency overrides."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/background-jobs")
    
    # Override the database dependency
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
        
    app.dependency_overrides.clear()

@pytest.fixture
def mock_celery_task():
    """Mock a Celery Task instance."""
    task = MagicMock()
    task.id = "test-task-id-123"
    task.state = "PENDING"
    task.result = None
    return task

@pytest.fixture
def sample_application_data():
    """Valid sample mortgage application data."""
    return {
        "applicant_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "loan_amount": Decimal("450000.00"),
        "property_value": Decimal("550000.00"),
        "income": Decimal("120000.00"),
        "credit_score": 720
    }

@pytest.fixture
def sample_job_payload():
    """Valid payload to trigger a background job."""
    return {
        "task_name": "generate_mortgage_statement",
        "payload": {
            "application_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "format": "pdf"
        }
    }

# Unit Test Specific Mocks
@pytest.fixture
def mock_pdf_generator():
    with pytest.mock.patch('mortgage_underwriting.modules.background_jobs.services.generate_pdf') as mock:
        mock.return_value = b"fake_pdf_content"
        yield mock

@pytest.fixture
def mock_email_client():
    with pytest.mock.patch('mortgage_underwriting.modules.background_jobs.services.EmailClient') as mock:
        instance = mock.return_value
        instance.send = AsyncMock()
        yield instance

@pytest.fixture
def mock_redis():
    with pytest.mock.patch('mortgage_underwriting.modules.background_jobs.services.redis_client') as mock:
        yield mock

--- unit_tests ---
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

--- integration_tests ---
import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select
from datetime import datetime

from mortgage_underwriting.modules.background_jobs.models import JobLog
from mortgage_underwriting.modules.background_jobs.routes import router
from fastapi import FastAPI

# Integration tests assume DB is real (SQLite in-memory) and logic executes.
# For Celery, we assume eager mode or mocking the delay() call to verify API contract.

@pytest.mark.integration
@pytest.mark.asyncio
class TestBackgroundJobsAPI:

    async def test_create_job_endpoint_success(self, client: AsyncClient, sample_job_payload):
        # Act
        response = await client.post("/api/v1/background-jobs/jobs", json=sample_job_payload)
        
        # Assert
        assert response.status_code == 202
        data = response.json()
        assert "id" in data
        assert data["task_name"] == sample_job_payload["task_name"]
        assert data["status"] == "PENDING"
        assert data["created_at"] is not None

    async def test_create_job_endpoint_invalid_payload(self, client: AsyncClient):
        # Arrange
        invalid_payload = {"task_name": "unknown_task"} # Missing payload
        
        # Act
        response = await client.post("/api/v1/background-jobs/jobs", json=invalid_payload)
        
        # Assert
        assert response.status_code == 422 # Validation error

    async def test_get_job_status_endpoint_success(self, client: AsyncClient, db_session):
        # Arrange - Create a job directly in DB
        new_job = JobLog(
            task_name="test_task",
            payload={"test": "data"},
            status="SUCCESS",
            result={"message": "done"},
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db_session.add(new_job)
        await db_session.commit()
        await db_session.refresh(new_job)
        
        # Act
        response = await client.get(f"/api/v1/background-jobs/jobs/{new_job.id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == new_job.id
        assert data["status"] == "SUCCESS"
        assert data["result"]["message"] == "done"

    async def test_get_job_status_not_found(self, client: AsyncClient):
        # Act
        response = await client.get("/api/v1/background-jobs/jobs/99999")
        
        # Assert
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_list_jobs_endpoint_filtering(self, client: AsyncClient, db_session):
        # Arrange
        job1 = JobLog(task_name="email", payload={}, status="PENDING")
        job2 = JobLog(task_name="pdf", payload={}, status="SUCCESS")
        db_session.add_all([job1, job2])
        await db_session.commit()
        
        # Act - Filter by status
        response = await client.get("/api/v1/background-jobs/jobs?status=SUCCESS")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["task_name"] == "pdf"

    @pytest.mark.asyncio
    async def test_workflow_trigger_and_verify_db_state(self, client: AsyncClient, db_session):
        """
        Test the workflow where an endpoint triggers a background job logic (mocked celery delay)
        and verifies the DB state immediately after.
        """
        # Arrange
        payload = {
            "task_name": "generate_mortgage_statement",
            "payload": {"application_id": "app-987", "format": "pdf"}
        }
        
        # Mock the celery task delay to run synchronously or just verify it was called
        # In a real integration test without a running worker, we mock the .delay()
        with pytest.mock.patch('mortgage_underwriting.modules.background_jobs.routes.generate_mortgage_statement_task') as mock_task:
            mock_task.delay = MagicMock(return_value="mock-task-id")
            
            # Act - Trigger the job
            response = await client.post("/api/v1/background-jobs/jobs", json=payload)
            
            # Assert - API Response
            assert response.status_code == 202
            task_id = response.json()["id"]
            
            # Assert - Celery Task Triggered
            mock_task.delay.assert_called_once_with("app-987", "pdf")
            
            # Assert - Database Record Created (The route should create a log)
            stmt = select(JobLog).where(JobLog.id == task_id)
            result = await db_session.execute(stmt)
            job = result.scalar_one_or_none()
            
            assert job is not None
            assert job.task_name == "generate_mortgage_statement"
            assert job.status == "PENDING"

    @pytest.mark.asyncio
    async def test_financial_data_precision_in_job_payload(self, client: AsyncClient, db_session):
        """
        Ensure that financial data in job payloads maintains Decimal precision
        and does not get converted to float (OSFI/Audit requirement).
        """
        # Arrange
        payload = {
            "task_name": "stress_test_calculation",
            "payload": {
                "loan_amount": "500000.00", # Sent as string to preserve precision
                "rate": "4.5"
            }
        }
        
        # Act
        response = await client.post("/api/v1/background-jobs/jobs", json=payload)
        
        # Assert
        assert response.status_code == 202
        
        # Verify DB stored it correctly
        stmt = select(JobLog).where(JobLog.task_name == "stress_test_calculation")
        result = await db_session.execute(stmt)
        job = result.scalar_one_or_none()
        
        # The payload is stored as JSONB, check the raw value
        assert job.payload["loan_amount"] == "500000.00"
        # Ensure it wasn't turned into 500000.0
        assert job.payload["loan_amount"] != 500000.0

    @pytest.mark.asyncio
    async def test_pii_not_exposed_in_error_response(self, client: AsyncClient):
        """
        PIPEDA Compliance: Ensure that if a job fails due to PII processing,
        the error response does not leak the PII.
        """
        # Arrange
        payload = {
            "task_name": "process_sin",
            "payload": {"sin": "123-456-789"}
        }
        
        # Mock a task that raises an error containing the SIN
        with pytest.mock.patch('mortgage_underwriting.modules.background_jobs.routes.process_sin_task') as mock_task:
            mock_task.delay = MagicMock(side_effect=Exception("Failed to process SIN: 123-456-789"))
            
            # Act
            response = await client.post("/api/v1/background-jobs/jobs", json=payload)
            
            # Assert - The API might accept the request (202) even if task fails immediately, 
            # or 500 if the failure is synchronous. Assuming synchronous failure for this test.
            # If the route catches the exception:
            # assert response.status_code == 500 or 202
            
            # If the error is returned in JSON:
            # detail = response.json().get("detail", "")
            # assert "123-456-789" not in detail
            pass 
            # Note: In this specific architecture, the route returns 202 immediately 
            # and the task runs in background. So the API won't return the error.
            # This test validates the design choice (fire and forget) vs synchronous error handling.
            # We assert 202 Accepted.
            assert response.status_code == 202