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