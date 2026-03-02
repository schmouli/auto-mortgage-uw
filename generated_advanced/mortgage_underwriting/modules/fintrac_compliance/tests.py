Here are the comprehensive tests for the **FINTRAC Compliance** module of the OnLendHub project.

These tests cover Canadian mortgage underwriting requirements, specifically focusing on:
1.  **Identity Verification** (Individual vs. Corporation)
2.  **PEP (Politically Exposed Persons) & Sanctions Screening**
3.  **Large Cash Transaction Reporting (LCTR)** thresholds ($10,000 CAD)
4.  **Suspicious Transaction Reporting (STR)** logic

---

--- conftest.py ---
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Dict, Any

# Assuming a standard project structure for OnLendHub
# In a real scenario, these would import from your actual models and main app
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

# --- Mock Models for Test Context ---
class ComplianceRecord(Base):
    __tablename__ = "compliance_records"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, index=True)
    is_pep = Column(Boolean, default=False)
    is_sanctioned = Column(Boolean, default=False)
    cash_transaction_amount = Column(Float, default=0.0)
    risk_score = Column(Integer, default=0)
    status = Column(String, default="pending")

class LoanApplication(Base):
    __tablename__ = "loan_applications"
    id = Column(Integer, primary_key=True, index=True)
    applicant_name = Column(String)
    id_type = Column(String) # "PASSPORT", "DRIVER_LICENSE"
    id_number = Column(String)
    id_expiry = Column(DateTime)

# --- Fixtures ---

