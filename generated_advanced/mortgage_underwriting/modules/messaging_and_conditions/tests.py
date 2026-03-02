Here are the comprehensive tests for the **OnLendHub Messaging & Conditions** module.

These tests cover the logic for evaluating mortgage underwriting conditions (e.g., LTV ratios, credit scores) and the messaging system that notifies brokers and applicants. The unit tests isolate the business logic, while the integration tests verify the API workflows and database interactions.

--- conftest.py ---
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Dict, Any

# Hypothetical imports based on project structure
# from app.main import app
# from app.database import Base, get_db
# from app.models import Application, Condition, MessageLog

# MOCK SETUP FOR STANDALONE RUNNING
# In a real scenario, these would import the actual app and models
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from datetime import datetime
import sys

# Minimal Mock Models for context
Base = None
try:
    from app.database import Base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    applicant_name = Column(String)
    loan_amount = Column(Integer)
    property_value = Column(Integer)
    credit_score = Column(Integer)
    status = Column(String, default="pending")

class Condition(Base):
    __tablename__ = "conditions"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    type = Column(String)  # e.g., "ltv_check", "credit_check"
    description = Column(String)
    is_met = Column(Boolean, default=False)

class MessageLog(Base):
    __tablename__ = "message_logs"
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    recipient = Column(String)
    channel = Column(String) # email, sms
    status = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    # Mock dependency override
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    # Assuming app exists, otherwise we mock it for the example
    try:
        from app.main import app
        app.dependency_overrides[get_db] = override_get_db
        yield TestClient(app)
        app.dependency_overrides.clear()
    except ImportError:
        # If app doesn't exist, we return a dummy client for structure demonstration
        # In real usage, this block is removed
        class DummyApp:
            def dependency_overrides = {}
        yield TestClient(DummyApp())

# --- Data Fixtures ---

@pytest.fixture
def sample_application(db: Session) -> Application:
    app_data = Application(
        applicant_name="John Doe",
        loan_amount=400000,
        property_value=500000,
        credit_score=720,
        status="submitted"
    )
    db.add(app_data)
    db.commit()
    db.refresh(app_data)
    return app_data

@pytest.fixture
def high_risk_application(db: Session) -> Application:
    app_data = Application(
        applicant_name="Jane Risk",
        loan_amount=450000,
        property_value=500000, # 90% LTV
        credit_score=600,
        status="submitted"
    )
    db.add(app_data)
    db.commit()
    db.refresh(app_data)
    return app_data

@pytest.fixture
def condition_payload() -> Dict[str, Any]:
    return {
        "type": "document_verification",
        "description": "Please provide recent pay stubs."
    }
```

--- unit_tests ---
```python
import pytest
from unittest.mock import Mock, patch, call
from datetime import datetime

# Assuming the module exists: app.services.messaging_conditions_service
# For the purpose of this output, we will define the functions inline or mock them heavily 
# to demonstrate the testing strategy.

# --- Hypothetical Service Logic to Test ---
class ConditionEvaluator:
    @staticmethod
    def calculate_ltv(loan_amount: int, property_value: int) -> float:
        if property_value <= 0:
            raise ValueError("Property value must be positive")
        return round((loan_amount / property_value) * 100, 2)

    @staticmethod
    def check_ltv_condition(ltv: float, max_allowed: float = 80.0) -> bool:
        return ltv <= max_allowed

    @staticmethod
    def check_credit_condition(score: int, min_required: int = 650) -> bool:
        return score >= min_required

class MessageFormatter:
    @staticmethod
    def format_condition_notification(applicant_name: str, condition_desc: str) -> str:
        if not applicant_name or not condition_desc:
            raise ValueError("Missing required fields for formatting")
        return f"Dear {applicant_name}, a new condition requires attention: {condition_desc}"

class NotificationService:
    def __init__(self, email_client, sms_client):
        self.email_client = email_client
        self.sms_client = sms_client

    def send_update(self, recipient: str, message: str, channel: str = "email"):
        if channel == "email":
            return self.email_client.send(recipient, message)
        elif channel == "sms":
            return self.sms_client.send(recipient, message)
        else:
            raise ValueError("Invalid channel")

# --- TESTS ---

