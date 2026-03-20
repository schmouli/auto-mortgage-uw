--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# WARNING: The 'testing_suite' module structure is assumed based on project conventions
# and OSFI B-20 requirements. Ensure module paths match actual implementation.
from mortgage_underwriting.common.config import settings
from mortgage_underwriting.modules.testing_suite.routes import router

# Use in-memory SQLite for integration tests to ensure isolation and speed
# In a real CI/CD pipeline, this might point to a test Postgres instance.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_test_session_maker = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session(event_loop) -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture to create a fresh database session for each test.
    Creates tables on setup and drops them on teardown.
    """
    async with engine.begin() as conn:
        # Import Base here to avoid circular deps if models import fixtures
        from mortgage_underwriting.modules.testing_suite.models import Base
        await conn.run_sync(Base.metadata.create_all)

    async with async_test_session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def mock_db_session() -> AsyncMock:
    """
    Provides a mock AsyncSession for unit tests where DB interaction is faked.
    """
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()
    return mock_session

@pytest.fixture
def app() -> FastAPI:
    """
    Fixture to create a test FastAPI app instance including the testing_suite router.
    """
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/testing-suite", tags=["Testing Suite"])
    return test_app

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture to provide an HTTPX AsyncClient for integration testing.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

# --- Data Fixtures ---

@pytest.fixture
def valid_stress_test_payload() -> dict:
    """
    Returns a payload that should pass OSFI B-20 stress test logic.
    Assumptions:
    - Contract Rate: 4.5%
    - Qualifying Rate: max(4.5 + 2, 5.25) = 6.5%
    - Monthly Payment calculated at 6.5%.
    - Income sufficient to cover GDS/TDS.
    """
    return {
        "applicant_id": "test-app-001",
        "loan_amount": "450000.00",
        "property_value": "500000.00", # 90% LTV
        "contract_rate": "4.5",
        "amortization_years": 25,
        "gross_annual_income": "150000.00",
        "property_tax_annual": "3000.00",
        "heating_cost_monthly": "150.00",
        "other_debt_monthly": "500.00"
    }

@pytest.fixture
def high_gds_payload() -> dict:
    """
    Returns a payload designed to fail the GDS test (>39%).
    Low income relative to housing costs.
    """
    return {
        "applicant_id": "test-app-fail-gds",
        "loan_amount": "400000.00",
        "property_value": "450000.00",
        "contract_rate": "3.0", # Qual rate 5.25%
        "amortization_years": 25,
        "gross_annual_income": "40000.00", # Very low income
        "property_tax_annual": "4000.00",
        "heating_cost_monthly": "200.00",
        "other_debt_monthly": "0.00"
    }

@pytest.fixture
def high_tds_payload() -> dict:
    """
    Returns a payload designed to fail the TDS test (>44%).
    High other debt.
    """
    return {
        "applicant_id": "test-app-fail-tds",
        "loan_amount": "300000.00",
        "property_value": "350000.00",
        "contract_rate": "4.0", # Qual rate 6.0%
        "amortization_years": 25,
        "gross_annual_income": "80000.00",
        "property_tax_annual": "2500.00",
        "heating_cost_monthly": "150.00",
        "other_debt_monthly": "2500.00" # Significant debt load
    }
```

--- unit_tests ---
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

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

# Import models to verify DB state
from mortgage_underwriting.modules.testing_suite.models import StressTestResult

@pytest.mark.integration
class TestStressTestEndpoints:
    """
    Integration tests for the Testing Suite API endpoints.
    Tests the full request/response cycle and database persistence.
    """

    @pytest.mark.asyncio
    async def test_post_stress_test_success(self, client: AsyncClient, valid_stress_test_payload, db_session):
        """
        Test a successful stress test submission via API.
        Verifies HTTP 201, response structure, and DB insertion.
        """
        response = await client.post("/api/v1/testing-suite/run", json=valid_stress_test_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["applicant_id"] == "test-app-001"
        assert data["is_passed"] is True
        assert Decimal(data["qualifying_rate"]) == Decimal("6.50")
        assert Decimal(data["gds_ratio"]) <= Decimal("39.00")
        assert Decimal(data["tds_ratio"]) <= Decimal("44.00")
        assert "created_at" in data

        # Verify Database Persistence
        stmt = select(StressTestResult).where(StressTestResult.id == data["id"])
        result = await db_session.execute(stmt)
        db_record = result.scalar_one()
        
        assert db_record is not None
        assert db_record.applicant_id == "test-app-001"
        assert db_record.is_passed is True

    @pytest.mark.asyncio
    async def test_post_stress_test_fail_gds(self, client: AsyncClient, high_gds_payload, db_session):
        """
        Test stress test resulting in failure due to high GDS.
        """
        response = await client.post("/api/v1/testing-suite/run", json=high_gds_payload)
        
        assert response.status_code == 201 # We accept the result even if failed
        data = response.json()
        
        assert data["is_passed"] is False
        assert Decimal(data["gds_ratio"]) > Decimal("39.00")

    @pytest.mark.asyncio
    async def test_post_stress_test_validation_error(self, client: AsyncClient):
        """
        Test API validation with malformed payload (missing fields).
        """
        incomplete_payload = {
            "applicant_id": "test"
            # Missing all required financial fields
        }
        
        response = await client.post("/api/v1/testing-suite/run", json=incomplete_payload)
        
        assert response.status_code == 422
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_post_stress_test_invalid_type(self, client: AsyncClient, valid_stress_test_payload):
        """
        Test API validation with incorrect data types (string instead of number).
        """
        bad_payload = valid_stress_test_payload.copy()
        bad_payload["loan_amount"] = "not-a-number"
        
        response = await client.post("/api/v1/testing-suite/run", json=bad_payload)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_stress_test_history(self, client: AsyncClient, valid_stress_test_payload, db_session):
        """
        Test retrieving history for a specific applicant.
        """
        # 1. Create a record
        post_resp = await client.post("/api/v1/testing-suite/run", json=valid_stress_test_payload)
        assert post_resp.status_code == 201
        applicant_id = post_resp.json()["applicant_id"]

        # 2. Retrieve history
        get_resp = await client.get(f"/api/v1/testing-suite/history/{applicant_id}")
        
        assert get_resp.status_code == 200
        history = get_resp.json()
        assert isinstance(history, list)
        assert len(history) >= 1
        assert history[0]["applicant_id"] == applicant_id

    @pytest.mark.asyncio
    async def test_get_stress_test_result_by_id(self, client: AsyncClient, valid_stress_test_payload):
        """
        Test retrieving a specific stress test result by ID.
        """
        # 1. Create
        post_resp = await client.post("/api/v1/testing-suite/run", json=valid_stress_test_payload)
        result_id = post_resp.json()["id"]

        # 2. Get by ID
        get_resp = await client.get(f"/api/v1/testing-suite/{result_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == result_id
        assert "qualifying_rate" in data

    @pytest.mark.asyncio
    async def test_get_stress_test_not_found(self, client: AsyncClient):
        """
        Test retrieving a non-existent result returns 404.
        """
        get_resp = await client.get("/api/v1/testing-suite/99999")
        assert get_resp.status_code == 404
        assert "detail" in get_resp.json()

    @pytest.mark.asyncio
    async def test_osfi_compliance_logging(self, client: AsyncClient, valid_stress_test_payload, caplog):
        """
        Test that the calculation breakdown is logged for audit purposes (OSFI B-20).
        Note: This depends on the implementation using structlog/logger.
        """
        # Assuming the endpoint logs the calculation details
        with caplog.at_level("INFO"):
            response = await client.post("/api/v1/testing-suite/run", json=valid_stress_test_payload)
            assert response.status_code == 201
            
            # Check if any log contains calculation keywords
            # This is a basic check; real implementation might check specific JSON log output
            logs = [record.message for record in caplog.records]
            assert any("qualifying_rate" in msg.lower() for msg in logs) or \
                   any("gds" in msg.lower() for msg in logs)

    @pytest.mark.asyncio
    async def test_security_no_pii_in_response(self, client: AsyncClient, valid_stress_test_payload):
        """
        Ensure PII (SIN, DOB) is not leaked in the response.
        Assuming the payload might contain PII (though schema minimizes it),
        ensure it doesn't echo back if it wasn't explicitly requested or if handled securely.
        """
        # Add a hypothetical SIN field (if schema allowed it, though PIPEDA says minimize)
        # Since our defined schema in conftest doesn't have SIN, we check existing fields.
        response = await client.post("/api/v1/testing-suite/run", json=valid_stress_test_payload)
        data = response.json()
        
        # Ensure no sensitive internal IDs or raw data leaks
        # Just a structural check for this example
        assert "sin" not in data
        assert "dob" not in data
```