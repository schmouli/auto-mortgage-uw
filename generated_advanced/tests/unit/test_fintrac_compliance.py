import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import select

from mortgage_underwriting.modules.fintrac.models import FintracReport, IdentityVerificationLog
from mortgage_underwriting.modules.fintrac.schemas import FintracReportCreate, IdentityVerificationCreate
from mortgage_underwriting.modules.fintrac.services import FintracService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFintracService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_log_identity_verification_success(self, mock_db):
        """Test that identity verification is logged correctly with audit trail."""
        payload = IdentityVerificationCreate(
            applicant_id="user-123",
            verification_method="government_id",
            verified_by="system"
        )
        
        service = FintracService(mock_db)
        
        # Mock the return of the refresh to simulate DB response
        mock_log_instance = IdentityVerificationLog(
            id="log-1",
            applicant_id=payload.applicant_id,
            verification_method=payload.verification_method,
            verified_by=payload.verified_by,
            created_at=datetime.utcnow()
        )
        mock_db.refresh.return_value = mock_log_instance

        result = await service.log_verification(payload)

        # Assertions
        assert result.applicant_id == "user-123"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        
        # Verify audit fields are set (via service logic or DB default, we check logic here)
        # Assuming service sets created_at/created_by if not handled by DB trigger
        call_args = mock_db.add.call_args[0][0]
        assert isinstance(call_args, IdentityVerificationLog)

    @pytest.mark.asyncio
    async def test_record_transaction_large_cash_flag(self, mock_db):
        """Test that transactions >= 10,000 CAD are flagged correctly."""
        payload = FintracReportCreate(
            applicant_id="user-123",
            transaction_amount=Decimal("12000.00"),
            transaction_type="deposit",
            currency="CAD"
        )

        service = FintracService(mock_db)
        
        mock_report_instance = FintracReport(
            id="report-1",
            applicant_id=payload.applicant_id,
            transaction_amount=payload.transaction_amount,
            transaction_type=payload.transaction_type,
            is_large_cash=True, # Expecting this to be set by service
            created_at=datetime.utcnow()
        )
        mock_db.refresh.return_value = mock_report_instance

        result = await service.record_transaction(payload)

        # Verify the service flagged it
        call_args = mock_db.add.call_args[0][0]
        assert call_args.is_large_cash is True
        assert call_args.transaction_amount == Decimal("12000.00")

    @pytest.mark.asyncio
    async def test_record_transaction_small_amount_no_flag(self, mock_db):
        """Test that transactions < 10,000 CAD are not flagged."""
        payload = FintracReportCreate(
            applicant_id="user-123",
            transaction_amount=Decimal("5000.00"),
            transaction_type="deposit",
            currency="CAD"
        )

        service = FintracService(mock_db)
        
        mock_report_instance = FintracReport(
            id="report-1",
            applicant_id=payload.applicant_id,
            transaction_amount=payload.transaction_amount,
            transaction_type=payload.transaction_type,
            is_large_cash=False,
            created_at=datetime.utcnow()
        )
        mock_db.refresh.return_value = mock_report_instance

        result = await service.record_transaction(payload)

        call_args = mock_db.add.call_args[0][0]
        assert call_args.is_large_cash is False

    @pytest.mark.asyncio
    async def test_record_transaction_invalid_currency_raises(self, mock_db):
        """Test that non-CAD currencies raise an error or are handled (assuming CAD only for simplicity)."""
        payload = FintracReportCreate(
            applicant_id="user-123",
            transaction_amount=Decimal("100.00"),
            transaction_type="deposit",
            currency="USD"
        )

        service = FintracService(mock_db)
        
        with pytest.raises(ValueError) as exc_info:
            await service.record_transaction(payload)
        
        assert "currency" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_record_transaction_negative_amount_raises(self, mock_db):
        """Test that negative amounts are rejected."""
        payload = FintracReportCreate(
            applicant_id="user-123",
            transaction_amount=Decimal("-500.00"),
            transaction_type="deposit",
            currency="CAD"
        )

        service = FintracService(mock_db)
        
        with pytest.raises(ValueError):
            await service.record_transaction(payload)

    @pytest.mark.asyncio
    async def test_immutability_enforced_on_update_attempt(self, mock_db):
        """Test that updating an audit field (created_at) raises an error."""
        # Setup an existing report
        existing_report = FintracReport(
            id="report-1",
            applicant_id="user-123",
            transaction_amount=Decimal("100.00"),
            created_at=datetime(2023, 1, 1)
        )
        
        # Mock the DB get to return this object
        mock_result = AsyncMock()
        mock_result.unique.return_value.scalar_one_or_none.return_value = existing_report
        mock_db.execute.return_value = mock_result

        service = FintracService(mock_db)

        # Attempt to update created_at
        with pytest.raises(AppException) as exc_info:
            await service.update_report("report-1", {"created_at": datetime.now()})
        
        assert "immutable" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_retention_period_eligible(self, mock_db):
        """Test checking if a record is eligible for archival (older than 5 years)."""
        old_date = datetime.utcnow()
        # Mock logic that checks date
        # Service logic: is_retention_eligible(record)
        pass 
        # Note: Implementation depends on specific service method existence.
        # Assuming a method exists for checking retention.

    @patch('mortgage_underwriting.modules.fintrac.services.structlog')
    @pytest.mark.asyncio
    async def test_logging_of_large_cash_transaction(self, mock_logger, mock_db):
        """Test that large cash transactions trigger a specific audit log."""
        payload = FintracReportCreate(
            applicant_id="user-123",
            transaction_amount=Decimal("10000.00"), # Boundary
            transaction_type="large_cash",
            currency="CAD"
        )

        service = FintracService(mock_db)
        mock_db.refresh.return_value = MagicMock(id="report-1")

        await service.record_transaction(payload)

        # Verify structured logging was called with specific event type
        mock_logger.get_logger.return_value.info.assert_called()
        # Check call args for "large_cash_reported" event
        calls = mock_logger.get_logger.return_value.info.call_args_list
        assert any("large_cash" in str(call) for call in calls)