class TestConditionEvaluator:
    
    def test_calculate_ltv_standard_case(self):
        # Happy path: Standard mortgage
        loan = 400000
        value = 500000
        result = ConditionEvaluator.calculate_ltv(loan, value)
        assert result == 80.0

    def test_calculate_ltv_high_ratio(self):
        # Edge case: High ratio mortgage
        loan = 480000
        value = 500000
        result = ConditionEvaluator.calculate_ltv(loan, value)
        assert result == 96.0

    def test_calculate_ltv_zero_value(self):
        # Error case: Division by zero protection
        with pytest.raises(ValueError) as excinfo:
            ConditionEvaluator.calculate_ltv(100000, 0)
        assert "Property value must be positive" in str(excinfo.value)

    def test_calculate_ltv_negative_value(self):
        # Error case: Negative value
        with pytest.raises(ValueError):
            ConditionEvaluator.calculate_ltv(100000, -50000)

    def test_check_ltv_condition_pass(self):
        # Happy path: LTV within limit
        assert ConditionEvaluator.check_ltv_condition(75.0, 80.0) is True

    def test_check_ltv_condition_fail(self):
        # Sad path: LTV exceeds limit
        assert ConditionEvaluator.check_ltv_condition(85.0, 80.0) is False

    def test_check_ltv_boundary(self):
        # Boundary case: Exactly at limit
        assert ConditionEvaluator.check_ltv_condition(80.0, 80.0) is True

    def test_check_credit_condition_pass(self):
        # Happy path: Good credit
        assert ConditionEvaluator.check_credit_condition(700, 650) is True

    def test_check_credit_condition_fail(self):
        # Sad path: Poor credit
        assert ConditionEvaluator.check_credit_condition(600, 650) is False

    def test_check_credit_exact_boundary(self):
        # Boundary case
        assert ConditionEvaluator.check_credit_condition(650, 650) is True


class TestMessageFormatter:

    def test_format_condition_notification_success(self):
        # Happy path
        result = MessageFormatter.format_condition_notification("Alice", "Upload ID")
        assert result == "Dear Alice, a new condition requires attention: Upload ID"

    def test_format_missing_applicant_name(self):
        # Error case: Missing data
        with pytest.raises(ValueError) as excinfo:
            MessageFormatter.format_condition_notification("", "Upload ID")
        assert "Missing required fields" in str(excinfo.value)

    def test_format_missing_description(self):
        # Error case: Missing description
        with pytest.raises(ValueError):
            MessageFormatter.format_condition_notification("Bob", None)
            
    def test_format_with_special_characters(self):
        # Edge case: Special chars in description
        result = MessageFormatter.format_condition_notification("Çélîne", "Proof of $ (Income)")
        assert "Çélîne" in result
        assert "$" in result


class TestNotificationService:

    @pytest.fixture
    def mock_clients(self):
        email_mock = Mock()
        sms_mock = Mock()
        return email_mock, sms_mock

    def test_send_email_success(self, mock_clients):
        # Happy path: Sending email
        e_mock, s_mock = mock_clients
        service = NotificationService(e_mock, s_mock)
        
        service.send_update("test@example.com", "Hello", "email")
        
        e_mock.send.assert_called_once_with("test@example.com", "Hello")
        s_mock.send.assert_not_called()

    def test_send_sms_success(self, mock_clients):
        # Happy path: Sending SMS
        e_mock, s_mock = mock_clients
        service = NotificationService(e_mock, s_mock)
        
        service.send_update("+1234567890", "Hello", "sms")
        
        s_mock.send.assert_called_once_with("+1234567890", "Hello")
        e_mock.send.assert_not_called()

    def test_send_invalid_channel(self, mock_clients):
        # Error case: Invalid channel type
        e_mock, s_mock = mock_clients
        service = NotificationService(e_mock, s_mock)
        
        with pytest.raises(ValueError) as excinfo:
            service.send_update("user", "msg", "fax")
        assert "Invalid channel" in str(excinfo.value)

    def test_send_email_client_exception(self, mock_clients):
        # Error handling: External email client fails
        e_mock, s_mock = mock_clients
        e_mock.send.side_effect = Exception("SMTP Timeout")
        service = NotificationService(e_mock, s_mock)
        
        # Assuming the service raises or handles it, here we expect it to propagate
        with pytest.raises(Exception, match="SMTP Timeout"):
            service.send_update("user@test.com", "Msg", "email")

    def test_send_multiple_channels(self, mock_clients):
        # Workflow: Sending to both channels
        e_mock, s_mock = mock_clients
        service = NotificationService(e_mock, s_mock)
        
        service.send_update("user@test.com", "Msg", "email")
        service.send_update("+1111", "Msg", "sms")
        
        assert e_mock.send.call_count == 1
        assert s_mock.send.call_count == 1

# Total assertions: ~20+
```

--- integration_tests ---
```python
import pytest
from fastapi import status
from sqlalchemy.orm import Session

# --- Integration Tests ---

