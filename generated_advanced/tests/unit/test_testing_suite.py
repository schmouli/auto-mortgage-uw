import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.testing_suite.services import ScenarioService
from mortgage_underwriting.modules.testing_suite.models import TestScenario, TestResult
from mortgage_underwriting.modules.testing_suite.exceptions import (
    ScenarioNotFoundError,
    InvalidScenarioConfigError,
    CalculationEngineError
)
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.unit
class TestScenarioService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.get = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_scenario_success(self, mock_db, valid_scenario_payload):
        """Test successful creation of a test scenario."""
        service = ScenarioService(mock_db)
        
        # Mock the return of the added object (simulate refresh)
        mock_scenario = TestScenario(**valid_scenario_payload)
        mock_scenario.id = 1
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)

        result = await service.create(valid_scenario_payload)

        assert result.name == "OSFI Stress Test Scenario A"
        assert result.id == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_scenario_invalid_config_type(self, mock_db):
        """Test that invalid JSON structure in config raises error."""
        service = ScenarioService(mock_db)
        payload = {
            "name": "Bad Scenario",
            "description": "Config is not a dict",
            "config": "just_a_string_instead_of_json"
        }

        with pytest.raises(InvalidScenarioConfigError):
            await service.create(payload)
        
        # Ensure DB transaction was rolled back or not committed
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_scenario_missing_required_fields(self, mock_db):
        """Test validation failure when required fields are missing."""
        service = ScenarioService(mock_db)
        payload = {"description": "Missing name and config"}

        with pytest.raises(ValueError): # Or Pydantic ValidationError depending on implementation
            await service.create(payload)

    @pytest.mark.asyncio
    async def test_get_scenario_by_id_success(self, mock_db):
        """Test retrieving a scenario by ID."""
        service = ScenarioService(mock_db)
        
        mock_scenario = TestScenario(
            id=1,
            name="Scenario 1",
            description="Test",
            config={"rate": "5.0"}
        )
        mock_db.get.return_value = mock_scenario

        result = await service.get_by_id(1)

        assert result is not None
        assert result.name == "Scenario 1"
        mock_db.get.assert_called_once_with(TestScenario, 1)

    @pytest.mark.asyncio
    async def test_get_scenario_by_id_not_found(self, mock_db):
        """Test retrieving a non-existent scenario raises specific error."""
        service = ScenarioService(mock_db)
        mock_db.get.return_value = None

        with pytest.raises(ScenarioNotFoundError):
            await service.get_by_id(999)

    @pytest.mark.asyncio
    async def test_execute_scenario_success(self, mock_db, valid_execution_payload):
        """Test executing a scenario and saving results."""
        service = ScenarioService(mock_db)
        
        # Mock the scenario retrieval
        mock_scenario = TestScenario(
            id=1,
            name="Stress Test",
            description="",
            config={"max_gds": "39.00"}
        )
        mock_db.get.return_value = mock_scenario
        
        # Mock the DB add for the result
        mock_result = TestResult(id=1, scenario_id=1, passed=True, details={})
        mock_db.add.side_effect = lambda x: setattr(x, 'id', 1)
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)

        # Patch the internal calculation logic
        with patch.object(service, '_calculate_ratios', return_value={"gds": Decimal("35.5"), "tds": Decimal("42.0")}):
            result = await service.execute_scenario(1, valid_execution_payload)

        assert result.scenario_id == 1
        assert result.passed is True
        assert mock_db.add.call_count == 1 # Result added
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_scenario_fails_validation(self, mock_db, valid_execution_payload):
        """Test execution fails if calculated ratios exceed limits defined in scenario."""
        service = ScenarioService(mock_db)
        
        mock_scenario = TestScenario(
            id=1,
            name="Strict Test",
            description="",
            config={"max_gds": "30.00"} # Very strict limit
        )
        mock_db.get.return_value = mock_scenario
        
        # Calculation returns high GDS
        with patch.object(service, '_calculate_ratios', return_value={"gds": Decimal("35.5"), "tds": Decimal("42.0")}):
            result = await service.execute_scenario(1, valid_execution_payload)

        assert result.passed is False
        assert "35.5" in str(result.details) # Details should contain breakdown

    @pytest.mark.asyncio
    async def test_execute_scenario_not_found(self, mock_db, valid_execution_payload):
        """Test execution raises error if scenario ID does not exist."""
        service = ScenarioService(mock_db)
        mock_db.get.return_value = None

        with pytest.raises(ScenarioNotFoundError):
            await service.execute_scenario(999, valid_execution_payload)

    @pytest.mark.asyncio
    async def test_execute_scenario_calculation_error(self, mock_db, valid_execution_payload):
        """Test handling of unexpected errors during calculation."""
        service = ScenarioService(mock_db)
        
        mock_scenario = TestScenario(id=1, name="Bad Math", description="", config={})
        mock_db.get.return_value = mock_scenario

        with patch.object(service, '_calculate_ratios', side_effect=Exception("Division by zero")):
            with pytest.raises(CalculationEngineError):
                await service.execute_scenario(1, valid_execution_payload)
        
        # Ensure no commit happened on error
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_list_scenarios(self, mock_db):
        """Test listing all scenarios."""
        service = ScenarioService(mock_db)
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            TestScenario(id=1, name="A", description="", config={}),
            TestScenario(id=2, name="B", description="", config={})
        ]
        mock_db.execute.return_value = mock_result

        results = await service.list_all()
        
        assert len(results) == 2
        assert results[0].name == "A"

    @pytest.mark.asyncio
    async def test_delete_scenario_success(self, mock_db):
        """Test soft delete or hard delete of a scenario."""
        service = ScenarioService(mock_db)
        
        mock_scenario = TestScenario(id=1, name="To Delete", description="", config={})
        mock_db.get.return_value = mock_scenario

        await service.delete(1)
        
        mock_db.delete.assert_called_once_with(mock_scenario)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_scenario_not_found(self, mock_db):
        """Test deleting a non-existent scenario raises error."""
        service = ScenarioService(mock_db)
        mock_db.get.return_value = None

        with pytest.raises(ScenarioNotFoundError):
            await service.delete(999)
        
        mock_db.delete.assert_not_called()