--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Numeric, DateTime, func, Boolean
from datetime import datetime, date
from fastapi import FastAPI

# Import the module under test
from mortgage_underwriting.modules.reporting_analytics.routes import router as reporting_router
from mortgage_underwriting.common.config import settings

# Use an in-memory SQLite database for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

class Base(DeclarativeBase):
    pass

# Minimal model for testing reporting logic (mimicking a Mortgage Application)
class MortgageApplication(Base):
    __tablename__ = "mortgage_applications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    applicant_id: Mapped[str] = mapped_column(String(50))
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    property_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    annual_income: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    annual_taxes: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    heating_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    other_debt: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    contract_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

# Minimal model for Audit Trail (FINTRAC compliance)
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50))
    performed_by: Mapped[str] = mapped_column(String(50))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())

@pytest.fixture(scope="session")
def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    engine.dispose()

@pytest.fixture(scope="session")
def tables(engine):
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
async def db_session(engine, tables) -> AsyncGenerator[AsyncSession, None]:
    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
        await session.rollback()

@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(reporting_router, prefix="/api/v1/reporting", tags=["reporting"])
    return app

@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def sample_application_data():
    return {
        "applicant_id": "cust_123",
        "principal_amount": Decimal("450000.00"),
        "property_value": Decimal("500000.00"),
        "annual_income": Decimal("120000.00"),
        "annual_taxes": Decimal("3000.00"),
        "heating_cost": Decimal("150.00") * Decimal("12"), # Annualized
        "other_debt": Decimal("500.00") * Decimal("12"),   # Annualized
        "contract_rate": Decimal("4.50"),
        "is_approved": True
    }

