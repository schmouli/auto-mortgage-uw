import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.fintrac_compliance.services import FintracService
from mortgage_underwriting.modules.fintrac_compliance.schemas import FintracReportCreate
from mortgage_underwriting.modules.fintrac_compliance.exceptions import FintracValidationError

# Import models for type hinting/mocking
from mortgage_underwriting.modules.fintrac_compliance.models import FintracReport

@pytest.mark.unit
class TestFintracService:

    @pytest.mark.asyncio
    async def test_create_report_success(self, mock_db_session):
        """Test successful creation of a standard FINTRAC report."""
        service = FintracService(mock_db_session)
        payload = FintracReportCreate(
            amount=Decimal("5000.00"),
            transaction_type="deposit",
            created_by="underwriter_1"
        )

        # Mock the return of refresh
        mock_report = FintracReport(
            id=1,
            amount=payload.amount,
            transaction_type=payload.transaction_type,
            is_high_value=False,
            created_by=payload.created_by
        )
        mock_db_session.refresh.return_value = mock_report

        result = await service.create_report(payload)

        assert result.amount == Decimal("5000.00")
        assert result.is_high_value is False
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_report_high_value_threshold(self, mock_db_session):
        """Test that transactions > 10,000 CAD are flagged as high value."""
        service = FintracService(mock_db_session)
        
        # Boundary test: Exactly 10,000
        payload_boundary = FintracReportCreate(
            amount=Decimal("10000.00"),
            transaction_type="wire",
            created_by="system"
        )
        mock_report_boundary = FintracReport(
            id=1, amount=payload_boundary.amount, 
            transaction_type=payload_boundary.transaction_type, 
            is_high_value=False, created_by="system"
        )
        mock_db_session.refresh.return_value = mock_report_boundary
        
        result_boundary = await service.create_report(payload_boundary)
        assert result_boundary.is_high_value is False

        # Boundary test: 10,000.01 (Should be True)
        payload_over = FintracReportCreate(
            amount=Decimal("10000.01"),
            transaction_type="wire",
            created_by="system"
        )
        mock_report_over = FintracReport(
            id=2, amount=payload_over.amount, 
            transaction_type=payload_over.transaction_type, 
            is_high_value=True, created_by="system"
        )
        mock_db_session.refresh.return_value = mock_report_over

        result_over = await service.create_report(payload_over)
        assert result_over.is_high_value is True

    @pytest.mark.asyncio
    async def test_create_report_negative_amount_raises(self, mock_db_session):
        """Test validation error for negative financial values."""
        service = FintracService(mock_db_session)
        
        with pytest.raises(FintracValidationError) as exc_info:
            await service.create_report(
                FintracReportCreate(
                    amount=Decimal("-50.00"),
                    transaction_type="cash",
                    created_by="user"
                )
            )
        
        assert "Amount must be positive" in str(exc_info.value)
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_report_missing_created_by_raises(self, mock_db_session):
        """Test validation error if audit field created_by is missing."""
        service = FintracService(mock_db_session)
        
        with pytest.raises(FintracValidationError) as exc_info:
            await service.create_report(
                FintracReportCreate(
                    amount=Decimal("100.00"),
                    transaction_type="cash",
                    created_by="" # Empty string
                )
            )
        
        assert "created_by is required for audit trail" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_log_identity_verification_success(self, mock_db_session, caplog):
        """Test logging of identity verification attempts."""
        service = FintracService(mock_db_session)
        
        # Assuming a method log_verification exists
        # We check that the service logic handles the logging requirement
        with caplog.at_level("INFO"):
            service.log_identity_verification(
                user_id="user_123", 
                method="passport", 
                status="verified"
            )
        
        assert any("Identity verification" in record.message for record in caplog.records)
        assert "user_123" in caplog.text

    @pytest.mark.asyncio
    async def test_get_report_by_id(self, mock_db_session):
        """Test retrieving a report."""
        service = FintracService(mock_db_session)
        
        mock_report = FintracReport(
            id=1,
            amount=Decimal("500.00"),
            transaction_type="cash",
            is_high_value=False,
            created_by="admin"
        )
        
        # Mock the scalar/where logic
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_report
        mock_db_session.execute.return_value = mock_result

        result = await service.get_report(1)
        
        assert result is not None
        assert result.id == 1
        assert result.amount == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, mock_db_session):
        """Test retrieving a non-existent report returns None."""
        service = FintracService(mock_db_session)
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await service.get_report(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_retention_period(self):
        """Test that 5-year retention logic is correctly calculated."""
        service = FintracService(AsyncMock())
        
        created_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        retention_date = service.calculate_retention_expiry(created_date)
        
        expected_year = created_date.year + 5
        assert retention_date.year == expected_year
        assert retention_date.month == created_date.month
        assert retention_date.day == created_date.day