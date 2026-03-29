--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Assuming the Base is imported from common.database in the actual project
# For the sake of the test environment, we define a local one or import if available
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.testing_suite.routes import router as testing_suite_router
from mortgage_underwriting.modules.testing_suite.models import TestScenario

# pytest-asyncio configuration
pytest_plugins = ("pytest_asyncio",)

# Database URL for in-memory SQLite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest.fixture(scope="function")
def app() -> Generator[FastAPI, None, None]:
    app = FastAPI()
    app.include_router(testing_suite_router, prefix="/api/v1/testing-suite", tags=["testing-suite"])
    yield app

@pytest.fixture(scope="function")
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_scenario_payload():
    return {
        "name": "OSFI Standard Stress Test",
        "description": "Test case for B-20 compliance",
        "borrower_annual_income": "96000.00",
        "property_value": "500000.00",
        "loan_amount": "400000.00",
        "contract_rate": "4.50",
        "property_tax_annual": "3000.00",
        "heating_cost_monthly": "150.00",
        "other_debt_monthly": "500.00"
    }

@pytest.fixture
def high_risk_scenario_payload():
    return {
        "name": "High TDS Scenario",
        "description": "TDS exceeding 44%",
        "borrower_annual_income": "50000.00",
        "property_value": "600000.00",
        "loan_amount": "550000.00",
        "contract_rate": "5.00",
        "property_tax_annual": "5000.00",
        "heating_cost_monthly": "200.00",
        "other_debt_monthly": "2000.00"
    }
```

--- unit_tests ---
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

--- integration_tests ---
```python
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.testing_suite.models import TestScenario

@pytest.mark.integration
@pytest.mark.asyncio
class TestScenarioEndpoints:
    """Tests for the API endpoints of the Testing Suite module."""

    async def test_create_scenario_endpoint_success(self, client: AsyncClient, valid_scenario_payload):
        response = await client.post("/api/v1/testing-suite/scenarios", json=valid_scenario_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == valid_scenario_payload["name"]
        assert data["borrower_annual_income"] == valid_scenario_payload["borrower_annual_income"]
        assert "created_at" in data

    async def test_create_scenario_endpoint_invalid_data(self, client: AsyncClient):
        invalid_payload = {
            "name": "Bad Data",
            "borrower_annual_income": "not_a_number"
        }
        
        response = await client.post("/api/v1/testing-suite/scenarios", json=invalid_payload)
        
        assert response.status_code == 422 # Unprocessable Entity

    async def test_get_scenario_endpoint(self, client: AsyncClient, valid_scenario_payload, db_session):
        # Create a scenario directly in DB to test GET
        scenario = TestScenario(
            name=valid_scenario_payload["name"],
            description=valid_scenario_payload["description"],
            borrower_annual_income=Decimal(valid_scenario_payload["borrower_annual_income"]),
            property_value=Decimal(valid_scenario_payload["property_value"]),
            loan_amount=Decimal(valid_scenario_payload["loan_amount"]),
            contract_rate=Decimal(valid_scenario_payload["contract_rate"]),
            property_tax_annual=Decimal(valid_scenario_payload["property_tax_annual"]),
            heating_cost_monthly=Decimal(valid_scenario_payload["heating_cost_monthly"]),
            other_debt_monthly=Decimal(valid_scenario_payload["other_debt_monthly"])
        )
        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        response = await client.get(f"/api/v1/testing-suite/scenarios/{scenario.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == scenario.id
        assert Decimal(data["loan_amount"]) == scenario.loan_amount

    async def test_get_scenario_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/testing-suite/scenarios/99999")
        assert response.status_code == 404

    async def test_run_stress_test_workflow(self, client: AsyncClient, valid_scenario_payload):
        # 1. Create Scenario
        create_resp = await client.post("/api/v1/testing-suite/scenarios", json=valid_scenario_payload)
        assert create_resp.status_code == 201
        scenario_id = create_resp.json()["id"]

        # 2. Run Stress Test
        run_resp = await client.post(f"/api/v1/testing-suite/scenarios/{scenario_id}/run")
        assert run_resp.status_code == 200
        
        result = run_resp.json()
        assert "gds_ratio" in result
        assert "tds_ratio" in result
        assert "qualifying_rate" in result
        assert "is_approved" in result
        
        # Verify OSFI B-20 logic result (should pass with valid payload)
        assert result["is_approved"] is True
        
        # Verify qualifying rate logic (Contract 4.5 + 2 = 6.5 > 5.25)
        assert Decimal(result["qualifying_rate"]) == Decimal("6.50")

    async def test_run_stress_test_fails_regulatory_check(self, client: AsyncClient, high_risk_scenario_payload):
        # 1. Create High Risk Scenario
        create_resp = await client.post("/api/v1/testing-suite/scenarios", json=high_risk_scenario_payload)
        assert create_resp.status_code == 201
        scenario_id = create_resp.json()["id"]

        # 2. Run Stress Test
        run_resp = await client.post(f"/api/v1/testing-suite/scenarios/{scenario_id}/run")
        
        # Expecting a 400 or specific error code for regulatory failure
        assert run_resp.status_code == 400
        data = run_resp.json()
        assert "detail" in data
        assert "limit" in data["detail"].lower()

    async def test_list_scenarios_pagination(self, client: AsyncClient, valid_scenario_payload, db_session):
        # Create multiple scenarios
        for i in range(3):
            scenario = TestScenario(
                name=f"Scenario {i}",
                description="Batch test",
                borrower_annual_income=Decimal("100000.00"),
                property_value=Decimal("400000.00"),
                loan_amount=Decimal("300000.00"),
                contract_rate=Decimal("3.00"),
                property_tax_annual=Decimal("2000.00"),
                heating_cost_monthly=Decimal("100.00"),
                other_debt_monthly=Decimal("0.00")
            )
            db_session.add(scenario)
        await db_session.commit()

        response = await client.get("/api/v1/testing-suite/scenarios?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 3
```