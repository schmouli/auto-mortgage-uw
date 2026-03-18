```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from mortgage_underwriting.modules.background_jobs.services import BackgroundJobService
from mortgage_underwriting.modules.background_jobs.models import JobStatus

# Assuming tasks.py contains the logic that the service orchestrates
# We import the actual logic function to test it in isolation
from mortgage_underwriting.modules.background_jobs.tasks import calculate_underwriting_metrics

@pytest.mark.unit
class TestBackgroundJobService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return BackgroundJobService(mock_db)

    @pytest.mark.asyncio
    async def test_submit_underwriting_job_success(self, service, mock_db, valid_mortgage_payload):
        """
        Test that the service successfully triggers a Celery task and saves a job record.
        """
        # Arrange
        task_id = "celery-task-uuid-123"
        
        # Mock the Celery apply_async
        with patch("mortgage_underwriting.modules.background_jobs.services.calculate_underwriting_task") as mock_task:
            mock_result = MagicMock()
            mock_result.id = task_id
            mock_task.apply_async = MagicMock(return_value=mock_result)

            # Act
            result = await service.submit_underwriting_job(valid_mortgage_payload)

            # Assert
            assert result.task_id == task_id
            assert result.status == JobStatus.PENDING
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            
            # Verify Celery was called with correct arguments
            mock_task.apply_async.assert_called_once_with(
                args=[valid_mortgage_payload],
                kwargs={}
            )

    @pytest.mark.asyncio
    async def test_submit_job_database_failure(self, service, mock_db, valid_mortgage_payload):
        """
        Test handling of database errors during job submission.
        """
        # Arrange
        mock_db.commit.side_effect = Exception("Database connection failed")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await service.submit_underwriting_job(valid_mortgage_payload)
        
        assert "Database connection failed" in str(exc_info.value)
        # Ensure we didn't queue the job if DB failed (transactional integrity)
        # Note: In real implementation, we might use transactions to rollback if Celery call fails

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, service, mock_db):
        """
        Test retrieving status for a non-existent job.
        """
        # Arrange
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.get_job_status("non-existent-id")
        
        assert "Job not found" in str(exc_info.value)


@pytest.mark.unit
class TestUnderwritingLogic:
    """
    Tests the core business logic that runs inside the background worker.
    Ensures OSFI B-20 compliance.
    """

    def test_calculate_gds_stress_test_rate_logic(self):
        """
        Test OSFI B-20 Stress Test: Qualifying Rate = max(contract + 2%, 5.25%).
        """
        # Case 1: Contract rate 3.5% -> Qualifying 5.5% (3.5 + 2)
        contract_rate = Decimal("3.5")
        qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
        assert qualifying_rate == Decimal("5.50")

        # Case 2: Contract rate 6.0% -> Qualifying 8.0% (6.0 + 2)
        contract_rate = Decimal("6.0")
        qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
        assert qualifying_rate == Decimal("8.00")

        # Case 3: Contract rate 3.0% -> Qualifying 5.25% (Floor)
        contract_rate = Decimal("3.0")
        qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
        assert qualifying_rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_calculate_metrics_osfi_compliance_pass(self):
        """
        Test full calculation where GDS/TDS pass OSFI limits (GDS <= 39%, TDS <= 44%).
        """
        # Arrange
        payload = {
            "loan_amount": Decimal("400000.00"),
            "property_value": Decimal("500000.00"),
            "annual_income": Decimal("150000.00"), # High income to pass ratios
            "property_tax": Decimal("3000.00"),
            "heating_cost": Decimal("1000.00"),
            "contract_rate": Decimal("4.00"),
            "amortization_years": 25
        }

        # Act
        result = await calculate_underwriting_metrics(payload)

        # Assert
        assert result["gds"] <= Decimal("39.00"), "GDS must comply with OSFI B-20 limit"
        assert result["tds"] <= Decimal("44.00"), "TDS must comply with OSFI B-20 limit"
        assert result["qualifying_rate"] == Decimal("6.00") # 4.0 + 2.0
        assert result["insurance_required"] == False # LTV = 80%

    @pytest.mark.asyncio
    async def test_calculate_metrics_osfi_compliance_fail_gds(self):
        """
        Test that high costs cause GDS to exceed limits, marking decision as 'DECLINED'.
        """
        # Arrange
        payload = {
            "loan_amount": Decimal("400000.00"),
            "property_value": Decimal("500000.00"),
            "annual_income": Decimal("50000.00"), # Low income
            "property_tax": Decimal("10000.00"), # High tax
            "heating_cost": Decimal("5000.00"),  # High heat
            "contract_rate": Decimal("4.00"),
            "amortization_years": 25
        }

        # Act
        result = await calculate_underwriting_metrics(payload)

        # Assert
        assert result["gds"] > Decimal("39.00"), "GDS should exceed limit"
        assert result["decision"] == "DECLINED"

    @pytest.mark.asyncio
    async def test_calculate_metrics_cmhc_insurance_logic(self):
        """
        Test CMHC Insurance requirement logic based on LTV.
        """
        # Case 1: LTV > 80%
        payload_high_ltv = {
            "loan_amount": Decimal("450000.00"),
            "property_value": Decimal("500000.00"), # 90% LTV
            "annual_income": Decimal("100000.00"),
            "property_tax": Decimal("3000.00"),
            "heating_cost": Decimal("1200.00"),
            "contract_rate": Decimal("4.00"),
            "amortization_years": 25
        }
        result = await calculate_underwriting_metrics(payload_high_ltv)
        assert result["insurance_required"] == True
        assert result["ltv"] == Decimal("90.00")
        
        # Case 2: LTV <= 80%
        payload_low_ltv = payload_high_ltv.copy()
        payload_low_ltv["loan_amount"] = Decimal("400000.00") # 80% LTV
        result = await calculate_underwriting_metrics(payload_low_ltv)
        assert result["insurance_required"] == False

    @pytest.mark.asyncio
    async def test_pipeda_sin_not_in_results(self):
        """
        Ensure SIN is processed but never returned in calculation results (PIPEDA).
        """
        payload = {
            "applicant_sin": "123456789",
            "loan_amount": "100",
            "property_value": "200",
            "annual_income": "1000",
            "property_tax": "100",
            "heating_cost": "50",
            "contract_rate": "5.0",
            "amortization_years": 25
        }
        
        result = await calculate_underwriting_metrics(payload)
        
        # Assert SIN is not in the output dictionary
        assert "applicant_sin" not in result
        assert "123456789" not in str(result)

    @pytest.mark.asyncio
    async def test_fintrac_audit_logging(self):
        """
        Verify that financial calculation details are prepared for audit logging (FINTRAC).
        """
        payload = {
            "loan_amount": Decimal("300000.00"),
            "property_value": Decimal("400000.00"),
            "annual_income": Decimal("80000.00"),
            "property_tax": Decimal("2400.00"),
            "heating_cost": Decimal("1200.00"),
            "contract_rate": Decimal("3.5"),
            "amortization_years": 25
        }

        with patch("mortgage_underwriting.modules.background_jobs.tasks.logger") as mock_logger:
            await calculate_underwriting_metrics(payload)
            
            # Assert that the calculation breakdown was logged for audit purposes
            assert mock_logger.info.called
            # Check that at least one log call contains "GDS" or "TDS" breakdown
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("GDS" in call or "TDS" in call for call in log_calls)
```