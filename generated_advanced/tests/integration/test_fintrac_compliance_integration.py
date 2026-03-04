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