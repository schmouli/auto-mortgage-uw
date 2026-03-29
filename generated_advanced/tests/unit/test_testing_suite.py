```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.testing_suite.services import TestingSuiteService
from mortgage_underwriting.modules.testing_suite.schemas import ScenarioCreate, ScenarioResponse
from mortgage_underwriting.modules.testing_suite.exceptions import CalculationError, InvalidScenarioError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestStressTestCalculator:
    """Tests for the regulatory calculation logic (OSFI B-20)."""

    @pytest.mark.asyncio
    async def test_calculate_qualifying_rate_floor(self):
        """Test that qualifying rate respects the 5.25% floor."""
        service = TestingSuiteService(db=AsyncMock())
        
        # Contract rate 3.0% -> Floor 5.25%
        rate = await service._calculate_qualifying_rate(Decimal("3.0"))
        assert rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_calculate_qualifying_rate_buffer(self):
        """Test that qualifying rate applies contract + 2% buffer."""
        service = TestingSuiteService(db=AsyncMock())
        
        # Contract rate 5.0% -> 5.0 + 2.0 = 7.0%
        rate = await service._calculate_qualifying_rate(Decimal("5.0"))
        assert rate == Decimal("7.0")

    @pytest.mark.asyncio
    async def test_calculate_gds_success(self):
        """Test GDS calculation (Property Tax + Heat + Mortgage Payment) / Income."""
        service = TestingSuiteService(db=AsyncMock())
        
        # Monthly Income: 8000
        # Mortgage: 2000, Tax: 250, Heat: 150
        # GDS = (2400 / 8000) = 0.30 (30%)
        gds = await service._calculate_gds(
            monthly_income=Decimal("8000.00"),
            mortgage_payment=Decimal("2000.00"),
            property_tax=Decimal("250.00"),
            heating_cost=Decimal("150.00")
        )
        assert gds == Decimal("0.30")

    @pytest.mark.asyncio
    async def test_calculate_tds_success(self):
        """Test TDS calculation (GDS Components + Other Debt) / Income."""
        service = TestingSuiteService(db=AsyncMock())
        
        # Monthly Income: 8000
        # Housing Costs: 2400, Other Debt: 500
        # TDS = (2900 / 8000) = 0.3625 (36.25%)
        tds = await service._calculate_tds(
            monthly_income=Decimal("8000.00"),
            housing_costs=Decimal("2400.00"),
            other_debt=Decimal("500.00")
        )
        assert tds == Decimal("0.3625")

    @pytest.mark.asyncio
    async def test_gds_limit_enforcement(self):
        """Test that GDS > 39% raises a regulatory error."""
        service = TestingSuiteService(db=AsyncMock())
        
        # Income 5000, Costs 2000 -> 40%
        with pytest.raises(CalculationError) as exc_info:
            await service._validate_gds_limit(Decimal("0.40"))
        
        assert "GDS exceeds regulatory limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tds_limit_enforcement(self):
        """Test that TDS > 44% raises a regulatory error."""
        service = TestingSuiteService(db=AsyncMock())
        
        # Income 5000, Costs 2300 -> 46%
        with pytest.raises(CalculationError) as exc_info:
            await service._validate_tds_limit(Decimal("0.46"))
        
        assert "TDS exceeds regulatory limit" in str(exc_info.value)


@pytest.mark.unit
class TestScenarioService:
    """Tests for the service layer handling scenario logic."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_scenario_success(self, mock_db, valid_scenario_payload):
        service = TestingSuiteService(mock_db)
        payload = ScenarioCreate(**valid_scenario_payload)
        
        result = await service.create_scenario(payload)
        
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_scenario_missing_field_raises(self, mock_db):
        service = TestingSuiteService(mock_db)
        # Missing required field 'loan_amount'
        invalid_payload = {
            "name": "Test",
            "borrower_annual_income": "100.00"
        }
        
        with pytest.raises(ValueError): # Pydantic validation error
            ScenarioCreate(**invalid_payload)

    @pytest.mark.asyncio
    async def test_run_scenario_passing(self, mock_db, valid_scenario_payload):
        service = TestingSuiteService(mock_db)
        payload = ScenarioCreate(**valid_scenario_payload)
        
        # Mock the scenario object
        mock_scenario = MagicMock()
        mock_scenario.id = 1
        mock_scenario.borrower_annual_income = Decimal(payload.borrower_annual_income)
        mock_scenario.loan_amount = Decimal(payload.loan_amount)
        mock_scenario.contract_rate = Decimal(payload.contract_rate)
        mock_scenario.property_tax_annual = Decimal(payload.property_tax_annual)
        mock_scenario.heating_cost_monthly = Decimal(payload.heating_cost_monthly)
        mock_scenario.other_debt_monthly = Decimal(payload.other_debt_monthly)

        result = await service.run_stress_test(mock_scenario)
        
        assert result.is_approved is True
        assert result.gds_ratio is not None
        assert result.tds_ratio is not None
        assert result.qualifying_rate >= Decimal("5.25")

    @pytest.mark.asyncio
    async def test_run_scenario_failing_tds(self, mock_db, high_risk_scenario_payload):
        service = TestingSuiteService(mock_db)
        payload = ScenarioCreate(**high_risk_scenario_payload)
        
        mock_scenario = MagicMock()
        mock_scenario.id = 2
        mock_scenario.borrower_annual_income = Decimal(payload.borrower_annual_income)
        mock_scenario.loan_amount = Decimal(payload.loan_amount)
        mock_scenario.contract_rate = Decimal(payload.contract_rate)
        mock_scenario.property_tax_annual = Decimal(payload.property_tax_annual)
        mock_scenario.heating_cost_monthly = Decimal(payload.heating_cost_monthly)
        mock_scenario.other_debt_monthly = Decimal(payload.other_debt_monthly)

        with pytest.raises(CalculationError) as exc_info:
            await service.run_stress_test(mock_scenario)
        
        assert "TDS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_scenario_not_found(self, mock_db):
        service = TestingSuiteService(mock_db)
        
        # Mock scalar returning None
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(AppException) as exc_info:
            await service.get_scenario(999)
        
        assert exc_info.value.status_code == 404
```