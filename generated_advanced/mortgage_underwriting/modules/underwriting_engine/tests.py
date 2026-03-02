Here are the comprehensive tests for the **OnLendHub Underwriting Engine**.

These tests assume a standard structure where:
- `UnderwritingEngine` is a class containing business logic.
- FastAPI is used for the API layer.
- SQLAlchemy is used for ORM.

--- conftest.py ---
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from unittest.mock import MagicMock
from decimal import Decimal

# Assuming these models exist in the project structure
from onlendhub.models import Base, MortgageApplication, Applicant
from onlendhub.main import app  # The FastAPI application instance

# Database Setup for Integration Tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Creates a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session: Session):
    """Creates a test client with a dependency override for the DB."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    # Mock the dependency override if using get_db dependency
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def mock_credit_bureau():
    """Mocks the external Credit Bureau API client."""
    with pytest.mock.patch('onlendhub.services.credit_bureau.CreditBureauClient') as mock:
        mock_instance = MagicMock()
        mock_instance.get_score.return_value = 750
        mock.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def valid_application_payload():
    """Returns a valid payload for a Canadian mortgage application."""
    return {
        "applicant_id": "cust_001",
        "loan_amount": 450000.00,
        "property_value": 600000.00,
        "down_payment": 150000.00,
        "annual_income": 120000.00,
        "monthly_debt": 500.00,
        "property_tax_annual": 3600.00,
        "heating_cost_monthly": 150.00,
        "province": "ON",
        "amortization_years": 25
    }

@pytest.fixture
def valid_application_obj(valid_application_payload):
    """Returns a database model object for the application."""
    return MortgageApplication(**valid_application_payload, status="PENDING")
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from onlendhub.engine import UnderwritingEngine
from onlendhub.exceptions import UnderwritingError
from onlendhub.models import DecisionEnum

# Test Configuration Constants
MAX_LTV_INSURABLE = Decimal("0.80")  # 80%
MIN_CREDIT_SCORE = 600
MAX_GDS = Decimal("0.39")  # 39%
MAX_TDS = Decimal("0.44")  # 44%

class TestUnderwritingCalculations:
    """Unit tests for mathematical calculations within the engine."""

    def test_calculate_ltv_happy_path(self):
        engine = UnderwritingEngine()
        # Loan 400k, Value 500k = 80%
        ltv = engine._calculate_ltv(Decimal("400000"), Decimal("500000"))
        assert ltv == Decimal("0.80")

    def test_calculate_ltv_high_ratio(self):
        engine = UnderwritingEngine()
        # Loan 450k, Value 500k = 90%
        ltv = engine._calculate_ltv(Decimal("450000"), Decimal("500000"))
        assert ltv == Decimal("0.90")
        assert ltv > MAX_LTV_INSURABLE

    def test_calculate_ltv_zero_value_error(self):
        engine = UnderwritingEngine()
        with pytest.raises(UnderwritingError):
            engine._calculate_ltv(Decimal("100000"), Decimal("0"))

    def test_calculate_gds_within_limits(self):
        engine = UnderwritingEngine()
        # Mortgage: 2000/mo, Tax: 300/mo, Heat: 150/mo. Income: 6500/mo
        # (2000 + 300 + 150) / 6500 = ~38.4%
        gds = engine._calculate_gds(
            mortgage_payment=Decimal("2000"),
            property_tax=Decimal("300"),
            heating=Decimal("150"),
            income=Decimal("6500")
        )
        assert gds <= MAX_GDS
        assert gds == Decimal("0.384615").quantize(Decimal("0.000001"))

    def test_calculate_gds_exceeds_limit(self):
        engine = UnderwritingEngine()
        gds = engine._calculate_gds(
            mortgage_payment=Decimal("3000"),
            property_tax=Decimal("500"),
            heating=Decimal("200"),
            income=Decimal("6500")
        )
        assert gds > MAX_GDS

    def test_calculate_tds_within_limits(self):
        engine = UnderwritingEngine()
        # GDS components (2450) + Other Debts (500) / Income (6500)
        tds = engine._calculate_tds(
            housing_costs=Decimal("2450"),
            other_debts=Decimal("500"),
            income=Decimal("6500")
        )
        assert tds <= MAX_TDS

    def test_calculate_tds_exceeds_limit(self):
        engine = UnderwritingEngine()
        tds = engine._calculate_tds(
            housing_costs=Decimal("2450"),
            other_debts=Decimal("2000"),
            income=Decimal("6500")
        )
        assert tds > MAX_TDS

class TestUnderwritingLogic:
    """Unit tests for decision logic and rules."""

    def test_evaluate_credit_score_approval(self):
        engine = UnderwritingEngine()
        result = engine._evaluate_credit(720)
        assert result == DecisionEnum.APPROVED

    def test_evaluate_credit_score_rejection(self):
        engine = UnderwritingEngine()
        result = engine._evaluate_credit(550)
        assert result == DecisionEnum.REJECTED

    def test_evaluate_credit_score_boundary(self):
        engine = UnderwritingEngine()
        # Test exactly on the boundary
        result = engine._evaluate_credit(600)
        # Assuming 600 is the floor for approval
        assert result in [DecisionEnum.APPROVED, DecisionEnum.REFER]

    @patch('onlendhub.engine.UnderwritingEngine._calculate_ltv')
    @patch('onlendhub.engine.UnderwritingEngine._calculate_gds')
    @patch('onlendhub.engine.UnderwritingEngine._calculate_tds')
    def test_decision_matrix_perfect_candidate(self, mock_tds, mock_gds, mock_ltv):
        """Test a candidate that passes all metrics."""
        engine = UnderwritingEngine()
        mock_ltv.return_value = Decimal("0.75")
        mock_gds.return_value = Decimal("0.30")
        mock_tds.return_value = Decimal("0.35")

        decision = engine._apply_rules(
            ltv=Decimal("0.75"),
            gds=Decimal("0.30"),
            tds=Decimal("0.35"),
            credit_score=750
        )
        assert decision == DecisionEnum.APPROVED

    @patch('onlendhub.engine.UnderwritingEngine._calculate_ltv')
    def test_insurance_requirement_detection(self, mock_ltv):
        engine = UnderwritingEngine()
        mock_ltv.return_value = Decimal("0.85")
        
        is_required = engine._check_insurance_required(ltv=Decimal("0.85"))
        assert is_required is True

    @patch('onlendhub.engine.UnderwritingEngine._calculate_ltv')
    def test_insurance_not_required_conventional(self, mock_ltv):
        engine = UnderwritingEngine()
        mock_ltv.return_value = Decimal("0.80")
        
        is_required = engine._check_insurance_required(ltv=Decimal("0.80"))
        assert is_required is False

    def test_process_application_missing_field(self):
        engine = UnderwritingEngine()
        incomplete_data = {
            "loan_amount": 100000,
            # Missing property_value
        }
        with pytest.raises(KeyError):
            engine.process(incomplete_data)

    def test_process_application_negative_income(self):
        engine = UnderwritingEngine()
        with pytest.raises(UnderwritingError):
            engine._validate_income(Decimal("-50000"))

    def test_process_application_zero_downpayment(self):
        engine = UnderwritingEngine()
        # In Canada, 0% down is generally not allowed for standard residential
        with pytest.raises(UnderwritingError):
            engine._validate_downpayment(loan=Decimal("400000"), down=Decimal("0"))

    @patch('onlendhub.services.credit_bureau.CreditBureauClient')
    def test_integration_with_credit_bureau_mock(self, mock_client_class):
        engine = UnderwritingEngine()
        mock_instance = MagicMock()
        mock_instance.get_score.return_value = 680
        mock_client_class.return_value = mock_instance

        score = engine._get_external_credit_score("sin_123")
        assert score == 680
        mock_instance.get_score.assert_called_once_with("sin_123")

    def test_amortization_limit_validation(self):
        engine = UnderwritingEngine()
        # Canada max amortization is usually 25y (insured) or 30y (uninsured)
        # Testing strict 25 year limit for this engine
        is_valid = engine._validate_amortization(30)
        assert is_valid is False
        
        is_valid = engine._validate_amortization(25)
        assert is_valid is True

    def test_calculate_monthly_mortgage_payment(self):
        engine = UnderwritingEngine()
        # Principal 300k, Rate 5%, 25 years (300 months)
        # M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # i = 0.05/12 = 0.004166
        payment = engine._calculate_payment(
            principal=Decimal("300000"), 
            annual_rate=Decimal("0.05"), 
            months=300
        )
        # Rough check
        assert payment > Decimal("1500") and payment < Decimal("2000")
```

--- integration_tests ---
```python
import pytest
from fastapi import status
from sqlalchemy.orm import Session

class TestUnderwritingAPI:
    """Integration tests for the Underwriting API endpoints."""

    def test_submit_application_success(self, client: TestClient, valid_application_payload):
        """Test submitting a valid application results in 201 Created."""
        response = client.post("/api/v1/applications/", json=valid_application_payload)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "PENDING"
        assert "id" in data
        assert data["loan_amount"] == 450000.00

    def test_submit_application_validation_error(self, client: TestClient):
        """Test submitting invalid data returns 422."""
        invalid_payload = {
            "loan_amount": -500,  # Invalid
            "property_value": "not_a_number" # Invalid
        }
        response = client.post("/api/v1/applications/", json=invalid_payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_underwrite_workflow_approved(self, client: TestClient, db_session: Session, valid_application_payload, mock_credit_bureau):
        """
        Full workflow: Create App -> Trigger Underwriting -> Verify DB State.
        Assumes a POST /applications/{id}/underwrite endpoint.
        """
        # 1. Create Application
        create_resp = client.post("/api/v1/applications/", json=valid_application_payload)
        app_id = create_resp.json()["id"]

        # 2. Trigger Underwriting
        # Mocking credit bureau to return high score for approval
        mock_credit_bureau.get_score.return_value = 780
        
        underwrite_resp = client.post(f"/api/v1/applications/{app_id}/underwrite")
        assert underwrite_resp.status_code == status.HTTP_200_OK
        
        result_data = underwrite_resp.json()
        assert result_data["decision"] == "APPROVED"
        assert "ltv" in result_data["details"]
        assert "gds" in result_data["details"]

        # 3. Verify Database Persistence
        db_app = db_session.query(MortgageApplication).filter(MortgageApplication.id == app_id).first()
        assert db_app is not None
        assert db_app.status == "APPROVED"

    def test_underwrite_workflow_rejected_low_credit(self, client: TestClient, db_session: Session, valid_application_payload, mock_credit_bureau):
        """Test rejection flow due to low credit score."""
        # 1. Create Application
        create_resp = client.post("/api/v1/applications/", json=valid_application_payload)
        app_id = create_resp.json()["id"]

        # 2. Trigger Underwriting with bad credit
        mock_credit_bureau.get_score.return_value = 500
        
        underwrite_resp = client.post(f"/api/v1/applications/{app_id}/underwrite")
        assert underwrite_resp.status_code == status.HTTP_200_OK
        
        result_data = underwrite_resp.json()
        assert result_data["decision"] == "REJECTED"
        assert "Credit score too low" in result_data["reason"]

    def test_underwrite_workflow_rejected_high_tds(self, client: TestClient, valid_application_payload, mock_credit_bureau):
        """Test rejection flow due to high debt service ratios."""
        # 1. Create Application with high debt relative to income
        payload = valid_application_payload.copy()
        payload["monthly_debt"] = 4000.00 # High debt
        payload["annual_income"] = 50000.00 # Low income
        
        create_resp = client.post("/api/v1/applications/", json=payload)
        app_id = create_resp.json()["id"]

        # 2. Trigger Underwriting (Credit is fine, but TDS will fail)
        mock_credit_bureau.get_score.return_value = 700
        
        underwrite_resp = client.post(f"/api/v1/applications/{app_id}/underwrite")
        assert underwrite_resp.status_code == status.HTTP_200_OK
        
        result_data = underwrite_resp.json()
        assert result_data["decision"] == "REJECTED"
        assert "TDS" in result_data["reason"]

    def test_get_application_details(self, client: TestClient, valid_application_payload):
        """Test retrieving a specific application."""
        create_resp = client.post("/api/v1/applications/", json=valid_application_payload)
        app_id = create_resp.json()["id"]

        get_resp = client.get(f"/api/v1/applications/{app_id}")
        assert get_resp.status_code == status.HTTP_200_OK
        data = get_resp.json()
        assert data["id"] == app_id
        assert data["province"] == "ON"

    def test_get_non_existent_application(self, client: TestClient):
        """Test 404 when application does not exist."""
        get_resp = client.get("/api/v1/applications/99999")
        assert get_resp.status_code == status.HTTP_404_NOT_FOUND

    def test_list_applications(self, client: TestClient, valid_application_payload):
        """Test listing all applications."""
        # Create two apps
        client.post("/api/v1/applications/", json=valid_application_payload)
        payload2 = valid_application_payload.copy()
        payload2["applicant_id"] = "cust_002"
        client.post("/api/v1/applications/", json=payload2)

        list_resp = client.get("/api/v1/applications/")
        assert list_resp.status_code == status.HTTP_200_OK
        data = list_resp.json()
        assert len(data) >= 2

    def test_concurrent_underwriting_protection(self, client: TestClient, valid_application_payload, mock_credit_bureau):
        """
        Test that underwriting an already underwritten app doesn't change state 
        or returns a specific conflict/error.
        """
        create_resp = client.post("/api/v1/applications/", json=valid_application_payload)
        app_id = create_resp.json()["id"]

        # First run
        mock_credit_bureau.get_score.return_value = 700
        resp1 = client.post(f"/api/v1/applications/{app_id}/underwrite")
        assert resp1.status_code == 200

        # Second run (Should ideally be idempotent or return 409 Conflict)
        resp2 = client.post(f"/api/v1/applications/{app_id}/underwrite")
        # Assuming the API returns 400 Bad Request or 409 Conflict if already processed
        assert resp2.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

    def test_calculator_endpoint(self, client: TestClient):
        """Test a simple helper endpoint for mortgage calculations if available."""
        params = {
            "principal": 500000,
            "rate": 4.5,
            "years": 25
        }
        resp = client.get("/api/v1/tools/calculate-payment", params=params)
        assert resp.status_code == status.HTTP_200_OK
        assert "monthly_payment" in resp.json()
```