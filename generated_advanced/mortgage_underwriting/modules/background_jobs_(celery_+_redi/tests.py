--- conftest.py ---
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from decimal import Decimal
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from mortgage_underwriting.common.database import Base, get_async_session
from mortgage_underwriting.modules.background_jobs.models import BackgroundJob
from mortgage_underwriting.modules.applicant.models import Applicant
from mortgage_underwriting.modules.property.models import Property
from mortgage_underwriting.modules.mortgage.models import Mortgage

# Use in-memory SQLite for integration tests for speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def override_get_db(db_session: AsyncSession):
    """
    Overrides the dependency for FastAPI to use the test session.
    """
    async def _override_get_db():
        yield db_session
    return _override_get_db


@pytest.fixture
def mock_celery_app():
    """
    Mocks the Celery application to prevent actual background task execution during tests.
    """
    with MagicMock() as mock_app:
        # Mock the send_task method to return a fake AsyncResult
        mock_result = MagicMock()
        mock_result.id = "test-task-id-12345"
        mock_result.status = "PENDING"
        mock_app.send_task.return_value = mock_result
        yield mock_app


@pytest.fixture
def sample_applicant_data():
    return {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-01",
        "sin_hash": "a" * 64, # SHA256 hash placeholder
        "email": "john.doe@example.com",
        "phone_number": "4165550199",
        "annual_income": Decimal("95000.00"),
    }


@pytest.fixture
def sample_property_data():
    return {
        "address": "123 Maple Street",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M4W1A5",
        "property_value": Decimal("750000.00"),
    }


@pytest.fixture
def sample_mortgage_data():
    return {
        "loan_amount": Decimal("600000.00"),
        "interest_rate": Decimal("5.25"),
        "amortization_years": 25,
        "down_payment": Decimal("150000.00"),
    }


@pytest.fixture
async def seeded_application(db_session: AsyncSession, sample_applicant_data, sample_property_data, sample_mortgage_data):
    """
    Creates a complete application in the DB for testing background jobs that depend on existing data.
    """
    applicant = Applicant(**sample_applicant_data)
    db_session.add(applicant)
    await db_session.flush()
    
    property_obj = Property(**sample_property_data)
    db_session.add(property_obj)
    await db_session.flush()

    mortgage_data = sample_mortgage_data.copy()
    mortgage_data["applicant_id"] = applicant.id
    mortgage_data["property_id"] = property_obj.id
    
    mortgage = Mortgage(**mortgage_data)
    db_session.add(mortgage)
    await db_session.commit()
    await db_session.refresh(mortgage)
    
    return mortgage

--- unit_tests ---
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

--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from decimal import Decimal

from mortgage_underwriting.main import app
from mortgage_underwriting.modules.background_jobs.models import BackgroundJob
from mortgage_underwriting.modules.background_jobs.routes import router
from mortgage_underwriting.common.security import verify_token


# Mock authentication decorator
@pytest.fixture(scope="function")
def authenticated_app():
    """
    Fixture to bypass auth checks for integration testing.
    """
    app.dependency_overrides[verify_token] = lambda: True
    app.include_router(router, prefix="/api/v1/background-jobs", tags=["background-jobs"])
    yield app
    app.dependency_overrides.clear()


@pytest.mark.integration
@pytest.mark.asyncio
class TestBackgroundJobIntegration:

    async def test_create_report_job_happy_path(self, authenticated_app, override_get_db, db_session, seeded_application):
        """
        Test full workflow: API Call -> DB Record -> Celery Dispatch Mock
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=authenticated_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "application_id": seeded_application.id,
                "report_type": "underwriting_decision"
            }
            response = await client.post("/api/v1/background-jobs/generate", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "PENDING"

        # Verify DB Record (FINTRAC: Audit trail created)
        stmt = select(BackgroundJob).where(BackgroundJob.task_id == data["job_id"])
        result = await db_session.execute(stmt)
        job_record = result.scalar_one_or_none()

        assert job_record is not None
        assert job_record.task_name == "tasks.generate_report"
        assert job_record.created_at is not None
        assert job_record.created_by == "system" # Assuming system user for internal jobs

    async def test_create_report_job_not_found(self, authenticated_app, override_get_db, db_session):
        """
        Test attempting to create a job for a non-existent application.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        transport = ASGITransport(app=authenticated_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "application_id": 99999, # Does not exist
                "report_type": "underwriting_decision"
            }
            response = await client.post("/api/v1/background-jobs/generate", json=payload)

        assert response.status_code == 404
        assert "Application not found" in response.json()["detail"]

    async def test_get_job_status_integration(self, authenticated_app, override_get_db, db_session):
        """
        Test retrieving job status via API.
        """
        # Manually insert a job to simulate a completed state
        new_job = BackgroundJob(
            id=1,
            task_id="manual-job-123",
            task_name="tasks.archive_application_data",
            status="SUCCESS",
            result={"archive_path": "/s3/archives/1.zip"},
            created_by="system"
        )
        db_session.add(new_job)
        await db_session.commit()

        app.dependency_overrides[get_async_session] = override_get_db
        transport = ASGITransport(app=authenticated_app)
        
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/background-jobs/manual-job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "manual-job-123"
        assert data["status"] == "SUCCESS"
        assert "archive_path" in data["result"]
        # Verify audit fields are returned
        assert "created_at" in data

    async def test_create_archive_job_fintrac_compliance(self, authenticated_app, override_get_db, db_session, seeded_application):
        """
        Test that archive jobs are created correctly for retention compliance.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        transport = ASGITransport(app=authenticated_app)
        
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/background-jobs/archive", json={"application_id": seeded_application.id})

        assert response.status_code == 202
        
        # Verify immutable audit trail
        stmt = select(BackgroundJob).where(BackgroundJob.task_name == "tasks.archive_application_data")
        result = await db_session.execute(stmt)
        job = result.scalar_one_or_none()
        
        assert job is not None
        assert job.status == "PENDING"
        assert job.created_at is not None
        # Ensure no PII in the task arguments stored in DB (we store task_name, not args in the model usually, 
        # but if we did store metadata, it should be clean)

    async def test_invalid_report_type(self, authenticated_app, override_get_db, db_session, seeded_application):
        """
        Test validation of report_type input.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        transport = ASGITransport(app=authenticated_app)
        
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "application_id": seeded_application.id,
                "report_type": "invalid_report_type"
            }
            response = await client.post("/api/v1/background-jobs/generate", json=payload)

        assert response.status_code == 422 # Validation Error

    async def test_concurrent_job_creation(self, authenticated_app, override_get_db, db_session, seeded_application):
        """
        Test handling multiple requests simultaneously.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        transport = ASGITransport(app=authenticated_app)
        
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Fire two requests for the same app
            payload = {"application_id": seeded_application.id, "report_type": "summary"}
            req1 = client.post("/api/v1/background-jobs/generate", json=payload)
            req2 = client.post("/api/v1/background-jobs/generate", json=payload)
            
            results = await asyncio.gather(req1, req2)

        assert results[0].status_code == 202
        assert results[1].status_code == 202
        
        # Verify two distinct jobs were created
        stmt = select(BackgroundJob).where(BackgroundJob.task_name == "tasks.generate_report")
        result = await db_session.execute(stmt)
        jobs = result.scalars().all()
        
        assert len(jobs) == 2
        assert jobs[0].task_id != jobs[1].task_id