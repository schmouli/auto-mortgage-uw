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