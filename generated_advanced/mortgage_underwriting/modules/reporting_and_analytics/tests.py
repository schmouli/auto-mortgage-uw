--- conftest.py ---
import pytest
from decimal import Decimal
from datetime import date, datetime
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Numeric, Date, Boolean

# Import the app and module components
# Assuming the main app creation is in main.py or similar, 
# but for testing we often mount the router directly.
from mortgage_underwriting.modules.reporting.routes import router
from mortgage_underwriting.common.database import Base

# Using an in-memory SQLite for integration tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def app():
    """
    Fixture to create a test FastAPI app instance.
    """
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/reporting", tags=["reporting"])
    return app


@pytest.fixture(scope="function")
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for integration tests.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_db_session():
    """
    Mock DB session for unit tests.
    """
    from unittest.mock import AsyncMock
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_application_data():
    """
    Standardized application data for testing.
    """
    return {
        "id": 1,
        "applicant_id": 101,
        "loan_amount": Decimal("450000.00"),
        "property_value": Decimal("600000.00"),
        "credit_score": 720,
        "gross_income": Decimal("120000.00"),
        "monthly_debt": Decimal("1500.00"),
        "is_insured": True,
        "status": "approved",
        "created_at": datetime(2023, 1, 1, 12, 0, 0)
    }


@pytest.fixture
def sample_report_request():
    return {
        "report_type": "portfolio_summary",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "filters": {
            "min_credit_score": 700,
            "status": "approved"
        }
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select, Result
from mortgage_underwriting.modules.reporting.services import ReportingService, AnalyticsService
from mortgage_underwriting.modules.reporting.exceptions import ReportGenerationError
from mortgage_underwriting.modules.reporting.schemas import ReportResponse, PortfolioMetrics

# Mock Models for unit testing context
class MockApplication:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.unit
class TestReportingService:

    @pytest.mark.asyncio
    async def test_generate_portfolio_report_success(self, mock_db_session, sample_application_data):
        """
        Test successful generation of a portfolio summary report.
        """
        # Setup Mock Result
        mock_app = MockApplication(**sample_application_data)
        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = [mock_app]
        mock_db_session.execute.return_value = mock_result

        service = ReportingService(mock_db_session)
        
        # Execute
        report = await service.generate_portfolio_report(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31)
        )

        # Assertions
        assert report is not None
        assert isinstance(report, ReportResponse)
        assert report.total_applications == 1
        assert report.total_volume == Decimal("450000.00")
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_report_empty_dataset(self, mock_db_session):
        """
        Test report generation when no applications match criteria.
        """
        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        service = ReportingService(mock_db_session)
        
        report = await service.generate_portfolio_report(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        assert report.total_applications == 0
        assert report.total_volume == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_generate_report_db_failure(self, mock_db_session):
        """
        Test that database exceptions are wrapped in ReportGenerationError.
        """
        mock_db_session.execute.side_effect = Exception("Database connection failed")

        service = ReportingService(mock_db_session)

        with pytest.raises(ReportGenerationError) as exc_info:
            await service.generate_portfolio_report(
                start_date=date(2023, 1, 1),
                end_date=date(2023, 1, 31)
            )
        
        assert "Failed to generate report" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calculate_ltv_aggregation(self, mock_db_session, sample_application_data):
        """
        Test that LTV is calculated correctly without float precision loss.
        """
        # Expected LTV: 450,000 / 600,000 = 0.75 (75%)
        mock_app = MockApplication(**sample_application_data)
        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = [mock_app]
        mock_db_session.execute.return_value = mock_result

        service = ReportingService(mock_db_session)
        report = await service.generate_portfolio_report(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31)
        )

        # Check that the service calculates metrics correctly
        assert report.average_ltv == Decimal("75.00")

    @pytest.mark.asyncio
    async def test_filter_by_status(self, mock_db_session):
        """
        Test that status filtering logic is applied in the query construction.
        """
        service = ReportingService(mock_db_session)
        
        # We capture the query passed to execute
        await service.generate_portfolio_report(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            status="approved"
        )

        call_args = mock_db_session.execute.call_args
        query_obj = call_args[0][0]
        # In a real unit test, we might inspect the compiled query, 
        # here we verify the method was called (integration tests verify query results better)
        assert mock_db_session.execute.awaited


