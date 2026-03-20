--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Numeric, DateTime, func, Boolean
from datetime import datetime
from fastapi import FastAPI

# Import the module under test
from mortgage_underwriting.modules.decision_service.routes import router as decision_router
from mortgage_underwriting.common.config import settings

# Test Database Setup (SQLite in-memory for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
AsyncTestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

# Simplified Model for testing DB interactions
class MortgageApplicationModel(Base):
    __tablename__ = "mortgage_applications"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    applicant_id: Mapped[str] = mapped_column(String, nullable=False)
    loan_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    property_value: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    annual_income: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    annual_property_tax: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=Decimal("0.00"))
    annual_heating_cost: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=Decimal("1200.00"))
    other_debts: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=Decimal("0.00"))
    contract_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    amortization_years: Mapped[int] = mapped_column(default=25)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncTestingSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(decision_router, prefix="/api/v1/decision", tags=["decision"])
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_application_payload() -> dict:
    return {
        "applicant_id": "test-user-123",
        "loan_amount": "400000.00",
        "property_value": "500000.00",
        "annual_income": "100000.00",
        "annual_property_tax": "3000.00",
        "annual_heating_cost": "1200.00",
        "other_debts": "500.00",
        "contract_rate": "4.50",
        "amortization_years": 25
    }

@pytest.fixture
def high_risk_payload() -> dict:
    return {
        "applicant_id": "test-user-999",
        "loan_amount": "450000.00",
        "property_value": "500000.00", # 90% LTV
        "annual_income": "50000.00",   # Low income
        "annual_property_tax": "4000.00",
        "annual_heating_cost": "1500.00",
        "other_debts": "1000.00",
        "contract_rate": "5.00",
        "amortization_years": 25
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.decision_service.services import DecisionService
from mortgage_underwriting.modules.decision_service.schemas import ApplicationCreate, DecisionResponse
from mortgage_underwriting.modules.decision_service.exceptions import UnderwritingError

@pytest.mark.unit
class TestDecisionServiceCalculations:
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_db):
        return DecisionService(mock_db)

    def test_calculate_monthly_payment(self, service):
        # Principal: 400k, Rate: 5% (annual), Term: 25 years (300 months)
        # Formula: M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # i = 0.05 / 12 = 0.004166...
        principal = Decimal("400000.00")
        annual_rate = Decimal("0.05")
        months = 300
        
        payment = service._calculate_monthly_payment(principal, annual_rate, months)
        
        # Expected approx 2338.36
        assert payment > Decimal("2338.00")
        assert payment < Decimal("2339.00")

    def test_calculate_ltv_success(self, service):
        loan_amount = Decimal("400000.00")
        property_value = Decimal("500000.00")
        
        ltv = service.calculate_ltv(loan_amount, property_value)
        
        assert ltv == Decimal("0.80")

    def test_calculate_ltv_zero_property_raises(self, service):
        with pytest.raises(ValueError, match="Property value must be positive"):
            service.calculate_ltv(Decimal("100000"), Decimal("0"))

    def test_determine_qualifying_rate_osfi_low_contract(self, service):
        # Contract 3.0% + 2% = 5.0%. Min is 5.25%. Result: 5.25%
        rate = service.determine_qualifying_rate(Decimal("0.03"))
        assert rate == Decimal("0.0525")

    def test_determine_qualifying_rate_osfi_high_contract(self, service):
        # Contract 5.0% + 2% = 7.0%. Min is 5.25%. Result: 7.0%
        rate = service.determine_qualifying_rate(Decimal("0.05"))
        assert rate == Decimal("0.07")

    def test_calculate_gds_within_limit(self, service):
        # Income 100k/yr. 
        # Monthly Payment ~2338.36 (at qualifying rate)
        # Tax 250/mo, Heat 100/mo. Total Monthly Debt ~ 2688.
        # GDS = (2688 * 12) / 100000 = 32.2%
        annual_income = Decimal("100000.00")
        monthly_payment = Decimal("2338.36")
        monthly_tax = Decimal("250.00")
        monthly_heat = Decimal("100.00")
        
        gds = service.calculate_gds(monthly_payment, monthly_tax, monthly_heat, annual_income)
        
        assert gds == Decimal("0.322") # Approx based on inputs
        assert gds <= Decimal("0.39")

    def test_calculate_tds_exceeds_limit(self, service):
        # High TDS scenario
        annual_income = Decimal("50000.00")
        monthly_payment = Decimal("2000.00")
        monthly_tax = Decimal("400.00")
        monthly_heat = Decimal("150.00")
        other_debts = Decimal("1000.00")
        
        # Total Monthly = 3550. Annual = 42600. TDS = 42600 / 50000 = 85.2%
        tds = service.calculate_tds(monthly_payment, monthly_tax, monthly_heat, other_debts, annual_income)
        
        assert tds > Decimal("0.44")

    def test_get_cmhc_insurance_rate_none_required(self, service):
        # LTV <= 80%
        rate = service.get_cmhc_insurance_rate(Decimal("0.80"))
        assert rate == Decimal("0.00")

    def test_get_cmhc_insurance_rate_tier_1(self, service):
        # 80.01% - 85%
        rate = service.get_cmhc_insurance_rate(Decimal("0.82"))
        assert rate == Decimal("0.0280")

    def test_get_cmhc_insurance_rate_tier_2(self, service):
        # 85.01% - 90%
        rate = service.get_cmhc_insurance_rate(Decimal("0.88"))
        assert rate == Decimal("0.0310")

    def test_get_cmhc_insurance_rate_tier_3(self, service):
        # 90.01% - 95%
        rate = service.get_cmhc_insurance_rate(Decimal("0.92"))
        assert rate == Decimal("0.0400")

    def test_get_cmhc_insurance_rate_invalid_ltv(self, service):
        # LTV > 95% (Uninsurable)
        with pytest.raises(ValueError, match="LTV exceeds maximum insurable limit"):
            service.get_cmhc_insurance_rate(Decimal("0.96"))

