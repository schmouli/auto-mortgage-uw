Here are the comprehensive tests for the **Canadian Mortgage Underwriting System - Testing Suite**.

--- conftest.py ---
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Dict, Any

# Assuming the project structure uses SQLAlchemy and FastAPI
# Adjust imports based on actual project layout
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Database Setup for Integration Tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Mock Models for testing context (Simplified for the fixture)
class MortgageApplication(Base):
    __tablename__ = "applications"
    id = int
    applicant_name = str
    income = float
    credit_score = int
    loan_amount = float
    status = str

@pytest.fixture(scope="function")
def db_session():
    """
    Creates a fresh database session for each test.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Creates a FastAPI TestClient with a database session override.
    """
    from main import app, get_db  # Assumed entry point

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def valid_applicant_data() -> Dict[str, Any]:
    """
    Standard payload for a successful mortgage application.
    """
    return {
        "applicant_name": "John Doe",
        "income": 85000.00,
        "credit_score": 780,
        "loan_amount": 350000.00,
        "property_value": 450000.00,
        "property_tax": 3000.00,
        "heating_cost": 1200.00,
        "other_debt": 450.00
    }

@pytest.fixture
def high_risk_applicant_data() -> Dict[str, Any]:
    """
    Payload for an applicant likely to be rejected (High TDS, Low Credit).
    """
    return {
        "applicant_name": "Jane Risk",
        "income": 45000.00,
        "credit_score": 580,
        "loan_amount": 300000.00,
        "property_value": 310000.00,
        "property_tax": 4000.00,
        "heating_cost": 1500.00,
        "other_debt": 1200.00
    }

@pytest.fixture
def mock_credit_bureau_response(monkeypatch):
    """
    Mocks the external credit bureau API call.
    """
    def mock_get_score(*args, **kwargs):
        return {"score": 750, "status": "excellent"}
    
    # Assuming 'requests' or an internal client is used
    import sys
    sys.modules['external_credit_service'] = pytest.Mock()
    sys.modules['external_credit_service'].get_credit_score = mock_get_score
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from app.testing_suite import underwriting_logic, calculations, validators

# Module: app.testing_suite.calculations

class TestCalculations:
    """
    Unit tests for financial calculation functions.
    """
    def test_calculate_gds_happy_path(self):
        """
        Test Gross Debt Service ratio calculation.
        GDS = (Mortgage Tax + Heat + Condo Fees) / Annual Income
        """
        # Scenario: Monthly costs = $2500, Annual Income = $100,000
        monthly_costs = Decimal('2500.00')
        annual_income = Decimal('100000.00')
        
        expected_gds = (monthly_costs * 12) / annual_income
        result = calculations.calculate_gds(monthly_costs, annual_income)
        
        assert result == pytest.approx(float(expected_gds), rel=1e-3)
        assert result < 0.39  # Standard Canadian threshold check

    def test_calculate_tds_happy_path(self):
        """
        Test Total Debt Service ratio calculation.
        TDS = (Housing Costs + Other Debts) / Annual Income
        """
        monthly_housing = Decimal('2000.00')
        other_debts = Decimal('500.00')
        annual_income = Decimal('80000.00')
        
        expected_tds = ((monthly_housing + other_debts) * 12) / annual_income
        result = calculations.calculate_tds(monthly_housing, other_debts, annual_income)
        
        assert result == pytest.approx(float(expected_tds), rel=1e-3)
        assert 0.0 < result < 1.0

    def test_calculate_loan_to_value(self):
        """
        Test LTV calculation.
        LTV = Loan Amount / Property Value
        """
        loan_amount = Decimal('400000.00')
        property_value = Decimal('500000.00')
        
        result = calculations.calculate_ltv(loan_amount, property_value)
        
        assert result == 0.80
        assert isinstance(result, float)

    def test_zero_income_handling(self):
        """
        Test that division by zero is handled gracefully in GDS calculation.
        """
        with pytest.raises(ValueError) as exc_info:
            calculations.calculate_gds(Decimal('2000.00'), Decimal('0.00'))
        assert "Income cannot be zero" in str(exc_info.value)

    def test_negative_debt_handling(self):
        """
        Test handling of negative debt inputs (invalid scenario).
        """
        with pytest.raises(ValueError):
            calculations.calculate_tds(Decimal('2000.00'), Decimal('-500.00'), Decimal('50000.00'))

