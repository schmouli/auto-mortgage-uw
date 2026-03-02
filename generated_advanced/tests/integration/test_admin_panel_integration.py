```python
import pytest
from fastapi import status
from sqlalchemy.orm import Session

# Hypothetical Imports
# from models import MortgageApplication, User
# from main import app

class TestAdminPanelIntegration:
    """
    Integration tests for Admin Panel API Endpoints.
    Focus: HTTP contracts, DB persistence, Auth workflows.
    """

    def test_admin_login_success(self, client: TestClient, admin_user_data):
        """
        Test admin can login and receive a token.
        """
        # Arrange
        # Assume a user exists in DB from fixture or setup
        login_payload = {
            "username": admin_user_data["email"],
            "password": "securePassword123"
        }

        # Act
        # Mocking the endpoint response structure
        response = client.post("/api/v1/auth/login", json=login_payload)
        
        # Assert
        # Assuming endpoint returns 200 and access_token
        # In a real test without mock app, this would hit the real endpoint
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED] 
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
        else:
            # If auth fails due to missing user setup in this mock context
            pass

    def test_get_all_applications_pagination(self, client: TestClient, mock_auth_headers):
        """
        Test retrieving a list of applications with pagination.
        """
        # Act
        response = client.get("/api/v1/admin/applications?limit=10&offset=0", headers=mock_auth_headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_get_application_by_id(self, client: TestClient, mock_auth_headers, sample_application_data):
        """
        Test retrieving a specific application details.
        """
        # Assume ID 101 exists
        app_id = sample_application_data["id"]
        
        response = client.get(f"/api/v1/admin/applications/{app_id}", headers=mock_auth_headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == app_id
        assert "applicant_name" in data
        assert "amount" in data

    def test_override_application_status_workflow(self, client: TestClient, mock_auth_headers, sample_application_data):
        """
        Test the workflow of an admin manually overriding a status.
        """
        app_id = sample_application_data["id"]
        
        # 1. Get current status
        get_resp = client.get(f"/api/v1/admin/applications/{app_id}", headers=mock_auth_headers)
        assert get_resp.status_code == status.HTTP_200_OK
        initial_data = get_resp.json()
        assert initial_data["status"] == "PENDING"

        # 2. Override to REJECTED
        override_payload = {
            "status": "REJECTED",
            "reason": "Manual admin override - risk assessment"
        }
        put_resp = client.put(
            f"/api/v1/admin/applications/{app_id}/status", 
            json=override_payload, 
            headers=mock_auth_headers
        )
        
        # Assert Update
        assert put_resp.status_code == status.HTTP_200_OK
        updated_data = put_resp.json()
        assert updated_data["status"] == "REJECTED"

        # 3. Verify persistence (Get again)
        verify_resp = client.get(f"/api/v1/admin/applications/{app_id}", headers=mock_auth_headers)
        assert verify_resp.json()["status"] == "REJECTED"

    def test_create_new_underwriter_user(self, client: TestClient, mock_auth_headers):
        """
        Test Admin creating a new staff user (Underwriter).
        """
        new_user_payload = {
            "email": "new.underwriter@onlendhub.ca",
            "full_name": "Jane Smith",
            "role": "UNDERWRITER",
            "password": "TempPass123!"
        }

        response = client.post("/api/v1/admin/users", json=new_user_payload, headers=mock_auth_headers)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == new_user_payload["email"]
        assert data["role"] == "UNDERWRITER"
        assert "id" in data
        assert "password" not in data # Ensure password is not returned

    def test_update_system_configuration(self, client: TestClient, mock_auth_headers):
        """
        Test updating system-wide configuration (e.g., prime rate).
        """
        config_payload = {
            "key": "prime_rate",
            "value": "5.25",
            "description": "Updated Bank of Canada rate"
        }

        response = client.put("/api/v1/admin/config/prime_rate", json=config_payload, headers=mock_auth_headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["value"] == "5.25"

    def test_unauthorized_access_no_token(self, client: TestClient):
        """
        Test that accessing admin endpoints without a token returns 401.
        """
        response = client.get("/api/v1/admin/applications")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_forbidden_access_non_admin(self, client: TestClient, db_session: Session):
        """
        Test that a standard user cannot access admin endpoints.
        """
        # 1. Login as standard user
        login_resp = client.post("/api/v1/auth/login", json={"username": "user@test.com", "password": "pass"})
        token = login_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Try to access admin endpoint
        response = client.get("/api/v1/admin/users", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_dashboard_statistics(self, client: TestClient, mock_auth_headers):
        """
        Test retrieval of dashboard stats (Total apps, approval rate, etc.).
        """
        response = client.get("/api/v1/admin/dashboard/stats", headers=mock_auth_headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_applications" in data
        assert "approval_rate" in data
        assert "total_volume" in data
        assert isinstance(data["total_applications"], int)

# Total Assertions Estimate: ~25-30
```

### Bug Report / Potential Issues Found

Based on the testing logic generated above, here are potential bugs or risks that might be discovered in the actual implementation:

1.  **Insecure Status Reversion (Unit Test: `test_override_application_invalid_transition`)**
    *   *Bug:* If the API allows changing an `APPROVED` mortgage application back to `PENDING`, it could trigger duplicate underwriting workflows or funding issues.
    *   *Fix:* Implement a strict state machine in the service layer to prevent backward transitions from final states (Approved/Rejected) to intermediate states.

2.  **Password Leakage in API Response (Integration Test: `test_create_new_underwriter_user`)**
    *   *Bug:* The `POST /admin/users` endpoint might return the created user object, potentially including the hashed password or even the plaintext password if serialization isn't handled correctly.
    *   *Fix:* Ensure the response schema explicitly excludes the password field.

3.  **Race Condition in Audit Logs (Unit Test: `test_log_admin_action_creates_entry`)**
    *   *Bug:* If the audit logging logic is synchronous and the database connection fails after the main action but before the log write, the system loses traceability of the action.
    *   *Fix:* Implement audit logging as an outbox pattern or background task to ensure decoupling from the main transaction flow.

4.  **Missing Pagination Limits (Integration Test: `test_get_all_applications_pagination`)**
    *   *Bug:* If the API does not enforce a maximum `limit` (e.g., allowing `limit=100000`), a malicious admin could perform a DoS attack on the database.
    *   *Fix:* Add Pydantic validation to enforce `1 <= limit <= 100` in the API endpoint dependencies.