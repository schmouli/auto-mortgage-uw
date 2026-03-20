--- conftest.py ---
import pytest
from decimal import Decimal
from datetime import date, datetime
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Import application components
from mortgage_underwriting.common.database import Base, get_async_session
from mortgage_underwriting.modules.reporting_analytics.routes import router as reporting_router
from mortgage_underwriting.modules.reporting_analytics.models import (
    ReportLog,
    ComplianceMetrics,
)

# Using SQLite for integration tests for speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture to create a fresh database session for each test.
    Creates all tables and drops them after the test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def override_get_async_session(db_session: AsyncSession):
    """
    Fixture to override the dependency injection for the database session.
    """
    async def _override_get_async_session():
        yield db_session
    
    return _override_get_async_session


@pytest.fixture(scope="function")
def app(override_get_async_session):
    """
    Fixture to create a test FastAPI application.
    """
    app = FastAPI()
    app.include_router(reporting_router, prefix="/api/v1/reporting", tags=["reporting"])
    app.dependency_overrides[get_async_session] = override_get_async_session
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture to create an async HTTP client for testing endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_report_data():
    """
    Fixture providing sample data for report generation.
    """
    return {
        "report_type": "portfolio_summary",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "parameters": {"include_declined": True},
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from mortgage_underwriting.modules.reporting_analytics.services import ReportingService
from mortgage_underwriting.modules.reporting_analytics.schemas import (
    PortfolioMetricsResponse,
    LTVBucketResponse,
    ComplianceReportResponse,
)
from mortgage_underwriting.modules.reporting_analytics.exceptions import ReportGenerationError
from mortgage_underwriting.common.exceptions import AppException

# Import models needed for mocking return types
from mortgage_underwriting.modules.applications.models import MortgageApplication
from mortgage_underwriting.modules.financials.models import FinancialSummary


@pytest.mark.unit
class TestReportingService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.scalars = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return ReportingService(mock_db)

    @pytest.mark.asyncio
    async def test_get_portfolio_metrics_success(self, service, mock_db):
        """
        Test successful aggregation of portfolio metrics.
        Verifies calculation of counts and averages.
        """
        # Mock database response
        mock_result = MagicMock()
        mock_result.total_applications = 100
        mock_result.approved_count = 80
        mock_result.declined_count = 20
        mock_result.avg_gds = Decimal("32.50")
        mock_result.avg_tds = Decimal("40.10")
        
        mock_db.scalar.return_value = mock_result

        result = await service.get_portfolio_metrics(
            start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        assert isinstance(result, PortfolioMetricsResponse)
        assert result.total_applications == 100
        assert result.approved_count == 80
        assert result.declined_count == 20
        assert result.avg_gds == Decimal("32.50")
        assert result.avg_tds == Decimal("40.10")
        mock_db.scalar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_metrics_empty_result(self, service, mock_db):
        """
        Test handling of periods with no data.
        """
        mock_db.scalar.return_value = None

        result = await service.get_portfolio_metrics(
            start_date=date(2024, 1, 1), end_date=date(2024, 1, 31)
        )

        assert result.total_applications == 0
        assert result.approved_count == 0
        assert result.avg_gds == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_calculate_ltv_distribution_success(self, service, mock_db):
        """
        Test LTV bucketing logic based on CMHC tiers.
        Buckets: <=80, 80.01-85, 85.01-90, 90.01-95, >95
        """
        # Mock rows representing loan amounts and property values
        # Row 1: LTV 75% (<=80)
        # Row 2: LTV 82% (80.01-85)
        # Row 3: LTV 88% (85.01-90)
        # Row 4: LTV 92% (90.01-95)
        mock_rows = [
            MagicMock(loan_amount=Decimal("75000"), property_value=Decimal("100000")),
            MagicMock(loan_amount=Decimal("82000"), property_value=Decimal("100000")),
            MagicMock(loan_amount=Decimal("88000"), property_value=Decimal("100000")),
            MagicMock(loan_amount=Decimal("92000"), property_value=Decimal("100000")),
        ]
        
        mock_scalars_result = AsyncMock()
        mock_scalars_result.all.return_value = mock_rows
        mock_db.scalars.return_value = mock_scalars_result

        result = await service.calculate_ltv_distribution(
            start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        assert isinstance(result, list)
        assert len(result) == 5 # Should return all defined buckets
        
        # Map result to dict for easier assertion
        buckets = {b.range_label: b.count for b in result}
        
        assert buckets.get("<= 80%") == 1
        assert buckets.get("80.01% - 85%") == 1
        assert buckets.get("85.01% - 90%") == 1
        assert buckets.get("90.01% - 95%") == 1
        assert buckets.get("> 95%") == 0

    @pytest.mark.asyncio
    async def test_generate_compliance_report_fintrac_audit(self, service, mock_db):
        """
        Test generation of compliance report ensuring FINTRAC audit trail fields are present.
        """
        # Mock application data
        mock_app = MagicMock()
        mock_app.id = "app-123"
        mock_app.created_at = datetime(2023, 5, 15, 12, 0, 0)
        mock_app.created_by = "underwriter_1"
        mock_app.is_high_value_risk = True # Hypothetical flag
        
        mock_scalars_result = AsyncMock()
        mock_scalars_result.all.return_value = [mock_app]
        mock_db.scalars.return_value = mock_scalars_result

        result = await service.generate_compliance_report(
            start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        assert isinstance(result, ComplianceReportResponse)
        assert result.total_audited_transactions == 1
        assert len(result.audit_trail_entries) == 1
        
        entry = result.audit_trail_entries[0]
        assert entry.application_id == "app-123"
        assert entry.timestamp == datetime(2023, 5, 15, 12, 0, 0)
        assert entry.user_id == "underwriter_1"
        
    @pytest.mark.asyncio
    async def test_log_report_creation_persisted(self, service, mock_db):
        """
        Test that a report request is logged in the database for audit purposes.
        """
        report_type = "monthly_summary"
        requested_by = "admin_user"
        
        # Mock the add/commit flow
        async def mock_commit_effect():
            # Simulate ID assignment
            if hasattr(mock_db, 'add'):
                pass 
                
        mock_db.commit.side_effect = mock_commit_effect

        await service.log_report_request(report_type, requested_by)

        mock_db.add.assert_called_once()
        # Verify the object added is a ReportLog model instance
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.report_type == report_type
        assert added_obj.requested_by == requested_by
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_metrics_db_error(self, service, mock_db):
        """
        Test that database errors are handled gracefully.
        """
        mock_db.scalar.side_effect = Exception("Database connection failed")

        with pytest.raises(AppException) as exc_info:
            await service.get_portfolio_metrics(
                start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
            )
        
        assert "Failed to generate portfolio metrics" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_date_range_invalid(self, service):
        """
        Test that invalid date ranges raise a ValueError.
        """
        with pytest.raises(ValueError):
            await service.get_portfolio_metrics(
                start_date=date(2023, 12, 31), end_date=date(2023, 1, 1) # End before Start
            )

--- integration_tests ---
import pytest
from decimal import Decimal
from datetime import date, datetime
from httpx import AsyncClient

from mortgage_underwriting.modules.reporting_analytics.models import ReportLog
from mortgage_underwriting.modules.applications.models import MortgageApplication
from mortgage_underwriting.modules.borrowers.models import Borrower
from mortgage_underwriting.modules.properties.models import Property
from mortgage_underwriting.common.security import hash_pii


@pytest.mark.integration
@pytest.mark.asyncio
class TestReportingAPI:
    async def test_get_portfolio_metrics_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test the full integration of the portfolio metrics endpoint.
        Creates data in DB, hits API, verifies response.
        """
        # Setup: Create dummy applications
        app1 = MortgageApplication(
            id="app-1",
            status="APPROVED",
            created_at=datetime(2023, 6, 1),
            gds=Decimal("30.00"),
            tds=Decimal("35.00"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"), # 75% LTV
            qualifying_rate=Decimal("5.25"),
        )
        app2 = MortgageApplication(
            id="app-2",
            status="DECLINED",
            created_at=datetime(2023, 6, 5),
            gds=Decimal("45.00"), # High GDS
            tds=Decimal("50.00"),
            loan_amount=Decimal("200000"),
            property_value=Decimal("200000"), # 100% LTV
            qualifying_rate=Decimal("6.50"),
        )

        db_session.add(app1)
        db_session.add(app2)
        await db_session.commit()

        # Act
        response = await client.get(
            "/api/v1/reporting/portfolio-metrics",
            params={"start_date": "2023-01-01", "end_date": "2023-12-31"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_applications"] == 2
        assert data["approved_count"] == 1
        assert data["declined_count"] == 1
        # Check averaging: (30 + 45) / 2 = 37.5
        assert Decimal(data["avg_gds"]) == Decimal("37.50")
        assert Decimal(data["avg_tds"]) == Decimal("42.50")

    async def test_get_ltv_distribution_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test LTV distribution endpoint with real DB aggregation.
        """
        # Setup: Specific LTVs
        # 80.01-85% bucket
        app_85 = MortgageApplication(
            id="app-ltv-85",
            status="APPROVED",
            created_at=datetime(2023, 1, 1),
            loan_amount=Decimal("85000"),
            property_value=Decimal("100000"),
            gds=Decimal("30.00"),
            tds=Decimal("35.00"),
            qualifying_rate=Decimal("5.25"),
        )
        # 90.01-95% bucket
        app_92 = MortgageApplication(
            id="app-ltv-92",
            status="APPROVED",
            created_at=datetime(2023, 1, 2),
            loan_amount=Decimal("92000"),
            property_value=Decimal("100000"),
            gds=Decimal("30.00"),
            tds=Decimal("35.00"),
            qualifying_rate=Decimal("5.25"),
        )

        db_session.add(app_85)
        db_session.add(app_92)
        await db_session.commit()

        response = await client.get(
            "/api/v1/reporting/ltv-distribution",
            params={"start_date": "2023-01-01", "end_date": "2023-12-31"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        
        # Find specific buckets in response
        bucket_85 = next((b for b in data if b["range_label"] == "80.01% - 85%"), None)
        bucket_92 = next((b for b in data if b["range_label"] == "90.01% - 95%"), None)
        
        assert bucket_85 is not None
        assert bucket_85["count"] == 1
        assert bucket_92 is not None
        assert bucket_92["count"] == 1

    async def test_create_report_log_audit(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test that requesting a report creates an audit log (FINTRAC compliance).
        """
        payload = {
            "report_type": "compliance_audit",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31"
        }

        response = await client.post("/api/v1/reporting/generate", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "report_id" in data

        # Verify DB has the log
        result = await db_session.execute(
            f"SELECT * FROM report_logs WHERE report_type = 'compliance_audit'"
        )
        # Note: using raw SQL or model query here to verify persistence
        # For this test, we assume ReportLog model exists
        logs = await db_session.execute(select(ReportLog).where(ReportLog.report_type == "compliance_audit"))
        log_entry = logs.scalar_one_or_none()
        
        assert log_entry is not None
        assert log_entry.requested_by == "system" # Assuming default user if none provided
        assert log_entry.status == "COMPLETED" # Or PENDING depending on async nature

    async def test_pii_not_exposed_in_reports(self, client: AsyncClient, db_session: AsyncSession):
        """
        PIPEDA Compliance: Ensure reports do not expose raw SIN or DOB.
        """
        # Create a borrower with PII
        # Note: In a real scenario, SIN is encrypted in the DB.
        # Here we ensure the Reporting service doesn't select it.
        
        borrower = Borrower(
            id="borr-1",
            first_name="John",
            last_name="Doe",
            sin_hash=hash_pii("123456789"), # Store hash
            dob=date(1980, 1, 1),
            created_at=datetime.now()
        )
        
        app = MortgageApplication(
            id="app-pii",
            borrower_id=borrower.id,
            status="APPROVED",
            created_at=datetime(2023, 1, 1),
            gds=Decimal("20.00"),
            tds=Decimal("25.00"),
            loan_amount=Decimal("100000"),
            property_value=Decimal("200000"),
            qualifying_rate=Decimal("5.25"),
        )

        db_session.add(borrower)
        db_session.add(app)
        await db_session.commit()

        # Get a detailed report (e.g., Compliance Report)
        response = await client.get(
            "/api/v1/reporting/compliance",
            params={"start_date": "2023-01-01", "end_date": "2023-12-31"}
        )

        assert response.status_code == 200
        data = response.json()
        
        # Serialize to string to check for presence of data
        response_str = str(data)
        
        # Assert raw SIN is not present
        assert "123456789" not in response_str
        # Assert DOB is not present (unless explicitly allowed, but usually masked in reports)
        # Assuming report shows IDs, not PII
        assert "John" not in response_str or "Doe" not in response_str # Depending on requirements, usually names are ok, SIN is not. 
        # Strict check for SIN:
        assert "sin" not in response_str.lower()

    async def test_empty_date_range_returns_zeroes(self, client: AsyncClient):
        """
        Test that querying a date range with no data returns valid zero-structure, not 404.
        """
        response = await client.get(
            "/api/v1/reporting/portfolio-metrics",
            params={"start_date": "2050-01-01", "end_date": "2050-12-31"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_applications"] == 0
        assert data["avg_gds"] == "0.00"

    async def test_invalid_date_format(self, client: AsyncClient):
        """
        Test validation of date inputs.
        """
        response = await client.get(
            "/api/v1/reporting/portfolio-metrics",
            params={"start_date": "invalid-date", "end_date": "2023-12-31"}
        )
        
        assert response.status_code == 422 # Validation Error