# Module: app.testing_suite.validators

class TestValidators:
    """
    Unit tests for validation logic.
    """
    def test_validate_credit_score_success(self):
        """
        Test validation for acceptable credit score.
        """
        score = 720
        is_valid = validators.validate_credit_score(score)
        assert is_valid is True

    def test_validate_credit_score_failure_low(self):
        """
        Test validation for credit score below minimum (e.g., < 600).
        """
        score = 550
        is_valid = validators.validate_credit_score(score)
        assert is_valid is False

    def test_validate_borrower_age(self):
        """
        Test age of majority rule (18 in Canada).
        """
        assert validators.validate_age(25, "ON") is True
        assert validators.validate_age(17, "ON") is False
        assert validators.validate_age(18, "AB") is True

    def test_validate_down_payment_minimum(self):
        """
        Test minimum down payment rules (5% for first 500k, 10% for remainder).
        """
        purchase_price = 600000
        min_down = 30000 # 5% of 500k + 10% of 100k
        
        # Valid down payment
        assert validators.validate_down_payment(purchase_price, 35000) is True
        # Invalid down payment
        assert validators.validate_down_payment(purchase_price, 20000) is False

# Module: app.testing_suite.underwriting_logic

class TestUnderwritingLogic:
    """
    Unit tests for the main decision engine.
    """
    @patch('app.testing_suite.validators.validate_credit_score')
    @patch('app.testing_suite.calculations.calculate_gds')
    @patch('app.testing_suite.calculations.calculate_tds')
    def test_decision_engine_approved(
        self, mock_tds, mock_gds, mock_credit
    ):
        """
        Test happy path for application approval.
        """
        # Setup mocks
        mock_credit.return_value = True
        mock_gds.return_value = 0.30 # < 0.39
        mock_tds.return_value = 0.35 # < 0.44
        
        application_data = MagicMock()
        application_data.income = 100000
        application_data.loan_amount = 300000
        
        decision = underwriting_logic.make_decision(application_data)
        
        assert decision['status'] == 'APPROVED'
        assert decision['rate'] is not None
        mock_credit.assert_called_once()
        mock_gds.assert_called_once()
        mock_tds.assert_called_once()

    @patch('app.testing_suite.validators.validate_credit_score')
    def test_decision_engine_declined_credit(self, mock_credit):
        """
        Test decline path due to bad credit.
        """
        mock_credit.return_value = False
        
        application_data = MagicMock()
        decision = underwriting_logic.make_decision(application_data)
        
        assert decision['status'] == 'DECLINED'
        assert 'Credit score' in decision['reason']

    @patch('app.testing_suite.validators.validate_credit_score')
    @patch('app.testing_suite.calculations.calculate_tds')
    def test_decision_engine_declined_tds(self, mock_tds, mock_credit):
        """
        Test decline path due to high TDS.
        """
        mock_credit.return_value = True
        mock_tds.return_value = 0.50 # > 0.44 threshold
        
        application_data = MagicMock()
        decision = underwriting_logic.make_decision(application_data)
        
        assert decision['status'] == 'DECLINED'
        assert 'TDS' in decision['reason']

    def test_stress_test_calculation(self):
        """
        Test the mortgage stress test logic (Benchmark rate + 2%).
        """
        contract_rate = 0.045 # 4.5%
        benchmark_rate = 0.055 # 5.5%
        
        qualifying_rate = underwriting_logic.determine_qualifying_rate(contract_rate, benchmark_rate)
        
        # Should be the higher of (Contract + 2%) or Benchmark
        # Contract + 2% = 6.5%
        # Benchmark = 5.5%
        assert qualifying_rate == 0.065
```

--- integration_tests ---
```python
import pytest
from fastapi import status