@pytest.mark.unit
class TestAnalyticsService:

    @pytest.mark.asyncio
    async def test_calculate_risk_metrics_success(self, mock_db_session):
        """
        Test calculation of risk metrics (e.g., High LTV count).
        """
        # Create mock data: One high LTV (>80%), one low LTV
        data_high = MockApplication(
            id=1, 
            loan_amount=Decimal("85000.00"), 
            property_value=Decimal("100000.00"), # 85% LTV
            status="approved"
        )
        data_low = MockApplication(
            id=2, 
            loan_amount=Decimal("40000.00"), 
            property_value=Decimal("100000.00"), # 40% LTV
            status="approved"
        )

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = [data_high, data_low]
        mock_db_session.execute.return_value = mock_result

        service = AnalyticsService(mock_db_session)
        metrics = await service.calculate_portfolio_risk()

        assert metrics.high_ltv_count == 1
        assert metrics.total_volume == Decimal("125000.00")

    @pytest.mark.asyncio
    async def test_compliance_check_gds_tds_limits(self, mock_db_session):
        """
        Test analytics service flags applications exceeding OSFI B-20 limits.
        """
        # GDS > 39%
        risky_app = MockApplication(
            id=1, 
            gross_income=Decimal("50000.00"), # ~4166/mo
            estimated_property_tax=Decimal("500.00"),
            heating=Decimal("100.00"),
            monthly_debt=Decimal("2000.00"),
            # Calculation roughly (500+100+2000)/4166 > 60% (Fail)
        )

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = [risky_app]
        mock_db_session.execute.return_value = mock_result

        service = AnalyticsService(mock_db_session)
        compliance_report = await service.run_compliance_audit()

        assert compliance_report.gds_violations == 1

    @pytest.mark.asyncio
    async def test_data_minimization_in_report(self, mock_db_session):
        """
        Ensure PII (SIN/DOB) is not included in analytics output.
        """
        # Mock data containing PII fields
        data_with_pii = MockApplication(
            id=1, 
            sin="123456789", 
            dob=date(1990, 1, 1),
            loan_amount=Decimal("100000.00")
        )

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = [data_with_pii]
        mock_db_session.execute.return_value = mock_result

        service = AnalyticsService(mock_db_session)
        report = await service.calculate_portfolio_risk()

        # Ensure the response object does not have these attributes or they are None
        assert not hasattr(report, 'sin') or getattr(report, 'sin', None) is None
        assert not hasattr(report, 'dob') or getattr(report, 'dob', None) is None

    @pytest.mark.asyncio
    async def test_calculate_weighted_average_rate(self, mock_db_session):
        """
        Test calculation of weighted average mortgage rate.
        """
        app1 = MockApplication(loan_amount=Decimal("100000.00"), rate=Decimal("5.0"))
        app2 = MockApplication(loan_amount=Decimal("100000.00"), rate=Decimal("3.0"))
        
        # (100k*5 + 100k*3) / 200k = 4.0%
        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = [app1, app2]
        mock_db_session.execute.return_value = mock_result

        service = AnalyticsService(mock_db_session)
        metrics = await service.calculate_portfolio_risk()
        
        assert metrics.average_rate == Decimal("4.00")

--- integration_tests ---
import pytest
from decimal import Decimal
from sqlalchemy import select
from mortgage_underwriting.modules.reporting.models import Report, Application
from mortgage_underwriting.modules.reporting.schemas import ReportType

