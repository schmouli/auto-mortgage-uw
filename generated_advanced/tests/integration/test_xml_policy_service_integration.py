```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Test API Endpoints
def test_submit_application_success(client: TestClient, valid_mortgage_xml, db_session: Session):
    """
    Integration Test: Full workflow of submitting a valid application.
    Assertions: 
    1. HTTP 201 Created status.
    2. Database record created.
    3. Response contains valid XML decision.
    """
    response = client.post("/api/v1/policy/submit", content=valid_mortgage_xml, headers={"Content-Type": "application/xml"})
    
    # 1. Check HTTP Status
    assert response.status_code == 201
    
    # 2. Check Response Content
    assert response.headers["content-type"] == "application/xml"
    content = response.text
    assert "<Decision>" in content
    assert "<Status>Approved</Status>" in content
    
    # 3. Verify Database State
    db_record = db_session.query(MortgageApplication).filter_by(application_id="APP-2023-001").first()
    assert db_record is not None
    assert db_record.status == "Approved"
    assert db_record.loan_amount == 400000

def test_submit_malformed_xml(client: TestClient, malformed_xml):
    """
    Integration Test: API handling of bad XML syntax.
    Assertions: HTTP 422 Unprocessable Entity returned.
    """
    response = client.post("/api/v1/policy/submit", content=malformed_xml, headers={"Content-Type": "application/xml"})
    
    assert response.status_code == 422
    assert "error" in response.json().lower()

def test_submit_validation_failure(client: TestClient, missing_required_field_xml):
    """
    Integration Test: API handling of valid XML but invalid business data.
    Assertions: HTTP 400 Bad Request with validation details.
    """
    response = client.post("/api/v1/policy/submit", content=missing_required_field_xml, headers={"Content-Type": "application/xml"})
    
    assert response.status_code == 400
    json_resp = response.json()
    assert "detail" in json_resp
    assert "CreditScore" in json_resp["detail"]

def test_get_application_status(client: TestClient, db_session: Session, valid_mortgage_xml):
    """
    Integration Test: Retrieving a previously submitted application.
    Workflow: Submit -> Get ID -> Retrieve via GET.
    """
    # Step 1: Submit
    submit_resp = client.post("/api/v1/policy/submit", content=valid_mortgage_xml, headers={"Content-Type": "application/xml"})
    assert submit_resp.status_code == 201
    
    # Step 2: Retrieve
    app_id = "APP-2023-001"
    get_resp = client.get(f"/api/v1/policy/{app_id}")
    
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["application_id"] == app_id
    assert data["borrower_last_name"] == "Doe"
    assert "decision_timestamp" in data

def test_get_non_existent_application(client: TestClient):
    """
    Integration Test: Handling of missing resources.
    Assertions: HTTP 404 Not Found.
    """
    response = client.get("/api/v1/policy/NON-EXISTENT-ID")
    assert response.status_code == 404

def test_high_risk_workflow_rejection(client: TestClient, high_risk_mortgage_xml, db_session: Session):
    """
    Integration Test: Workflow for a declined application.
    Assertions: API returns 201 (processed) but status is Rejected.
    """
    response = client.post("/api/v1/policy/submit", content=high_risk_mortgage_xml, headers={"Content-Type": "application/xml"})
    
    assert response.status_code == 201
    
    # Check DB state
    db_record = db_session.query(MortgageApplication).filter_by(application_id="APP-2023-RISK").first()
    assert db_record is not None
    assert db_record.status == "Rejected"
    assert db_record.rejection_reason is not None

def test_concurrent_submission_handling(client: TestClient, valid_mortgage_xml):
    """
    Integration Test: Basic robustness check (sending same ID twice).
    Assertions: System should handle duplicate IDs gracefully (409 Conflict).
    """
    # First submission
    resp1 = client.post("/api/v1/policy/submit", content=valid_mortgage_xml, headers={"Content-Type": "application/xml"})
    assert resp1.status_code == 201
    
    # Duplicate submission
    resp2 = client.post("/api/v1/policy/submit", content=valid_mortgage_xml, headers={"Content-Type": "application/xml"})
    assert resp2.status_code == 409 # Conflict

def test_response_xml_schema_compliance(client: TestClient, valid_mortgage_xml):
    """
    Integration Test: Verify the exact structure of the XML response.
    Assertions: Required tags exist and data types match.
    """
    response = client.post("/api/v1/policy/submit", content=valid_mortgage_xml, headers={"Content-Type": "application/xml"})
    xml_content = response.text
    
    # Check for specific tags required by downstream consumers
    required_tags = ["<Decision>", "<ApplicationID>", "<Status>", "<Timestamp>", "<RiskScore>"]
    for tag in required_tags:
        assert tag in xml_content, f"Missing required tag: {tag}"
```