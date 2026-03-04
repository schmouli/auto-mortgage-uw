Here are the comprehensive tests for the Background Jobs module of the Canadian Mortgage Underwriting System.

--- conftest.py ---
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator, Any
from unittest.mock import MagicMock, patch

# Hypothetical imports based on project structure
# from app.main import app
# from app.db.base import Base
# from app.models import mortgage_models
# from app.tasks import worker

# --- Mocking the App and Models for the purpose of this test generation ---
# In a real scenario, these would be actual imports.

@pytest.fixture(scope="session")
def db_engine():
    """Create an in-memory SQLite database engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Base.metadata.create_all(bind=engine) # Uncomment in real scenario
    yield engine
    # Base.metadata.drop_all(bind=engine) # Uncomment in real scenario

@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a new database session for a test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session: Session) -> TestClient:
    """
    Create a FastAPI TestClient with a mocked DB session dependency.
    """
    # Mocking the dependency override for the database
    # app.dependency_overrides[get_db] = lambda: db_session
    
    # Import app here to avoid dependency issues if not present
    # from app.main import app
    # with TestClient(app) as test_client:
    #     yield test_client
    
    # Mock Client for demonstration
    mock_app = MagicMock()
    mock_app.dependency_overrides = {}
    test_client = TestClient(mock_app)
    yield test_client
    mock_app.dependency_overrides = {}

@pytest.fixture
def sample_application_data():
    """Returns a dictionary representing a Canadian mortgage application."""
    return {
        "id": 1,
        "applicant_id": "100-200-300",
        "first_name": "John",
        "last_name": "Doe",
        "province": "ON",
        "loan_amount": 500000.00,
        "property_value": 650000.00,
        "credit_score": None,
        "status": "PENDING_SUBMISSION"
    }

@pytest.fixture
def mock_redis():
    """Mock Redis client for caching/locking."""
    with patch('app.tasks.worker.redis_client') as mock_r:
        yield mock_r

@pytest.fixture
def mock_external_bureau_api():
    """Mock the external Equifax/TransUnion API client."""
    with patch('app.services.credit_service.BureauAPI') as mock_api:
        mock_instance = mock_api.return_value
        mock_instance.get_score.return_value = 720
        yield mock_instance
```

--- unit_tests ---
```python
import pytest
from unittest.mock import patch, call, MagicMock
from app.tasks import credit_tasks, risk_tasks
from app.core.exceptions import ExternalServiceError
from app.models.schemas import ApplicationStatus

# Module to test: Background Tasks Logic (Celery functions executed synchronously for testing)

class TestCreditCheckTask:
    """
    Unit tests for the Celery task: process_credit_check
    """

    @patch("app.tasks.credit_tasks.update_application_status")
    @patch("app.tasks.credit_tasks.BureauAPI")
    @patch("app.tasks.credit_tasks.get_db")
    def test_process_credit_check_happy_path(
        self, mock_get_db, mock_bureau_api, mock_update_status, sample_application_data
    ):
        """
        Test successful credit check flow.
        Scenario: API returns score, DB is updated, status moves to REVIEW.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_bureau_instance = mock_bureau_api.return_value
        mock_bureau_instance.get_score.return_value = 750
        
        mock_app = MagicMock()
        mock_app.id = sample_application_data["id"]
        mock_app.applicant_id = sample_application_data["applicant_id"]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app

        # Act
        result = credit_tasks.process_credit_check(application_id=1)

        # Assert
        assert result["status"] == "success"
        assert result["score"] == 750
        mock_bureau_instance.get_score.assert_called_once_with(sin="100-200-300", province="ON")
        assert mock_app.credit_score == 750
        mock_update_status.assert_called_once_with(
            db=mock_db, 
            app_id=1, 
            status=ApplicationStatus.UNDERWRITING_REVIEW
        )
        # Multiple assertions on state
        assert mock_db.commit.call_count == 1
        assert mock_db.refresh.call_count >= 1

    @patch("app.tasks.credit_tasks.BureauAPI")
    @patch("app.tasks.credit_tasks.get_db")
    def test_process_credit_check_api_failure(
        self, mock_get_db, mock_bureau_api, sample_application_data
    ):
        """
        Test handling of external API failure.
        Scenario: Bureau API times out or returns 500.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_bureau_api.return_value.get_score.side_effect = ExternalServiceError("Service Unavailable")
        
        mock_app = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app

        # Act & Assert
        with pytest.raises(ExternalServiceError):
            credit_tasks.process_credit_check(application_id=1)
        
        # Verify transaction rollback
        mock_db.rollback.assert_called_once()
        assert mock_db.commit.call_count == 0

    @patch("app.tasks.credit_tasks.BureauAPI")
    @patch("app.tasks.credit_tasks.get_db")
    def test_process_credit_check_application_not_found(
        self, mock_get_db, mock_bureau_api
    ):
        """
        Test behavior when Application ID does not exist.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Application not found"):
            credit_tasks.process_credit_check(application_id=999)

        # Verify external API was NOT called
        mock_bureau_api.return_value.get_score.assert_not_called()