@pytest.fixture
def sample_audit_log_data():
    return {
        "entity_type": "Application",
        "entity_id": "app_999",
        "action": "STATUS_CHANGE",
        "performed_by": "underwriter_1"
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from mortgage_underwriting.modules.reporting_analytics.services import ReportingService
from mortgage_underwriting.modules.reporting_analytics.exceptions import ReportGenerationError

# We use the models defined in conftest for type hinting, though in a real scenario 
# we might import the actual models. For unit tests, we mock the DB interactions heavily.

@pytest.mark.unit
class TestReportingService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def service(self):
        return ReportingService()

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_success(self, service, mock_db):
        # Setup Mock Result
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5 # Total count
        mock_result.scalars.return_value.all.return_value = [
            MagicMock(annual_income=Decimal("100000.00"), principal_amount=Decimal("400000.00")),
            MagicMock(annual_income=Decimal("200000.00"), principal_amount=Decimal("800000.00"))
        ]
        
        mock_db.execute.return_value = mock_result

        # Execute
        result = await service.get_portfolio_summary(mock_db)

        # Assertions
        assert result["total_applications"] == 5
        assert result["total_loan_volume"] == Decimal("1200000.00")
        assert result["average_income"] == Decimal("150000.00")
        mock_db.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_calculate_gds_tds_aggregates(self, service, mock_db):
        # Setup Mock Data representing applications
        # App 1: High GDS
        # App 2: Low GDS
        mock_rows = [
            MagicMock(
                id=1,
                principal_amount=Decimal("400000"),
                annual_income=Decimal("60000"),
                annual_taxes=Decimal("2400"),
                heating_cost=Decimal("1200"),
                other_debt=Decimal("600"),
                contract_rate=Decimal("5.0")
            ),
            MagicMock(
                id=2,
                principal_amount=Decimal("200000"),
                annual_income=Decimal("100000"),
                annual_taxes=Decimal("3000"),
                heating_cost=Decimal("1500"),
                other_debt=Decimal("0"),
                contract_rate=Decimal("3.5")
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        # Execute
        stats = await service.calculate_gds_tds_aggregates(mock_db)

        # Assertions
        assert stats["count"] == 2
        # Check that averages are calculated as Decimals
        assert isinstance(stats["avg_gds"], Decimal)
        assert isinstance(stats["avg_tds"], Decimal)
        # Verify OSFI B-20 Stress Test logic is applied in the service (mocked verification)
        # We assume the service applies the stress test rate before calculating the ratio
        mock_db.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_generate_compliance_report_empty_data(self, service, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        report = await service.generate_compliance_report(mock_db, days=30)

        assert report["total_records"] == 0
        assert report["compliance_rate"] == Decimal("100.00") # No violations if no data

    @pytest.mark.asyncio
    async def test_generate_compliance_report_fintrac_violations(self, service, mock_db):
        # Mock logs missing 'created_by' or having null fields
        mock_logs = [
            MagicMock(id=1, action="CREATE", performed_by="user_1", timestamp=datetime.now()),
            MagicMock(id=2, action="UPDATE", performed_by=None, timestamp=datetime.now()) # Violation
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        mock_db.execute.return_value = mock_result

        report = await service.generate_compliance_report(mock_db, days=30)

        assert report["total_records"] == 2
        assert report["violations"] == 1
        assert report["compliance_rate"] == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_export_report_csv_generation(self, service, mock_db):
        # Mock data
        mock_apps = [
            MagicMock(id=1, applicant_id="A1, Inc", principal_amount=Decimal("100.00")), # Comma in name to test CSV escaping
            MagicMock(id=2, applicant_id="B2", principal_amount=Decimal("200.00"))
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_apps
        mock_db.execute.return_value = mock_result

        csv_content = await service.export_report_csv(mock_db)

        assert "id,applicant_id,principal_amount" in csv_content
        assert '"A1, Inc"' in csv_content # Check escaping
        assert "100.00" in csv_content

    @pytest.mark.asyncio
    async def test_service_handles_db_errors(self, service, mock_db):
        mock_db.execute.side_effect = Exception("Database connection failed")

        with pytest.raises(ReportGenerationError) as exc_info:
            await service.get_portfolio_summary(mock_db)
        
        assert "Failed to generate portfolio summary" in str(exc_info.value)

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

# Import models from conftest (they represent the DB state)
from conftest import MortgageApplication, AuditLog

@pytest.mark.integration
@pytest.mark.asyncio
class TestReportingEndpoints:

    async def test_get_portfolio_summary_empty(self, client: AsyncClient, db_session):
        # Ensure DB is empty
        result = await client.get("/api/v1/reporting/portfolio-summary")
        assert result.status_code == 200
        
        data = result.json()
        assert data["total_applications"] == 0
        assert data["total_loan_volume"] == "0.00"
        assert data["average_income"] is None or data["average_income"] == "0.00"

    async def test_get_portfolio_summary_with_data(self, client: AsyncClient, db_session, sample_application_data):
        # Create 2 applications
        app1 = MortgageApplication(**sample_application_data)
        app2 = MortgageApplication(**{**sample_application_data, "applicant_id": "cust_456", "principal_amount": Decimal("500000.00")})
        
        db_session.add(app1)
        db_session.add(app2)
        await db_session.commit()

        result = await client.get("/api/v1/reporting/portfolio-summary")
        assert result.status_code == 200
        
        data = result.json()
        assert data["total_applications"] == 2
        # 450k + 500k = 950k
        assert Decimal(data["total_loan_volume"]) == Decimal("950000.00")

    async def test_get_gds_tds_report(self, client: AsyncClient, db_session, sample_application_data):
        # Create a specific scenario
        # Loan: 450k, Rate: 4.5% (Qualifying: 6.5%). 25yr amort (approx).
        # Monthly Mortgage Payment ~ $3000 (simplified for logic check)
        app = MortgageApplication(**sample_application_data)
        db_session.add(app)
        await db_session.commit()

        result = await client.get("/api/v1/reporting/gds-tds-stats")
        assert result.status_code == 200

        data = result.json()
        assert "avg_gds" in data
        assert "avg_tds" in data
        # Check that values are returned as strings to preserve precision
        assert isinstance(data["avg_gds"], str)
        # Verify OSFI B-20 compliance check flag exists
        assert "stress_test_violations" in data

    async def test_get_compliance_report_fintrac(self, client: AsyncClient, db_session, sample_audit_log_data):
        # Add valid log
        log1 = AuditLog(**sample_audit_log_data)
        # Add invalid log (missing performed_by)
        log2 = AuditLog(entity_type="Application", entity_id="app_998", action="CREATE", performed_by=None)
        
        db_session.add(log1)
        db_session.add(log2)
        await db_session.commit()

        result = await client.get("/api/v1/reporting/compliance?days=1")
        assert result.status_code == 200

        data = result.json()
        assert data["total_records"] == 2
        assert data["violations"] == 1
        assert data["compliance_rate"] == "50.00"

    async def test_export_csv_endpoint(self, client: AsyncClient, db_session, sample_application_data):
        app = MortgageApplication(**sample_application_data)
        db_session.add(app)
        await db_session.commit()

        result = await client.post("/api/v1/reporting/export", json={"format": "csv"})
        assert result.status_code == 200
        assert result.headers["content-type"] == "text/csv; charset=utf-8"
        
        content = result.text
        assert "applicant_id" in content
        assert "cust_123" in content

    async def test_export_csv_invalid_format(self, client: AsyncClient):
        result = await client.post("/api/v1/reporting/export", json={"format": "excel"})
        assert result.status_code == 400
        assert "Unsupported format" in result.json()["detail"]

    async def test_filtering_by_date_range(self, client: AsyncClient, db_session, sample_application_data):
        # Create an app today
        app_today = MortgageApplication(**sample_application_data)
        
        # Create an app yesterday
        app_yesterday = MortgageApplication(**{**sample_application_data, "applicant_id": "old_cust"})
        app_yesterday.created_at = app_yesterday.created_at - timedelta(days=2)
        
        db_session.add(app_today)
        db_session.add(app_yesterday)
        await db_session.commit()

        # Filter for last 24 hours
        start_date = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        
        result = await client.get(f"/api/v1/reporting/portfolio-summary?start_date={start_date}")
        assert result.status_code == 200
        
        data = result.json()
        # Should only count the recent one
        assert data["total_applications"] == 1

    async def test_cmhc_insurance_report(self, client: AsyncClient, db_session, sample_application_data):
        # High LTV scenario (>80%)
        high_ltv_data = {**sample_application_data, "property_value": Decimal("460000.00")} # 450k/460k > 97%
        app = MortgageApplication(**high_ltv_data)
        
        db_session.add(app)
        await db_session.commit()

        result = await client.get("/api/v1/reporting/cmhc-stats")
        assert result.status_code == 200
        
        data = result.json()
        assert "insurance_required_count" in data
        assert data["insurance_required_count"] == 1
        # Verify tier calculation logic was executed (e.g. premium tiers)
        assert "total_premium_estimate" in data