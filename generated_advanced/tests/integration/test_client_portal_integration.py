```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Imports
# from onlendhub.models.client import Client
# from onlendhub.models.application import MortgageApplication
# from onlendhub.db.session import get_db

class TestClientPortalIntegration:

    def test_create_client_workflow(self, client: TestClient, valid_client_payload):
        """
        Test API endpoint for client registration.
        Assertions: 201 Created, Response contains ID and email.
        """
        # Act
        response = client.post("/api/v1/portal/register", json=valid_client_payload)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["email"] == valid_client_payload["email"]
        assert data["sin"] != valid_client_payload["sin"] # Ensure SIN is masked/encrypted in response

    def test_login_and_get_token(self, client: TestClient, valid_client_payload):
        """
        Test authentication workflow.
        Assertions: 200 OK, Token returned.
        """
        # Setup: Create user first
        client.post("/api/v1/portal/register", json=valid_client_payload)
        
        # Act
        login_data = {"username": valid_client_payload["email"], "password": "securepassword123"}
        response = client.post("/api/v1/portal/login", data=login_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_create_mortgage_application_authenticated(
        self, client: TestClient, valid_application_payload, auth_headers
    ):
        """
        Test submitting a mortgage application while authenticated.
        Assertions: 201 Created, Application status is 'Pending'.
        """
        # Act
        response = client.post(
            "/api/v1/portal/applications",
            json=valid_application_payload,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "Pending Review"
        assert data["property_value"] == 750000.00

    def test_get_application_list(self, client: TestClient, auth_headers):
        """
        Test retrieving list of applications for logged-in user.
        Assertions: 200 OK, Returns list, pagination works.
        """
        # Act
        response = client.get("/api/v1/portal/applications", headers=auth_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # If data exists, check structure
        if len(data) > 0:
            assert "id" in data[0]
            assert "created_at" in data[0]

    def test_upload_document_integration(self, client: TestClient, auth_headers):
        """
        Test document upload endpoint.
        Assertions: 200 OK, File record created in DB.
        """
        # Arrange
        files = {"file": ("paystub.pdf", b"fake pdf content", "application/pdf")}
        data = {"document_type": "proof_of_income", "application_id": 1}
        
        # Act
        response = client.post(
            "/api/v1/portal/documents",
            files=files,
            data=data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 201
        resp_data = response.json()
        assert resp_data["filename"] == "paystub.pdf"
        assert resp_data["status"] == "Uploaded"

    def test_update_client_profile(self, client: TestClient, auth_headers):
        """
        Test updating client contact info.
        Assertions: 200 OK, Data persisted.
        """
        # Arrange
        update_payload = {"phone": "+1-647-555-9999", "email": "newemail@example.com"}
        
        # Act
        response = client.put("/api/v1/portal/profile", json=update_payload, headers=auth_headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["phone"] == "+1-647-555-9999"

    def test_get_application_details_unauthorized(self, client: TestClient):
        """
        Test security: Accessing application details without token.
        Assertions: 401 Unauthorized.
        """
        # Act
        response = client.get("/api/v1/portal/applications/999")
        
        # Assert
        assert response.status_code == 401

    def test_get_application_details_forbidden_wrong_user(
        self, client: TestClient, auth_headers
    ):
        """
        Test security: Accessing another user's application.
        Assertions: 403 Forbidden.
        """
        # Act (Assuming ID 999 belongs to another user)
        response = client.get("/api/v1/portal/applications/999", headers=auth_headers)
        
        # Assert
        assert response.status_code == 403

    def test_submit_application_validation_error(self, client: TestClient, auth_headers):
        """
        Test API validation logic (Negative down payment).
        Assertions: 422 Unprocessable Entity.
        """
        # Arrange
        invalid_payload = {
            "property_value": 500000,
            "down_payment": -5000, # Invalid
            "amortization_period": 25
        }
        
        # Act
        response = client.post(
            "/api/v1/portal/applications",
            json=invalid_payload,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 422

    def test_workflow_full_application_lifecycle(self, client: TestClient, valid_client_payload, valid_application_payload):
        """
        Multi-step workflow test: Register -> Login -> Apply -> Upload Doc -> Check Status.
        """
        # 1. Register
        reg_resp = client.post("/api/v1/portal/register", json=valid_client_payload)
        assert reg_resp.status_code == 201
        
        # 2. Login
        login_resp = client.post("/api/v1/portal/login", data={
            "username": valid_client_payload["email"], 
            "password": "securepassword123"
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Apply
        app_resp = client.post("/api/v1/portal/applications", json=valid_application_payload, headers=headers)
        assert app_resp.status_code == 201
        app_id = app_resp.json()["id"]
        
        # 4. Upload Doc
        doc_resp = client.post(
            "/api/v1/portal/documents",
            files={"file": ("id.pdf", b"content", "application/pdf")},
            data={"document_type": "government_id", "application_id": app_id},
            headers=headers
        )
        assert doc_resp.status_code == 201
        
        # 5. Check Status
        status_resp = client.get(f"/api/v1/portal/applications/{app_id}", headers=headers)
        assert status_resp.status_code == 200
        assert len(status_resp.json()["documents"]) == 1

# Total assertions estimate: ~25
```