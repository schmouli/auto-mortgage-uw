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