class TestConditionsAPI:
    """
    Tests the API endpoints for managing underwriting conditions.
    Workflow: Create App -> Add Condition -> Verify DB -> Fulfill Condition
    """

    def test_create_condition_on_application(self, client: TestClient, sample_application: dict):
        # Happy path: Adding a condition to an existing application
        response = client.post(
            f"/applications/{sample_application['id']}/conditions",
            json={"type": "income_verification", "description": "Submit 2022 T4"}
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["application_id"] == sample_application['id']
        assert data["type"] == "income_verification"
        assert data["is_met"] is False
        assert "id" in data

    def test_create_condition_invalid_app(self, client: TestClient):
        # Sad path: Application does not exist
        response = client.post(
            "/applications/99999/conditions",
            json={"type": "income_verification", "description": "Submit T4"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_condition_missing_fields(self, client: TestClient, sample_application: dict):
        # Error case: Bad payload
        response = client.post(
            f"/applications/{sample_application['id']}/conditions",
            json={"type": "income_verification"} # Missing description
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_conditions_for_application(self, client: TestClient, sample_application: dict, db: Session):
        # Workflow: Verify retrieval
        # First, seed a condition directly in DB
        from conftest import Condition
        cond = Condition(application_id=sample_application['id'], type="seed", description="seeded", is_met=False)
        db.add(cond)
        db.commit()

        response = client.get(f"/applications/{sample_application['id']}/conditions")
        assert response.status_code == status.HTTP_200_OK
        
        conditions = response.json()
        assert len(conditions) >= 1
        assert any(c["type"] == "seed" for c in conditions)

    def test_fulfill_condition(self, client: TestClient, sample_application: dict, db: Session):
        # Workflow: Mark a condition as met
        from conftest import Condition
        # Create condition
        cond = Condition(application_id=sample_application['id'], type="doc_check", description="check", is_met=False)
        db.add(cond)
        db.commit()
        db.refresh(cond)

        # Action: Fulfill
        response = client.put(f"/applications/{sample_application['id']}/conditions/{cond['id']}/fulfill")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["is_met"] is True
        
        # Verify in DB
        db.refresh(cond)
        assert cond.is_met is True


class TestMessagingWorkflow:
    """
    Tests the integration of Conditions triggering Messages.
    Workflow: Create App -> Add Critical Condition -> Verify Auto-Notification
    """

    def test_condition_creation_triggers_notification(self, client: TestClient, sample_application: dict, db: Session):
        # Workflow: Adding a 'critical' condition should trigger an email to the applicant
        from conftest import MessageLog
        
        initial_log_count = db.query(MessageLog).count()
        
        # Endpoint: Create condition
        response = client.post(
            f"/applications/{sample_application['id']}/conditions",
            json={"type": "critical_document", "description": "Urgent: Proof of Insurance"}
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify side-effect: Message log created
        # Note: In a real async app, we might need a small delay or event processing check
        logs = db.query(MessageLog).filter(MessageLog.application_id == sample_application['id']).all()
        assert len(logs) > initial_log_count
        
        new_log = logs[-1]
        assert new_log.channel == "email"
        assert "Urgent" in new_log.content
        assert new_log.status in ["queued", "sent"]

    def test_get_message_history(self, client: TestClient, sample_application: dict, db: Session):
        # Happy path: Retrieve communication log
        from conftest import MessageLog
        
        # Seed a message
        log = MessageLog(
            application_id=sample_application['id'],
            recipient="applicant@example.com",
            channel="email",
            status="sent",
            content="Welcome to OnLendHub"
        )
        db.add(log)
        db.commit()

        response = client.get(f"/applications/{sample_application['id']}/messages")
        assert response.status_code == status.HTTP_200_OK
        
        messages = response.json()
        assert len(messages) >= 1
        assert messages[0]["content"] == "Welcome to OnLendHub"

    def test_manual_send_notification_endpoint(self, client: TestClient, sample_application: dict):
        # Test manual trigger endpoint
        payload = {
            "channel": "sms",
            "content": "Your application is under review."
        }
        response = client.post(f"/applications/{sample_application['id']}/notify", json=payload)
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["message"] == "Notification queued successfully"

    def test_multi_step_underwriting_workflow(self, client: TestClient, sample_application: dict, db: Session):
        # COMPLEX WORKFLOW TEST
        # 1. App is Submitted
        # 2. System adds LTV Condition (Simulated by POST)
        # 3. User fulfills Condition
        # 4. System sends "Conditions Met" message
        
        from conftest import Condition, MessageLog

        # Step 2: Add LTV Condition
        cond_resp = client.post(
            f"/applications/{sample_application['id']}/conditions",
            json={"type": "ltv_check", "description": "LTV too high, increase down payment"}
        )
        cond_id = cond_resp.json()["id"]
        
        # Verify notification for new condition
        logs = db.query(MessageLog).filter(MessageLog.application_id == sample_application['id']).all()
        assert any("LTV too high" in log.content for log in logs)

        # Step 3: Fulfill Condition
        client.put(f"/applications/{sample_application['id']}/conditions/{cond_id}/fulfill")
        
        # Step 4: Trigger re-evaluation (Simulated endpoint)
        eval_resp = client.post(f"/applications/{sample_application['id']}/evaluate")
        assert eval_resp.status_code == status.HTTP_200_OK
        assert eval_resp.json()["status"] == "approved" # Assuming logic passes now

        # Verify final success message
        final_logs = db.query(MessageLog).filter(MessageLog.application_id == sample_application['id']).all()
        assert any("approved" in log.content.lower() for log in final_logs)

# Total assertions: ~20+
```