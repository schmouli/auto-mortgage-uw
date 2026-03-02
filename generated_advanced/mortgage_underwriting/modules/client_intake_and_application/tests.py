Here are the comprehensive tests for the **Client Intake & Application** module of the OnLendHub project.

--- conftest.py ---
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Dict, Any

# Assuming the project structure follows standard FastAPI + SQLAlchemy patterns
# Importing the actual app and models would happen here in a real environment
# For this test generation, we assume these imports exist:
from app.main import app
from app.database import Base, get_db
from app.models import Client, Application

# SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
# engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
# TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Creates a fresh database session for each test.
    Uses in-memory SQLite for speed and isolation.
    """
    # Setup
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = TestingSessionLocal()
    
    # Dependency Override
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    
    yield db
    
    # Teardown
    db.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session: Session) -> TestClient:
    """
    Creates a FastAPI TestClient with the database dependency overridden.
    """
    return TestClient(app)

@pytest.fixture
def sample_client_payload() -> Dict[str, Any]:
    """
    Valid payload for creating a client.
    """
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "4165550199",
        "date_of_birth": "1985-05-20",
        "sin": "046454286", # Valid test SIN
        "address": {
            "street": "123 Maple Ave",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M4W1A5"
        }
    }

@pytest.fixture
def sample_application_payload() -> Dict[str, Any]:
    """
    Valid payload for creating a mortgage application.
    """
    return {
        "property_value": 750000.00,
        "down_payment": 150000.00,
        "amortization_years": 25,
        "employment_status": "full-time",
        "annual_income": 120000.00,
        "monthly_debts": 500.00,
        "property_tax_annual": 3000.00,
        "heating_cost_monthly": 150.00
    }
```

--- unit_tests ---
```python
import pytest
from unittest.mock import Mock, patch
from decimal import Decimal

# Assuming these imports from the business logic layer
from app.services.intake_service import (
    calculate_gds, 
    calculate_tds, 
    validate_sin, 
    determine_eligibility,
    process_intake_form
)
from app.schemas.application import ApplicationStatus
from app.exceptions import InvalidSinError, IncomeValidationError

class TestFinancialCalculations:
    """
    Unit tests for financial ratio calculations (GDS/TDS).
    Critical for Canadian mortgage underwriting.
    """

    def test_calculate_gds_happy_path(self):
        """
        Test Gross Debt Service ratio calculation.
        Formula: (Mortgage + Tax + Heat) / Annual Income
        """
        # Monthly mortgage payment approx: (600k loan @ 5% for 25yrs) ~ $3500
        monthly_mortgage = Decimal("3500.00")
        monthly_tax = Decimal("250.00")
        monthly_heat = Decimal("150.00")
        annual_income = Decimal("120000.00")

        gds = calculate_gds(monthly_mortgage, monthly_tax, monthly_heat, annual_income)
        
        expected_numerator = (3500 + 250 + 150) * 12 # 46800
        expected_gds = expected_numerator / 120000 # 0.39 (39%)
        
        assert abs(gds - Decimal("0.39")) < Decimal("0.01")

    def test_calculate_tds_happy_path(self):
        """
        Test Total Debt Service ratio calculation.
        Formula: (Mortgage + Tax + Heat + Other Debts) / Annual Income
        """
        monthly_mortgage = Decimal("3500.00")
        monthly_tax = Decimal("250.00")
        monthly_heat = Decimal("150.00")
        monthly_debts = Decimal("500.00")
        annual_income = Decimal("120000.00")

        tds = calculate_tds(monthly_mortgage, monthly_tax, monthly_heat, monthly_debts, annual_income)
        
        expected_numerator = (3500 + 250 + 150 + 500) * 12 # 52800
        expected_tds = expected_numerator / 120000 # 0.44 (44%)
        
        assert abs(tds - Decimal("0.44")) < Decimal("0.01")

    def test_calculations_zero_income_raises_error(self):
        """
        Test that division by zero is handled gracefully for income.
        """
        with pytest.raises(IncomeValidationError):
            calculate_gds(100, 100, 100, 0)
        
        with pytest.raises(IncomeValidationError):
            calculate_tds(100, 100, 100, 100, 0)

    def test_calculations_negative_values(self):
        """
        Ensure negative inputs don't result in negative ratios (logic check).
        """
        with pytest.raises(ValueError):
            calculate_gds(-100, 100, 100, 1000)

class TestSinValidation:
    """
    Unit tests for Social Insurance Number (SIN) validation.
    Uses Luhn algorithm validation logic.
    """

    def test_valid_sin_format(self):
        valid_sin = "046454286"
        assert validate_sin(valid_sin) is True

    def test_invalid_sin_checksum(self):
        # Correct format, fails Luhn check
        invalid_sin = "046454287"
        with pytest.raises(InvalidSinError):
            validate_sin(invalid_sin)

    def test_sin_non_numeric(self):
        with pytest.raises(InvalidSinError):
            validate_sin("ABCDEFGHIJ")

    def test_sin_wrong_length(self):
        with pytest.raises(InvalidSinError):
            validate_sin("123456")
        
        with pytest.raises(InvalidSinError):
            validate_sin("1234567890123")


class TestEligibilityLogic:
    """
    Unit tests for business rules regarding application eligibility.
    """

    @patch('app.services.intake_service.get_credit_score')
    def test_eligibility_approved(self, mock_credit_score):
        """
        Scenario: High credit score, GDS < 32%, TDS < 40%.
        Expected: Approved.
        """
        mock_credit_score.return_value = 750
        
        gds = Decimal("0.30")
        tds = Decimal("0.35")
        client_id = 1
        
        status = determine_eligibility(client_id, gds, tds)
        assert status == ApplicationStatus.APPROVED

    @patch('app.services.intake_service.get_credit_score')
    def test_eligibility_rejected_low_credit(self, mock_credit_score):
        """
        Scenario: Credit score too low (below 600).
        Expected: Rejected regardless of ratios.
        """
        mock_credit_score.return_value = 550
        
        gds = Decimal("0.20")
        tds = Decimal("0.25")
        client_id = 1
        
        status = determine_eligibility(client_id, gds, tds)
        assert status == ApplicationStatus.REJECTED

    @patch('app.services.intake_service.get_credit_score')
    def test_eligibility_rejected_high_tds(self, mock_credit_score):
        """
        Scenario: Good credit, but TDS > 42% (Strict limit).
        Expected: Referred or Rejected.
        """
        mock_credit_score.return_value = 700
        
        gds = Decimal("0.30")
        tds = Decimal("0.45") # Too high
        client_id = 1
        
        status = determine_eligibility(client_id, gds, tds)
        assert status == ApplicationStatus.REFER

class TestIntakeProcessing:
    """
    Unit tests for the orchestration service that processes the form.
    """

    @patch('app.services.intake_service.determine_eligibility')
    @patch('app.services.intake_service.calculate_tds')
    @patch('app.services.intake_service.calculate_gds')
    @patch('app.services.intake_service.validate_sin')
    def test_process_intake_success_flow(
        self, mock_sin, mock_gds, mock_tds, mock_eligibility
    ):
        """
        Test the happy path of the service layer processing valid data.
        """
        mock_sin.return_value = True
        mock_gds.return_value = Decimal("0.30")
        mock_tds.return_value = Decimal("0.35")
        mock_eligibility.return_value = ApplicationStatus.APPROVED

        payload = {
            "sin": "123456789",
            "income": 100000,
            "mortgage": 2000,
            "tax": 200,
            "heat": 100,
            "debts": 0
        }

        # Mock DB repo
        mock_repo = Mock()
        mock_repo.create.return_value = Mock(id=1)

        result = process_intake_form(payload, mock_repo)
        
        mock_sin.assert_called_once_with("123456789")
        mock_gds.assert_called_once()
        mock_eligibility.assert_called_once()
        mock_repo.create.assert_called_once()
        assert result.status == ApplicationStatus.APPROVED

    @patch('app.services.intake_service.validate_sin')
    def test_process_intake_invalid_sin_stops_execution(self, mock_sin):
        """
        Test that invalid SIN prevents database writes.
        """
        mock_sin.side_effect = InvalidSinError("Bad SIN")
        mock_repo = Mock()

        payload = {"sin": "000", "income": 0}

        with pytest.raises(InvalidSinError):
            process_intake_form(payload, mock_repo)
            
        mock_repo.create.assert_not_called()
```

--- integration_tests ---
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import models for DB verification
from app.models import Client, Application

class TestClientIntakeAPI:
    """
    Integration tests for Client Creation and Retrieval.
    """

    def test_create_client_success(self, client: TestClient, sample_client_payload):
        """
        Test API contract for creating a new client.
        """
        response = client.post("/api/v1/intake/clients", json=sample_client_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["first_name"] == "John"
        assert data["email"] == "john.doe@example.com"
        assert "sin" not in data # Ensure sensitive data isn't exposed in response

    def test_create_client_duplicate_email(self, client: TestClient, sample_client_payload, db_session: Session):
        """
        Test uniqueness constraint on email.
        """
        # First creation
        client.post("/api/v1/intake/clients", json=sample_client_payload)
        
        # Duplicate creation
        response = client.post("/api/v1/intake/clients", json=sample_client_payload)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_create_client_validation_error(self, client: TestClient):
        """
        Test Pydantic validation (invalid email format).
        """
        invalid_payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "not-an-email",
            "phone": "4165550199",
            "date_of_birth": "1985-05-20",
            "sin": "046454286"
        }
        
        response = client.post("/api/v1/intake/clients", json=invalid_payload)
        assert response.status_code == 422

class TestApplicationAPI:
    """
    Integration tests for Mortgage Application submission.
    """

    def test_submit_application_success(
        self, 
        client: TestClient, 
        sample_client_payload, 
        sample_application_payload,
        db_session: Session
    ):
        """
        Test submitting an application for an existing client.
        Verify DB state and response.
        """
        # 1. Create Client
        create_resp = client.post("/api/v1/intake/clients", json=sample_client_payload)
        client_id = create_resp.json()["id"]

        # 2. Submit Application
        app_resp = client.post(
            f"/api/v1/intake/clients/{client_id}/applications", 
            json=sample_application_payload
        )
        
        assert app_resp.status_code == 201
        data = app_resp.json()
        assert data["client_id"] == client_id
        assert data["status"] in ["PENDING", "APPROVED", "REFER"] # Depending on auto-logic
        assert "gds_ratio" in data
        assert "tds_ratio" in data

        # 3. Verify DB Record
        db_app = db_session.query(Application).filter(Application.client_id == client_id).first()
        assert db_app is not None
        assert db_app.annual_income == 120000.00

    def test_submit_application_client_not_found(self, client: TestClient, sample_application_payload):
        """
        Test 404 when submitting app for non-existent client.
        """
        response = client.post(
            "/api/v1/intake/clients/99999/applications", 
            json=sample_application_payload
        )
        assert response.status_code == 404

    def test_get_application_summary(self, client: TestClient, sample_client_payload, sample_application_payload):
        """
        Test retrieving the full application details.
        """
        # Setup
        create_resp = client.post("/api/v1/intake/clients", json=sample_client_payload)
        client_id = create_resp.json()["id"]
        app_resp = client.post(f"/api/v1/intake/clients/{client_id}/applications", json=sample_application_payload)
        app_id = app_resp.json()["id"]

        # Act
        get_resp = client.get(f"/api/v1/intake/applications/{app_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == app_id
        assert data["client"]["first_name"] == "John" # Check nested serialization

class TestEndToEndWorkflow:
    """
    Multi-step workflow tests simulating real user behavior.
    """

    def test_full_intake_workflow_with_auto_decision(
        self, 
        client: TestClient, 
        db_session: Session
    ):
        """
        Complete workflow: Register -> Apply -> Auto-Underwrite -> Check Status.
        """
        # Step 1: User Registers
        client_data = {
            "first_name": "Sarah",
            "last_name": "Connor",
            "email": "sarah@skynet.com",
            "phone": "6045550123",
            "date_of_birth": "1980-01-01",
            "sin": "123456782", # Valid format
            "address": {
                "street": "456 Cyber Lane",
                "city": "Vancouver",
                "province": "BC",
                "postal_code": "V5K1A1"
            }
        }
        reg_resp = client.post("/api/v1/intake/clients", json=client_data)
        assert reg_resp.status_code == 201
        client_id = reg_resp.json()["id"]

        # Step 2: User Submits Application (Strong financials)
        app_data = {
            "property_value": 500000.00,
            "down_payment": 150000.00, # 30% down
            "amortization_years": 20,
            "employment_status": "full-time",
            "annual_income": 150000.00, # High income
            "monthly_debts": 0.00,
            "property_tax_annual": 2500.00,
            "heating_cost_monthly": 120.00
        }
        
        app_resp = client.post(f"/api/v1/intake/clients/{client_id}/applications", json=app_data)
        assert app_resp.status_code == 201
        app_json = app_resp.json()

        # Step 3: Verify Automatic Underwriting Logic (Integration)
        # Income 150k. Mortgage ~2000/mo. Tax ~210/mo. Heat 120. Total ~2330/mo.
        # Annual housing ~ 28k. GDS = 28k/150k = ~18.6%. TDS = 18.6%.
        # Should be APPROVED automatically.
        assert app_json["status"] == "APPROVED"
        assert float(app_json["gds_ratio"]) < 0.32
        
        # Step 4: Retrieve Client Dashboard
        dashboard_resp = client.get(f"/api/v1/intake/clients/{client_id}")
        assert dashboard_resp.status_code == 200
        dashboard_data = dashboard_resp.json()
        assert len(dashboard_data["applications"]) == 1
        assert dashboard_data["applications"][0]["status"] == "APPROVED"

    def test_workflow_referred_for_manual_review(
        self, 
        client: TestClient, 
        db_session: Session
    ):
        """
        Workflow where application triggers high TDS and requires manual review.
        """
        # Register
        client_data = {
            "first_name": "Mike",
            "last_name": "Smith",
            "email": "mike@example.com",
            "phone": "4035550999",
            "date_of_birth": "1990-06-15",
            "sin": "987654321",
            "address": {
                "street": "789 Oil Rd",
                "city": "Calgary",
                "province": "AB",
                "postal_code": "T2P1V8"
            }
        }
        reg_resp = client.post("/api/v1/intake/clients", json=client_data)
        client_id = reg_resp.json()["id"]

        # Submit High Debt Application
        app_data = {
            "property_value": 600000.00,
            "down_payment": 50000.00, # Low down payment
            "amortization_years": 30,
            "employment_status": "contract",
            "annual_income": 70000.00, # Moderate income
            "monthly_debts": 1500.00, # High debts
            "property_tax_annual": 3600.00,
            "heating_cost_monthly": 200.00
        }

        app_resp = client.post(f"/api/v1/intake/clients/{client_id}/applications", json=app_data)
        app_json = app_resp.json()

        # Verify Logic
        # High debt + lower income + contract job = REFER or REJECT
        # Assuming our logic returns REFER for high TDS
        assert app_json["status"] in ["REFER", "REJECTED"]
        
        # Check DB for audit trail
        db_record = db_session.query(Application).filter(Application.id == app_json["id"]).first()
        assert db_record is not None
```