class TestMortgageAPI:
    """
    Integration tests for the Underwriting API Endpoints.
    """

    def test_create_application_success(self, client: TestClient, valid_applicant_data):
        """
        Test creating a new application via POST.
        """
        response = client.post("/api/v1/applications", json=valid_applicant_data)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["applicant_name"] == valid_applicant_data["applicant_name"]
        assert data["status"] == "PENDING_REVIEW"

    def test_create_application_validation_error(self, client: TestClient):
        """
        Test API validation with missing required fields.
        """
        invalid_data = {
            "applicant_name": "Missing Data User"
            # Missing income, credit_score, etc.
        }
        
        response = client.post("/api/v1/applications", json=invalid_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "detail" in response.json()

    def test_get_application(self, client: TestClient, valid_applicant_data):
        """
        Test retrieving a specific application by ID.
        """
        # 1. Create an application
        create_resp = client.post("/api/v1/applications", json=valid_applicant_data)
        app_id = create_resp.json()["id"]
        
        # 2. Retrieve it
        get_resp = client.get(f"/api/v1/applications/{app_id}")
        
        assert get_resp.status_code == status.HTTP_200_OK
        data = get_resp.json()
        assert data["id"] == app_id
        assert data["income"] == valid_applicant_data["income"]

    def test_get_application_not_found(self, client: TestClient):
        """
        Test retrieving a non-existent application.
        """
        response = client.get("/api/v1/applications/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_submit_underwriting_evaluation_approved(
        self, client: TestClient, valid_applicant_data, db_session
    ):
        """
        End-to-End workflow: Create App -> Evaluate -> Check DB Status.
        """
        # 1. Create Application
        create_resp = client.post("/api/v1/applications", json=valid_applicant_data)
        app_id = create_resp.json()["id"]
        
        # 2. Trigger Underwriting Evaluation
        eval_resp = client.post(f"/api/v1/applications/{app_id}/evaluate")
        assert eval_resp.status_code == status.HTTP_200_OK
        
        eval_data = eval_resp.json()
        assert eval_data["application_id"] == app_id
        assert eval_data["decision"] in ["APPROVED", "DECLINED", "REFER"]
        
        # 3. Verify Database State
        # (Assuming direct DB access is available for verification)
        from app.models import Application
        db_app = db_session.query(Application).filter(Application.id == app_id).first()
        
        assert db_app is not None
        assert db_app.status == eval_data["decision"]
        assert db_app.last_updated is not None

    def test_submit_underwriting_evaluation_high_risk(
        self, client: TestClient, high_risk_applicant_data
    ):
        """
        End-to-End workflow for a declined application.
        """
        # 1. Create High Risk Application
        create_resp = client.post("/api/v1/applications", json=high_risk_applicant_data)
        app_id = create_resp.json()["id"]
        
        # 2. Evaluate
        eval_resp = client.post(f"/api/v1/applications/{app_id}/evaluate")
        assert eval_resp.status_code == status.HTTP_200_OK
        
        eval_data = eval_resp.json()
        # Based on the fixture data (Low credit, high debt), we expect decline
        assert eval_data["decision"] == "DECLINED"
        assert "reason" in eval_data
        assert len(eval_data["reason"]) > 0

    def test_update_application_status(self, client: TestClient, valid_applicant_data):
        """
        Test manual status update endpoint (Admin function).
        """
        create_resp = client.post("/api/v1/applications", json=valid_applicant_data)
        app_id = create_resp.json()["id"]
        
        update_payload = {"status": "MANUAL_REVIEW", "notes": "Complex income structure"}
        update_resp = client.patch(f"/api/v1/applications/{app_id}", json=update_payload)
        
        assert update_resp.status_code == status.HTTP_200_OK
        data = update_resp.json()
        assert data["status"] == "MANUAL_REVIEW"
        assert data["notes"] == "Complex income structure"

    def test_concurrent_evaluation_handling(self, client: TestClient, valid_applicant_data):
        """
        Test that re-evaluating an already evaluated app handles state correctly.
        """
        create_resp = client.post("/api/v1/applications", json=valid_applicant_data)
        app_id = create_resp.json()["id"]
        
        # First Evaluation
        client.post(f"/api/v1/applications/{app_id}/evaluate")
        
        # Second Evaluation (Idempotency check or Lock check)
        second_eval_resp = client.post(f"/api/v1/applications/{app_id}/evaluate")
        
        # Depending on business logic, this should either return the same result 
        # or a Conflict/Already Processed error. Assuming 200 OK with same data for idempotency.
        assert second_eval_resp.status_code == status.HTTP_200_OK
```