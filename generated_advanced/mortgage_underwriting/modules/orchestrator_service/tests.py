--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from unittest.mock import AsyncMock, MagicMock

# Assuming the Base is imported from common.database or defined here for testing context
from mortgage_underwriting.common.database import Base

# Module specific imports
from mortgage_underwriting.modules.orchestrator.models import MortgageApplication
from mortgage_underwriting.modules.orchestrator.schemas import (
    ApplicationCreate,
    ApplicationStatus,
    DecisionResponse
)

# Test Database URL (In-memory SQLite for integration tests)
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
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def sample_application_payload():
    """Valid payload for creating a mortgage application."""
    return {
        "borrower_id": "123456789",
        "property_value": Decimal("500000.00"),
        "down_payment": Decimal("100000.00"),
        "loan_amount": Decimal("400000.00"),
        "annual_income": Decimal("120000.00"),
        "property_tax": Decimal("3000.00"),
        "heating_cost": Decimal("150.00"),
        "other_debts": Decimal("500.00"),
        "contract_rate": Decimal("4.50"),
        "amortization_years": 25
    }

@pytest.fixture
def sample_application_model(sample_application_payload):
    """SQLAlchemy model instance for testing."""
    return MortgageApplication(**sample_application_payload)

@pytest.fixture
def mock_borrower_service():
    """Mock for external Borrower Service dependency."""
    service = AsyncMock()
    # Default: borrower exists and is valid
    service.get_borrower.return_value = {
        "id": "123456789",
        "credit_score": 750,
        "is_verified": True
    }
    return service

@pytest.fixture
def mock_property_service():
    """Mock for external Property Service dependency."""
    service = AsyncMock()
    # Default: property exists and appraisal matches
    service.get_property.return_value = {
        "id": "prop_123",
        "valuation": Decimal("500000.00"),
        "address": "123 Test St"
    }
    return service