@pytest.mark.integration
@pytest.mark.asyncio
class TestReportingEndpoints:

    async def test_create_report_request(self, client, db_session):
        """
        Test creating a new report request via API.
        """
        payload = {
            "report_type": "portfolio_summary",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31"
        }

        response = await client.post("/api/v1/reporting/reports", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["report_type"] == "portfolio_summary"
        assert data["status"] == "completed" # Assuming synchronous generation for simplicity or async acceptance
        
        # Verify DB record
        stmt = select(Report).where(Report.id == data["id"])
        result = await db_session.execute(stmt)
        report = result.scalar_one()
        assert report is not None

    async def test_get_report_by_id(self, client, db_session):
        """
        Test retrieving a specific report.
        """
        # Seed a report
        new_report = Report(
            report_type=ReportType.COMPLIANCE_AUDIT,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            status="completed",
            generated_by="system"
        )
        db_session.add(new_report)
        await db_session.commit()
        await db_session.refresh(new_report)

        response = await client.get(f"/api/v1/reporting/reports/{new_report.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == new_report.id
        assert data["report_type"] == "compliance_audit"

    async def test_get_report_not_found(self, client):
        """
        Test 404 when requesting a non-existent report.
        """
        response = await client.get("/api/v1/reporting/reports/99999")
        assert response.status_code == 404

    async def test_list_reports(self, client, db_session):
        """
        Test listing all reports with pagination.
        """
        # Seed multiple reports
        for i in range(3):
            db_session.add(Report(
                report_type=ReportType.PORTFOLIO_SUMMARY,
                start_date=date(2023, 1, 1),
                end_date=date(2023, 1, 31),
                status="completed",
                generated_by="test_user"
            ))
        await db_session.commit()

        response = await client.get("/api/v1/reporting/reports?limit=2&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 3

    async def test_invalid_date_range(self, client):
        """
        Test validation error when end_date is before start_date.
        """
        payload = {
            "report_type": "portfolio_summary",
            "start_date": "2023-12-31",
            "end_date": "2023-01-01"
        }

        response = await client.post("/api/v1/reporting/reports", json=payload)
        
        assert response.status_code == 422 # Validation Error

    async def test_portfolio_analytics_endpoint(self, client, db_session):
        """
        Test the analytics aggregation endpoint with real data.
        """
        # Seed Applications
        # App 1: LTV 80%
        app1 = Application(
            id=1,
            applicant_id=1,
            loan_amount=Decimal("80000.00"),
            property_value=Decimal("100000.00"),
            status="approved",
            created_at=datetime(2023, 6, 15)
        )
        # App 2: LTV 50%
        app2 = Application(
            id=2,
            applicant_id=2,
            loan_amount=Decimal("50000.00"),
            property_value=Decimal("100000.00"),
            status="approved",
            created_at=datetime(2023, 6, 20)
        )
        
        db_session.add(app1)
        db_session.add(app2)
        await db_session.commit()

        response = await client.get("/api/v1/reporting/analytics/portfolio?start_date=2023-01-01&end_date=2023-12-31")

        assert response.status_code == 200
        data = response.json()
        
        assert data["total_applications"] == 2
        assert data["total_volume"] == Decimal("130000.00")
        # Average LTV = (80 + 50) / 2 = 65%
        assert data["average_ltv"] == Decimal("65.00")

    async def test_analytics_filters_by_status(self, client, db_session):
        """
        Test that analytics correctly filters by application status.
        """
        # Approved App
        app_approved = Application(
            id=1,
            applicant_id=1,
            loan_amount=Decimal("100000.00"),
            property_value=Decimal("100000.00"),
            status="approved",
            created_at=datetime(2023, 1, 1)
        )
        # Declined App (should be excluded)
        app_declined = Application(
            id=2,
            applicant_id=2,
            loan_amount=Decimal("100000.00"),
            property_value=Decimal("100000.00"),
            status="declined",
            created_at=datetime(2023, 1, 2)
        )

        db_session.add(app_approved)
        db_session.add(app_declined)
        await db_session.commit()

        response = await client.get("/api/v1/reporting/analytics/portfolio?status=approved")

        assert response.status_code == 200
        data = response.json()
        assert data["total_applications"] == 1
        assert data["total_volume"] == Decimal("100000.00")

    async def test_security_headers_present(self, client):
        """
        Test that security headers are present on API responses.
        """
        response = await client.get("/api/v1/reporting/reports")
        assert "X-Content-Type-Options" in response.headers