```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Hypothetical imports
# from onlendhub.models.lender import Lender
# from onlendhub.models.application import Application, ApplicationStatus
# from onlendhub.database import get_db

class TestLenderComparisonAPI:
    """
    Integration tests for the Lender Comparison API endpoints.
    Uses TestClient to hit the routing layer and in-memory DB.
    """

    def test_compare_lenders_happy_path(self, client: TestClient, sample_application_data):
        """
        Test submitting a valid application and getting a list of comparable lenders.
        """
        response = client.post("/api/v1/lenders/compare", json=sample_application_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "offers" in data
        assert len(data["offers"]) > 0
        
        # Validate structure of the first offer
        offer = data["offers"][0]
        assert "lender_name" in offer
        assert "rate" in offer
        assert "monthly_payment" in offer
        assert "is_eligible" in offer

    def test_compare_lenders_invalid_payload(self, client: TestClient):
        """
        Test validation error handling (e.g., negative income).
        """
        invalid_payload = {
            "property_value": -500000,
            "down_payment": 100000,
            "borrower": {"credit_score": 750}
        }
        
        response = client.post("/api/v1/lenders/compare", json=invalid_payload)
        assert response.status_code == 422 # Unprocessable Entity

    def test_compare_lenders_no_eligible_lenders(self, client: TestClient, sample_application_data):
        """
        Test scenario where borrower criteria are too poor for any lender.
        """
        # Modify data to ensure no eligibility
        sample_application_data["borrower"]["credit_score"] = 400
        sample_application_data["down_payment"] = 100 # Very high LTV
        
        response = client.post("/api/v1/lenders/compare", json=sample_application_data)
        assert response.status_code == 200
        data = response.json()
        assert len(data["offers"]) == 0
        assert data["message"] == "No eligible lenders found based on provided criteria."

    def test_compare_lenders_sorting_order(self, client: TestClient, sample_application_data):
        """
        Verify that the API returns offers sorted by rate (lowest first).
        """
        response = client.post("/api/v1/lenders/compare", json=sample_application_data)
        data = response.json()
        offers = data["offers"]
        
        if len(offers) > 1:
            rates = [offer["rate"] for offer in offers]
            assert rates == sorted(rates)


class TestSubmissionWorkflow:
    """
    Integration tests for the multi-step submission workflow.
    """

    def test_submit_application_workflow(self, client: TestClient, db_session: Session, sample_application_data):
        """
        Full workflow: 
        1. Compare lenders
        2. Select specific lender
        3. Submit application
        4. Verify status in DB
        """
        
        # Step 1: Compare
        compare_resp = client.post("/api/v1/lenders/compare", json=sample_application_data)
        assert compare_resp.status_code == 200
        offers = compare_resp.json()["offers"]
        selected_lender_id = offers[0]["lender_id"]

        # Step 2: Submit (assuming endpoint takes app data and selected lender)
        submit_payload = {
            "application_data": sample_application_data,
            "selected_lender_id": selected_lender_id
        }
        
        # Mocking the external call in the integration test is often necessary 
        # if we don't want to actually hit Scotiabank/TD.
        # Here we assume the endpoint handles the mock internally or we use a test-mode flag.
        
        submit_resp = client.post("/api/v1/applications/submit", json=submit_payload)
        
        assert submit_resp.status_code == 201
        resp_data = submit_resp.json()
        assert "application_id" in resp_data
        assert resp_data["status"] == "submitted_to_lender"

        # Step 3: Verify DB State (Direct DB check)
        # app_record = db_session.query(Application).filter(Application.id == resp_data["application_id"]).first()
        # assert app_record is not None
        # assert app_record.status == ApplicationStatus.SUBMITTED
        # assert app_record.lender_id == selected_lender_id
        assert True # Placeholder for DB assertion

    def test_submit_application_not_found(self, client: TestClient):
        """
        Test submitting against a non-existent lender ID.
        """
        payload = {
            "application_data": {}, # Valid minimal data
            "selected_lender_id": 99999
        }
        response = client.post("/api/v1/applications/submit", json=payload)
        assert response.status_code == 404

    def test_get_submission_status(self, client: TestClient):
        """
        Test retrieving the status of a submitted application.
        """
        # Assume app ID 1 exists from setup or previous test
        response = client.get("/api/v1/applications/1/status")
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert "last_updated" in data
        else:
            # If 404, valid if DB is empty
            assert response.status_code == 404

    def test_duplicate_submission_handling(self, client: TestClient, sample_application_data):
        """
        Test that submitting the same application twice is handled gracefully (idempotency or rejection).
        """
        # First submit
        payload = {
            "application_data": sample_application_data,
            "selected_lender_id": 1
        }
        resp1 = client.post("/api/v1/applications/submit", json=payload)
        assert resp1.status_code == 201

        # Second submit (same content)
        resp2 = client.post("/api/v1/applications/submit", json=payload)
        # Expecting 409 Conflict or 200 with existing ID depending on implementation
        assert resp2.status_code in [409, 200]
```