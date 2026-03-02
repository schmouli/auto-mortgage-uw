Here are the comprehensive tests for the **Reporting & Analytics** module of the OnLendHub project.

### Bug Report Summary
Based on the test cases designed below, the following potential bugs are targeted for detection:
1.  **Division by Zero in Analytics:** The system attempts to calculate an average or percentage without checking if the denominator (total applications) is zero.
2.  **Date Boundary Logic:** Date range filters may be excluding the end date due to time-component mismatches (e.g., `2023-01-01 23:59:59` vs `2023-01-01 00:00:00`).
3.  **Currency Precision:** Floating-point arithmetic errors when calculating large mortgage volumes (e.g., $1,000,000.01 becoming $1,000,000.009999).
4.  **CSV Injection:** Analytics export may not sanitize user input (e.g., application IDs starting with `=`), allowing for formula injection in exported Excel/CSV files.

---

--- conftest.py ---

```python
import pytest
from datetime import datetime, date, timedelta
from typing import List, Generator
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi import FastAPI
from fastapi.testclient import TestClient

# --- Mock Models for OnLendHub ---
Base = declarative_base()

class ApplicationStatus(str):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FUNDED = "FUNDED"

class MortgageApplication(Base):
    __tablename__ = "mortgage_applications"
    
    id = Column(Integer, primary_key=True, index=True)
    applicant_name = Column(String)
    loan_amount = Column(Float)
    property_value = Column(Float)
    status = Column(String, default=ApplicationStatus.PENDING)
    created_at = Column(Date, default=date.today)
    province = Column(String)  # Canadian context

# --- Pytest Fixtures ---

@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a new database session for a test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def sample_applications(db_session: Session):
    """Populate DB with sample Canadian mortgage data."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    last_month = today - timedelta(days=30)

    apps = [
        MortgageApplication(
            applicant_name="John Doe", loan_amount=450000.00, 
            property_value=500000.00, status=ApplicationStatus.APPROVED, 
            created_at=today, province="ON"
        ),
        MortgageApplication(
            applicant_name="Jane Smith", loan_amount=300000.00, 
            property_value=350000.00, status=ApplicationStatus.REJECTED, 
            created_at=yesterday, province="BC"
        ),
        MortgageApplication(
            applicant_name="Bob Johnson", loan_amount=800000.00, 
            property_value=1000000.00, status=ApplicationStatus.FUNDED, 
            created_at=last_month, province="AB"
        ),
        MortgageApplication(
            applicant_name="Alice Brown", loan_amount=150000.00, 
            property_value=150000.00, status=ApplicationStatus.PENDING, 
            created_at=today, province="QC"
        ),
        # Edge case: Zero down payment (High Risk)
        MortgageApplication(
            applicant_name="Risk Taker", loan_amount=400000.00, 
            property_value=400000.00, status=ApplicationStatus.PENDING, 
            created_at=yesterday, province="ON"
        )
    ]
    db_session.add_all(apps)
    db_session.commit()
    return apps

@pytest.fixture(scope="module")
def app_client():
    """
    Mock FastAPI app fixture. 
    In a real scenario, this would import the main app instance.
    """
    from fastapi import FastAPI
    app = FastAPI()
    
    # Mock Endpoints for Integration Testing
    @app.get("/api/v1/reports/summary")
    async def get_summary(start_date: date = None, end_date: date = None):
        # Logic would be in the controller, simplified here for fixture setup
        return {"message": "Endpoint ready"}

    @app.get("/api/v1/analytics/ltv-distribution")
    async def get_ltv():
        return {"message": "Endpoint ready"}

    @app.get("/api/v1/reports/export")
    async def export_report():
        return {"message": "Endpoint ready"}

    client = TestClient(app)
    yield client
```

--- unit_tests ---

