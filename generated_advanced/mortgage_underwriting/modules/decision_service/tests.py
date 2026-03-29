--- conftest.py ---
```python
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import the module under test structure
from mortgage_underwriting.modules.decision.models import Decision
from mortgage_underwriting.common.database import Base

pytest_plugins = ("pytest_asyncio",)

@pytest.fixture(scope="function")
async def db_session():
    """
    Creates a fresh in-memory SQLite database for each test.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def valid_applicant_payload():
    """
    Provides a payload that should pass standard underwriting (GDS/TDS within limits).
    """
    return {
        "application_id": "test-app-001",
        "loan_amount": Decimal("400000.00"),
        "property_value": Decimal("500000.00"),
        "annual_income": Decimal("120000.00"),
        "mortgage_payment": Decimal("2000.00"),
        "property_tax": Decimal("300.00"),
        "heating_cost": Decimal("150.00"),
        "other_debt": Decimal("500.00"),
        "contract_rate": Decimal("4.50")
    }

@pytest.fixture
def high_tds_payload():
    """
    Payload designed to fail TDS (Total Debt Service) > 44%.
    """
    return {
        "application_id": "test-app-high-tds",
        "loan_amount": Decimal("450000.00"),
        "property_value": Decimal("500000.00"),
        "annual_income": Decimal("80000.00"),
        "mortgage_payment": Decimal("2600.00"),
        "property_tax": Decimal("400.00"),
        "heating_cost": Decimal("150.00"),
        "other_debt": Decimal("1500.00"),
        "contract_rate": Decimal("5.00")
    }
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.decision.services import DecisionService
from mortgage_underwriting.modules.decision.schemas import DecisionRequest, DecisionResponse
from mortgage_underwriting.modules.decision.exceptions import UnderwritingError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestDecisionServiceCalculations:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return DecisionService(mock_db)

    def test_calculate_ltv_success(self, service):
        loan_amount = Decimal("400000.00")
        property_value = Decimal("500000.00")
        
        ltv = service._calculate_ltv(loan_amount, property_value)
        
        assert ltv == Decimal("80.00")

    def test_calculate_ltv_high_risk(self, service):
        loan_amount = Decimal("475000.00")
        property_value = Decimal("500000.00")
        
        ltv = service._calculate_ltv(loan_amount, property_value)
        
        assert ltv == Decimal("95.00")

    def test_calculate_ltv_invalid_zero_value(self, service):
        with pytest.raises(ValueError) as exc_info:
            service._calculate_ltv(Decimal("100000.00"), Decimal("0.00"))
        assert "Property value must be greater than zero" in str(exc_info.value)

    def test_calculate_gds_success(self, service):
        # (2000 + 300 + 150) * 12 = 29400 / 120000 = 0.245 -> 24.5%
        mortgage_payment = Decimal("2000.00")
        property_tax = Decimal("300.00")
        heating = Decimal("150.00")
        annual_income = Decimal("120000.00")
        
        gds = service._calculate_gds(mortgage_payment, property_tax, heating, annual_income)
        
        assert gds == Decimal("24.50")

    def test_calculate_gds_boundary_limit(self, service):
        # GDS Limit is 39%
        # 0.39 * 100000 = 39000 annual housing costs
        # 39000 / 12 = 3250 monthly
        monthly_costs = Decimal("3250.00")
        annual_income = Decimal("100000.00")
        
        gds = service._calculate_gds(monthly_costs, Decimal("0"), Decimal("0"), annual_income)
        
        assert gds == Decimal("39.00")

    def test_calculate_tds_success(self, service):
        # GDS components: 29400
        # Other debt: 500 * 12 = 6000
        # Total debt: 35400 / 120000 = 0.295 -> 29.5%
        annual_housing_costs = Decimal("29400.00")
        other_debt_annual = Decimal("6000.00")
        annual_income = Decimal("120000.00")
        
        tds = service._calculate_tds(annual_housing_costs, other_debt_annual, annual_income)
        
        assert tds == Decimal("29.50")

    def test_calculate_tds_exceeds_limit(self, service):
        annual_housing_costs = Decimal("30000.00")
        other_debt_annual = Decimal("20000.00")
        annual_income = Decimal("100000.00")
        
        tds = service._calculate_tds(annual_housing_costs, other_debt_annual, annual_income)
        
        assert tds == Decimal("50.00")

    def test_determine_cmhc_insurance_no_insurance(self, service):
        # LTV <= 80%
        ltv = Decimal("80.00")
        required, rate = service._determine_cmhc_insurance(ltv)
        assert required is False
        assert rate == Decimal("0.00")

    def test_determine_cmhc_insurance_tier_1(self, service):
        # 80.01% - 85.00% -> 2.80%
        ltv = Decimal("82.50")
        required, rate = service._determine_cmhc_insurance(ltv)
        assert required is True
        assert rate == Decimal("2.80")

    def test_determine_cmhc_insurance_tier_2(self, service):
        # 85.01% - 90.00% -> 3.10%
        ltv = Decimal("88.00")
        required, rate = service._determine_cmhc_insurance(ltv)
        assert required is True
        assert rate == Decimal("3.10")

    def test_determine_cmhc_insurance_tier_3(self, service):
        # 90.01% - 95.00% -> 4.00%
        ltv = Decimal("92.00")
        required, rate = service._determine_cmhc_insurance(ltv)
        assert required is True
        assert rate == Decimal("4.00")

    def test_determine_cmhc_insurance_ltv_too_high(self, service):
        # > 95% is usually uninsurable for standard CMHC
        ltv = Decimal("96.00")
        with pytest.raises(UnderwritingError) as exc_info:
            service._determine_cmhc_insurance(ltv)
        assert "LTV exceeds insurable limit" in str(exc_info.value)

    def test_calculate_qualifying_rate_stress_test_floor(self, service):
        # Contract 4.0 + 2 = 6.0. Floor 5.25. Max is 6.0
        rate = service._calculate_qualifying_rate(Decimal("4.00"))
        assert rate == Decimal("6.00")

    def test_calculate_qualifying_rate_below_floor(self, service):
        # Contract 2.5 + 2 = 4.5. Floor 5.25. Max is 5.25
        rate = service._calculate_qualifying_rate(Decimal("2.50"))
        assert rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_evaluate_application_approved(self, service, valid_applicant_payload):
        payload = DecisionRequest(**valid_applicant_payload)
        
        result = await service.evaluate(payload)
        
        assert result.is_approved is True
        assert result.gds == Decimal("24.50")
        assert result.tds == Decimal("29.50")
        assert result.ltv == Decimal("80.00")
        assert result.insurance_required is False
        service.mock_db.add.assert_called_once()
        service.mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_application_declined_high_tds(self, service, high_tds_payload):
        payload = DecisionRequest(**high_tds_payload)
        
        result = await service.evaluate(payload)
        
        assert result.is_approved is False
        # TDS should be > 44% based on fixture
        assert result.tds > Decimal("44.00") 
        assert "TDS exceeds limit" in result.rejection_reason

    @pytest.mark.asyncio
    async def test_evaluate_application_declined_high_gds(self, service):
        payload_data = {
            "application_id": "test-gds-fail",
            "loan_amount": Decimal("400000.00"),
            "property_value": Decimal("500000.00"),
            "annual_income": Decimal("60000.00"), # Low income relative to costs
            "mortgage_payment": Decimal("2000.00"),
            "property_tax": Decimal("300.00"),
            "heating_cost": Decimal("150.00"),
            "other_debt": Decimal("0.00"),
            "contract_rate": Decimal("4.00")
        }
        payload = DecisionRequest(**payload_data)
        
        result = await service.evaluate(payload)
        
        assert result.is_approved is False
        assert result.gds > Decimal("39.00")
        assert "GDS exceeds limit" in result.rejection_reason

    @pytest.mark.asyncio
    async def test_evaluate_application_with_insurance(self, service):
        # LTV 85% -> Insurance required
        payload_data = {
            "application_id": "test-ins",
            "loan_amount": Decimal("425000.00"),
            "property_value": Decimal("500000.00"),
            "annual_income": Decimal("150000.00"),
            "mortgage_payment": Decimal("2200.00"),
            "property_tax": Decimal("300.00"),
            "heating_cost": Decimal("150.00"),
            "other_debt": Decimal("0.00"),
            "contract_rate": Decimal("4.0")
        }
        payload = DecisionRequest(**payload_data)
        
        result = await service.evaluate(payload)
        
        assert result.is_approved is True
        assert result.insurance_required is True
        assert result.insurance_rate == Decimal("2.80")

    @pytest.mark.asyncio
    async def test_evaluate_application_invalid_input_negative_income(self, service):
        payload_data = {
            "application_id": "test-bad",
            "loan_amount": Decimal("100.00"),
            "property_value": Decimal("200.00"),
            "annual_income": Decimal("-1000.00"),
            "mortgage_payment": Decimal("10.00"),
            "property_tax": Decimal("10.00"),
            "heating_cost": Decimal("10.00"),
            "other_debt": Decimal("0.00"),
            "contract_rate": Decimal("4.0")
        }
        
        with pytest.raises(AppException):
            await service.evaluate(DecisionRequest(**payload_data))
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

from mortgage_underwriting.modules.decision.routes import router
from mortgage_underwriting.modules.decision.models import Decision
from mortgage_underwriting.common.database import get_async_session

# Override the dependency for testing
async def override_get_db():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from mortgage_underwriting.common.database import Base
    
    # Use in-memory DB for integration tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session_maker() as session:
        yield session

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/decision", tags=["decision"])
    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestDecisionAPI:

    async def test_create_decision_success(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "application_id": "int-test-001",
                "loan_amount": "400000.00",
                "property_value": "500000.00",
                "annual_income": "120000.00",
                "mortgage_payment": "2000.00",
                "property_tax": "300.00",
                "heating_cost": "150.00",
                "other_debt": "500.00",
                "contract_rate": "4.5"
            }
            
            response = await client.post("/api/v1/decision/evaluate", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert data["application_id"] == "int-test-001"
            assert data["is_approved"] is True
            assert data["ltv"] == "80.00"
            assert "id" in data
            assert "created_at" in data

    async def test_create_decision_decline_tds(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "application_id": "int-test-decline",
                "loan_amount": "450000.00",
                "property_value": "500000.00",
                "annual_income": "80000.00",
                "mortgage_payment": "2600.00",
                "property_tax": "400.00",
                "heating_cost": "150.00",
                "other_debt": "1500.00",
                "contract_rate": "5.0"
            }
            
            response = await client.post("/api/v1/decision/evaluate", json=payload)
            
            assert response.status_code == 201 # Creation succeeds, but decision is negative
            data = response.json()
            assert data["is_approved"] is False
            assert "TDS" in data["rejection_reason"]

    async def test_create_decision_validation_error(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing required field
            payload = {
                "application_id": "int-test-bad",
                "loan_amount": "400000.00",
                # Missing property_value
                "annual_income": "120000.00",
                "mortgage_payment": "2000.00",
                "property_tax": "300.00",
                "heating_cost": "150.00",
                "other_debt": "500.00",
                "contract_rate": "4.5"
            }
            
            response = await client.post("/api/v1/decision/evaluate", json=payload)
            
            assert response.status_code == 422

    async def test_get_decision_by_id(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create a decision
            payload = {
                "application_id": "int-test-get",
                "loan_amount": "300000.00",
                "property_value": "400000.00",
                "annual_income": "100000.00",
                "mortgage_payment": "1500.00",
                "property_tax": "200.00",
                "heating_cost": "100.00",
                "other_debt": "0.00",
                "contract_rate": "3.0"
            }
            create_resp = await client.post("/api/v1/decision/evaluate", json=payload)
            decision_id = create_resp.json()["id"]

            # 2. Retrieve it
            get_resp = await client.get(f"/api/v1/decision/{decision_id}")
            
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["id"] == decision_id
            assert data["application_id"] == "int-test-get"

    async def test_get_decision_not_found(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/decision/99999")
            assert response.status_code == 404

    async def test_financial_precision_integrity(self, app: FastAPI):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Use specific decimals to ensure no float conversion issues
            payload = {
                "application_id": "int-test-precision",
                "loan_amount": "350000.55", 
                "property_value": "500000.99",
                "annual_income": "87500.12",
                "mortgage_payment": "1850.33",
                "property_tax": "275.44",
                "heating_cost": "125.22",
                "other_debt": "450.10",
                "contract_rate": "4.15"
            }
            
            response = await client.post("/api/v1/decision/evaluate", json=payload)
            assert response.status_code == 201
            
            data = response.json()
            # Verify response contains decimal strings, not floats (which might look like 1850.3300000000002)
            # FastAPI/Pydantic converts Decimals to strings in JSON usually
            assert data["gds"] is not None
            # Check that we can parse back to Decimal without losing precision
            gds_decimal = Decimal(data["gds"])
            assert gds_decimal > Decimal("0.00")
```