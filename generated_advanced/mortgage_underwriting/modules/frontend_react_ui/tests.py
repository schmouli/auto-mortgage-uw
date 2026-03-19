--- conftest.py ---
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

# Import the module under test components
from mortgage_underwriting.modules.frontend_react_ui.routes import router as frontend_router
from mortgage_underwriting.common.database import Base

# Test Database URL (SQLite for isolation)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create engine
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def app() -> FastAPI:
    """Create a test FastAPI application."""
    app = FastAPI()
    app.include_router(frontend_router, prefix="/api/v1/frontend", tags=["frontend"])
    return app

@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_applicant_payload():
    """Standard valid payload for mortgage application submission."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "sin": "123456789", # Will be encrypted/hashed in real flow
        "dob": "1990-01-01",
        "income": Decimal("120000.00"),
        "property_value": Decimal("500000.00"),
        "down_payment": Decimal("100000.00"),
        "loan_amount": Decimal("400000.00"),
        "contract_rate": Decimal("4.50"),
        "property_tax": Decimal("3000.00"),
        "heating_cost": Decimal("1200.00"),
        "condo_fees": Decimal("0.00"),
        "other_debt": Decimal("500.00")
    }

@pytest.fixture
def high_gds_payload():
    """Payload designed to fail OSFI GDS check (>39%)."""
    return {
        "first_name": "Jane",
        "last_name": "Smith",
        "sin": "987654321",
        "dob": "1985-05-15",
        "income": Decimal("50000.00"), # Low income relative to costs
        "property_value": Decimal("400000.00"),
        "down_payment": Decimal("80000.00"),
        "loan_amount": Decimal("320000.00"),
        "contract_rate": Decimal("5.00"),
        "property_tax": Decimal("5000.00"),
        "heating_cost": Decimal("2400.00"),
        "condo_fees": Decimal("500.00"),
        "other_debt": Decimal("0.00")
    }
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from mortgage_underwriting.modules.frontend_react_ui.services import FrontendService
from mortgage_underwriting.modules.frontend_react_ui.exceptions import (
    ApplicationValidationError,
    ComplianceError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFrontendServiceCalculations:

    @pytest.mark.asyncio
    async def test_calculate_stress_test_rate_below_floor(self):
        """
        Test OSFI B-20 Stress Test: Contract rate + 2% < 5.25%
        Result should be 5.25%.
        """
        service = FrontendService(db=AsyncMock())
        rate = Decimal("3.00")
        stress_rate = await service._calculate_qualifying_rate(rate)
        assert stress_rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_calculate_stress_test_rate_above_floor(self):
        """
        Test OSFI B-20 Stress Test: Contract rate + 2% > 5.25%
        Result should be Contract + 2%.
        """
        service = FrontendService(db=AsyncMock())
        rate = Decimal("5.00")
        stress_rate = await service._calculate_qualifying_rate(rate)
        assert stress_rate == Decimal("7.00")

    @pytest.mark.asyncio
    async def test_calculate_gds_success(self):
        """
        Test GDS Calculation: (Property Tax + Heat + 50% Condo + Mortgage Pmt) / Income
        """
        service = FrontendService(db=AsyncMock())
        # Pmt = ~2000, Tax = 3000/12=250, Heat = 100, Condo = 0. Income = 10000/12=833.33
        # GDS = (2350) / 8333 = ~28%
        income = Decimal("100000.00")
        monthly_payment = Decimal("2000.00")
        property_tax = Decimal("3000.00")
        heating = Decimal("1200.00")
        condo_fees = Decimal("0.00")

        gds = await service._calculate_gds(
            income, monthly_payment, property_tax, heating, condo_fees
        )
        # 2000 + 250 + 100 = 2350. 2350 / 8333.33 = 0.282
        assert gds == Decimal("0.2820")

    @pytest.mark.asyncio
    async def test_calculate_tds_success(self):
        """
        Test TDS Calculation: (Housing Costs + Other Debt) / Income
        """
        service = FrontendService(db=AsyncMock())
        income = Decimal("100000.00")
        housing_costs = Decimal("2350.00") # From GDS calculation
        other_debt = Decimal("500.00")

        tds = await service._calculate_tds(income, housing_costs, other_debt)
        # 2850 / 8333.33 = 0.342
        assert tds == Decimal("0.3420")

    @pytest.mark.asyncio
    async def test_calculate_ltv_and_cmhc_premium(self):
        """
        Test CMHC Logic:
        LTV > 80% -> Insurance Required
        LTV 80.01-85% -> 2.80%
        """
        service = FrontendService(db=AsyncMock())
        loan_amount = Decimal("85000.00")
        property_value = Decimal("100000.00")
        
        ltv, premium_rate = await service._calculate_ltv_and_premium(loan_amount, property_value)
        
        assert ltv == Decimal("0.85")
        assert premium_rate == Decimal("0.0280")

@pytest.mark.unit
class TestFrontendServiceValidation:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_validate_application_osfi_compliance_pass(self, mock_db, valid_applicant_payload):
        """
        Happy Path: GDS <= 39%, TDS <= 44%
        """
        service = FrontendService(mock_db)
        # Mocking internal calculation helpers to focus on validation logic
        service._calculate_gds = AsyncMock(return_value=Decimal("0.35")) # 35%
        service._calculate_tds = AsyncMock(return_value=Decimal("0.40")) # 40%
        
        # Should not raise
        await service._validate_osfi_compliance(valid_applicant_payload)

    @pytest.mark.asyncio
    async def test_validate_application_osfi_gds_fail(self, mock_db, valid_applicant_payload):
        """
        OSFI B-20 Violation: GDS > 39%
        """
        service = FrontendService(mock_db)
        service._calculate_gds = AsyncMock(return_value=Decimal("0.40")) # 40% > 39%
        
        with pytest.raises(ApplicationValidationError) as exc_info:
            await service._validate_osfi_compliance(valid_applicant_payload)
        
        assert "GDS" in str(exc_info.value)
        assert "39%" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_application_osfi_tds_fail(self, mock_db, valid_applicant_payload):
        """
        OSFI B-20 Violation: TDS > 44%
        """
        service = FrontendService(mock_db)
        service._calculate_gds = AsyncMock(return_value=Decimal("0.30"))
        service._calculate_tds = AsyncMock(return_value=Decimal("0.45")) # 45% > 44%
        
        with pytest.raises(ApplicationValidationError) as exc_info:
            await service._validate_osfi_compliance(valid_applicant_payload)
        
        assert "TDS" in str(exc_info.value)
        assert "44%" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_fintrac_logging(self, mock_db, valid_applicant_payload):
        """
        FINTRAC: Ensure identity verification is logged (simulated via mock logger)
        """
        service = FrontendService(mock_db)
        
        with patch('mortgage_underwriting.modules.frontend_react_ui.services.logger') as mock_logger:
            await service._log_identity_verification(valid_applicant_payload)
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            # PIPEDA Check: Ensure SIN is NOT in the logs
            assert valid_applicant_payload['sin'] not in call_args
            assert "Identity verified" in call_args

    @pytest.mark.asyncio
    async def test_encrypt_pii_fields(self, mock_db):
        """
        PIPEDA: Verify SIN is encrypted before storage logic
        """
        service = FrontendService(mock_db)
        raw_sin = "123456789"
        
        encrypted = await service._encrypt_sin(raw_sin)
        
        assert encrypted != raw_sin
        assert isinstance(encrypted, str)

    @pytest.mark.asyncio
    async def test_create_application_persistence(self, mock_db, valid_applicant_payload):
        """
        Test that service calls DB add/commit and returns a response
        """
        service = FrontendService(mock_db)
        
        # Mock the model creation
        with patch('mortgage_underwriting.modules.frontend_react_ui.services.MortgageApplication') as MockModel:
            mock_instance = MagicMock()
            mock_instance.id = 1
            MockModel.return_value = mock_instance
            
            result = await service.create_application(valid_applicant_payload)
            
            mock_db.add.assert_called_once_with(mock_instance)
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once_with(mock_instance)
            assert result.id == 1
--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from mortgage_underwriting.modules.frontend_react_ui.models import MortgageApplication

@pytest.mark.integration
@pytest.mark.asyncio
class TestFrontendRoutes:

    async def test_submit_application_success(self, client: AsyncClient, valid_applicant_payload):
        """
        Test successful submission of a mortgage application via API
        """
        response = await client.post("/api/v1/frontend/submit", json=valid_applicant_payload)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending_review"
        assert data["loan_amount"] == "400000.00"
        # PIPEDA Check: Ensure SIN is NOT exposed in response
        assert "sin" not in data or data.get("sin") != valid_applicant_payload["sin"]

    async def test_submit_application_invalid_schema(self, client: AsyncClient):
        """
        Test validation error on malformed input (missing required fields)
        """
        invalid_payload = {
            "first_name": "Test",
            # Missing last_name, income, etc.
        }
        
        response = await client.post("/api/v1/frontend/submit", json=invalid_payload)
        
        assert response.status_code == 422
        assert "detail" in response.json()

    async def test_submit_application_osfi_gds_rejection(self, client: AsyncClient, high_gds_payload):
        """
        Integration test: Verify API rejects application failing OSFI GDS limits
        """
        response = await client.post("/api/v1/frontend/submit", json=high_gds_payload)
        
        assert response.status_code == 400 # Bad Request / Validation Error
        data = response.json()
        assert "error_code" in data
        # Verify error message mentions compliance
        assert "GDS" in data["detail"] or "compliance" in data["detail"].lower()

    async def test_get_application_status(self, client: AsyncClient, valid_applicant_payload, db_session):
        """
        Test retrieving application status
        """
        # 1. Create an application first
        create_resp = await client.post("/api/v1/frontend/submit", json=valid_applicant_payload)
        app_id = create_resp.json()["id"]
        
        # 2. Retrieve status
        status_resp = await client.get(f"/api/v1/frontend/status/{app_id}")
        
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["id"] == app_id
        assert data["created_at"] is not None

    async def test_submit_application_high_ltv_triggers_cmhc(self, client: AsyncClient, db_session):
        """
        Test CMHC Insurance logic integration:
        High LTV (e.g., 90%) should result in insurance_required = True
        """
        payload = {
            "first_name": "Bob",
            "last_name": "Builder",
            "sin": "555555555",
            "dob": "1980-01-01",
            "income": Decimal("100000.00"),
            "property_value": Decimal("100000.00"),
            "down_payment": Decimal("5000.00"), # 5% down -> 95% LTV
            "loan_amount": Decimal("95000.00"),
            "contract_rate": Decimal("4.00"),
            "property_tax": Decimal("1000.00"),
            "heating_cost": Decimal("1000.00"),
            "condo_fees": Decimal("0.00"),
            "other_debt": Decimal("0.00")
        }
        
        response = await client.post("/api/v1/frontend/submit", json=payload)
        assert response.status_code == 201
        
        # Verify DB state
        result = await db_session.execute(select(MortgageApplication).where(MortgageApplication.id == response.json()["id"]))
        app = result.scalar_one()
        
        assert app.insurance_required is True
        assert app.ltv_ratio == Decimal("0.95")
        assert app.cmhc_premium_rate == Decimal("0.04") # 90.01-95% tier

    async def test_fintrac_audit_fields_present(self, client: AsyncClient, valid_applicant_payload, db_session):
        """
        FINTRAC: Verify audit fields (created_at, created_by) are immutable and present
        """
        response = await client.post("/api/v1/frontend/submit", json=valid_applicant_payload)
        app_id = response.json()["id"]
        
        result = await db_session.execute(select(MortgageApplication).where(MortgageApplication.id == app_id))
        app = result.scalar_one()
        
        assert app.created_at is not None
        assert app.created_by is not None # Should be 'system' or user ID

    async def test_pipeda_sin_not_logged(self, client: AsyncClient, valid_applicant_payload, caplog):
        """
        PIPEDA: Ensure raw SIN never appears in logs
        """
        # This test assumes the application logs inputs at INFO level for debugging
        # We want to ensure the security middleware/logger scrubs the SIN
        
        with caplog.at_level("INFO"):
            response = await client.post("/api/v1/frontend/submit", json=valid_applicant_payload)
            
        # Gather all log messages
        log_messages = "".join(record.message for record in caplog.records)
        
        # Assert raw SIN is NOT present
        assert valid_applicant_payload["sin"] not in log messages
        # Assert placeholder or hash IS present (optional, but good practice)
        assert "******" in log_messages or "hashed" in log_messages.lower()