@pytest.mark.unit
class TestDecisionServiceLogic:
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_db):
        return DecisionService(mock_db)

    @pytest.mark.asyncio
    async def test_render_decision_approved(self, service):
        # Setup inputs that pass all criteria
        payload = ApplicationCreate(
            applicant_id="u1",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("120000.00"),
            annual_property_tax=Decimal("3000.00"),
            annual_heating_cost=Decimal("1200.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("0.04"),
            amortization_years=25
        )
        
        result = await service.render_decision(payload)
        
        assert result.decision == "Approved"
        assert result.gds <= Decimal("0.39")
        assert result.tds <= Decimal("0.44")
        assert result.insurance_required is False

    @pytest.mark.asyncio
    async def test_render_decision_rejected_high_tds(self, service):
        # Setup inputs with high debts
        payload = ApplicationCreate(
            applicant_id="u2",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("60000.00"), # Low income
            annual_property_tax=Decimal("3000.00"),
            annual_heating_cost=Decimal("1200.00"),
            other_debts=Decimal("2000.00"), # High other debts
            contract_rate=Decimal("0.04"),
            amortization_years=25
        )
        
        result = await service.render_decision(payload)
        
        assert result.decision == "Rejected"
        assert "TDS" in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_render_decision_insurance_required(self, service):
        # LTV 85%
        payload = ApplicationCreate(
            applicant_id="u3",
            loan_amount=Decimal("425000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("150000.00"),
            annual_property_tax=Decimal("3000.00"),
            annual_heating_cost=Decimal("1200.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("0.04"),
            amortization_years=25
        )
        
        result = await service.render_decision(payload)
        
        assert result.decision == "Approved" # Assuming income is high enough
        assert result.insurance_required is True
        assert result.insurance_premium_rate == Decimal("0.0280")

    @pytest.mark.asyncio
    async def test_render_decision_stress_test_application(self, service):
        # Verify that the qualifying rate logic is applied, not just contract rate
        # Contract 3.0%, Qualifying 5.25%. Payment at 5.25% is higher.
        payload = ApplicationCreate(
            applicant_id="u4",
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("85000.00"), # Tight margin at 5.25%
            annual_property_tax=Decimal("3000.00"),
            annual_heating_cost=Decimal("1200.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("0.03"), # Low rate
            amortization_years=25
        )
        
        result = await service.render_decision(payload)
        
        # Service should calculate payment based on 5.25%
        # 400k @ 5.25% = ~2400/mo
        # 2400 + 250 + 100 = 2750
        # 2750 * 12 = 33000
        # 33000 / 85000 = 38.8% (Passes GDS)
        
        assert result.decision == "Approved"

--- integration_tests ---
import pytest
from httpx import AsyncClient
from decimal import Decimal

from mortgage_underwriting.modules.decision_service.models import MortgageApplication
from sqlalchemy import select

@pytest.mark.integration
@pytest.mark.asyncio
class TestDecisionEndpoints:

    async def test_evaluate_application_success(self, client: AsyncClient, valid_application_payload):
        response = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["decision"] in ["Approved", "Rejected", "Refer"]
        assert "id" in data
        assert "gds" in data
        assert "tds" in data
        assert "ltv" in data
        assert "created_at" in data
        assert "updated_at" in data
        
        # Verify Decimal precision is preserved in JSON (usually string or float, checking type conversion)
        # Pydantic/FastAPI converts Decimals to floats in JSON by default, but logic uses Decimals.
        assert isinstance(data["gds"], float) or isinstance(data["gds"], str)

    async def test_evaluate_application_rejection_high_ltv(self, client: AsyncClient):
        # LTV > 95%
        payload = {
            "applicant_id": "high-ltv",
            "loan_amount": "480000.00",
            "property_value": "500000.00",
            "annual_income": "200000.00",
            "annual_property_tax": "3000.00",
            "annual_heating_cost": "1200.00",
            "other_debts": "0.00",
            "contract_rate": "4.00",
            "amortization_years": 25
        }
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "Rejected"
        assert "LTV" in data["rejection_reasons"]

    async def test_evaluate_application_validation_error_missing_field(self, client: AsyncClient):
        payload = {
            "applicant_id": "missing-data",
            "loan_amount": "400000.00",
            # Missing property_value
            "annual_income": "100000.00",
            "contract_rate": "4.00",
            "amortization_years": 25
        }
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        
        assert response.status_code == 422
        assert "detail" in response.json()

    async def test_evaluate_application_creates_db_record(self, client: AsyncClient, valid_application_payload, db_session):
        response = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        assert response.status_code == 200
        
        app_id = response.json()["id"]
        
        # Verify in DB
        result = await db_session.execute(select(MortgageApplication).where(MortgageApplication.id == app_id))
        db_record = result.scalar_one_or_none()
        
        assert db_record is not None
        assert db_record.applicant_id == valid_application_payload["applicant_id"]
        assert db_record.loan_amount == Decimal(valid_application_payload["loan_amount"])
        assert db_record.created_at is not None

    async def test_evaluate_application_osfi_stress_test_compliance(self, client: AsyncClient, db_session):
        # Scenario: Low contract rate (3%), but must qualify at 5.25%
        # Income is tight at 5.25%
        payload = {
            "applicant_id": "stress-test",
            "loan_amount": "400000.00",
            "property_value": "500000.00",
            "annual_income": "84000.00", # ~$7000/mo income
            "annual_property_tax": "3000.00",
            "annual_heating_cost": "1200.00",
            "other_debts": "0.00",
            "contract_rate": "3.00", # Actual payment would be ~$1896
            "amortization_years": 25
        }
        
        # Logic check:
        # Payment @ 3%: ~1896. GDS = (1896+250+100)*12 / 84000 = 30.8% (Pass)
        # Payment @ 5.25%: ~2400. GDS = (2400+250+100)*12 / 84000 = 39.1% (Fail)
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        data = response.json()
        
        # If the service correctly implements OSFI B-20, this should be rejected or referred
        # because the GDS at the qualifying rate (5.25%) exceeds 39%.
        assert data["decision"] in ["Rejected", "Refer"]
        assert "GDS" in data["rejection_reasons"]

    async def test_evaluate_application_cmhc_insurance_calculation(self, client: AsyncClient):
        # LTV 90% -> Premium 3.10%
        payload = {
            "applicant_id": "ins-test",
            "loan_amount": "450000.00",
            "property_value": "500000.00",
            "annual_income": "150000.00",
            "annual_property_tax": "3000.00",
            "annual_heating_cost": "1200.00",
            "other_debts": "0.00",
            "contract_rate": "4.00",
            "amortization_years": 25
        }
        
        response = await client.post("/api/v1/decision/evaluate", json=payload)
        data = response.json()
        
        assert data["decision"] == "Approved" # Income is high
        assert data["insurance_required"] is True
        assert data["insurance_premium_rate"] == 0.031 # 3.10%

    async def test_get_application_history(self, client: AsyncClient, valid_application_payload, db_session):
        # Create one first
        post_resp = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        app_id = post_resp.json()["id"]
        
        # Get history
        get_resp = await client.get(f"/api/v1/decision/applications/{valid_application_payload['applicant_id']}")
        
        assert get_resp.status_code == 200
        apps = get_resp.json()
        assert len(apps) >= 1
        assert any(a["id"] == app_id for a in apps)

    async def test_fintrac_audit_trail_fields_present(self, client: AsyncClient, valid_application_payload):
        # FINTRAC: Immutable audit trail (created_at)
        response = await client.post("/api/v1/decision/evaluate", json=valid_application_payload)
        data = response.json()
        
        assert "created_at" in data
        assert "updated_at" in data
        # Ensure we aren't logging PII (SIN) - verified by absence in response keys
        assert "sin" not in data
        assert "dob" not in data