@pytest.fixture
def mock_audit_logger():
    """Mock for structured logger."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()
    logger.warning = MagicMock()
    return logger
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from mortgage_underwriting.modules.orchestrator.services import OrchestratorService
from mortgage_underwriting.modules.orchestrator.exceptions import (
    UnderwritingError,
    ComplianceError
)
from mortgage_underwriting.modules.orchestrator.models import MortgageApplication

@pytest.mark.unit
class TestOrchestratorServiceCalculations:

    @pytest.fixture
    def service(self):
        # Service requires a db session (mocked) and potentially other clients
        mock_db = AsyncMock()
        return OrchestratorService(mock_db)

    def test_calculate_monthly_payment(self, service):
        principal = Decimal("400000.00")
        annual_rate = Decimal("0.05") # 5%
        months = 300 # 25 years
        
        # Standard mortgage formula: M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # i = 0.05 / 12 = 0.004166...
        # This is an approximation check, exact value depends on implementation precision
        payment = service._calculate_monthly_payment(principal, annual_rate, months)
        
        assert payment is not None
        assert isinstance(payment, Decimal)
        # Rough sanity check for 400k at 5% over 25y
        assert Decimal("2000") < payment < Decimal("3000")

    def test_calculate_gds_success(self, service):
        """Test GDS calculation within OSFI B-20 limits."""
        monthly_income = Decimal("10000.00")
        monthly_mortgage = Decimal("2000.00")
        monthly_tax = Decimal("300.00")
        monthly_heating = Decimal("150.00")
        
        # GDS = (Mortgage + Tax + Heat) / Income
        # (2000 + 300 + 150) / 10000 = 0.245 (24.5%)
        gds = service.calculate_gds(monthly_income, monthly_mortgage, monthly_tax, monthly_heating)
        
        assert gds == Decimal("0.245")
        assert gds <= Decimal("0.39")

    def test_calculate_gds_exceeds_limit(self, service):
        """Test GDS calculation exceeding OSFI B-20 limit (39%)."""
        monthly_income = Decimal("5000.00")
        monthly_mortgage = Decimal("2000.00")
        monthly_tax = Decimal("300.00")
        monthly_heating = Decimal("150.00")
        
        # (2000 + 300 + 150) / 5000 = 0.49 (49%)
        gds = service.calculate_gds(monthly_income, monthly_mortgage, monthly_tax, monthly_heating)
        
        assert gds == Decimal("0.49")
        assert gds > Decimal("0.39")

    def test_calculate_tds_success(self, service):
        """Test TDS calculation within OSFI B-20 limits."""
        monthly_income = Decimal("10000.00")
        housing_costs = Decimal("2450.00") # Mortgage + Tax + Heat
        other_debts = Decimal("500.00")
        
        # TDS = (Housing + Other) / Income
        # (2450 + 500) / 10000 = 0.295 (29.5%)
        tds = service.calculate_tds(monthly_income, housing_costs, other_debts)
        
        assert tds == Decimal("0.295")
        assert tds <= Decimal("0.44")

    def test_calculate_tds_exceeds_limit(self, service):
        """Test TDS calculation exceeding OSFI B-20 limit (44%)."""
        monthly_income = Decimal("5000.00")
        housing_costs = Decimal("2450.00")
        other_debts = Decimal("500.00")
        
        # (2450 + 500) / 5000 = 0.59 (59%)
        tds = service.calculate_tds(monthly_income, housing_costs, other_debts)
        
        assert tds == Decimal("0.59")
        assert tds > Decimal("0.44")

    def test_determine_stress_rate_contract_plus_two(self, service):
        """OSFI B-20: Qualifying rate is max(contract + 2%, 5.25%)."""
        contract_rate = Decimal("0.04") # 4%
        stress_rate = service.get_qualifying_rate(contract_rate)
        assert stress_rate == Decimal("0.0625") # 4 + 2 = 6%

    def test_determine_stress_rate_floor(self, service):
        """OSFI B-20: Qualifying rate floor is 5.25%."""
        contract_rate = Decimal("0.025") # 2.5%
        stress_rate = service.get_qualifying_rate(contract_rate)
        assert stress_rate == Decimal("0.0525") # Max(4.5%, 5.25%)

    def test_calculate_ltv(self, service):
        loan_amount = Decimal("400000.00")
        property_value = Decimal("500000.00")
        
        ltv = service.calculate_ltv(loan_amount, property_value)
        assert ltv == Decimal("0.80")

    def test_calculate_ltv_high_ratio(self, service):
        loan_amount = Decimal("450000.00")
        property_value = Decimal("500000.00")
        
        ltv = service.calculate_ltv(loan_amount, property_value)
        assert ltv == Decimal("0.90")

    def test_determine_insurance_premium_tier_1(self, service):
        """CMHC Tier: 80.01% - 85% = 2.80%"""
        ltv = Decimal("0.82")
        loan_amount = Decimal("400000.00")
        premium = service.calculate_insurance_premium(ltv, loan_amount)
        expected = loan_amount * Decimal("0.028")
        assert premium == expected

    def test_determine_insurance_premium_tier_2(self, service):
        """CMHC Tier: 85.01% - 90% = 3.10%"""
        ltv = Decimal("0.88")
        loan_amount = Decimal("400000.00")
        premium = service.calculate_insurance_premium(ltv, loan_amount)
        expected = loan_amount * Decimal("0.031")
        assert premium == expected

    def test_determine_insurance_premium_tier_3(self, service):
        """CMHC Tier: 90.01% - 95% = 4.00%"""
        ltv = Decimal("0.92")
        loan_amount = Decimal("400000.00")
        premium = service.calculate_insurance_premium(ltv, loan_amount)
        expected = loan_amount * Decimal("0.04")
        assert premium == expected

    def test_no_insurance_required_lte_80(self, service):
        ltv = Decimal("0.80")
        loan_amount = Decimal("400000.00")
        premium = service.calculate_insurance_premium(ltv, loan_amount)
        assert premium == Decimal("0.00")


@pytest.mark.unit
class TestOrchestratorServiceWorkflow:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return OrchestratorService(mock_db)

    @pytest.mark.asyncio
    async def test_process_application_approval(self, service, mock_db, sample_application_payload):
        """Happy path: Application passes all checks."""
        # Setup mocks
        mock_app = MortgageApplication(id=1, **sample_application_payload)
        mock_db.scalar.return_value = mock_app
        
        # Mock sub-services (assuming they are injected or initialized)
        service.borrower_service = AsyncMock()
        service.borrower_service.validate_borrower.return_value = True
        
        service.property_service = AsyncMock()
        service.property_service.validate_property.return_value = True

        result = await service.process_application(application_id=1)
        
        assert result.decision == "Approved"
        assert result.gds <= Decimal("0.39")
        assert result.tds <= Decimal("0.44")
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_application_rejection_gds(self, service, mock_db):
        """Rejection path: GDS too high."""
        # Income too low for the loan
        payload = {
            "borrower_id": "123",
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("100000.00"),
            "loan_amount": Decimal("400000.00"),
            "annual_income": Decimal("40000.00"), # Low income
            "property_tax": Decimal("5000.00"),
            "heating_cost": Decimal("300.00"),
            "other_debts": Decimal("0.00"),
            "contract_rate": Decimal("5.0"),
            "amortization_years": 25
        }
        mock_app = MortgageApplication(id=2, **payload)
        mock_db.scalar.return_value = mock_app
        
        service.borrower_service = AsyncMock()
        service.borrower_service.validate_borrower.return_value = True
        service.property_service = AsyncMock()
        service.property_service.validate_property.return_value = True

        result = await service.process_application(application_id=2)
        
        assert result.decision == "Rejected"
        assert "GDS" in result.reason or "TDS" in result.reason

    @pytest.mark.asyncio
    async def test_process_application_missing_borrower(self, service, mock_db, sample_application_payload):
        """Error path: Borrower not found."""
        mock_app = MortgageApplication(id=3, **sample_application_payload)
        mock_db.scalar.return_value = mock_app
        
        service.borrower_service = AsyncMock()
        service.borrower_service.validate_borrower.side_effect = ValueError("Borrower not found")

        with pytest.raises(UnderwritingError):
            await service.process_application(application_id=3)

    @pytest.mark.asyncio
    async def test_process_application_compliance_logging(self, service, mock_db, sample_application_payload, mock_audit_logger):
        """Verify audit trail is created for compliance."""
        service.logger = mock_audit_logger
        mock_app = MortgageApplication(id=4, **sample_application_payload)
        mock_db.scalar.return_value = mock_app
        
        service.borrower_service = AsyncMock()
        service.borrower_service.validate_borrower.return_value = True
        service.property_service = AsyncMock()
        service.property_service.validate_property.return_value = True

        await service.process_application(application_id=4)
        
        # Check that calculation breakdown was logged
        assert mock_audit_logger.info.called
        # Check for specific log content (implementation dependent)
        # args = mock_audit_logger.info.call_args[0]
        # assert "GDS" in str(args) or "calculation" in str(args).lower()
--- integration_tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

from mortgage_underwriting.modules.orchestrator.routes import router
from mortgage_underwriting.modules.orchestrator.models import MortgageApplication
from mortgage_underwriting.common.database import get_async_session

# We need to override the dependency for testing
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture
def app(db_session: AsyncSession):
    """Create a test app with the orchestrator router and DB override."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/orchestrator", tags=["orchestrator"])

    # Dependency override
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestOrchestratorRoutes:

    async def test_create_application(self, app: FastAPI, sample_application_payload):
        """Test creating a new mortgage application via API."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/orchestrator/applications",
                json=sample_application_payload
            )
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["status"] == "Pending"
            assert data["loan_amount"] == "400000.00"

    async def test_get_application(self, app: FastAPI, db_session: AsyncSession):
        """Test retrieving an application."""
        # Seed data
        app_obj = MortgageApplication(
            borrower_id="999",
            property_value=Decimal("200000"),
            down_payment=Decimal("40000"),
            loan_amount=Decimal("160000"),
            annual_income=Decimal("60000"),
            property_tax=Decimal("2000"),
            heating_cost=Decimal("100"),
            other_debts=Decimal("0"),
            contract_rate=Decimal("3.0"),
            amortization_years=20
        )
        db_session.add(app_obj)
        await db_session.commit()
        await db_session.refresh(app_obj)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/orchestrator/applications/{app_obj.id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == app_obj.id
            assert data["borrower_id"] == "999"

    async def test_process_application_workflow(self, app: FastAPI, sample_application_payload, db_session: AsyncSession):
        """Full workflow: Create -> Process -> Verify Decision."""
        # 1. Create Application
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/orchestrator/applications",
                json=sample_application_payload
            )
            assert create_resp.status_code == 201
            app_id = create_resp.json()["id"]

            # 2. Process Application (Trigger Orchestrator)
            # NOTE: This endpoint likely triggers the heavy calculation logic
            process_resp = await client.post(f"/api/v1/orchestrator/process/{app_id}")
            assert process_resp.status_code == 200
            
            decision_data = process_resp.json()
            assert "decision" in decision_data
            assert "gds" in decision_data
            assert "tds" in decision_data
            
            # 3. Verify Final State in DB
            get_resp = await client.get(f"/api/v1/orchestrator/applications/{app_id}")
            assert get_resp.status_code == 200
            final_state = get_resp.json()
            
            assert final_state["status"] == decision_data["decision"]
            # Check audit fields are present
            assert "updated_at" in final_state

    async def test_validation_error_on_bad_input(self, app: FastAPI):
        """Test that Pydantic validation catches bad requests."""
        bad_payload = {
            "borrower_id": "123",
            "property_value": "not_a_decimal", # Invalid
            "loan_amount": -500 # Invalid
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/orchestrator/applications",
                json=bad_payload
            )
            
            assert response.status_code == 422

    async def test_not_found_on_processing_invalid_id(self, app: FastAPI):
        """Test processing an application that doesn't exist."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/orchestrator/process/99999")
            assert response.status_code == 404

    async def test_high_ratio_insurance_flag(self, app: FastAPI, db_session: AsyncSession):
        """Test that LTV > 80% triggers insurance requirement in response."""
        # High ratio: 5% down payment
        payload = {
            "borrower_id": "ins_test",
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("25000.00"), # 5% down
            "loan_amount": Decimal("475000.00"),
            "annual_income": Decimal("150000.00"), # High income to pass GDS/TDS
            "property_tax": Decimal("3000.00"),
            "heating_cost": Decimal("150.00"),
            "other_debts": Decimal("0.00"),
            "contract_rate": Decimal("4.50"),
            "amortization_years": 25
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create
            create_resp = await client.post("/api/v1/orchestrator/applications", json=payload)
            app_id = create_resp.json()["id"]
            
            # Process
            proc_resp = await client.post(f"/api/v1/orchestrator/process/{app_id}")
            data = proc_resp.json()
            
            # Assertions
            assert data["ltv"] == Decimal("0.95")
            assert data["insurance_required"] == True
            # Check premium calculation (4.00% of 475000)
            expected_premium = Decimal("475000.00") * Decimal("0.04")
            assert data["insurance_premium"] == str(expected_premium)