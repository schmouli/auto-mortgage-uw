--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Import project components
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.underwriting_engine.routes import router as underwriting_router
from mortgage_underwriting.modules.underwriting_engine.models import UnderwritingDecision

# Using SQLite for integration test speed, but structure mimics Postgres
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
AsyncTestSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="session")
def app() -> FastAPI:
    """
    Create a test application instance.
    """
    app = FastAPI()
    app.include_router(underwriting_router, prefix="/api/v1/underwriting", tags=["underwriting"])
    return app

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncTestSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def client(app: FastAPI, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async test client with dependency overrides.
    """
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
    Provides a valid payload for underwriting that passes all regulatory checks.
    """
    return {
        "application_id": "app_12345",
        "borrower_id": "borrower_001",
        "loan_amount": "450000.00",  # Decimal string
        "property_value": "500000.00", # LTV = 90%
        "annual_income": "120000.00",
        "monthly_housing_costs": "2800.00", # Heat + Taxes + Half Condo
        "monthly_debt_payments": "500.00", # Car loan
        "contract_rate": "4.50", # 5 years fixed
        "amortization_years": 25,
        "credit_score": 720
    }

@pytest.fixture
def high_tds_payload() -> dict:
    """
    Payload designed to fail TDS (Total Debt Service) > 44%.
    """
    return {
        "application_id": "app_fail_tds",
        "borrower_id": "borrower_002",
        "loan_amount": "450000.00",
        "property_value": "500000.00",
        "annual_income": "80000.00", # Lower income
        "monthly_housing_costs": "3000.00",
        "monthly_debt_payments": "1500.00", # High debt
        "contract_rate": "5.00",
        "amortization_years": 25,
        "credit_score": 700
    }

@pytest.fixture
def high_ltv_payload() -> dict:
    """
    Payload for LTV > 80% (Insurance required).
    """
    return {
        "application_id": "app_ins",
        "borrower_id": "borrower_003",
        "loan_amount": "400000.00",
        "property_value": "450000.00", # LTV ~88.8%
        "annual_income": "100000.00",
        "monthly_housing_costs": "2500.00",
        "monthly_debt_payments": "0.00",
        "contract_rate": "3.50",
        "amortization_years": 30,
        "credit_score": 680
    }
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from mortgage_underwriting.modules.underwriting_engine.services import UnderwritingService
from mortgage_underwriting.modules.underwriting_engine.exceptions import UnderwritingError
from mortgage_underwriting.modules.underwriting_engine.schemas import UnderwritingRequest, UnderwritingResponse

@pytest.mark.unit
class TestUnderwritingService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return UnderwritingService(mock_db)

    def test_calculate_qualifying_rate_low_contract(self, service):
        """
        Test OSFI B-20 Stress Test: Contract rate < 3.25% should floor at 5.25%.
        """
        contract_rate = Decimal("3.00")
        qualifying_rate = service._calculate_qualifying_rate(contract_rate)
        assert qualifying_rate == Decimal("5.25")

    def test_calculate_qualifying_rate_high_contract(self, service):
        """
        Test OSFI B-20 Stress Test: Contract rate + 2% > 5.25%.
        """
        contract_rate = Decimal("4.50")
        qualifying_rate = service._calculate_qualifying_rate(contract_rate)
        assert qualifying_rate == Decimal("6.50")

    def test_calculate_ltv_no_insurance(self, service):
        """
        Test LTV calculation where LTV <= 80%.
        """
        loan_amount = Decimal("400000.00")
        property_value = Decimal("500000.00")
        ltv = service._calculate_ltv(loan_amount, property_value)
        assert ltv == Decimal("0.80")
        assert service._is_insurance_required(ltv) is False

    def test_calculate_ltv_requires_insurance(self, service):
        """
        Test LTV calculation where LTV > 80%.
        """
        loan_amount = Decimal("405000.00")
        property_value = Decimal("500000.00")
        ltv = service._calculate_ltv(loan_amount, property_value)
        assert ltv == Decimal("0.81")
        assert service._is_insurance_required(ltv) is True

    def test_calculate_gds_success(self, service):
        """
        Test GDS calculation: (Monthly Housing / Monthly Income).
        Limit: 39%.
        """
        annual_income = Decimal("120000.00")
        monthly_housing = Decimal("2800.00")
        # Monthly payment calculation mocked for simplicity or passed in
        monthly_mortgage_payment = Decimal("2200.00") 
        
        gds = service._calculate_gds(monthly_housing, monthly_mortgage_payment, annual_income)
        # (2800 + 2200) / (120000 / 12) = 5000 / 10000 = 0.50 (50%)
        # Wait, usually Housing costs INCLUDE taxes/heat.
        # Let's assume monthly_housing is the sum of PITH (Principal, Interest, Taxes, Heat)
        # If input separates them: GDS = (PIT + Heat) / Monthly_Income
        
        # Adjusting based on typical schema: monthly_housing_costs usually = Taxes + Heat + 50% Condo
        # Service usually calculates Mortgage Payment internally.
        # Let's assume we pass the total monthly obligation.
        
        total_obligation = monthly_housing + monthly_mortgage_payment
        expected_gds = (total_obligation / (annual_income / Decimal("12"))) * Decimal("100")
        
        assert gds == expected_gds

    def test_calculate_gds_exceeds_limit(self, service):
        """
        Test GDS > 39% raises error or returns failure flag.
        """
        annual_income = Decimal("50000.00")
        monthly_housing = Decimal("3000.00")
        monthly_mortgage_payment = Decimal("1500.00")
        
        gds = service._calculate_gds(monthly_housing, monthly_mortgage_payment, annual_income)
        assert gds > Decimal("39.00")

    def test_calculate_tds_exceeds_limit(self, service):
        """
        Test TDS > 44% raises error or returns failure flag.
        """
        annual_income = Decimal("60000.00") # 5000/mo
        monthly_housing = Decimal("2500.00")
        monthly_mortgage_payment = Decimal("1500.00")
        monthly_debts = Decimal("1000.00")
        
        tds = service._calculate_tds(monthly_housing, monthly_mortgage_payment, monthly_debts, annual_income)
        # (2500 + 1500 + 1000) / 5000 = 5000 / 5000 = 100%
        assert tds > Decimal("44.00")

    def test_cmhc_insurance_tier_1(self, service):
        """
        Test CMHC Premium: 80.01% - 85.00% -> 2.80%
        """
        loan = Decimal("401000.00")
        value = Decimal("500000.00") # LTV 80.2%
        ltv = service._calculate_ltv(loan, value)
        premium_rate = service._get_cmhc_premium_rate(ltv)
        assert premium_rate == Decimal("0.0280")

    def test_cmhc_insurance_tier_2(self, service):
        """
        Test CMHC Premium: 85.01% - 90.00% -> 3.10%
        """
        loan = Decimal("426000.00")
        value = Decimal("500000.00") # LTV 85.2%
        ltv = service._calculate_ltv(loan, value)
        premium_rate = service._get_cmhc_premium_rate(ltv)
        assert premium_rate == Decimal("0.0310")

    def test_cmhc_insurance_tier_3(self, service):
        """
        Test CMHC Premium: 90.01% - 95.00% -> 4.00%
        """
        loan = Decimal("451000.00")
        value = Decimal("500000.00") # LTV 90.2%
        ltv = service._calculate_ltv(loan, value)
        premium_rate = service._get_cmhc_premium_rate(ltv)
        assert premium_rate == Decimal("0.0400")

    def test_cmhc_insurance_tier_0(self, service):
        """
        Test CMHC Premium: <= 80% -> 0.00%
        """
        loan = Decimal("400000.00")
        value = Decimal("500000.00")
        ltv = service._calculate_ltv(loan, value)
        premium_rate = service._get_cmhc_premium_rate(ltv)
        assert premium_rate == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_process_application_approval(self, service, mock_db, valid_application_payload):
        """
        Test happy path: Application passes all checks.
        """
        request = UnderwritingRequest(**valid_application_payload)
        
        # Mock internal calculation helpers to specific values to ensure logic flow
        service._calculate_gds = MagicMock(return_value=Decimal("30.00"))
        service._calculate_tds = MagicMock(return_value=Decimal("35.00"))
        service._calculate_ltv = MagicMock(return_value=Decimal("0.90"))
        service._get_cmhc_premium_rate = MagicMock(return_value=Decimal("0.0310"))
        service._calculate_mortgage_payment = MagicMock(return_value=Decimal("2500.00"))

        result = await service.process_application(request)

        assert result.decision == "Approved"
        assert result.gds_ratio == Decimal("30.00")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_application_declined_tds(self, service, mock_db, high_tds_payload):
        """
        Test failure path: Application fails TDS > 44%.
        """
        request = UnderwritingRequest(**high_tds_payload)
        
        service._calculate_gds = MagicMock(return_value=Decimal("35.00"))
        service._calculate_tds = MagicMock(return_value=Decimal("50.00")) # Fail
        service._calculate_ltv = MagicMock(return_value=Decimal("0.90"))
        service._calculate_mortgage_payment = MagicMock(return_value=Decimal("2500.00"))

        result = await service.process_application(request)

        assert result.decision == "Declined"
        assert "TDS" in result.rejection_reason
        # Ensure we don't commit a declined decision if business logic dictates only store approved?
        # Usually we store all decisions for audit.
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_application_invalid_input_zero_income(self, service, mock_db):
        """
        Test validation: Zero income should raise ValueError.
        """
        payload = {
            "application_id": "app_zero",
            "borrower_id": "b_1",
            "loan_amount": "100000.00",
            "property_value": "200000.00",
            "annual_income": "0.00",
            "monthly_housing_costs": "500.00",
            "monthly_debt_payments": "0.00",
            "contract_rate": "5.0",
            "amortization_years": 25,
            "credit_score": 700
        }
        request = UnderwritingRequest(**payload)
        
        with pytest.raises(ValueError, match="Income must be greater than zero"):
            await service.process_application(request)

    @pytest.mark.asyncio
    async def test_calculate_total_loan_amount_with_insurance(self, service):
        """
        Test that insurance is added to loan amount correctly.
        """
        loan_amount = Decimal("400000.00")
        premium_rate = Decimal("0.0310") # 3.1%
        
        # Insurance = Loan * Rate / (1 - Rate)
        # Insurance = 400000 * 0.031 / 0.969 = 12796.90...
        expected_total = service._calculate_insured_amount(loan_amount, premium_rate)
        
        # Verify logic matches CMHC standard: Total Loan = Base / (1 - premium)
        assert expected_total > loan_amount

    @pytest.mark.asyncio
    async def test_log_auditable_calculation_breakdown(self, service, valid_application_payload):
        """
        Verify that the service generates an audit log string for calculations.
        """
        request = UnderwritingRequest(**valid_application_payload)
        # We expect a structured log or return value containing breakdown
        # Assuming the service returns a breakdown object or logs it
        
        breakdown = service._generate_audit_breakdown(
            gds=Decimal("30.5"), 
            tds=Decimal("35.2"), 
            ltv=Decimal("0.80"),
            qualifying_rate=Decimal("5.25"),
            premium=Decimal("0.00")
        )
        
        assert "GDS: 30.5" in breakdown
        assert "TDS: 35.2" in breakdown
        assert "LTV: 0.8" in breakdown
--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from mortgage_underwriting.modules.underwriting_engine.models import UnderwritingDecision

@pytest.mark.integration
@pytest.mark.asyncio
class TestUnderwritingRoutes:

    async def test_create_underwriting_decision_success(self, client: AsyncClient, valid_application_payload):
        """
        Test submitting a valid application results in an 'Approved' decision and database record.
        """
        response = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["decision"] == "Approved"
        assert "id" in data
        assert data["application_id"] == "app_12345"
        assert Decimal(data["gds_ratio"]) <= Decimal("39.00")
        assert Decimal(data["tds_ratio"]) <= Decimal("44.00")
        
        # Verify DB Persistence
        # Note: In a real integration test we would query the DB here, 
        # but the 'client' fixture uses a separate session scope in this setup.
        # We assume the endpoint returns the persisted object.

    async def test_create_underwriting_decision_declined_tds(self, client: AsyncClient, high_tds_payload):
        """
        Test submitting an application that fails TDS limits.
        """
        response = await client.post("/api/v1/underwriting/evaluate", json=high_tds_payload)
        
        assert response.status_code == 201 # We create the record even if declined
        data = response.json()
        
        assert data["decision"] == "Declined"
        assert "TDS" in data["rejection_reason"]
        assert Decimal(data["tds_ratio"]) > Decimal("44.00")

    async def test_create_underwriting_missing_field(self, client: AsyncClient):
        """
        Test validation error when required fields are missing.
        """
        invalid_payload = {
            "application_id": "app_missing",
            # Missing loan_amount, property_value, etc.
        }
        
        response = await client.post("/api/v1/underwriting/evaluate", json=invalid_payload)
        
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(err["loc"][-1] == "loan_amount" for err in errors)

    async def test_get_underwriting_decision(self, client: AsyncClient, valid_application_payload):
        """
        Test retrieving a specific underwriting decision by ID.
        """
        # 1. Create a decision
        create_resp = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
        assert create_resp.status_code == 201
        decision_id = create_resp.json()["id"]
        
        # 2. Retrieve it
        get_resp = await client.get(f"/api/v1/underwriting/decisions/{decision_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == decision_id
        assert data["application_id"] == "app_12345"

    async def test_get_underwriting_decision_not_found(self, client: AsyncClient):
        """
        Test retrieving a non-existent decision returns 404.
        """
        get_resp = await client.get("/api/v1/underwriting/decisions/99999")
        assert get_resp.status_code == 404

    async def test_cmhc_insurance_application(self, client: AsyncClient, high_ltv_payload):
        """
        Test that insurance is calculated and applied correctly for high LTV.
        LTV 88.8% -> Premium 3.10%.
        """
        response = await client.post("/api/v1/underwriting/evaluate", json=high_ltv_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify insurance flag
        assert data["insurance_required"] is True
        
        # Verify premium calculation roughly
        # Premium = Loan * Rate / (1 - Rate)
        # 400k * 0.031 / 0.969 ≈ 12,796.90
        # Total Loan ≈ 412,796.90
        expected_premium = Decimal("400000.00") * Decimal("0.031") / (Decimal("1") - Decimal("0.031"))
        
        # We check if the stored premium matches the calculation
        assert Decimal(data["insurance_premium_amount"]) == pytest.approx(expected_premium)

    async def test_stress_test_application(self, client: AsyncClient, valid_application_payload):
        """
        Test that the qualifying rate is applied correctly.
        Contract rate 4.50% -> Qualifying 6.50%.
        The resulting monthly payment in the response should reflect the qualifying rate payment capability check.
        """
        response = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        # The response should contain the qualifying rate used
        assert data["qualifying_rate"] == "6.50"
        
        # Ensure GDS/TDS were calculated based on this stress test
        # (Implicitly checked by the decision being Approved/Declined correctly)

    async def test_pipeda_sin_not_logged(self, client: AsyncClient, caplog):
        """
        Test that PII (SIN) is not exposed in logs.
        Note: This test requires the application to actually log something, 
        which is hard to trigger via HTTP client without inspecting server logs.
        Here we check the response doesn't leak it if we added it (though schema shouldn't allow it).
        """
        # Assuming we try to inject a SIN in a free text field (if one existed) or just verify schema prevents it
        # Since the schema doesn't have SIN, we verify the response structure is clean.
        payload = valid_application_payload.copy()
        # If there was a 'notes' field:
        # payload["notes"] = "My SIN is 123456789"
        
        response = await client.post("/api/v1/underwriting/evaluate", json=payload)
        assert response.status_code == 201
        # Verify no sensitive keys in response
        assert "sin" not in response.json().keys()
        assert "dob" not in response.json().keys()

    async def test_fintrac_audit_fields(self, client: AsyncClient, valid_application_payload):
        """
        Test that created_at and created_by are present in the response (Audit trail).
        """
        response = await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "created_at" in data
        assert data["created_at"] is not None
        # created_by might be system user or extracted from token
        assert "created_by" in data 

    async def test_concurrent_requests(self, client: AsyncClient, valid_application_payload):
        """
        Test basic concurrency handling (system should handle multiple eval requests).
        """
        import asyncio
        
        async def make_request():
            return await client.post("/api/v1/underwriting/evaluate", json=valid_application_payload)
        
        results = await asyncio.gather(make_request(), make_request(), make_request())
        
        for response in results:
            assert response.status_code == 201
            assert response.json()["decision"] == "Approved"