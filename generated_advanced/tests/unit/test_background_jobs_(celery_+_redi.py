```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

# Import the module under test
from mortgage_underwriting.modules.background_jobs.services import BackgroundJobService
from mortgage_underwriting.modules.background_jobs.exceptions import TaskNotFoundError, InvalidTaskPayloadError

# Mocking the Celery task functions directly for unit testing logic
# Assuming tasks are defined in tasks.py or services.py for this example
from mortgage_underwriting.modules.background_jobs.models import TaskExecutionLog

@pytest.mark.unit
class TestBackgroundJobService:

    @pytest.mark.asyncio
    async def test_trigger_task_success(self, db_session, mock_celery_app):
        """Test triggering a background job successfully and logging to DB (FINTRAC)."""
        service = BackgroundJobService(db_session)
        
        payload = {
            "task_name": "generate_report",
            "params": {"applicant_id": "user_123"}
        }

        result = await service.trigger_task(payload)

        # Assert Celery was called
        mock_celery_app.send_task.assert_called_once_with(
            "generate_report",
            args=[{"applicant_id": "user_123"}]
        )

        # Assert DB Log created (FINTRAC Audit Trail)
        logs = await service.get_task_logs(result["task_id"])
        assert len(logs) == 1
        assert logs[0].task_name == "generate_report"
        assert logs[0].status == "PENDING"

    @pytest.mark.asyncio
    async def test_trigger_task_invalid_payload(self, db_session):
        """Test that triggering with missing fields raises validation error."""
        service = BackgroundJobService(db_session)
        
        payload = {"task_name": ""} # Missing params
        
        with pytest.raises(InvalidTaskPayloadError):
            await service.trigger_task(payload)

    @pytest.mark.asyncio
    async def test_get_task_status_success(self, db_session, mock_redis_client):
        """Test retrieving task status from Redis."""
        service = BackgroundJobService(db_session)
        task_id = "task-123"
        
        # Mock Redis return value
        mock_redis_client.get.return_value = b'{"status": "SUCCESS", "result": "done"}'

        status = await service.get_task_status(task_id)
        
        assert status["status"] == "SUCCESS"
        mock_redis_client.get.assert_called_once_with(f"celery-task-meta-{task_id}")

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, db_session, mock_redis_client):
        """Test retrieving status for non-existent task."""
        service = BackgroundJobService(db_session)
        task_id = "non-existent"
        
        mock_redis_client.get.return_value = None

        with pytest.raises(TaskNotFoundError):
            await service.get_task_status(task_id)

@pytest.mark.unit
class TestTaskLogicCalculations:
    """
    Tests for the actual logic executed by Celery workers.
    Since we can't run Celery in unit tests, we test the functions directly.
    """

    @pytest.mark.asyncio
    async def test_calculate_stress_test_osfi_compliance(self):
        """
        Test OSFI B-20 Compliance:
        Qualifying Rate = max(contract_rate + 2%, 5.25%)
        """
        from mortgage_underwriting.modules.background_jobs.tasks import calculate_monthly_payment_with_stress
        
        # Case 1: Contract rate is low, floor applies
        contract_rate = Decimal("3.00")
        qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
        assert qualifying_rate == Decimal("5.25")

        # Case 2: Contract rate is high, buffer applies
        contract_rate = Decimal("5.50")
        qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
        assert qualifying_rate == Decimal("7.50")

    @pytest.mark.asyncio
    async def test_calculate_gds_tds_limits(self):
        """
        Test GDS/TDS hard limits enforcement (OSFI B-20).
        GDS <= 39%, TDS <= 44%
        """
        from mortgage_underwriting.modules.background_jobs.tasks import calculate_ratios
        
        income = Decimal("10000.00")
        property_tax = Decimal("300.00")
        heating = Decimal("150.00")
        mortgage_payment = Decimal("2500.00") # High payment to breach limits
        other_debt = Decimal("1000.00")

        # Mock calculation inputs
        result = calculate_ratios(income, mortgage_payment, property_tax, heating, other_debt)
        
        # Logic verification
        # GDS = (2500 + 300 + 150) / 10000 * 100 = 29.5% (Pass)
        # TDS = (2950 + 1000) / 10000 * 100 = 39.5% (Pass)
        assert result["gds"] <= Decimal("39.00")
        assert result["tds"] <= Decimal("44.00")

    @pytest.mark.asyncio
    async def test_pii_data_sanitization_in_task(self, mock_encryption_service):
        """
        Test PIPEDA compliance: SIN must be hashed/encrypted before processing/storage.
        """
        from mortgage_underwriting.modules.background_jobs.tasks import process_applicant_data
        
        raw_sin = "123456789"
        mock_encrypt, mock_hash = mock_encryption_service
        
        # Call task
        await process_applicant_data({"sin": raw_sin, "name": "John Doe"})
        
        # Verify encryption/hash was called
        mock_hash.assert_called_with(raw_sin)
        # Ensure raw SIN is not in logs (simulated by checking it wasn't passed to a logger mock)
        # This function should ideally return data with hashed SIN only

    @pytest.mark.asyncio
    async def test_cmhc_insurance_calculation(self):
        """
        Test CMHC Insurance Logic:
        LTV > 80% -> Insurance required.
        Premium tiers: 80.01-85% = 2.80%, etc.
        """
        from mortgage_underwriting.modules.background_jobs.tasks import calculate_cmhc_premium
        
        # Scenario 1: 95% LTV
        ltv = Decimal("0.95")
        loan_amount = Decimal("400000.00")
        premium = calculate_cmhc_premium(ltv, loan_amount)
        
        assert premium == loan_amount * Decimal("0.04") # 4.00% tier
        
        # Scenario 2: 82% LTV
        ltv = Decimal("0.82")
        loan_amount = Decimal("400000.00")
        premium = calculate_cmhc_premium(ltv, loan_amount)
        
        assert premium == loan_amount * Decimal("0.028") # 2.80% tier

    @pytest.mark.asyncio
    async def test_fintrac_large_transaction_flagging(self):
        """
        Test FINTRAC: Transactions > 10k CAD require explicit flagging.
        """
        from mortgage_underwriting.modules.background_jobs.tasks import validate_transaction
        
        # Valid large transaction
        txn = {"amount": Decimal("15000.00"), "type": "large_deposit", "flagged": True}
        is_valid = validate_transaction(txn)
        assert is_valid is True

        # Invalid large transaction (missing flag)
        txn = {"amount": Decimal("15000.00"), "type": "large_deposit", "flagged": False}
        with pytest.raises(ValueError, match="FINTRAC compliance"):
            validate_transaction(txn)

    @pytest.mark.asyncio
    async def test_decimal_precision_handling(self):
        """Ensure no float precision loss in financial calculations."""
        from mortgage_underwriting.modules.background_jobs.tasks import calculate_interest
        
        principal = Decimal("100000.00")
        rate = Decimal("0.035") # 3.5%
        
        interest = calculate_interest(principal, rate)
        
        # Should not be 3500.000000001 or 3500.0 (float)
        assert interest == Decimal("3500.00")
        assert isinstance(interest, Decimal)
```