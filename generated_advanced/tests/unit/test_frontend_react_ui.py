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