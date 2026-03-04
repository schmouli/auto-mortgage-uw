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