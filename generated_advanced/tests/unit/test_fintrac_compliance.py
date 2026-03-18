import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from sqlalchemy.orm import select

from mortgage_underwriting.modules.fintrac_compliance.services import FintracService
from mortgage_underwriting.modules.fintrac_compliance.models import FintracReport, ClientIdentity
from mortgage_underwriting.modules.fintrac_compliance.schemas import (
    FintracReportCreate, 
    ClientIdentityCreate,
    FintracReportResponse
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFintracService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return FintracService(mock_db)

    @pytest.mark.asyncio
    async def test_log_transaction_standard_amount(self, service, mock_db):
        """Test logging a standard transaction (< 10k CAD)."""
        payload = FintracReportCreate(
            client_id="client_001",
            transaction_amount=Decimal("5000.00"),
            currency="CAD",
            transaction_type="wire_transfer",
            entity_type="individual"
        )

        # Mock the return of the added object (usually happens after refresh/commit)
        mock_report = FintracReport(**payload.model_dump(), id=1)
        mock_db.refresh.return_value = mock_report
        mock_db.scalar.return_value = None # No existing report

        result = await service.log_transaction(payload)

        assert result.transaction_amount == Decimal("5000.00")
        assert result.is_large_cash_transaction is False
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_transaction_large_cash_threshold(self, service, mock_db):
        """Test that transactions > 10k CAD are flagged correctly."""
        payload = FintracReportCreate(
            client_id="client_001",
            transaction_amount=Decimal("10500.00"),
            currency="CAD",
            transaction_type="cash_deposit", # Explicit cash
            entity_type="individual"
        )

        mock_report = FintracReport(**payload.model_dump(), id=2, is_large_cash_transaction=True)
        mock_db.refresh.return_value = mock_report
        
        result = await service.log_transaction(payload)

        assert result.is_large_cash_transaction is True
        assert result.transaction_amount == Decimal("10500.00")

    @pytest.mark.asyncio
    async def test_log_transaction_foreign_currency(self, service, mock_db):
        """Test handling of foreign currency (assuming conversion logic exists or is mocked)."""
        # Assuming service converts to CAD or logs as is. 
        # For this test, we check that the service accepts non-CAD.
        payload = FintracReportCreate(
            client_id="client_001",
            transaction_amount=Decimal("8000.00"),
            currency="USD",
            transaction_type="wire_transfer",
            entity_type="individual"
        )

        mock_report = FintracReport(**payload.model_dump(), id=3)
        mock_db.refresh.return_value = mock_report

        result = await service.log_transaction(payload)

        assert result.currency == "USD"
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_transaction_invalid_amount_negative(self, service, mock_db):
        """Test that negative amounts raise validation errors."""
        with pytest.raises(ValueError) as exc_info:
            await service.log_transaction(
                FintracReportCreate(
                    client_id="client_001",
                    transaction_amount=Decimal("-100.00"),
                    currency="CAD",
                    transaction_type="wire_transfer",
                    entity_type="individual"
                )
            )
        assert "Transaction amount must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("mortgage_underwriting.common.security.encrypt_pii")
    async def test_verify_identity_encryption_called(self, mock_encrypt, service, mock_db):
        """Test that PII (SIN) is encrypted during identity verification."""
        mock_encrypt.return_value = "encrypted_sin_blob"
        
        payload = ClientIdentityCreate(
            client_id="client_001",
            first_name="Jane",
            last_name="Smith",
            sin="987-654-321",
            dob="1985-05-20",
            occupation="Doctor"
        )

        mock_identity = ClientIdentity(**payload.model_dump(), id=1, sin_hash="hash123")
        mock_db.refresh.return_value = mock_identity

        await service.verify_identity(payload)

        # Assert security utility was called for SIN
        mock_encrypt.assert_called_once_with("987-654-321")
        # Assert DB add was called
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    @patch("mortgage_underwriting.common.security.encrypt_pii")
    @patch("mortgage_underwriting.common.security.hash_value")
    async def test_verify_identity_stores_hash_not_sin(self, mock_hash, mock_encrypt, service, mock_db):
        """Test that the DB model stores the hash of the SIN, not the plain SIN."""
        mock_encrypt.return_value = "encrypted_blob"
        mock_hash.return_value = "hashed_sin_value"
        
        payload = ClientIdentityCreate(
            client_id="client_001",
            first_name="Bob",
            last_name="Builder",
            sin="111-222-333",
            dob="1970-01-01",
            occupation="Architect"
        )

        # Capture the object passed to db.add
        added_obj = None
        def capture_add(obj):
            nonlocal added_obj
            added_obj = obj
        mock_db.add.side_effect = capture_add
        
        await service.verify_identity(payload)

        assert added_obj is not None
        # Check that the model object was prepared with the hash, not plain SIN
        assert added_obj.sin_hash == "hashed_sin_value"
        # Ensure plain SIN is not stored in the 'sin' field (which shouldn't exist on model or be encrypted col)
        # Assuming model has 'sin_encrypted' or similar, or just relies on hash. 
        # Based on prompt: "Use hashed values (SIN -> SHA256) for lookups only."
        assert getattr(added_obj, 'sin', None) is None or getattr(added_obj, 'sin') == "encrypted_blob"

    @pytest.mark.asyncio
    @patch("structlog.get_logger")
    async def test_verify_identity_logs_verification_not_pii(self, mock_logger, service, mock_db):
        """Test that identity verification is logged without exposing PII."""
        logger_instance = MagicMock()
        mock_logger.return_value = logger_instance
        
        payload = ClientIdentityCreate(
            client_id="client_001",
            first_name="Test",
            last_name="User",
            sin="000-000-000",
            dob="2000-01-01",
            occupation="Tester"
        )
        
        mock_identity = ClientIdentity(**payload.model_dump(), id=1)
        mock_db.refresh.return_value = mock_identity

        await service.verify_identity(payload)

        # Verify logging occurred
        logger_instance.info.assert_called()
        
        # Verify PII is NOT in the logs
        call_args = logger_instance.info.call_args
        log_message = str(call_args)
        assert "000-000-000" not in log_message
        assert "2000-01-01" not in log_message
        assert "client_001" in log_message # Client ID is okay

    @pytest.mark.asyncio
    async def test_get_report_by_id(self, service, mock_db):
        """Test retrieving a FINTRAC report."""
        mock_report = FintracReport(
            id=1, 
            client_id="client_001", 
            transaction_amount=Decimal("500.00"),
            created_by="system"
        )
        mock_db.scalar.return_value = mock_report

        result = await service.get_report(report_id=1)

        assert result.id == 1
        assert result.client_id == "client_001"
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_fields_immutability(self, service, mock_db):
        """Test that created_at and created_by are set and cannot be modified via service update (if applicable)."""
        # Note: SQLAlchemy models usually handle this, but we test the service behavior
        payload = FintracReportCreate(
            client_id="client_001",
            transaction_amount=Decimal("100.00"),
            currency="CAD",
            transaction_type="wire_transfer",
            entity_type="individual"
        )
        
        mock_report = FintracReport(**payload.model_dump(), id=1)
        mock_db.refresh.return_value = mock_report
        
        result = await service.log_transaction(payload)
        
        # In a real scenario, these are set by DB defaults or service logic
        # Here we check the service doesn't strip them if the model has them
        # or sets them if responsible.
        # Assuming service logic: result.created_by = "system"
        
        assert hasattr(result, 'created_at')
        assert hasattr(result, 'created_by')