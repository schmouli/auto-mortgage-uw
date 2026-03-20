import pytest
from decimal import Decimal
from sqlalchemy import select

# Imports from the module under test
from mortgage_underwriting.modules.application.models import MortgageApplication
from mortgage_underwriting.modules.applicant.models import Applicant
from mortgage_underwriting.modules.property.models import Property

@pytest.mark.integration
class TestFrontendUIRoutes:

    def test_get_dashboard_endpoint(self, client: TestClient, populated_db):
        """
        Test the /dashboard endpoint returns aggregated stats.
        Verifies correct JSON structure and Decimal serialization.
        """
        response = client.get("/api/v1/frontend/dashboard")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_applications" in data
        assert "total_volume" in data
        assert "approved_count" in data
        
        # Verify data matches populated_db fixture
        assert data["total_applications"] == 1
        # JSON serialization turns Decimal into string or float depending on config.
        # Pydantic v2 defaults to float for numbers, but our project says Decimal for money.
        # FastAPI response serialization usually handles this. 
        # We check string representation to be safe against float precision issues.
        assert data["total_volume"] == "400000.00" or data["total_volume"] == 400000.00

    def test_get_application_list_endpoint(self, client: TestClient, populated_db):
        """
        Test fetching list of applications for the UI table.
        Ensures PII (SIN) is not exposed.
        """
        response = client.get("/api/v1/frontend/applications")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 1
        
        app_data = data[0]
        assert app_data["id"] == 101
        assert app_data["applicant_name"] == "John Doe" # Assuming formatted name
        assert "sin" not in app_data  # PIPEDA Check
        assert "sin_hash" not in app_data
        assert "date_of_birth" not in app_data

    def test_get_application_detail_endpoint_success(self, client: TestClient, populated_db):
        """
        Test retrieving details for a specific application.
        """
        response = client.get("/api/v1/frontend/applications/101")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == 101
        assert data["loan_amount"] == "400000.00" or data["loan_amount"] == 400000.00
        assert data["status"] == "pending_review"
        # Check nested property data
        assert "property" in data
        assert data["property"]["city"] == "Toronto"

    def test_get_application_detail_endpoint_not_found(self, client: TestClient, populated_db):
        """
        Test 404 handling for non-existent application.
        """
        response = client.get("/api/v1/frontend/applications/99999")
        
        assert response.status_code == 404
        error_data = response.json()
        assert "detail" in error_data
        assert "error_code" in error_data

    def test_create_application_frontend_submission(self, client: TestClient, db_session):
        """
        Test the submission endpoint used by the React form.
        Validates input validation and database creation.
        """
        payload = {
            "applicant": {
                "first_name": "Alice",
                "last_name": "Wonderland",
                "email": "alice@example.com",
                "annual_income": "85000.00",
                "credit_score": 720
            },
            "property": {
                "address": "456 Wonderland Ave",
                "city": "Vancouver",
                "province": "BC",
                "postal_code": "V6E1M5",
                "property_value": "750000.00"
            },
            "mortgage": {
                "loan_amount": "600000.00",
                "down_payment": "150000.00",
                "amortization_years": 30
            }
        }
        
        response = client.post("/api/v1/frontend/submit-application", json=payload)
        
        # Assuming backend processes this synchronously or returns 202 Accepted
        # For this test, let's assume 201 Created
        assert response.status_code in [201, 202]
        
        if response.status_code == 201:
            data = response.json()
            assert "application_id" in data
            
            # Verify DB state
            stmt = select(MortgageApplication).where(MortgageApplication.id == data["application_id"])
            result = db_session.execute(stmt).scalar_one_or_none()
            assert result is not None
            assert result.loan_amount == Decimal("600000.00")

    def test_submit_application_validation_error(self, client: TestClient):
        """
        Test that invalid financial data (e.g., negative income) is rejected.
        """
        invalid_payload = {
            "applicant": {
                "first_name": "Bad",
                "last_name": "Data",
                "email": "bad@test.com",
                "annual_income": "-5000.00", # Invalid
                "credit_score": 300
            },
            "property": {
                "address": "123 St",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M5V1A1",
                "property_value": "1000.00"
            },
            "mortgage": {
                "loan_amount": "2000.00",
                "down_payment": "0.00",
                "amortization_years": 5
            }
        }
        
        response = client.post("/api/v1/frontend/submit-application", json=invalid_payload)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_frontend_health_check(self, client: TestClient):
        """
        Test a simple health check endpoint for the frontend to verify connectivity.
        """
        response = client.get("/api/v1/frontend/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}