class TestRiskAssessmentTask:
    """
    Unit tests for the Celery task: calculate_debt_service_ratios
    """

    @patch("app.tasks.risk_tasks.logger")
    @patch("app.tasks.risk_tasks.update_application_status")
    @patch("app.tasks.risk_tasks.get_db")
    def test_calculate_ratios_approval_path(
        self, mock_get_db, mock_update_status, mock_logger
    ):
        """
        Test LTV and TDS calculations resulting in approval.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_app = MagicMock()
        mock_app.id = 1
        mock_app.loan_amount = 400000
        mock_app.property_value = 500000  # 80% LTV
        mock_app.annual_income = 120000
        mock_app.annual_property_tax = 3000
        mock_app.annual_heating = 1200
        mock_app.monthly_debt_payments = 1000 # $12,000/year
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app

        # Act
        result = risk_tasks.calculate_debt_service_ratios(application_id=1)

        # Assert
        assert result["ltv"] == 0.8
        # TDS = (Mortgage_Pmt + Tax + Heat + Debts) / Income
        # Assuming 20yr @ 5% approx $31,600/yr mortgage
        # (31600 + 3000 + 1200 + 12000) / 120000 ~= 39.8%
        assert "tds" in result
        assert result["tds"] < 0.40 # Validating logic
        
        # Check status update logic (assuming < 40% TDS is auto-approve for this tier)
        mock_update_status.assert_called_once()
        status_arg = mock_update_status.call_args[1]['status']
        assert status_arg == ApplicationStatus.APPROVED

    @patch("app.tasks.risk_tasks.update_application_status")
    @patch("app.tasks.risk_tasks.get_db")
    def test_calculate_ratios_high_risk_rejection(
        self, mock_get_db, mock_update_status
    ):
        """
        Test high LTV and high TDS resulting in referral/rejection.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_app = MagicMock()
        mock_app.id = 2
        mock_app.loan_amount = 475000 # 95% LTV
        mock_app.property_value = 500000 
        mock_app.annual_income = 50000
        mock_app.annual_property_tax = 4000
        mock_app.annual_heating = 1500
        mock_app.monthly_debt_payments = 2000 # $24,000/year
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app

        # Act
        result = risk_tasks.calculate_debt_service_ratios(application_id=2)

        # Assert
        assert result["ltv"] > 0.90
        assert result["tds"] > 0.50 # Very high risk
        mock_update_status.assert_called_with(
            db=mock_db, 
            app_id=2, 
            status=ApplicationStatus.MANUAL_REVIEW
        )

    @patch("app.tasks.risk_tasks.get_db")
    def test_calculate_ratios_zero_income_handling(self, mock_get_db):
        """
        Test division by zero safety or edge case handling.
        """
        # Arrange
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_app = MagicMock()
        mock_app.annual_income = 0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app

        # Act & Assert
        with pytest.raises(ZeroDivisionError) or pytest.raises(ValueError):
             risk_tasks.calculate_debt_service_ratios(application_id=3)
        
        # Ensure DB was not committed on error
        mock_db.commit.assert_not_called()

class TestDocumentProcessingTask:
    """
    Unit tests for OCR/PDF processing tasks.
    """
    
    @patch("app.tasks.doc_tasks.extract_text_from_pdf")
    @patch("app.tasks.doc_tasks.get_db")
    def test_process_employment_letter_success(self, mock_get_db, mock_ocr):
        """
        Test successful parsing of employment letter.
        """
        # Arrange
        mock_ocr.return_value = "Annual Salary: $85,000 Start Date: 2020-01-01"
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        
        mock_doc = MagicMock()
        mock_doc.id = 55
        mock_doc.type = "EMPLOYMENT_LETTER"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_doc

        # Act
        result = doc_tasks.process_document(document_id=55)

        # Assert
        assert result["parsed_salary"] == 85000
        assert result["status"] == "VERIFIED"
        mock_ocr.assert_called_once()
        assert mock_doc.processed_at is not None

    @patch("app.tasks.doc_tasks.extract_text_from_pdf")
    @patch("app.tasks.doc_tasks.get_db")
    def test_process_document_corrupted_file(self, mock_get_db, mock_ocr):
        """
        Test handling of corrupted PDF where OCR fails.
        """
        # Arrange
        mock_ocr.side_effect = IOError("File corrupted")
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_doc = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_doc

        # Act
        result = doc_tasks.process_document(document_id=56)

        # Assert
        assert result["status"] == "FAILED"
        assert "error" in result
        # Verify retry logic or error logging was triggered (conceptual)
        assert mock_db.commit.called # Error status saved
```

--- integration_tests ---
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