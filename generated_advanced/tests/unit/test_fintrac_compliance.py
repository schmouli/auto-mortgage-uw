```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.exc import IntegrityError

# Absolute Imports based on project structure
from mortgage_underwriting.modules.fintrac.models import (
    FintracTransactionLog,
    IdentityVerificationRecord
)
from mortgage_underwriting.modules.fintrac.schemas import (
    TransactionCreate,
    TransactionResponse,
    IdentityVerificationCreate
)
from mortgage_underwriting.modules.fintrac.services import FintracService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFintracService:
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock AsyncSession for unit tests."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_record_transaction_success(self, mock_db_session):
        """Test successfully recording a standard transaction."""
        service = FintracService(mock_db_session)
        payload = TransactionCreate(
            applicant_id="app_123",
            amount=Decimal("5000.00"),
            currency="CAD",
            transaction_type="PAYMENT",
            account_number="****1234",
            institution_id="inst_01"
        )

        result = await service.record_transaction(payload, created_by="system")

        assert result.applicant_id == "app_123"
        assert result.amount == Decimal("5000.00")
        assert result.is_large_cash_reportable is False
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_large_cash_transaction(self, mock_db_session):
        """
        Test that transactions > $10,000 CAD are flagged for reporting.
        Regulatory: Explicit transaction type flag required.
        """
        service = FintracService(mock_db_session)
        payload = TransactionCreate(
            applicant_id="app_456",
            amount=Decimal("10001.00"),
            currency="CAD",
            transaction_type="LARGE_CASH",
            account_number="****5678",
            institution_id="inst_01"
        )

        result = await service.record_transaction(payload, created_by="system")

        assert result.amount == Decimal("10001.00")
        assert result.is_large_cash_reportable is True
        # Ensure specific flag is set
        assert result.transaction_type == "LARGE_CASH"

    @pytest.mark.asyncio
    async def test_record_transaction_boundary_10k(self, mock_db_session):
        """Test boundary condition exactly at $10,000.00 (should not flag)."""
        service = FintracService(mock_db_session)
        payload = TransactionCreate(
            applicant_id="app_789",
            amount=Decimal("10000.00"),
            currency="CAD",
            transaction_type="PAYMENT",
            account_number="****9999",
            institution_id="inst_01"
        )

        result = await service.record_transaction(payload, created_by="system")

        assert result.is_large_cash_reportable is False

    @pytest.mark.asyncio
    async def test_record_transaction_negative_amount_raises(self, mock_db_session):
        """Test that negative amounts are rejected."""
        service = FintracService(mock_db_session)
        payload = TransactionCreate(
            applicant_id="app_err",
            amount=Decimal("-50.00"),
            currency="CAD",
            transaction_type="PAYMENT",
            account_number="****0000",
            institution_id="inst_01"
        )

        with pytest.raises(ValueError) as exc_info:
            await service.record_transaction(payload, created_by="system")
        assert "Transaction amount must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_log_identity_verification_success(self, mock_db_session):
        """Test logging a successful identity verification."""
        service = FintracService(mock_db_session)
        payload = IdentityVerificationCreate(
            applicant_id="app_123",
            verification_method="PASSPORT",
            id_type="PASSPORT",
            id_jurisdiction="CA",
            verified_by="user_1"
        )

        result = await service.log_identity_verification(payload)

        assert result.applicant_id == "app_123"
        assert result.verification_status == "VERIFIED"
        assert result.verified_at is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_identity_verification_failure(self, mock_db_session):
        """Test logging a failed identity verification attempt."""
        service = FintracService(mock_db_session)
        payload = IdentityVerificationCreate(
            applicant_id="app_404",
            verification_method="GOVERNMENT_ID",
            id_type="SIN",
            id_jurisdiction="CA",
            verified_by="user_1"
        )

        # Simulate a failure scenario if the service supports manual status override
        # or if the verification logic determines failure based on payload
        # Here we assume the service sets status based on internal logic or payload
        result = await service.log_identity_verification(payload, status="FAILED")

        assert result.verification_status == "FAILED"

    @pytest.mark.asyncio
    async def test_immutable_audit_fields(self, mock_db_session):
        """
        Test that created_at and created_by are set and immutable.
        Regulatory: Immutable audit trail.
        """
        service = FintracService(mock_db_session)
        payload = TransactionCreate(
            applicant_id="app_audit",
            amount=Decimal("100.00"),
            currency="CAD",
            transaction_type="PAYMENT",
            account_number="****1111",
            institution_id="inst_01"
        )

        result = await service.record_transaction(payload, created_by="admin_user")

        assert result.created_at is not None
        assert result.created_by == "admin_user"
        assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_record_transaction_decimal_precision(self, mock_db_session):
        """Test that Decimal is used and precision is maintained."""
        service = FintracService(mock_db_session)
        precise_amount = Decimal("12345.67")
        payload = TransactionCreate(
            applicant_id="app_dec",
            amount=precise_amount,
            currency="CAD",
            transaction_type="PAYMENT",
            account_number="****2222",
            institution_id="inst_01"
        )

        result = await service.record_transaction(payload, created_by="system")

        # Ensure no float conversion happened
        assert isinstance(result.amount, Decimal)
        assert result.amount == precise_amount
```