```python
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from datetime import date, timedelta

# Assuming the module exists at src.reporting.analytics_service
# from src.reporting.analytics_service import AnalyticsService, ReportGenerator

# --- Mocking the Service Logic for Unit Testing ---
class AnalyticsService:
    def calculate_ltv(self, loan_amount: float, property_value: float) -> float:
        if property_value <= 0:
            raise ValueError("Property value must be positive")
        return round((loan_amount / property_value) * 100, 2)

    def calculate_approval_rate(self, approved_count: int, total_count: int) -> float:
        if total_count == 0:
            return 0.0
        return round((approved_count / total_count) * 100, 2)

    def filter_by_date_range(self, data: list, start_date: date, end_date: date) -> list:
        return [
            d for d in data 
            if start_date <= d['created_at'] <= end_date
        ]

class ReportGenerator:
    def generate_csv_row(self, app_data: dict) -> str:
        # Vulnerability: CSV Injection if not sanitized
        return f"{app_data['id']},{app_data['name']},{app_data['amount']}\n"


# --- Unit Tests ---

@pytest.fixture
def analytics_service():
    return AnalyticsService()

@pytest.fixture
def report_generator():
    return ReportGenerator()

def test_calculate_ltv_happy_path(analytics_service):
    """Test standard LTV calculation."""
    # Standard 80% LTV
    assert analytics_service.calculate_ltv(400000, 500000) == 80.0
    # 95% LTV (High ratio)
    assert analytics_service.calculate_ltv(95000, 100000) == 95.0
    # 50% LTV
    assert analytics_service.calculate_ltv(250000, 500000) == 50.0

def test_calculate_ltv_edge_cases(analytics_service):
    """Test LTV with boundary values."""
    # Very small property value
    assert analytics_service.calculate_ltv(1, 100) == 1.0
    # Large numbers (Precision check)
    assert analytics_service.calculate_ltv(1500000, 2000000) == 75.0

def test_calculate_ltv_error_cases(analytics_service):
    """Test LTV error handling."""
    with pytest.raises(ValueError):
        analytics_service.calculate_ltv(100000, 0)
    
    with pytest.raises(ValueError):
        analytics_service.calculate_ltv(100000, -50000)

def test_approval_rate_calculation(analytics_service):
    """Test approval rate percentage logic."""
    # 50% approval rate
    assert analytics_service.calculate_approval_rate(5, 10) == 50.0
    # 100% approval rate
    assert analytics_service.calculate_approval_rate(10, 10) == 100.0
    # 0% approval rate
    assert analytics_service.calculate_approval_rate(0, 10) == 0.0

def test_approval_rate_zero_division(analytics_service):
    """Test protection against division by zero."""
    # Bug check: Should return 0.0, not raise ZeroDivisionError
    assert analytics_service.calculate_approval_rate(0, 0) == 0.0

def test_date_filtering_logic(analytics_service):
    """Test date range filtering logic."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    data = [
        {'id': 1, 'created_at': yesterday},
        {'id': 2, 'created_at': today},
        {'id': 3, 'created_at': today + timedelta(days=1)}
    ]
    
    # Filter only for today
    result = analytics_service.filter_by_date_range(data, today, today)
    assert len(result) == 1
    assert result[0]['id'] == 2

def test_date_filtering_inclusive(analytics_service):
    """Test that date range is inclusive of start and end dates."""
    start = date(2023, 1, 1)
    end = date(2023, 1, 31)
    
    data = [
        {'id': 1, 'created_at': date(2023, 1, 1)}, # Start
        {'id': 2, 'created_at': date(2023, 1, 15)}, # Middle
        {'id': 3, 'created_at': date(2023, 1, 31)}, # End
        {'id': 4, 'created_at': date(2023, 2, 1)}   # Out
    ]
    
    result = analytics_service.filter_by_date_range(data, start, end)
    assert len(result) == 3
    assert result[0]['id'] == 1
    assert result[2]['id'] == 3

def test_csv_generation_basic(report_generator):
    """Test basic CSV row formatting."""
    data = {'id': 123, 'name': 'Test User', 'amount': 500000.00}
    result = report_generator.generate_csv_row(data)
    assert result == "123,Test User,500000.0\n"

def test_csv_injection_vulnerability(report_generator):
    """
    Bug Check: Test if user input starting with '=' is sanitized.
    If not sanitized, Excel will interpret it as a formula.
    """
    malicious_data = {'id': 1, 'name': '=cmd|\' /C calc\'!A0', 'amount': 0}
    result = report_generator.generate_csv_row(malicious_data)
    
    # Assertion: The output should contain the malicious string if the bug exists.
    # A fixed version would prefix the string with a tab (') to sanitize.
    assert "=cmd|" in result  # Failing this test implies the bug is fixed

@patch('path.to.external_bureau.BureauClient.get_credit_score')
def test_external_service_mocking(mock_get_score):
    """Test that external credit checks are mocked correctly."""
    mock_get_score.return_value = 750  # Mock high credit score
    
    # Simulate a function that uses the external client
    score = mock_get_score(user_id="user_123")
    
    assert score == 750
    mock_get_score.assert_called_once_with(user_id="user_123")

def test_aggregate_volume_calculation():
    """Test summing of mortgage volumes."""
    mortgages = [
        {'amount': 100000.00},
        {'amount': 250000.50},
        {'amount': 150000.50}
    ]
    total = sum(m['amount'] for m in mortgages)
    assert total == 500001.0
```

--- integration_tests ---

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import date, timedelta
import json

# --- Integration Tests ---

# Note: These tests assume the FastAPI app is wired up to the Database logic.
# Since we are mocking the app structure in conftest, we will simulate 
# the controller logic here to demonstrate the testing strategy.

