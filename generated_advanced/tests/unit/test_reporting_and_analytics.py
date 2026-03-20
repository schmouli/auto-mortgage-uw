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