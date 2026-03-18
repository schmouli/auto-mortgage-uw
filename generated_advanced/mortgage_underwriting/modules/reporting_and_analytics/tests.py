--- conftest.py ---
```python
import pytest
from decimal import Decimal
from datetime import date, datetime
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from unittest.mock import AsyncMock, MagicMock

# Import paths based on project structure
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.reporting_analytics.models import (
    Report,
    ApplicationAggregate,
)
from mortgage_underwriting.modules.reporting_analytics.schemas import (
    ReportCreate,
    ReportType,
    AnalyticsFilter,
)

# Test Database URL (In-memory SQLite for unit/integration isolation)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock DB session for unit tests to avoid DB overhead."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session

@pytest.fixture
def sample_report_payload() -> dict:
    return {
        "report_type": "application_summary",
        "filters": {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "region": "ON"
        },
        "format": "pdf"
    }

@pytest.fixture
def sample_application_aggregates() -> list[ApplicationAggregate]:
    """Sample data for analytics aggregation tests."""
    return [
        ApplicationAggregate(
            id=1,
            total_applications=10,
            approved_count=8,
            rejected_count=2,
            total_loan_amount=Decimal("5000000.00"),
            average_ltv=Decimal("75.50"),
            region="ON",
            created_at=datetime.utcnow()
        ),
        ApplicationAggregate(
            id=2,
            total_applications=5,
            approved_count=3,
            rejected_count=2,
            total_loan_amount=Decimal("2000000.00"),
            average_ltv=Decimal("80.00"),
            region="BC",
            created_at=datetime.utcnow()
        )
    ]

@pytest.fixture
def app():
    """Fixture to create a FastAPI app instance for integration testing."""
    from fastapi import FastAPI
    from mortgage_underwriting.modules.reporting_analytics.routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/reporting", tags=["reporting"])
    return app
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

# Import the module under test
from mortgage_underwriting.modules.reporting_analytics.services import (
    ReportingService,
    AnalyticsService,
)
from mortgage_underwriting.modules.reporting_analytics.models import Report, ApplicationAggregate
from mortgage_underwriting.modules.reporting_analytics.exceptions import (
    ReportGenerationError,
    InvalidDateRangeError,
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestReportingService:
    
    @pytest.fixture
    def service(self, mock_db_session):
        return ReportingService(mock_db_session)

    @pytest.mark.asyncio
    async def test_create_report_success(self, service, mock_db_session, sample_report_payload):
        # Arrange
        report_create = sample_report_payload
        
        # Act
        result = await service.create_report(report_create)

        # Assert
        assert isinstance(result, Report)
        assert result.report_type == report_create["report_type"]
        assert result.status == "pending"
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_report_invalid_date_range_raises(self, service, sample_report_payload):
        # Arrange
        sample_report_payload["filters"]["start_date"] = "2023-12-31"
        sample_report_payload["filters"]["end_date"] = "2023-01-01"

        # Act & Assert
        with pytest.raises(InvalidDateRangeError):
            await service.create_report(sample_report_payload)

    @pytest.mark.asyncio
    async def test_get_report_by_id_success(self, service, mock_db_session):
        # Arrange
        report_id = 1
        mock_report = Report(
            id=report_id,
            report_type="application_summary",
            status="completed",
            generated_url="http://s3.bucket/report.pdf",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Mock the scalar return
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_report
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.get_report_by_id(report_id)

        # Assert
        assert result is not None
        assert result.id == report_id
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_get_report_by_id_not_found(self, service, mock_db_session):
        # Arrange
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.get_report_by_id(999)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_report_content_success(self, service):
        # Arrange
        report = Report(
            id=1,
            report_type="application_summary",
            status="pending",
            filters={"region": "ON"},
            created_at=datetime.utcnow()
        )
        
        # Mock data retrieval
        mock_data = [
            {"month": "2023-01", "count": 10, "volume": Decimal("1000000.00")},
            {"month": "2023-02", "count": 15, "volume": Decimal("1500000.00")},
        ]

        with patch.object(service, '_fetch_aggregate_data', return_value=mock_data):
            # Act
            await service._generate_report_content(report)

            # Assert
            assert report.status == "completed"
            assert report.generated_url is not None
            assert report.file_size > 0

@pytest.mark.unit
class TestAnalyticsService:

    @pytest.fixture
    def service(self, mock_db_session):
        return AnalyticsService(mock_db_session)

    @pytest.mark.asyncio
    async def test_calculate_regional_summary_success(self, service, mock_db_session, sample_application_aggregates):
        # Arrange
        start_date = date(2023, 1, 1)
        end_date = date(2023, 12, 31)
        
        # Mock DB response
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = sample_application_aggregates
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.calculate_regional_summary(start_date, end_date)

        # Assert
        assert len(result) == 2
        assert result[0].region == "ON"
        assert result[0].total_applications == 10
        # Financial precision check
        assert result[0].total_loan_amount == Decimal("5000000.00")

    @pytest.mark.asyncio
    async def test_calculate_approval_rates_empty_data(self, service, mock_db_session):
        # Arrange
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.calculate_approval_rates(date(2023, 1, 1), date(2023, 1, 31))

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_validate_filters_missing_region(self, service):
        # Arrange
        filters = {"start_date": "2023-01-01"}

        # Act & Assert - Service should handle missing optional region or default it
        # Assuming service logic defaults region if not provided for specific reports
        result = await service.sanitize_filters(filters)
        assert "region" not in result or result.get("region") is None

    @pytest.mark.asyncio
    async def test_get_ltv_distribution_buckets(self, service):
        # Arrange
        # Mocking raw SQL query results for LTV buckets
        mock_rows = [
            {"bucket": "< 60%", "count": 5},
            {"bucket": "60-80%", "count": 10},
            {"bucket": "> 80%", "count": 2},
        ]
        mock_result = AsyncMock()
        mock_result.all.return_value = mock_rows
        mock_db_session.execute.return_value = mock_result

        # Act
        distribution = await service.get_ltv_distribution(date(2023, 1, 1))

        # Assert
        assert len(distribution) == 3
        assert distribution[1]["count"] == 10

    @pytest.mark.asyncio
    async def test_export_analytics_csv_success(self, service):
        # Arrange
        data = [
            {"id": 1, "region": "ON", "count": 5},
            {"id": 2, "region": "BC", "count": 3},
        ]
        
        # Act
        csv_content = await service.export_to_csv(data)

        # Assert
        assert "id,region,count" in csv_content
        assert "1,ON,5" in csv_content
        assert "2,BC,3" in csv_content

    @pytest.mark.asyncio
    async def test_export_analytics_empty_list(self, service):
        # Act
        csv_content = await service.export_to_csv([])

        # Assert
        assert csv_content == ""
```

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from datetime import datetime, date
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

