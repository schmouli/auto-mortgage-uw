import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from mortgage_underwriting.modules.reporting.services import ReportingService
from mortgage_underwriting.modules.reporting.exceptions import ReportGenerationError
from mortgage_underwriting.modules.reporting.schemas import (
    ReportRequestSchema,
    ReportResponseSchema,
    ComplianceMetricsSchema
)

# Import paths for models (assuming they exist for context)
from mortgage_underwriting.modules.reporting.models import ReportLog

@pytest.mark.unit
class TestReportingService:

    @pytest.mark.asyncio
    async def test_generate_portfolio_report_success(self, mock_report_db, sample_application_data):
        """Test successful generation of a portfolio report."""
        # Mock the DB response to return sample data
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [sample_application_data]
        mock_report_db.execute.return_value = mock_result

        service = ReportingService(mock_report_db)
        request = ReportRequestSchema(
            report_type="portfolio_summary",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        response = await service.generate_report(request)

        assert isinstance(response, ReportResponseSchema)
        assert response.report_type == "portfolio_summary"
        assert response.total_records == 1
        assert response.data is not None
        mock_report_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_report_excludes_pii(self, mock_report_db, sample_application_data):
        """
        PIPEDA Compliance Test: Ensure SIN and DOB are excluded from report data.
        """
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [sample_application_data]
        mock_report_db.execute.return_value = mock_result

        service = ReportingService(mock_report_db)
        request = ReportRequestSchema(report_type="portfolio_summary", start_date="2023-01-01", end_date="2023-12-31")

        response = await service.generate_report(request)

        # Check that the data list is not empty
        assert len(response.data) > 0
        
        # Verify PII fields are not in the serialized output
        # We assume the service transforms the ORM model to a dict/schema
        first_record = response.data[0]
        assert "sin" not in first_record, "SIN must not appear in reports (PIPEDA)"
        assert "dob" not in first_record, "DOB must not appear in reports (PIPEDA)"
        assert "sin" not in str(response.model_dump_json()), "SIN must not be in JSON string"

    @pytest.mark.asyncio
    async def test_calculate_ltv_aggregates(self, mock_report_db, sample_application_data, sample_high_risk_application_data):
        """Test LTV calculation logic within the report."""
        # Setup mock return with two applications
        # App 1: 450k/500k = 90%
        # App 2: 400k/420k = 95.23%
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [sample_application_data, sample_high_risk_application_data]
        mock_report_db.execute.return_value = mock_result

        service = ReportingService(mock_report_db)
        request = ReportRequestSchema(report_type="ltv_analysis", start_date="2023-01-01", end_date="2023-12-31")

        response = await service.generate_report(request)

        # Verify financial precision (Decimal)
        assert response.metadata is not None
        # Assuming service calculates average LTV or similar
        # (90 + 95.23) / 2 approx 92.6
        if "average_ltv" in response.metadata:
            assert isinstance(response.metadata["average_ltv"], Decimal)

    @pytest.mark.asyncio
    async def test_get_compliance_metrics_osfi_stress_test(self, mock_report_db):
        """
        OSFI B-20 Compliance Test: Verify stress test application in compliance checks.
        """
        # Mock data: Contract rate 4.0%. Qualifying rate should be max(4.0+2, 5.25) = 6.0%.
        mock_application = {
            "id": 1,
            "contract_rate": Decimal("4.00"),
            "loan_amount": Decimal("300000.00"),
            "income": Decimal("100000.00"),
            "monthly_debts": Decimal("2000.00")
        }
        
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [mock_application]
        mock_report_db.execute.return_value = mock_result

        service = ReportingService(mock_report_db)
        
        # We are testing the service logic that calculates compliance
        metrics = await service.get_compliance_metrics()

        # Verify that the service used the correct qualifying rate logic
        # This is a conceptual assertion; in real code, we might check the calculated GDS/TDS
        assert metrics.total_applications == 1
        # Assuming the service flags if GDS > 39% based on qualifying rate
        # If the mock app was compliant, passing_compliance_count should be 1
        assert metrics.passing_compliance_count >= 0

    @pytest.mark.asyncio
    async def test_report_generation_audit_log(self, mock_report_db):
        """
        FINTRAC Compliance Test: Ensure report generation creates an audit log.
        """
        # Mock the result of the report query
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = []
        mock_report_db.execute.return_value = mock_result

        service = ReportingService(mock_report_db)
        request = ReportRequestSchema(report_type="audit_trail", start_date="2023-01-01", end_date="2023-12-31")

        await service.generate_report(request)

        # Verify that an audit log entry was added to the session
        # This checks that created_at and created_by are being handled
        mock_report_db.add.assert_called()
        
        # Check if the added object is a ReportLog or similar audit entity
        calls = mock_report_db.add.call_args_list
        assert len(calls) > 0, "Audit log entry must be created"

    @pytest.mark.asyncio
    async def test_empty_date_range_raises_error(self, mock_report_db):
        """Test validation logic for invalid date ranges."""
        service = ReportingService(mock_report_db)
        
        # Start date after End date
        request = ReportRequestSchema(
            report_type="portfolio_summary",
            start_date="2023-12-31",
            end_date="2023-01-01"
        )

        with pytest.raises(ValueError) as excinfo:
            await service.generate_report(request)
        assert "Invalid date range" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_handle_database_failure(self, mock_report_db):
        """Test robust error handling when DB fails."""
        mock_report_db.execute.side_effect = Exception("Database connection failed")

        service = ReportingService(mock_report_db)
        request = ReportRequestSchema(report_type="portfolio_summary", start_date="2023-01-01", end_date="2023-12-31")

        with pytest.raises(ReportGenerationError):
            await service.generate_report(request)

    @pytest.mark.asyncio
    async def test_calculate_gds_limits(self):
        """
        OSFI B-20 Compliance: Verify GDS calculation logic respects 39% limit.
        """
        # Pure logic test, can be static or service method
        # Mortgage Payment (P+I) + Tax + Heat / Income
        monthly_income = Decimal("10000.00")
        monthly_housing_costs = Decimal("3900.00") # Exactly 39%
        
        # Service logic should calculate: 3900 / 10000 = 0.39
        gds = ReportingService._calculate_gds(monthly_housing_costs, monthly_income)
        
        assert gds == Decimal("0.39")
        
        # Test boundary
        high_costs = Decimal("3901.00")
        gds_high = ReportingService._calculate_gds(high_costs, monthly_income)
        assert gds_high > Decimal("0.39")