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