# Import models and app
from mortgage_underwriting.modules.reporting_analytics.models import Report, ApplicationAggregate
from mortgage_underwriting.modules.reporting_analytics.routes import router
from fastapi import FastAPI

@pytest.mark.integration
@pytest.mark.asyncio
class TestReportingEndpoints:

    async def test_create_report_endpoint_success(self, app, db_session):
        # Arrange
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "report_type": "application_summary",
                "filters": {
                    "start_date": "2023-01-01",
                    "end_date": "2023-01-31"
                },
                "format": "pdf"
            }

            # Act
            response = await client.post("/api/v1/reporting/reports", json=payload)

            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["id"] > 0
            assert data["status"] == "pending"
            assert "created_at" in data

            # Verify DB state
            stmt = select(Report).where(Report.id == data["id"])
            result = await db_session.execute(stmt)
            report = result.scalar_one()
            assert report is not None
            assert report.report_type == "application_summary"

    async def test_create_report_endpoint_invalid_date_range(self, app):
        # Arrange
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "report_type": "application_summary",
                "filters": {
                    "start_date": "2023-12-31",
                    "end_date": "2023-01-01"
                },
                "format": "pdf"
            }

            # Act
            response = await client.post("/api/v1/reporting/reports", json=payload)

            # Assert
            assert response.status_code == 400
            assert "error_code" in response.json()

    async def test_get_report_endpoint_success(self, app, db_session):
        # Arrange - Create a report directly in DB
        new_report = Report(
            report_type="application_summary",
            status="completed",
            generated_url="http://example.com/report.pdf",
            filters={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(new_report)
        await db_session.commit()
        await db_session.refresh(new_report)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(f"/api/v1/reporting/reports/{new_report.id}")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == new_report.id
            assert data["status"] == "completed"
            assert data["generated_url"] == "http://example.com/report.pdf"

    async def test_get_report_endpoint_not_found(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/api/v1/reporting/reports/99999")

            # Assert
            assert response.status_code == 404

    async def test_list_reports_pagination(self, app, db_session):
        # Arrange - Seed 5 reports
        for i in range(5):
            db_session.add(Report(
                report_type="application_summary",
                status="completed",
                generated_url=f"url_{i}.pdf",
                filters={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ))
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/api/v1/reporting/reports?limit=2&offset=0")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["total"] == 5
            assert data["offset"] == 0

@pytest.mark.integration
@pytest.mark.asyncio
class TestAnalyticsEndpoints:

    async def test_get_regional_summary_success(self, app, db_session):
        # Arrange - Seed aggregate data
        agg1 = ApplicationAggregate(
            total_applications=10,
            approved_count=8,
            rejected_count=2,
            total_loan_amount=Decimal("1000000.00"),
            average_ltv=Decimal("75.00"),
            region="ON",
            created_at=datetime.utcnow()
        )
        agg2 = ApplicationAggregate(
            total_applications=5,
            approved_count=4,
            rejected_count=1,
            total_loan_amount=Decimal("500000.00"),
            average_ltv=Decimal("80.00"),
            region="QC",
            created_at=datetime.utcnow()
        )
        db_session.add_all([agg1, agg2])
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/api/v1/reporting/analytics/regional-summary")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            
            # Verify Decimal serialization and logic
            on_data = next((item for item in data if item["region"] == "ON"), None)
            assert on_data is not None
            assert on_data["total_applications"] == 10
            assert on_data["total_loan_amount"] == "1000000.00" # JSON string representation

    async def test_get_approval_rates(self, app, db_session):
        # Arrange
        agg = ApplicationAggregate(
            total_applications=100,
            approved_count=80,
            rejected_count=20,
            total_loan_amount=Decimal("0.00"),
            average_ltv=Decimal("0.00"),
            region="ALL",
            created_at=datetime.utcnow()
        )
        db_session.add(agg)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get("/api/v1/reporting/analytics/approval-rates")

            # Assert
            assert response.status_code == 200
            data = response.json()
            # Assuming endpoint returns a list of rates or a summary object
            # Testing that it returns valid JSON
            assert isinstance(data, list) or isinstance(data, dict)

    async def test_export_analytics_csv(self, app, db_session):
        # Arrange
        agg = ApplicationAggregate(
            total_applications=1,
            approved_count=1,
            rejected_count=0,
            total_loan_amount=Decimal("100.00"),
            average_ltv=Decimal("50.00"),
            region="AB",
            created_at=datetime.utcnow()
        )
        db_session.add(agg)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Act
            response = await client.get(
                "/api/v1/reporting/analytics/export",
                params={"format": "csv", "type": "regional_summary"}
            )

            # Assert
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            # Verify content contains headers
            content = response.text
            assert "region" in content.lower()
            assert "AB" in content
```