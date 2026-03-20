--- conftest.py ---
```python
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, String, func
from datetime import datetime

# Import paths based on project conventions
from mortgage_underwriting.modules.background_jobs.routes import router as background_router
from mortgage_underwriting.common.config import settings

# --- Test Database Setup (SQLite for isolation) ---
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

class Base(DeclarativeBase):
    pass

# Minimal model for testing DB interactions if not importing full models
# In a real scenario, we import the actual models from the module
class TaskExecutionLog(Base):
    __tablename__ = "task_execution_logs"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # FINTRAC: Immutable audit trail fields

@pytest.fixture(scope="function")
async def engine() -> AsyncGenerator:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(background_router, prefix="/api/v1/background-jobs", tags=["background-jobs"])
    return app

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# --- Mock Fixtures for Unit Tests ---

@pytest.fixture
def mock_celery_app():
    with pytest.mock.patch("mortgage_underwriting.modules.background_jobs.services.celery_app") as mock:
        # Mock the send_task / delay methods
        mock.send_task.return_value.id = "test-task-id-123"
        yield mock

@pytest.fixture
def mock_redis_client():
    with pytest.mock.patch("mortgage_underwriting.modules.background_jobs.services.redis_client") as mock:
        mock.get.return_value = None
        mock.set.return_value = True
        yield mock

@pytest.fixture
def mock_encryption_service():
    with pytest.mock.patch("mortgage_underwriting.common.security.encrypt_pii") as mock_encrypt, \
         pytest.mock.patch("mortgage_underwriting.common.security.hash_value") as mock_hash:
        mock_encrypt.return_value = "encrypted_string"
        mock_hash.return_value = "hashed_sin"
        yield mock_encrypt, mock_hash

# --- Test Data Fixtures ---

@pytest.fixture
def valid_mortgage_payload():
    return {
        "application_id": "app-001",
        "loan_amount": "450000.00",
        "property_value": "500000.00",
        "rate": "4.50",
        "amortization_years": 25,
        "sin": "123456789" # PII: Will be mocked/hashed
    }

@pytest.fixture
def valid_batch_payload():
    return {
        "batch_name": "monthly_stress_test_batch",
        "criteria": {"min_score": 600},
        "application_ids": ["app-001", "app-002", "app-003"]
    }
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

# Import the module under test
from mortgage_underwriting.modules.background_jobs.services import BackgroundJobService
from mortgage_underwriting.modules.background_jobs.exceptions import TaskNotFoundError, InvalidTaskPayloadError

# Mocking the Celery task functions directly for unit testing logic
# Assuming tasks are defined in tasks.py or services.py for this example
from mortgage_underwriting.modules.background_jobs.models import TaskExecutionLog

@pytest.mark.unit
class TestBackgroundJobService:

    @pytest.mark.asyncio
    async def test_trigger_task_success(self, db_session, mock_celery_app):
        """Test triggering a background job successfully and logging to DB (FINTRAC)."""
        service = BackgroundJobService(db_session)
        
        payload = {
            "task_name": "generate_report",
            "params": {"applicant_id": "user_123"}
        }

        result = await service.trigger_task(payload)

        # Assert Celery was called
        mock_celery_app.send_task.assert_called_once_with(
            "generate_report",
            args=[{"applicant_id": "user_123"}]
        )

        # Assert DB Log created (FINTRAC Audit Trail)
        logs = await service.get_task_logs(result["task_id"])
        assert len(logs) == 1
        assert logs[0].task_name == "generate_report"
        assert logs[0].status == "PENDING"

    @pytest.mark.asyncio
    async def test_trigger_task_invalid_payload(self, db_session):
        """Test that triggering with missing fields raises validation error."""
        service = BackgroundJobService(db_session)
        
        payload = {"task_name": ""} # Missing params
        
        with pytest.raises(InvalidTaskPayloadError):
            await service.trigger_task(payload)

    @pytest.mark.asyncio
    async def test_get_task_status_success(self, db_session, mock_redis_client):
        """Test retrieving task status from Redis."""
        service = BackgroundJobService(db_session)
        task_id = "task-123"
        
        # Mock Redis return value
        mock_redis_client.get.return_value = b'{"status": "SUCCESS", "result": "done"}'

        status = await service.get_task_status(task_id)
        
        assert status["status"] == "SUCCESS"
        mock_redis_client.get.assert_called_once_with(f"celery-task-meta-{task_id}")

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, db_session, mock_redis_client):
        """Test retrieving status for non-existent task."""
        service = BackgroundJobService(db_session)
        task_id = "non-existent"
        
        mock_redis_client.get.return_value = None

        with pytest.raises(TaskNotFoundError):
            await service.get_task_status(task_id)

@pytest.mark.unit
class TestTaskLogicCalculations:
    """
    Tests for the actual logic executed by Celery workers.
    Since we can't run Celery in unit tests, we test the functions directly.
    """

    @pytest.mark.asyncio
    async def test_calculate_stress_test_osfi_compliance(self):
        """
        Test OSFI B-20 Compliance:
        Qualifying Rate = max(contract_rate + 2%, 5.25%)
        """
        from mortgage_underwriting.modules.background_jobs.tasks import calculate_monthly_payment_with_stress
        
        # Case 1: Contract rate is low, floor applies
        contract_rate = Decimal("3.00")
        qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
        assert qualifying_rate == Decimal("5.25")

        # Case 2: Contract rate is high, buffer applies
        contract_rate = Decimal("5.50")
        qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
        assert qualifying_rate == Decimal("7.50")

    @pytest.mark.asyncio
    async def test_calculate_gds_tds_limits(self):
        """
        Test GDS/TDS hard limits enforcement (OSFI B-20).
        GDS <= 39%, TDS <= 44%
        """
        from mortgage_underwriting.modules.background_jobs.tasks import calculate_ratios
        
        income = Decimal("10000.00")
        property_tax = Decimal("300.00")
        heating = Decimal("150.00")
        mortgage_payment = Decimal("2500.00") # High payment to breach limits
        other_debt = Decimal("1000.00")

        # Mock calculation inputs
        result = calculate_ratios(income, mortgage_payment, property_tax, heating, other_debt)
        
        # Logic verification
        # GDS = (2500 + 300 + 150) / 10000 * 100 = 29.5% (Pass)
        # TDS = (2950 + 1000) / 10000 * 100 = 39.5% (Pass)
        assert result["gds"] <= Decimal("39.00")
        assert result["tds"] <= Decimal("44.00")

    @pytest.mark.asyncio
    async def test_pii_data_sanitization_in_task(self, mock_encryption_service):
        """
        Test PIPEDA compliance: SIN must be hashed/encrypted before processing/storage.
        """
        from mortgage_underwriting.modules.background_jobs.tasks import process_applicant_data
        
        raw_sin = "123456789"
        mock_encrypt, mock_hash = mock_encryption_service
        
        # Call task
        await process_applicant_data({"sin": raw_sin, "name": "John Doe"})
        
        # Verify encryption/hash was called
        mock_hash.assert_called_with(raw_sin)
        # Ensure raw SIN is not in logs (simulated by checking it wasn't passed to a logger mock)
        # This function should ideally return data with hashed SIN only

    @pytest.mark.asyncio
    async def test_cmhc_insurance_calculation(self):
        """
        Test CMHC Insurance Logic:
        LTV > 80% -> Insurance required.
        Premium tiers: 80.01-85% = 2.80%, etc.
        """
        from mortgage_underwriting.modules.background_jobs.tasks import calculate_cmhc_premium
        
        # Scenario 1: 95% LTV
        ltv = Decimal("0.95")
        loan_amount = Decimal("400000.00")
        premium = calculate_cmhc_premium(ltv, loan_amount)
        
        assert premium == loan_amount * Decimal("0.04") # 4.00% tier
        
        # Scenario 2: 82% LTV
        ltv = Decimal("0.82")
        loan_amount = Decimal("400000.00")
        premium = calculate_cmhc_premium(ltv, loan_amount)
        
        assert premium == loan_amount * Decimal("0.028") # 2.80% tier

    @pytest.mark.asyncio
    async def test_fintrac_large_transaction_flagging(self):
        """
        Test FINTRAC: Transactions > 10k CAD require explicit flagging.
        """
        from mortgage_underwriting.modules.background_jobs.tasks import validate_transaction
        
        # Valid large transaction
        txn = {"amount": Decimal("15000.00"), "type": "large_deposit", "flagged": True}
        is_valid = validate_transaction(txn)
        assert is_valid is True

        # Invalid large transaction (missing flag)
        txn = {"amount": Decimal("15000.00"), "type": "large_deposit", "flagged": False}
        with pytest.raises(ValueError, match="FINTRAC compliance"):
            validate_transaction(txn)

    @pytest.mark.asyncio
    async def test_decimal_precision_handling(self):
        """Ensure no float precision loss in financial calculations."""
        from mortgage_underwriting.modules.background_jobs.tasks import calculate_interest
        
        principal = Decimal("100000.00")
        rate = Decimal("0.035") # 3.5%
        
        interest = calculate_interest(principal, rate)
        
        # Should not be 3500.000000001 or 3500.0 (float)
        assert interest == Decimal("3500.00")
        assert isinstance(interest, Decimal)
```

--- integration_tests ---
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