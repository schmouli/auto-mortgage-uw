--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from fastapi import FastAPI

# Assuming standard project structure imports
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.underwriting_engine.routes import router as underwriting_router

# Use an in-memory SQLite database for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates a FastAPI AsyncClient with a database session override.
    """
    app = FastAPI()
    app.include_router(underwriting_router, prefix="/api/v1/underwriting", tags=["underwriting"])
    
    # Dependency override
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture
def valid_application_payload() -> dict:
    """
    Standard payload for a successful underwriting scenario.
    """
    return {
        "applicant_id": "test-user-123",
        "loan_amount": "450000.00",
        "property_value": "500000.00",
        "contract_rate": "4.50",
        "amortization_years": 25,
        "annual_income": "120000.00",
        "annual_property_tax": "3500.00",
        "annual_heating_cost": "1200.00",
        "monthly_condo_fees": "0.00",  # Not a condo
        "monthly_debt_payments": "500.00", # Car loan
    }

@pytest.fixture
def high_risk_payload() -> dict:
    """
    Payload designed to fail TDS/GDS regulatory limits.
    """
    return {
        "applicant_id": "high-risk-user",
        "loan_amount": "450000.00",
        "property_value": "500000.00",
        "contract_rate": "4.50",
        "amortization_years": 25,
        "annual_income": "50000.00", # Low income relative to loan
        "annual_property_tax": "5000.00",
        "annual_heating_cost": "2400.00",
        "monthly_condo_fees": "500.00",
        "monthly_debt_payments": "1500.00", # High debt
    }

@pytest.fixture
def high_ltv_payload() -> dict:
    """
    Payload for 95% LTV to test CMHC insurance tiers.
    """
    return {
        "applicant_id": "high-ltv-user",
        "loan_amount": "475000.00",
        "property_value": "500000.00", # 95% LTV
        "contract_rate": "5.00",
        "amortization_years": 25,
        "annual_income": "100000.00",
        "annual_property_tax": "4000.00",
        "annual_heating_cost": "1500.00",
        "monthly_condo_fees": "0.00",
        "monthly_debt_payments": "200.00",
    }
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

# Import paths based on project conventions
from mortgage_underwriting.modules.underwriting_engine.services import UnderwritingService
from mortgage_underwriting.modules.underwriting_engine.exceptions import (
    UnderwritingError,
    RegulatoryLimitExceededError
)

@pytest.mark.unit
class TestUnderwritingService:

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = AsyncMock(spec=AsyncSession)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return UnderwritingService(mock_db)

    # --- Stress Test Logic (OSFI B-20) ---
    def test_calculate_stress_rate_low_contract_rate(self, service):
        """
        Test stress test: contract_rate + 2% < 5.25%.
        Should return 5.25%.
        """
        contract_rate = Decimal("3.00")
        # 3.00 + 2.00 = 5.00 < 5.25 -> Floor is 5.25
        qualifying_rate = service._calculate_qualifying_rate(contract_rate)
        assert qualifying_rate == Decimal("5.25")

    def test_calculate_stress_rate_high_contract_rate(self, service):
        """
        Test stress test: contract_rate + 2% > 5.25%.
        Should return contract_rate + 2%.
        """
        contract_rate = Decimal("5.00")
        # 5.00 + 2.00 = 7.00 > 5.25
        qualifying_rate = service._calculate_qualifying_rate(contract_rate)
        assert qualifying_rate == Decimal("7.00")

    def test_calculate_stress_rate_boundary(self, service):
        """
        Test boundary condition exactly at 3.25%.
        3.25 + 2 = 5.25.
        """
        contract_rate = Decimal("3.25")
        qualifying_rate = service._calculate_qualifying_rate(contract_rate)
        assert qualifying_rate == Decimal("5.25")

    # --- Ratio Calculations (OSFI B-20) ---
    @pytest.mark.asyncio
    async def test_calculate_gds_success(self, service):
        """
        Test GDS Calculation: (Mortgage + Tax + Heat) / Income
        """
        monthly_mortgage = Decimal("2000.00")
        monthly_tax = Decimal("300.00")
        monthly_heat = Decimal("100.00")
        monthly_income = Decimal("8000.00") # Annual 96k

        gds = await service._calculate_gds(monthly_mortgage, monthly_tax, monthly_heat, Decimal("0"), monthly_income)
        
        expected = (2000 + 300 + 100) / 8000
        # (2400 / 8000) = 0.30 -> 30%
        assert gds == Decimal("0.30")

    @pytest.mark.asyncio
    async def test_calculate_gds_exceeds_limit(self, service):
        """
        Test GDS > 39% raises RegulatoryLimitExceededError.
        """
        monthly_mortgage = Decimal("4000.00")
        monthly_tax = Decimal("500.00")
        monthly_heat = Decimal("200.00")
        monthly_income = Decimal("10000.00") # Annual 120k
        
        # (4700 / 10000) = 47% > 39%
        with pytest.raises(RegulatoryLimitExceededError) as exc_info:
            await service._calculate_gds(monthly_mortgage, monthly_tax, monthly_heat, Decimal("0"), monthly_income)
        
        assert "GDS" in str(exc_info.value)
        assert "39%" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calculate_tds_success(self, service):
        """
        Test TDS Calculation: (Mortgage + Tax + Heat + Other Debt) / Income
        """
        monthly_mortgage = Decimal("2000.00")
        monthly_tax = Decimal("300.00")
        monthly_heat = Decimal("100.00")
        other_debt = Decimal("500.00")
        monthly_income = Decimal("8000.00")

        tds = await service._calculate_tds(monthly_mortgage, monthly_tax, monthly_heat, other_debt, Decimal("0"), monthly_income)
        
        # (2000 + 300 + 100 + 500) / 8000 = 2900 / 8000 = 0.3625
        assert tds == Decimal("0.3625")

    @pytest.mark.asyncio
    async def test_calculate_tds_exceeds_limit(self, service):
        """
        Test TDS > 44% raises RegulatoryLimitExceededError.
        """
        monthly_mortgage = Decimal("3000.00")
        monthly_tax = Decimal("400.00")
        monthly_heat = Decimal("150.00")
        other_debt = Decimal("1000.00")
        monthly_income = Decimal("10000.00")
        
        # (4550 / 10000) = 45.5% > 44%
        with pytest.raises(RegulatoryLimitExceededError) as exc_info:
            await service._calculate_tds(monthly_mortgage, monthly_tax, monthly_heat, other_debt, Decimal("0"), monthly_income)
        
        assert "TDS" in str(exc_info.value)
        assert "44%" in str(exc_info.value)

    # --- CMHC Insurance Logic ---
    def test_calculate_ltv_no_insurance(self, service):
        """LTV <= 80% -> No insurance required."""
        ltv = service._calculate_ltv(Decimal("400000"), Decimal("500000"))
        assert ltv == Decimal("0.80")
        assert service._check_insurance_required(ltv) is False

    def test_calculate_ltv_requires_insurance(self, service):
        """LTV > 80% -> Insurance required."""
        ltv = service._calculate_ltv(Decimal("401000"), Decimal("500000"))
        assert ltv == Decimal("0.802")
        assert service._check_insurance_required(ltv) is True

    def test_get_cmhc_premium_tier_1(self, service):
        """80.01% - 85.00% -> 2.80%"""
        ltv = Decimal("0.82")
        premium = service._get_cmhc_premium_rate(ltv)
        assert premium == Decimal("0.0280")

    def test_get_cmhc_premium_tier_2(self, service):
        """85.01% - 90.00% -> 3.10%"""
        ltv = Decimal("0.88")
        premium = service._get_cmhc_premium_rate(ltv)
        assert premium == Decimal("0.0310")

    def test_get_cmhc_premium_tier_3(self, service):
        """90.01% - 95.00% -> 4.00%"""
        ltv = Decimal("0.95")
        premium = service._get_cmhc_premium_rate(ltv)
        assert premium == Decimal("0.0400")

    def test_get_cmhc_premium_invalid_ltv(self, service):
        """LTV > 95% is typically uninsurable for standard CMHC."""
        ltv = Decimal("0.96")
        with pytest.raises(UnderwritingError):
            service._get_cmhc_premium_rate(ltv)

    # --- Mortgage Calculation ---
    @pytest.mark.asyncio
    async def test_calculate_monthly_payment(self, service):
        """
        Test mortgage payment calculation.
        Principal: 450,000
        Rate: 5.25% (Stress rate)
        Term: 25 years (300 months)
        """
        principal = Decimal("450000.00")
        annual_rate = Decimal("0.0525")
        months = 300
        
        # Using standard formula: M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1]
        # i = 0.0525 / 12 = 0.004375
        monthly_payment = await service._calculate_monthly_payment(principal, annual_rate, months)
        
        # Sanity check: Payment should be around 2700
        assert monthly_payment > Decimal("2000.00")
        assert monthly_payment < Decimal("3500.00")

    # --- Full Underwriting Workflow ---
    @pytest.mark.asyncio
    async def test_underwrite_application_approved(self, service, valid_application_payload):
        """
        Happy path: Application passes all checks.
        """
        # Mock the database save to return an object
        mock_result = MagicMock()
        mock_result.id = 1
        # Mock the model creation
        with patch('mortgage_underwriting.modules.underwriting_engine.services.UnderwritingDecision') as MockModel:
            MockModel.return_value = mock_result
            
            result = await service.underwrite(valid_application_payload)
            
            assert result.decision == "APPROVED"
            assert result.gds <= Decimal("0.39")
            assert result.tds <= Decimal("0.44")
            assert result.qualifying_rate == max(
                Decimal(str(valid_application_payload['contract_rate'])) + Decimal("0.02"), 
                Decimal("0.0525")
            )

    @pytest.mark.asyncio
    async def test_underwrite_application_declined_tds(self, service, high_risk_payload):
        """
        Sad path: Application fails TDS check.
        """
        with pytest.raises(RegulatoryLimitExceededError):
            await service.underwrite(high_risk_payload)

    @pytest.mark.asyncio
    async def test_underwrite_application_insurance_calculated(self, service, high_ltv_payload):
        """
        Verify CMHC premium is added to total loan amount if LTV > 80%.
        """
        with patch('mortgage_underwriting.modules.underwriting_engine.services.UnderwritingDecision') as MockModel:
            mock_result = MagicMock()
            mock_result.id = 2
            MockModel.return_value = mock_result
            
            result = await service.underwrite(high_ltv_payload)
            
            # LTV is 95%, so 4.00% premium
            # Loan 475,000 * 0.04 = 19,000 premium
            # Total insurable loan amount calculation check
            assert result.insurance_required is True
            assert result.cmhc_premium_rate == Decimal("0.0400")
            assert result.total_loan_amount > Decimal("475000.00")

    @pytest.mark.asyncio
    async def test_underwrite_invalid_input_negative_income(self, service):
        """
        Test validation logic inside service.
        """
        payload = {
            "annual_income": "-1000.00",
            "loan_amount": "100000.00",
            "property_value": "120000.00"
        }
        # Assuming Pydantic validation happens at route level, 
        # but service might have logic checks too.
        # Here we test if service handles bad data gracefully if it reaches it.
        with pytest.raises(ValueError): # Or specific validation error
             await service.underwrite(payload)
--- integration_tests ---
import pytest
from httpx import AsyncClient
from decimal import Decimal

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_create_underwriting_decision_success(client: AsyncClient, valid_application_payload):
    """
    Integration Test: Successful underwriting flow.
    """
    response = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert "id" in data
    assert data["decision"] == "APPROVED"
    assert data["applicant_id"] == "test-user-123"
    
    # Verify Regulatory Compliance fields are present
    assert "gds" in data
    assert "tds" in data
    assert "qualifying_rate" in data
    assert "insurance_required" in data
    assert "created_at" in data # Audit trail
    
    # Check math roughly
    assert Decimal(data["gds"]) <= Decimal("0.39")
    assert Decimal(data["tds"]) <= Decimal("0.44")

@pytest.mark.asyncio
async def test_create_underwriting_decision_declined(client: AsyncClient, high_risk_payload):
    """
    Integration Test: Application declined due to high TDS.
    API should return 400 Bad Request or specific rejection status with details.
    """
    response = await client.post("/api/v1/underwriting/evaluate", json=high_risk_payload)
    
    # Assuming the API returns 400 when regulatory limits are hit during evaluation
    assert response.status_code == 400
    
    data = response.json()
    assert "detail" in data
    assert "TDS" in data["detail"] or "limit" in data["detail"].lower()

@pytest.mark.asyncio
async def test_create_underwriting_validation_error(client: AsyncClient):
    """
    Integration Test: Input validation failure (Pydantic).
    """
    invalid_payload = {
        "applicant_id": "bad-user",
        "loan_amount": "-50000", # Negative money
        "property_value": "not_a_number"
    }
    
    response = await client.post("/api/v1/underwriting/evaluate", json=invalid_payload)
    
    assert response.status_code == 422 # Unprocessable Entity
    
    errors = response.json()["detail"]
    # Check that field errors are reported
    error_fields = [e["loc"][1] for e in errors]
    assert "loan_amount" in error_fields
    assert "property_value" in error_fields

@pytest.mark.asyncio
async def test_get_underwriting_decision(client: AsyncClient, valid_application_payload):
    """
    Integration Test: Retrieve a stored decision.
    """
    # 1. Create a decision
    create_resp = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
    assert create_resp.status_code == 201
    decision_id = create_resp.json()["id"]
    
    # 2. Retrieve the decision
    get_resp = await client.get(f"/api/v1/underwriting/decisions/{decision_id}")
    
    assert get_resp.status_code == 200
    data = get_resp.json()
    
    assert data["id"] == decision_id
    assert data["applicant_id"] == "test-user-123"
    # Ensure PII is not leaked (SIN/DOB should not be in response if model had them)
    assert "sin" not in data
    assert "date_of_birth" not in data

@pytest.mark.asyncio
async def test_stress_test_logic_endpoint(client: AsyncClient):
    """
    Verify the endpoint returns the correct qualifying rate based on OSFI rules.
    """
    # Low rate case
    payload_low = {
        **valid_application_payload, # defined in conftest, but we redefine here for clarity if needed
        "contract_rate": "3.5", # 3.5 + 2 = 5.5 < 5.25 is False, 5.5 > 5.25. 
                                # Wait, 3.5 + 2 = 5.5. 5.5 > 5.25. Qualifying = 5.5.
    }
    # Correct low case: 3.0 + 2 = 5.0. 5.0 < 5.25. Qualifying = 5.25.
    payload_low["contract_rate"] = "3.0"
    
    resp = await client.post("/api/v1/underwriting/evaluate", json=payload_low)
    assert resp.status_code == 201
    assert Decimal(resp.json()["qualifying_rate"]) == Decimal("0.0525")

    # High rate case
    payload_high = payload_low.copy()
    payload_high["applicant_id"] = "new-user" # unique constraint
    payload_high["contract_rate"] = "6.0" # 6.0 + 2 = 8.0. Qualifying = 8.0.
    
    resp = await client.post("/api/v1/underwriting/evaluate", json=payload_high)
    assert resp.status_code == 201
    assert Decimal(resp.json()["qualifying_rate"]) == Decimal("0.08")

@pytest.mark.asyncio
async def test_cmhc_insurance_tier_endpoint(client: AsyncClient, high_ltv_payload):
    """
    Verify CMHC premium calculation is persisted correctly via API.
    """
    resp = await client.post("/api/v1/underwriting/evaluate", json=high_ltv_payload)
    assert resp.status_code == 201
    
    data = resp.json()
    assert data["insurance_required"] is True
    assert data["ltv"] == "0.95" # 475k / 500k
    assert data["cmhc_premium_rate"] == "0.0400" # 4.00%
    
    # Check total loan amount includes premium
    # 475000 * 1.04 = 494000
    expected_total = Decimal("475000.00") * (Decimal("1.00") + Decimal("0.04"))
    assert Decimal(data["total_loan_amount"]) == expected_total

@pytest.mark.asyncio
async test test_audit_fields_populated(client: AsyncClient, valid_application_payload):
    """
    Verify audit fields (created_at, updated_at) are populated automatically.
    """
    resp = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
    assert resp.status_code == 201
    
    data = resp.json()
    assert "created_at" in data
    assert "updated_at" in data
    # Assuming ISO format strings
    assert data["created_at"] is not None
    assert data["updated_at"] is not None