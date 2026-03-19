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