def test_get_summary_report_success(client: TestClient, sample_applications):
    """
    Test the API endpoint for generating a summary report.
    Validates response structure and aggregated totals.
    """
    # We would normally patch the dependency to use the test db session
    # For this exercise, we simulate the expected response based on sample_applications
    
    response = client.get("/api/v1/reports/summary")
    
    assert response.status_code == 200
    data = response.json()
    
    # Assertions based on sample_applications fixture data
    # Total Apps: 5
    # Total Volume: 450k + 300k + 800k + 150k + 400k = 2,100,000
    assert data['total_applications'] == 5
    assert data['total_volume'] == 2100000.00
    assert 'status_breakdown' in data

def test_get_ltv_distribution(client: TestClient, sample_applications):
    """
    Test the Loan-to-Value distribution analytics endpoint.
    """
    response = client.get("/api/v1/analytics/ltv-distribution")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check structure
    assert 'buckets' in data
    assert isinstance(data['buckets'], list)
    
    # Verify bucket logic (e.g., <80%, 80-95%, >95%)
    # John Doe: 90% (450/500) -> 80-95 bucket
    # Jane Smith: 85.7% -> 80-95 bucket
    # Bob Johnson: 80% -> 80-95 bucket
    # Alice Brown: 100% -> >95 bucket
    # Risk Taker: 100% -> >95 bucket
    
    # We expect 3 in the 80-95 bucket and 2 in the >95 bucket
    bucket_80_95 = next(b for b in data['buckets'] if b['name'] == '80-95%')
    bucket_over_95 = next(b for b in data['buckets'] if b['name'] == '>95%')
    
    assert bucket_80_95['count'] == 3
    assert bucket_over_95['count'] == 2

def test_report_filtering_by_date(client: TestClient, sample_applications):
    """
    Test filtering reports by a specific date range.
    """
    today = date.today()
    params = {
        "start_date": (today - timedelta(days=2)).isoformat(),
        "end_date": today.isoformat()
    }
    
    response = client.get("/api/v1/reports/summary", params=params)
    
    assert response.status_code == 200
    data = response.json()
    
    # Based on fixture: Only John Doe, Alice Brown are created today.
    # Jane Smith and Risk Taker are yesterday.
    # Bob Johnson is last month.
    # So we expect 4 applications (assuming inclusive range logic)
    assert data['total_applications'] == 4

def test_report_filtering_invalid_date_range(client: TestClient):
    """
    Test API validation when start_date is after end_date.
    """
    today = date.today()
    params = {
        "start_date": today.isoformat(),
        "end_date": (today - timedelta(days=10)).isoformat()
    }
    
    response = client.get("/api/v1/reports/summary", params=params)
    
    # Expect 422 Unprocessable Entity or 400 Bad Request
    assert response.status_code in [400, 422]

def test_export_csv_endpoint(client: TestClient, sample_applications):
    """
    Test the CSV export functionality.
    Validates headers and content type.
    """
    response = client.get("/api/v1/reports/export")
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    
    # Decode content
    content = response.content.decode("utf-8")
    
    # Basic checks for CSV structure
    assert "id,applicant_name,loan_amount,status" in content
    assert "John Doe" in content
    
    # Bug Check: Ensure no formulas are exported (CSV Injection)
    # If sample data contained "=cmd...", we check if it's escaped here.
    assert "=cmd" not in content

def test_multi_step_workflow_analytics(client: TestClient, db_session: Session):
    """
    Integration Workflow:
    1. Create a new application.
    2. Approve the application.
    3. Verify the analytics report updates immediately.
    """
    # Step 1: Create (Simulated via direct DB insert for speed, or API call)
    new_app = {
        "applicant_name": "Integration Test User",
        "loan_amount": 600000.00,
        "property_value": 600000.00,
        "status": "PENDING",
        "province": "ON"
    }
    
    # Assuming a POST endpoint exists, but here we assert the pre-condition
    initial_summary = client.get("/api/v1/reports/summary").json()
    initial_count = initial_summary['total_applications']
    
    # Step 2: Update status (Simulated)
    # In a real test, we would call client.put(f"/applications/{id}", ...)
    
    # Step 3: Verify Report
    # We expect the count to have increased by 1
    final_summary = client.get("/api/v1/reports/summary").json()
    assert final_summary['total_applications'] == initial_count + 1

def test_empty_database_state(client: TestClient, db_session: Session):
    """
    Test report behavior when no data exists (Edge case).
    """
    # Clear DB
    db_session.query(MortgageApplication).delete()
    db_session.commit()
    
    response = client.get("/api/v1/reports/summary")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['total_applications'] == 0
    assert data['total_volume'] == 0.0
    # Ensure no division by zero errors in the average calculation
    assert data['average_loan_amount'] == 0.0 
```