```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.fintrac.services import FintracService
from mortgage_underwriting.modules.fintrac.models import FintracTransaction
from mortgage_underwriting.modules.fintrac.schemas import FintracTransactionCreate
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFintracService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = MagicMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return FintracService(mock_db)

    @pytest.mark.asyncio
    async def test_create_transaction_success(self, service, mock_db):
        payload = FintracTransactionCreate(
            applicant_id="app-123",
            amount=Decimal("5000.00"),
            currency="CAD",
            transaction_type="deposit",
            entity_type="individual"
        )

        result = await service.create_transaction(payload)

        assert result.applicant_id == "app-123"
        assert result.amount == Decimal("5000.00")
        assert result.is_large_cash_reportable is False
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_large_cash_transaction_flagged(self, service, mock_db):
        # Boundary test: Exactly 10000.00
        payload_boundary = FintracTransactionCreate(
            applicant_id="app-999",
            amount=Decimal("10000.00"),
            currency="CAD",
            transaction_type="cash_deposit",
            entity_type="individual"
        )
        result_boundary = await service.create_transaction(payload_boundary)
        assert result_boundary.is_large_cash_reportable is True

        # Test: Above 10000.00
        payload_high = FintracTransactionCreate(
            applicant_id="app-888",
            amount=Decimal("15000.50"),
            currency="CAD",
            transaction_type="cash_deposit",
            entity_type="individual"
        )
        result_high = await service.create_transaction(payload_high)
        assert result_high.is_large_cash_reportable is True

    @pytest.mark.asyncio
    async def test_create_non_cash_transaction_not_flagged(self, service, mock_db):
        # Even if > 10k, if it's not cash/physical, it might not be flagged as "Large Cash" 
        # depending on specific business logic, but here we test the cash flag specifically
        payload = FintracTransactionCreate(
            applicant_id="app-777",
            amount=Decimal("50000.00"),
            currency="CAD",
            transaction_type="wire_transfer", # Not cash
            entity_type="business"
        )
        result = await service.create_transaction(payload)
        # Assuming logic only flags cash transactions > 10k for this specific flag
        assert result.is_large_cash_reportable is False

    @pytest.mark.asyncio
    async def test_create_transaction_invalid_amount_raises_error(self, service, mock_db):
        with pytest.raises(ValueError) as exc_info:
            payload = FintracTransactionCreate(
                applicant_id="app-123",
                amount=Decimal("-500.00"),
                currency="CAD",
                transaction_type="deposit",
                entity_type="individual"
            )
            await service.create_transaction(payload)
        
        assert "Amount must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_transaction_zero_amount_raises_error(self, service, mock_db):
        with pytest.raises(ValueError) as exc_info:
            payload = FintracTransactionCreate(
                applicant_id="app-123",
                amount=Decimal("0.00"),
                currency="CAD",
                transaction_type="deposit",
                entity_type="individual"
            )
            await service.create_transaction(payload)
        
        assert "Amount must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_audit_fields_set_on_creation(self, service, mock_db):
        payload = FintracTransactionCreate(
            applicant_id="app-123",
            amount=Decimal("100.00"),
            currency="CAD",
            transaction_type="deposit",
            entity_type="individual"
        )

        result = await service.create_transaction(payload)

        assert result.created_at is not None
        assert result.created_by is not None # Assuming service sets this, e.g., "system" or user context
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_log_identity_verification(self, service, mock_db):
        with patch("mortgage_underwriting.modules.fintrac.services.logger") as mock_logger:
            payload = FintracTransactionCreate(
                applicant_id="app-123",
                amount=Decimal("100.00"),
                currency="CAD",
                transaction_type="deposit",
                entity_type="individual"
            )
            
            await service.create_transaction(payload)
            
            # Verify logging occurred for FINTRAC compliance
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args
            assert "Identity verification" in str(call_args) or "FINTRAC" in str(call_args)

    @pytest.mark.asyncio
    async def test_get_transaction_by_id(self, service, mock_db):
        # Setup mock result
        mock_transaction = FintracTransaction(
            id=1,
            applicant_id="app-123",
            amount=Decimal("100.00"),
            currency="CAD",
            transaction_type="deposit",
            entity_type="individual"
        )
        
        # Mock the execute/scalar chain for get
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_transaction
        mock_db.execute.return_value = mock_result

        result = await service.get_transaction(1)

        assert result is not None
        assert result.id == 1
        assert result.applicant_id == "app-123"

    @pytest.mark.asyncio
    async def test_get_transaction_not_found_returns_none(self, service, mock_db):
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.get_transaction(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_db_integrity_error_handling(self, service, mock_db):
        mock_db.commit.side_effect = IntegrityError("mock", "mock", "mock")
        
        payload = FintracTransactionCreate(
            applicant_id="app-123",
            amount=Decimal("100.00"),
            currency="CAD",
            transaction_type="deposit",
            entity_type="individual"
        )

        with pytest.raises(AppException) as exc_info:
            await service.create_transaction(payload)
        
        assert "Database error" in str(exc_info.value)
```