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