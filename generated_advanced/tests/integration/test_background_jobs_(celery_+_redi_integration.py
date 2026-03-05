import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from mortgage_underwriting.modules.background_jobs.models import BackgroundJob
from mortgage_underwriting.modules.background_jobs.schemas import JobStatus
from mortgage_underwriting.common.database import get_async_session

# Override DB dependency for testing
async def override_get_db(db_session):
    yield db_session

@pytest.mark.integration
@pytest.mark.asyncio
class TestBackgroundJobAPI:

    async def test_create_job_endpoint_success(self, app, db_session, sample_job_payload):
        """Test creating a job via API returns 201 and correct structure."""
        app.dependency_overrides[get_async_session] = lambda: override_get_db(db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/background-jobs", json=sample_job_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["task_name"] == sample_job_payload["task_name"]
        assert data["status"] == JobStatus.PENDING.value
        assert "created_at" in data
        assert "celery_task_id" in data # Should be populated if Celery is mocked in routes or real
        
        # Verify DB state
        stmt = select(BackgroundJob).where(BackgroundJob.id == data["id"])
        result = await db_session.execute(stmt)
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.task_name == sample_job_payload["task_name"]

        app.dependency_overrides.clear()

    async def test_create_job_endpoint_validation_error(self, app, db_session):
        """Test API validation with missing required fields."""
        app.dependency_overrides[get_async_session] = lambda: override_get_db(db_session)
        
        invalid_payload = {
            "task_name": "bad_task"
            # Missing 'payload'
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/background-jobs", json=invalid_payload)
        
        assert response.status_code == 422  # Unprocessable Entity
        
        app.dependency_overrides.clear()

    async def test_get_job_endpoint_success(self, app, db_session, sample_job_model):
        """Test retrieving a job status via API."""
        # Seed DB
        db_session.add(sample_job_model)
        await db_session.commit()
        await db_session.refresh(sample_job_model)
        
        app.dependency_overrides[get_async_session] = lambda: override_get_db(db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/background-jobs/{sample_job_model.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_job_model.id
        assert data["status"] == JobStatus.PENDING.value

        app.dependency_overrides.clear()

    async def test_get_job_endpoint_not_found(self, app, db_session):
        """Test retrieving a non-existent job returns 404."""
        app.dependency_overrides[get_async_session] = lambda: override_get_db(db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/background-jobs/99999")
        
        assert response.status_code == 404
        assert "detail" in response.json()

        app.dependency_overrides.clear()

    async def test_list_jobs_endpoint(self, app, db_session):
        """Test listing multiple jobs."""
        # Seed DB
        job1 = BackgroundJob(id=1, task_name="task_a", status=JobStatus.PENDING, payload={}, created_at=datetime.utcnow())
        job2 = BackgroundJob(id=2, task_name="task_b", status=JobStatus.COMPLETED, payload={}, result={"ok": True}, created_at=datetime.utcnow())
        db_session.add_all([job1, job2])
        await db_session.commit()
        
        app.dependency_overrides[get_async_session] = lambda: override_get_db(db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/background-jobs")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        
        # Verify serialization of Decimal results
        job_b = next(item for item in data["items"] if item["id"] == 2)
        assert job_b["result"] == {"ok": True}

        app.dependency_overrides.clear()

    async def test_update_job_status_endpoint_callback(self, app, db_session, sample_job_model):
        """Test the callback endpoint that Celery would hit to update status."""
        db_session.add(sample_job_model)
        await db_session.commit()
        
        app.dependency_overrides[get_async_session] = lambda: override_get_db(db_session)
        
        update_payload = {
            "status": JobStatus.COMPLETED.value,
            "result": {"stress_test_passed": True, "gds": "35.00"}
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Assuming a PUT or PATCH endpoint exists for callbacks
            response = await client.patch(
                f"/api/v1/background-jobs/{sample_job_model.id}/status", 
                json=update_payload
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == JobStatus.COMPLETED.value
        assert data["result"]["stress_test_passed"] is True

        # Verify persistence
        await db_session.refresh(sample_job_model)
        assert sample_job_model.status == JobStatus.COMPLETED

        app.dependency_overrides.clear()

    async def test_financial_data_precision_in_response(self, app, db_session):
        """Ensure financial data in job results maintains Decimal precision."""
        job = BackgroundJob(
            id=10,
            task_name="calculation",
            status=JobStatus.COMPLETED,
            payload={},
            result={"premium": Decimal("12345.67"), "tax": Decimal("0.00")},
            created_at=datetime.utcnow()
        )
        db_session.add(job)
        await db_session.commit()
        
        app.dependency_overrides[get_async_session] = lambda: override_get_db(db_session)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/background-jobs/{10}")
        
        assert response.status_code == 200
        data = response.json()
        # Pydantic/FastAPI should serialize Decimals to strings or floats correctly
        # Based on project conventions (Decimal for all), the schema should handle this.
        # Assuming the response schema returns strings for money to avoid float precision loss in JSON
        assert data["result"]["premium"] == "12345.67" 
        assert data["result"]["tax"] == "0.00"

        app.dependency_overrides.clear()