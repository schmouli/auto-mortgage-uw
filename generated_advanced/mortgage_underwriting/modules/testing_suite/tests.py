--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
import structlog

from mortgage_underwriting.common.config import settings
from mortgage_underwriting.common.database import Base

# Using SQLite for integration tests as per convention for speed/isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture to create a new database session for a test.
    Creates tables and drops them at the end of the test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app() -> FastAPI:
    """
    Fixture to create the FastAPI app instance.
    We import the router from the module under test.
    """
    from mortgage_underwriting.modules.testing_suite.routes import router
    
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/testing-suite", tags=["Testing Suite"])
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture to create an AsyncClient for making requests to the app.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_logger():
    """Fixture to capture structlog calls."""
    with patch("structlog.get_logger") as mock:
        logger = mock.return_value
        logger.info = MagicMock()
        logger.error = MagicMock()
        logger.warning = MagicMock()
        yield logger

# --- Unit Test Fixtures ---

@pytest.fixture
def valid_scenario_payload():
    return {
        "name": "OSFI Stress Test Scenario A",
        "description": "Tests GDS/TDS limits at qualifying rate + 2%",
        "config": {
            "qualifying_rate_buffer": "2.00",
            "max_gds": "39.00",
            "max_tds": "44.00"
        }
    }

@pytest.fixture
def valid_execution_payload():
    return {
        "applicant_income": Decimal("95000.00"),
        "property_value": Decimal("500000.00"),
        "loan_amount": Decimal("400000.00"),
        "heating_cost": Decimal("150.00"),
        "property_tax": Decimal("3000.00")
    }
--- unit_tests ---
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
--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.testing_suite.models import TestScenario, TestResult


@pytest.mark.integration
class TestScenarioRoutes:

    @pytest.mark.asyncio
    async def test_create_scenario_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test API endpoint to create a new test scenario."""
        payload = {
            "name": "CMHC Standard",
            "description": "Standard CMHC LTV calculation test",
            "config": {
                "min_downpayment_percent": "5.00",
                "ltv_threshold_insurance": "80.00"
            }
        }

        response = await client.post("/api/v1/testing-suite/scenarios", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["name"] == "CMHC Standard"
        assert "created_at" in data

        # Verify DB state
        stmt = select(TestScenario).where(TestScenario.name == "CMHC Standard")
        result = await db_session.execute(stmt)
        scenario = result.scalar_one()
        assert scenario is not None

    @pytest.mark.asyncio
    async def test_create_scenario_invalid_payload(self, client: AsyncClient):
        """Test API validation with missing fields."""
        payload = {
            "name": "Incomplete Scenario"
            # Missing description and config
        }

        response = await client.post("/api/v1/testing-suite/scenarios", json=payload)

        assert response.status_code == 422 # Unprocessable Entity

    @pytest.mark.asyncio
    async def test_get_scenario_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test retrieving a specific scenario."""
        # Setup: Create a scenario directly in DB
        scenario = TestScenario(
            name="Retrieval Test",
            description="Test GET",
            config={"rate": "5.5"}
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        response = await client.get(f"/api/v1/testing-suite/scenarios/{scenario.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == scenario.id
        assert data["name"] == "Retrieval Test"

    @pytest.mark.asyncio
    async def test_get_scenario_not_found(self, client: AsyncClient):
        """Test retrieving a non-existent scenario."""
        response = await client.get("/api/v1/testing-suite/scenarios/99999")
        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_execute_scenario_endpoint_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test running a scenario via API."""
        # Setup
        scenario = TestScenario(
            name="Execution Test",
            description="",
            config={"max_gds": "39.00", "max_tds": "44.00"}
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        exec_payload = {
            "applicant_income": "85000.00",
            "property_value": "450000.00",
            "loan_amount": "360000.00",
            "heating_cost": "120.00",
            "property_tax": "2500.00"
        }

        response = await client.post(
            f"/api/v1/testing-suite/scenarios/{scenario.id}/execute",
            json=exec_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert "result_id" in data
        assert "passed" in data
        assert "breakdown" in data
        
        # Verify result stored in DB
        stmt = select(TestResult).where(TestResult.scenario_id == scenario.id)
        result = await db_session.execute(stmt)
        db_result = result.scalar_one()
        assert db_result is not None

    @pytest.mark.asyncio
    async def test_execute_scenario_endpoint_failure_case(self, client: AsyncClient, db_session: AsyncSession):
        """Test running a scenario that fails business rules (e.g., High TDS)."""
        scenario = TestScenario(
            name="Strict TDS",
            description="",
            config={"max_tds": "30.00"} # Very low limit
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        exec_payload = {
            "applicant_income": "50000.00",
            "property_value": "400000.00",
            "loan_amount": "380000.00", # High debt load
            "heating_cost": "200.00",
            "property_tax": "4000.00"
        }

        response = await client.post(
            f"/api/v1/testing-suite/scenarios/{scenario.id}/execute",
            json=exec_payload
        )

        assert response.status_code == 200 # Execution succeeded, but logic failed
        data = response.json()
        assert data["passed"] is False
        assert "TDS" in data["breakdown"] # Expect details about why it failed

    @pytest.mark.asyncio
    async def test_list_scenarios_pagination(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing scenarios with pagination parameters."""
        # Create multiple scenarios
        for i in range(5):
            db_session.add(TestScenario(name=f"Scenario {i}", description="", config={}))
        await db_session.commit()

        response = await client.get("/api/v1/testing-suite/scenarios?limit=2&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5

    @pytest.mark.asyncio
    async def test_delete_scenario_endpoint(self, client: AsyncClient, db_session: AsyncSession):
        """Test deleting a scenario."""
        scenario = TestScenario(
            name="Delete Me",
            description="",
            config={}
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        response = await client.delete(f"/api/v1/testing-suite/scenarios/{scenario.id}")
        assert response.status_code == 204 # No Content

        # Verify deletion
        response_get = await client.get(f"/api/v1/testing-suite/scenarios/{scenario.id}")
        assert response_get.status_code == 404

    @pytest.mark.asyncio
    async def test_input_validation_decimal_precision(self, client: AsyncClient, db_session: AsyncSession):
        """Ensure financial inputs handle Decimal precision correctly."""
        scenario = TestScenario(name="Precision Test", description="", config={})
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        exec_payload = {
            "applicant_income": "100000.999", # High precision
            "property_value": "500000.005",
            "loan_amount": "400000.001",
            "heating_cost": "100.555",
            "property_tax": "2000.123"
        }

        response = await client.post(
            f"/api/v1/testing-suite/scenarios/{scenario.id}/execute",
            json=exec_payload
        )

        # Should accept valid numeric strings, system handles rounding/truncation internally
        # or returns 400 if strictly 2 decimals required. Assuming flexible input -> internal rounding.
        assert response.status_code == 200
        
        # Check breakdown values are Decimals
        data = response.json()
        assert "breakdown" in data

# Imports required for integration tests
from sqlalchemy import select