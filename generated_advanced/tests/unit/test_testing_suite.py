```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import the module under test
from mortgage_underwriting.modules.testing_suite.services import StressTestService
from mortgage_underwriting.modules.testing_suite.models import StressTestResult
from mortgage_underwriting.modules.testing_suite.schemas import StressTestRequest, StressTestResponse
from mortgage_underwriting.modules.testing_suite.exceptions import StressTestFailedError

# Import common exceptions
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestStressTestService:
    """
    Unit tests for StressTestService business logic.
    Focuses on OSFI B-20 calculations: Qualifying Rate, GDS, TDS.
    """

    @pytest.fixture
    def service(self, mock_db_session):
        return StressTestService(mock_db_session)

    @pytest.mark.asyncio
    async def test_calculate_qualifying_rate_contract_plus_two(self, service):
        """
        Test Qualifying Rate when contract_rate + 2% > 5.25%.
        """
        contract_rate = Decimal("5.00")
        qualifying_rate = service.calculate_qualifying_rate(contract_rate)
        # max(5.00 + 2.00, 5.25) = 7.00
        assert qualifying_rate == Decimal("7.00")

    @pytest.mark.asyncio
    async def test_calculate_qualifying_rate_floor(self, service):
        """
        Test Qualifying Rate when contract_rate + 2% < 5.25% (Floor applies).
        """
        contract_rate = Decimal("3.00")
        qualifying_rate = service.calculate_qualifying_rate(contract_rate)
        # max(3.00 + 2.00, 5.25) = 5.25
        assert qualifying_rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_calculate_qualifying_rate_boundary(self, service):
        """
        Test Qualifying Rate at exact boundary 3.25%.
        """
        contract_rate = Decimal("3.25")
        qualifying_rate = service.calculate_qualifying_rate(contract_rate)
        # max(3.25 + 2.00, 5.25) = 5.25
        assert qualifying_rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_calculate_monthly_payment_precision(self, service):
        """
        Ensure mortgage payment calculation uses Decimal and avoids float drift.
        """
        principal = Decimal("100000")
        annual_rate = Decimal("0.06") # 6%
        months = 12
        
        # Simple interest for calculation verification: 100000 * 0.06 / 12 = 500
        # (Assuming service implements a standard formula, we check return type and non-zero)
        payment = service.calculate_monthly_payment(principal, annual_rate, months)
        assert isinstance(payment, Decimal)
        assert payment > Decimal("0.00")

    @pytest.mark.asyncio
    async def test_calculate_gds_success(self, service):
        """
        Test GDS calculation: (Mortgage + Tax + Heat) / Income
        """
        monthly_payment = Decimal("2000.00")
        monthly_tax = Decimal("300.00")
        monthly_heat = Decimal("150.00")
        monthly_income = Decimal("8000.00")
        
        gds = service.calculate_gds(monthly_payment, monthly_tax, monthly_heat, monthly_income)
        expected = (Decimal("2450.00") / Decimal("8000.00")) * Decimal("100")
        # 30.625%
        assert gds == expected.quantize(Decimal("0.01"))

    @pytest.mark.asyncio
    async def test_calculate_tds_success(self, service):
        """
        Test TDS calculation: (Mortgage + Tax + Heat + Debt) / Income
        """
        monthly_payment = Decimal("2000.00")
        monthly_tax = Decimal("300.00")
        monthly_heat = Decimal("150.00")
        monthly_debt = Decimal("500.00")
        monthly_income = Decimal("8000.00")

        tds = service.calculate_tds(monthly_payment, monthly_tax, monthly_heat, monthly_debt, monthly_income)
        expected = (Decimal("2950.00") / Decimal("8000.00")) * Decimal("100")
        # 36.875%
        assert tds == expected.quantize(Decimal("0.01"))

    @pytest.mark.asyncio
    async def test_run_stress_test_happy_path(self, service, valid_stress_test_payload):
        """
        Test successful run of stress test where GDS/TDS are within limits.
        """
        # Prepare DTO
        request = StressTestRequest(**valid_stress_test_payload)
        
        # Mock the DB save
        mock_result = StressTestResult(
            id=1,
            applicant_id=request.applicant_id,
            qualifying_rate=Decimal("6.50"), # 4.5 + 2
            gds_ratio=Decimal("30.00"),
            tds_ratio=Decimal("35.00"),
            is_passed=True,
            created_at=datetime.utcnow()
        )
        service.db.add = MagicMock()
        service.db.commit = AsyncMock()
        service.db.refresh = AsyncMock(return_value=mock_result)

        response = await service.run_stress_test(request)

        assert response.is_passed is True
        assert response.qualifying_rate == Decimal("6.50")
        assert response.gds_ratio <= Decimal("39.00")
        assert response.tds_ratio <= Decimal("44.00")
        service.db.add.assert_called_once()
        service.db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_stress_test_gds_failure(self, service, high_gds_payload):
        """
        Test stress test failure when GDS exceeds 39%.
        """
        request = StressTestRequest(**high_gds_payload)
        
        # We expect the service to calculate and return a failed result, 
        # or raise an exception depending on implementation choice. 
        # Assuming it returns a result object with is_passed=False for audit purposes.
        
        mock_result = StressTestResult(
            id=2,
            applicant_id=request.applicant_id,
            qualifying_rate=Decimal("5.25"),
            gds_ratio=Decimal("45.00"), # Simulated high GDS
            tds_ratio=Decimal("45.00"),
            is_passed=False,
            created_at=datetime.utcnow()
        )
        
        service.db.add = MagicMock()
        service.db.commit = AsyncMock()
        service.db.refresh = AsyncMock(return_value=mock_result)

        response = await service.run_stress_test(request)

        assert response.is_passed is False
        assert response.gds_ratio > Decimal("39.00")

    @pytest.mark.asyncio
    async def test_run_stress_test_tds_failure(self, service, high_tds_payload):
        """
        Test stress test failure when TDS exceeds 44%.
        """
        request = StressTestRequest(**high_tds_payload)
        
        mock_result = StressTestResult(
            id=3,
            applicant_id=request.applicant_id,
            qualifying_rate=Decimal("6.00"),
            gds_ratio=Decimal("35.00"),
            tds_ratio=Decimal("50.00"), # Simulated high TDS
            is_passed=False,
            created_at=datetime.utcnow()
        )
        
        service.db.add = MagicMock()
        service.db.commit = AsyncMock()
        service.db.refresh = AsyncMock(return_value=mock_result)

        response = await service.run_stress_test(request)

        assert response.is_passed is False
        assert response.tds_ratio > Decimal("44.00")

    @pytest.mark.asyncio
    async def test_invalid_input_negative_income(self, service):
        """
        Test that service validates input and raises error for negative income.
        """
        payload = {
            "applicant_id": "bad",
            "loan_amount": "100000",
            "property_value": "100000",
            "contract_rate": "4.0",
            "amortization_years": 25,
            "gross_annual_income": "-50000", # Invalid
            "property_tax_annual": "1000",
            "heating_cost_monthly": "100",
            "other_debt_monthly": "0"
        }
        
        with pytest.raises(ValueError) as excinfo:
            await service.run_stress_test(StressTestRequest(**payload))
        
        assert "income" in str(excinfo.value).lower()

    @pytest.mark.asyncio
    async def test_zero_amortization_raises_error(self, service):
        """
        Test that zero amortization is handled.
        """
        payload = {
            "applicant_id": "bad",
            "loan_amount": "100000",
            "property_value": "100000",
            "contract_rate": "4.0",
            "amortization_years": 0, # Invalid
            "gross_annual_income": "50000",
            "property_tax_annual": "1000",
            "heating_cost_monthly": "100",
            "other_debt_monthly": "0"
        }
        
        with pytest.raises(ValueError):
            await service.run_stress_test(StressTestRequest(**payload))
```