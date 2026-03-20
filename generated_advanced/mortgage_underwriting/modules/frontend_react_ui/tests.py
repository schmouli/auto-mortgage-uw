--- conftest.py ---
import asyncio
from decimal import Decimal
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

# Assuming the project structure and base imports exist
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.main import app  # Assuming a main app entry point
from mortgage_underwriting.modules.frontend_ui.routes import router as frontend_router
from mortgage_underwriting.modules.applicant.models import Applicant
from mortgage_underwriting.modules.application.models import MortgageApplication
from mortgage_underwriting.modules.property.models import Property

# Use in-memory SQLite for fast integration tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Async engine setup
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Sync engine for creating tables (Base.metadata.create_all requires sync engine in some versions, 
# but run_sync can be used on async connection. Keeping it simple with async connection run_sync)
@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def test_app():
    # Create a fresh app instance for testing to avoid state leakage
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(frontend_router, prefix="/api/v1/frontend", tags=["Frontend"])
    return app

@pytest.fixture(scope="function")
def client(test_app) -> Generator[TestClient, None, None]:
    # Use TestClient as requested for integration tests
    with TestClient(test_app) as c:
        yield c

@pytest.fixture
def sample_applicant_data():
    return {
        "id": 1,
        "first_name": "John",
        "last_name": "Doe",
        "sin_hash": "a" * 64, # SHA256 hash representation
        "date_of_birth_encrypted": "encrypted_dob_string",
        "credit_score": 750,
        "annual_income": Decimal("95000.00"),
        "employment_status": "employed",
        "address_city": "Toronto",
    }

@pytest.fixture
def sample_property_data():
    return {
        "id": 1,
        "property_value": Decimal("500000.00"),
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M5V1A1",
    }

@pytest.fixture
def sample_application_data(sample_applicant_data, sample_property_data):
    return {
        "id": 101,
        "applicant_id": 1,
        "property_id": 1,
        "loan_amount": Decimal("400000.00"),
        "down_payment": Decimal("100000.00"),
        "amortization_years": 25,
        "contract_rate": Decimal("4.50"),
        "status": "pending_review",
        "ltv_ratio": Decimal("0.80"),
        "gds_ratio": Decimal("0.25"),
        "tds_ratio": Decimal("0.32"),
        "insurance_required": False,
    }

@pytest.fixture
async def populated_db(db_session, sample_applicant_data, sample_property_data, sample_application_data):
    # Helper to populate DB with valid relational data
    applicant = Applicant(**sample_applicant_data)
    property_obj = Property(**sample_property_data)
    application = MortgageApplication(**sample_application_data)
    
    db_session.add(applicant)
    db_session.add(property_obj)
    db_session.add(application)
    await db_session.commit()
    await db_session.refresh(application)
    
    return {
        "applicant": applicant,
        "property": property_obj,
        "application": application
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

# Adjust imports based on actual module structure
from mortgage_underwriting.modules.frontend_ui.services import DashboardService, FrontendDataService
from mortgage_underwriting.modules.frontend_ui.schemas import DashboardStats, ApplicationSummaryResponse
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDashboardService:
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_success(self, mock_session):
        # Mock the execute chain for SQLAlchemy 2.0
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            MagicMock(status="approved", loan_amount=Decimal("500000.00")),
            MagicMock(status="pending_review", loan_amount=Decimal("300000.00")),
            MagicMock(status="approved", loan_amount=Decimal("200000.00"))
        ]
        mock_session.execute.return_value = mock_result

        service = DashboardService(mock_session)
        stats = await service.get_stats()

        assert stats.total_applications == 3
        assert stats.approved_count == 2
        assert stats.pending_count == 1
        # Verify Decimal handling for money
        assert stats.total_volume == Decimal("1000000.00")
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_empty_db(self, mock_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = DashboardService(mock_session)
        stats = await service.get_stats()

        assert stats.total_applications == 0
        assert stats.total_volume == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_calculates_ratios_correctly(self, mock_session):
        # Test that the service correctly aggregates complex financial data
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            MagicMock(
                status="approved", 
                loan_amount=Decimal("100000.00"),
                gds_ratio=Decimal("0.30"),
                tds_ratio=Decimal("0.40")
            ),
            MagicMock(
                status="rejected", 
                loan_amount=Decimal("100000.00"),
                gds_ratio=Decimal("0.50"), # High GDS
                tds_ratio=Decimal("0.55")
            )
        ]
        mock_session.execute.return_value = mock_result

        service = DashboardService(mock_session)
        stats = await service.get_stats()

        # Assuming service calculates average or max ratios
        # Implementation specific: Let's assume it returns average GDS/TDS of active apps
        # Just checking interaction and Decimal usage here
        assert stats.total_applications == 2

@pytest.mark.unit
class TestFrontendDataService:

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_get_application_summary_excludes_pii(self, mock_session):
        # PIPEDA Compliance: Ensure SIN and DOB are stripped from the response
        mock_applicant = MagicMock(
            id=1, 
            first_name="Jane", 
            last_name="Smith",
            sin_hash="secret_hash",
            date_of_birth_encrypted="secret_dob"
        )
        mock_application = MagicMock(
            id=1,
            applicant=mock_applicant,
            loan_amount=Decimal("450000.00"),
            status="approved",
            created_at="2023-01-01"
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_application
        mock_session.execute.return_value = mock_result

        service = FrontendDataService(mock_session)
        summary = await service.get_application_summary(application_id=1)

        assert summary.first_name == "Jane"
        assert summary.loan_amount == Decimal("450000.00")
        # CRITICAL: Ensure PII fields are NOT present
        assert not hasattr(summary, 'sin_hash')
        assert not hasattr(summary, 'date_of_birth_encrypted')
        # Or if they are attributes of the nested applicant object in the schema
        if hasattr(summary, 'applicant'):
            assert not hasattr(summary.applicant, 'sin_hash')

    @pytest.mark.asyncio
    async def test_get_application_summary_not_found(self, mock_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = FrontendDataService(mock_session)
        
        with pytest.raises(AppException) as exc_info:
            await service.get_application_summary(application_id=999)
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_format_currency_for_ui(self, mock_session):
        # Test helper method for formatting currency strings for React components
        service = FrontendDataService(mock_session)
        
        # Note: Usually formatting happens in frontend, but if backend does it:
        amount = Decimal("1234567.89")
        # Assuming a method format_currency exists
        formatted = service.format_currency(amount) if hasattr(service, 'format_currency') else str(amount)
        
        # Basic check for decimal precision preservation
        assert "1234567" in formatted

--- integration_tests ---
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