@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a new database session for a test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Create a TestClient that overrides the database dependency.
    Note: This assumes a 'get_db' dependency in the main app.
    """
    from onlendhub.main import app # Assumed import path
    from onlendhub.database import get_db # Assumed import path

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

# --- Data Fixtures ---

@pytest.fixture
def valid_individual_payload() -> Dict[str, Any]:
    return {
        "client_type": "individual",
        "first_name": "John",
        "last_name": "Doe",
        "dob": "1980-01-01",
        "sin": "123456789",
        "id_document": {
            "type": "PASSPORT",
            "number": "AB1234567",
            "expiry_date": "2030-01-01",
            "issuing_country": "CAN"
        }
    }

@pytest.fixture
def valid_corp_payload() -> Dict[str, Any]:
    return {
        "client_type": "corporation",
        "business_name": "Doe Construction Inc.",
        "registration_number": "123456789",
        "jurisdiction": "Ontario"
    }

@pytest.fixture
def pep_watchlist_mock(mocker):
    """Mock response for an external PEP screening API."""
    return {
        "is_pep": True,
        "list_name": "Canadian Sanctions List",
        "match_score": 0.95
    }

@pytest.fixture
def clean_watchlist_mock(mocker):
    """Mock response for a clean external screening."""
    return {
        "is_pep": False,
        "list_name": None,
        "match_score": 0.0
    }
```

--- unit_tests ---
```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from onlendhub.modules.fintrac import service # Assumed module path
from onlendhub.modules.fintrac.exceptions import ComplianceError, DocumentExpiredError

# Unit Tests for FINTRAC Compliance Service Layer
# Focus: Business Logic, External API Mocking, Validation Rules

class TestIdentityVerification:

    def test_validate_passport_success(self, valid_individual_payload):
        """Test happy path for valid passport validation."""
        # Arrange
        doc_data = valid_individual_payload['id_document']
        
        # Act
        result = service.validate_identity_document(doc_data)
        
        # Assert
        assert result['is_valid'] is True
        assert result['document_type'] == 'PASSPORT'
        assert 'expiry_date' in result

    def test_validate_expired_document(self, valid_individual_payload):
        """Test that an expired document raises an error."""
        # Arrange
        past_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        valid_individual_payload['id_document']['expiry_date'] = past_date
        
        # Act & Assert
        with pytest.raises(DocumentExpiredError) as exc_info:
            service.validate_identity_document(valid_individual_payload['id_document'])
        
        assert "expired" in str(exc_info.value).lower()

    def test_validate_missing_id_number(self, valid_individual_payload):
        """Test validation failure when ID number is missing."""
        # Arrange
        valid_individual_payload['id_document']['number'] = ""
        
        # Act
        result = service.validate_identity_document(valid_individual_payload['id_document'])
        
        # Assert
        assert result['is_valid'] is False
        assert 'missing_field' in result['errors']

    def test_corporate_registration_validation(self, valid_corp_payload):
        """Test corporate registration number format."""
        # Act
        result = service.validate_corporate_entity(valid_corp_payload)
        
        # Assert
        assert result['is_valid'] is True
        assert result['jurisdiction'] == 'Ontario'

    def test_corporate_registration_invalid_length(self, valid_corp_payload):
        """Test that short registration numbers fail."""
        # Arrange
        valid_corp_payload['registration_number'] = "123"
        
        # Act
        result = service.validate_corporate_entity(valid_corp_payload)
        
        # Assert
        assert result['is_valid'] is False


class TestPEPScreening:

    @patch('onlendhub.modules.fintrac.service.requests.get')
    def test_check_pep_status_match_found(self, mock_get, pep_watchlist_mock):
        """Test external API call handling when PEP is found."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = pep_watchlist_mock
        mock_get.return_value = mock_response
        
        full_name = "John Doe"
        
        # Act
        result = service.screen_pep_and_sanctions(full_name)
        
        # Assert
        assert result['is_pep'] is True
        assert result['risk_level'] == 'HIGH'
        mock_get.assert_called_once()

    @patch('onlendhub.modules.fintrac.service.requests.get')
    def test_check_pep_status_clean(self, mock_get, clean_watchlist_mock):
        """Test external API call handling when client is clean."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = clean_watchlist_mock
        mock_get.return_value = mock_response
        
        full_name = "Jane Smith"
        
        # Act
        result = service.screen_pep_and_sanctions(full_name)
        
        # Assert
        assert result['is_pep'] is False
        assert result['risk_level'] == 'LOW'

    @patch('onlendhub.modules.fintrac.service.requests.get')
    def test_pep_api_timeout_handling(self, mock_get):
        """Test resilience when external watchlist API times out."""
        # Arrange
        mock_get.side_effect = Exception("Connection Timeout")
        
        # Act & Assert
        with pytest.raises(ComplianceError) as exc_info:
            service.screen_pep_and_sanctions("Bad Name")
        
        assert "external service unavailable" in str(exc_info.value).lower()


class TestTransactionThresholds:

    def test_large_cash_threshold_trigger(self):
        """Test that amounts >= $10,000 CAD trigger LCTR logic."""
        # Arrange
        amount_cad = 10000.00
        transaction_type = "CASH_DEPOSIT"
        
        # Act
        report_required = service.check_large_cash_threshold(amount_cad, transaction_type)
        
        # Assert
        assert report_required is True

    def test_large_cash_threshold_below_limit(self):
        """Test that amounts < $10,000 CAD do not trigger LCTR logic."""
        # Arrange
        amount_cad = 9999.99
        transaction_type = "CASH_DEPOSIT"
        
        # Act
        report_required = service.check_large_cash_threshold(amount_cad, transaction_type)
        
        # Assert
        assert report_required is False

    def test_non_cash_transaction_exemption(self):
        """Test that non-cash transactions (e.g., Wire) are exempt from LCTR."""
        # Arrange
        amount_cad = 15000.00
        transaction_type = "WIRE_TRANSFER"
        
        # Act
        report_required = service.check_large_cash_threshold(amount_cad, transaction_type)
        
        # Assert
        assert report_required is False

    def test_structuring_detection(self):
        """Test logic to detect structuring (splitting transactions)."""
        # Arrange
        transactions = [
            {"amount": 5000.00, "date": "2023-01-01"},
            {"amount": 5000.01, "date": "2023-01-01"},
            {"amount": 2000.00, "date": "2023-01-02"}
        ]
        
        # Act
        is_structuring = service.detect_structuring(transactions, threshold_window_days=1)
        
        # Assert
        assert is_structuring is True

    def test_suspicious_activity_flags(self):
        """Test various flags for suspicious activity."""
        # Arrange
        flags = ["client_nervous", "refuses_id", "unusual_source_of_funds"]
        
        # Act
        risk_score = service.calculate_suspicion_score(flags)
        
        # Assert
        assert risk_score > 50 # Assuming a threshold
        assert risk_score == 75 # 3 flags * 25 points each (example logic)


class TestReportGeneration:

    def test_generate_lctr_object(self):
        """Test creation of a Large Cash Transaction Report object."""
        # Arrange
        data = {
            "reporting_entity_id": "12345",
            "amount": 12000.00,
            "currency": "CAD",
            "date": "2023-10-27"
        }
        
        # Act
        lctr = service.create_lctr_report(data)
        
        # Assert
        assert lctr['report_type'] == 'LCTR'
        assert lctr['amount'] == 12000.00
        assert lctr['signature_block'] is not None

    def test_generate_str_object(self):
        """Test creation of a Suspicious Transaction Report object."""
        # Arrange
        data = {
            "suspicion_reasons": ["Unexplained wealth", "Shell company"],
            "filing_date": datetime.now().date()
        }
        
        # Act
        str_report = service.create_str_report(data)
        
        # Assert
        assert str_report['report_type'] == 'STR'
        assert len(str_report['suspicion_reasons']) == 2
        assert 'narrative' in str_report
```

--- integration_tests ---
```python
import pytest
from fastapi import status

# Integration Tests for FINTRAC Compliance API Endpoints
# Focus: Request/Response Contracts, DB Persistence, Workflows

class TestComplianceAPIEndpoints:

    def test_submit_client_verification_success(self, client: TestClient, valid_individual_payload):
        """Test full workflow of submitting a client for verification."""
        # Act
        response = client.post("/api/v1/fintrac/verify-client", json=valid_individual_payload)
        
        # Assert - Response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'submitted'
        assert 'verification_id' in data
        
        # Assert - Database State (Verification would require fetching from DB in real scenario)
        # Here we assume the endpoint returns the calculated state
        assert data['details']['id_check'] == 'passed'

    def test_submit_pep_client_flagged(self, client: TestClient, mocker, valid_individual_payload):
        """Test workflow where a client matches a PEP list."""
        # Arrange - Mock the external service call inside the API route
        mocker.patch('onlendhub.modules.fintrac.service.screen_pep_and_sanctions', 
                     return_value={"is_pep": True, "risk_level": "HIGH"})
        
        # Act
        response = client.post("/api/v1/fintrac/verify-client", json=valid_individual_payload)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'review_required'
        assert data['flags']['pep_match'] is True

    def test_submit_corporate_client(self, client: TestClient, valid_corp_payload):
        """Test corporate client compliance endpoint."""
        # Act
        response = client.post("/api/v1/fintrac/verify-corporation", json=valid_corp_payload)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['entity_type'] == 'corporation'
        assert data['beneficial_ownership_required'] is True

    def test_report_large_cash_transaction(self, client: TestClient, db_session: Session):
        """Test reporting a transaction that meets the $10k threshold."""
        # Arrange
        payload = {
            "loan_application_id": 1,
            "amount": 15000.00,
            "currency": "CAD",
            "transaction_method": "CASH",
            "date": "2023-11-01"
        }
        
        # Act
        response = client.post("/api/v1/fintrac/report-transaction", json=payload)
        
        # Assert - Response
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data['report_type'] == 'LCTR'
        assert data['status'] == 'filed'
        
        # Assert - DB Record
        # In a real integration test, we would query db_session here:
        # record = db_session.query(ComplianceRecord).filter_by(loan_application_id=1).first()
        # assert record.cash_transaction_amount == 15000.00

    def test_report_suspicious_transaction(self, client: TestClient):
        """Test STR filing endpoint."""
        # Arrange
        payload = {
            "loan_application_id": 2,
            "suspicion_details": "Client unable to explain source of down payment.",
            "priority": "HIGH"
        }
        
        # Act
        response = client.post("/api/v1/fintrac/report-suspicious", json=payload)
        
        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data['report_id'].startswith('STR-')

    def test_get_compliance_status(self, client: TestClient, db_session: Session):
        """Test retrieving the compliance status of a specific application."""
        # Assume ID 1 exists (setup in db_session or previous test)
        app_id = 101
        
        # Act
        response = client.get(f"/api/v1/fintrac/status/{app_id}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'application_id' in data
        assert 'overall_status' in data # e.g., "COMPLIANT", "NON_COMPLIANT"

    def test_invalid_input_missing_field(self, client: TestClient):
        """Test API validation on missing required fields."""
        # Arrange - Missing SIN
        payload = {
            "client_type": "individual",
            "first_name": "John",
            "last_name": "Doe"
            # "sin" is missing
        }
        
        # Act
        response = client.post("/api/v1/fintrac/verify-client", json=payload)
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        errors = response.json()['detail']
        assert any(err['loc'][-1] == 'sin' for err in errors)

    def test_unsupported_currency(self, client: TestClient):
        """Test validation of transaction currency (FINTRAC requires CAD equivalent)."""
        # Arrange
        payload = {
            "loan_application_id": 1,
            "amount": 5000,
            "currency": "BTC", # Unsupported
            "transaction_method": "WIRE"
        }
        
        # Act
        response = client.post("/api/v1/fintrac/report-transaction", json=payload)
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "currency" in response.json()['message'].lower()


class TestMultiStepComplianceWorkflow:

    def test_full_mortgage_underwriting_compliance_flow(self, client: TestClient, valid_individual_payload):
        """
        Complex Scenario:
        1. Submit Client
        2. System verifies ID
        3. User submits a Cash Deposit of $12,000
        4. System flags LCTR requirement
        5. User confirms LCTR filing
        """
        
        # Step 1: Submit Client
        verify_resp = client.post("/api/v1/fintrac/verify-client", json=valid_individual_payload)
        assert verify_resp.status_code == 200
        app_id = verify_resp.json()['application_id']
        
        # Step 2: Check Initial Status
        status_resp = client.get(f"/api/v1/fintrac/status/{app_id}")
        assert status_resp.json()['lctr_required'] is False
        
        # Step 3: Submit Large Cash Transaction
        trans_payload = {
            "loan_application_id": app_id,
            "amount": 12000.00,
            "currency": "CAD",
            "transaction_method": "CASH"
        }
        trans_resp = client.post("/api/v1/fintrac/report-transaction", json=trans_payload)
        assert trans_resp.status_code == 201
        assert trans_resp.json()['lctr_triggered'] is True
        
        # Step 4: Final Status Check
        final_status = client.get(f"/api/v1/fintrac/status/{app_id}")
        assert final_status.json()['compliance_hold'] is True
        assert 'LCTR' in final_status.json()['pending_reports']
```