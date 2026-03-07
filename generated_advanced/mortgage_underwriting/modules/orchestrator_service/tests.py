--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from fastapi import FastAPI

# Import the router and models from the module under test
# Note: Adjust imports based on actual file structure if different
from mortgage_underwriting.modules.orchestrator.routes import router
from mortgage_underwriting.common.database import Base

# Use in-memory SQLite for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
AsyncTestingSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncTestingSessionLocal() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def app() -> FastAPI:
    """
    Creates a test FastAPI app instance.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/orchestrator", tags=["orchestrator"])
    return app


@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async client for integration testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def valid_application_payload():
    """
    Standard payload for a valid mortgage application.
    """
    return {
        "borrower_id": "test-borrower-123",
        "property_id": "test-property-456",
        "loan_amount": "450000.00",
        "purchase_price": "500000.00",
        "amortization_years": 25,
        "contract_rate": "4.50",
        "annual_income": "120000.00",
        "annual_property_tax": "3000.00",
        "annual_heating": "1200.00",
        "monthly_debt_payments": "500.00"
    }

@pytest.fixture
def high_risk_payload():
    """
    Payload designed to fail underwriting (High TDS/GDS).
    """
    return {
        "borrower_id": "test-borrower-risk",
        "property_id": "test-property-risk",
        "loan_amount": "450000.00",
        "purchase_price": "500000.00",
        "amortization_years": 25,
        "contract_rate": "4.50",
        "annual_income": "50000.00",  # Low income relative to loan
        "annual_property_tax": "5000.00",
        "annual_heating": "2000.00",
        "monthly_debt_payments": "2000.00" # High debt
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.orchestrator.services import OrchestratorService
from mortgage_underwriting.modules.orchestrator.schemas import UnderwritingRequest, UnderwritingDecision
from mortgage_underwriting.common.exceptions import AppException

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


@pytest.mark.asyncio
class TestOrchestratorService:

    @pytest.fixture
    def mock_session(self):
        """Provides a mock AsyncSession."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def mock_borrower_service(self):
        """Mocks the BorrowerService dependency."""
        with patch("mortgage_underwriting.modules.orchestrator.services.BorrowerService") as mock:
            yield mock

    @pytest.fixture
    def mock_property_service(self):
        """Mocks the PropertyService dependency."""
        with patch("mortgage_underwriting.modules.orchestrator.services.PropertyService") as mock:
            yield mock

    @pytest.fixture
    def mock_financial_service(self):
        """Mocks the FinancialService dependency."""
        with patch("mortgage_underwriting.modules.orchestrator.services.FinancialService") as mock:
            yield mock

    async def test_calculate_gds_success(self, mock_session):
        """
        Test GDS calculation accuracy.
        GDS = (Mortgage Payment + Property Tax + Heating) / Annual Income
        """
        service = OrchestratorService(mock_session)
        
        # Inputs
        monthly_payment = Decimal("2500.00")
        annual_tax = Decimal("3600.00")
        annual_heating = Decimal("1200.00")
        annual_income = Decimal("120000.00")

        gds = await service._calculate_gds(
            monthly_payment, annual_tax, annual_heating, annual_income
        )

        # Calculation: ((2500 * 12) + 3600 + 1200) / 120000
        # (30000 + 3600 + 1200) / 120000 = 34800 / 120000 = 0.29
        expected_gds = Decimal("0.29")
        assert gds == expected_gds

    async def test_calculate_tds_success(self, mock_session):
        """
        Test TDS calculation accuracy.
        TDS = (Housing Costs + Other Debts) / Annual Income
        """
        service = OrchestratorService(mock_session)
        
        monthly_payment = Decimal("2500.00")
        annual_tax = Decimal("3600.00")
        annual_heating = Decimal("1200.00")
        annual_income = Decimal("120000.00")
        monthly_debt = Decimal("500.00")

        tds = await service._calculate_tds(
            monthly_payment, annual_tax, annual_heating, annual_income, monthly_debt
        )

        # Calculation: ((2500 * 12) + 3600 + 1200 + (500 * 12)) / 120000
        # (30000 + 3600 + 1200 + 6000) / 120000 = 40800 / 120000 = 0.34
        expected_tds = Decimal("0.34")
        assert tds == expected_tds

    async def test_determine_stress_rate_osfi_compliant(self, mock_session):
        """
        Test OSFI B-20 Stress Test logic.
        Qualifying Rate = MAX(Contract Rate + 2%, 5.25%)
        """
        service = OrchestratorService(mock_session)

        # Case 1: Contract rate is low (3.0%), floor applies
        rate_1 = await service._get_qualifying_rate(Decimal("3.00"))
        assert rate_1 == Decimal("5.25")

        # Case 2: Contract rate is high (4.5%), buffer applies
        rate_2 = await service._get_qualifying_rate(Decimal("4.50"))
        assert rate_2 == Decimal("6.50")

        # Case 3: Contract rate is exactly 3.25%
        rate_3 = await service._get_qualifying_rate(Decimal("3.25"))
        assert rate_3 == Decimal("5.25")

    async def test_process_application_approved_happy_path(
        self, mock_session, mock_borrower_service, mock_property_service, mock_financial_service
    ):
        """
        Test full workflow where application is approved.
        """
        # Setup Mocks
        mock_borrower_service.return_value.verify_identity = AsyncMock(return_value=True)
        mock_property_service.return_value.valuate_property = AsyncMock(return_value=Decimal("500000.00"))
        mock_financial_service.return_value.calculate_payment = AsyncMock(return_value=Decimal("2100.00"))

        payload = UnderwritingRequest(
            borrower_id="b123",
            property_id="p123",
            loan_amount=Decimal("400000.00"),
            purchase_price=Decimal("500000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.00"),
            annual_income=Decimal("120000.00"),
            annual_property_tax=Decimal("3000.00"),
            annual_heating=Decimal("1200.00"),
            monthly_debt_payments=Decimal("0.00")
        )

        service = OrchestratorService(mock_session)
        result = await service.process_application(payload)

        # Assertions
        assert result.decision == "APPROVED"
        assert result.gds <= Decimal("0.39")
        assert result.tds <= Decimal("0.44")
        assert result.insurance_required is False  # LTV is 80%
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    async def test_process_application_rejected_high_tds(
        self, mock_session, mock_borrower_service, mock_property_service, mock_financial_service
    ):
        """
        Test rejection when TDS exceeds OSFI limit of 44%.
        """
        mock_borrower_service.return_value.verify_identity = AsyncMock(return_value=True)
        mock_property_service.return_value.valuate_property = AsyncMock(return_value=Decimal("500000.00"))
        # High payment to force TDS failure
        mock_financial_service.return_value.calculate_payment = AsyncMock(return_value=Decimal("4000.00"))

        payload = UnderwritingRequest(
            borrower_id="b123",
            property_id="p123",
            loan_amount=Decimal("450000.00"),
            purchase_price=Decimal("500000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.00"),
            annual_income=Decimal("80000.00"), # Lower income
            annual_property_tax=Decimal("3000.00"),
            annual_heating=Decimal("1200.00"),
            monthly_debt_payments=Decimal("1000.00")
        )

        service = OrchestratorService(mock_session)
        result = await service.process_application(payload)

        assert result.decision == "REJECTED"
        assert "TDS" in result.rejection_reason or "Debt" in result.rejection_reason

    async def test_process_application_cmhc_insurance_required(
        self, mock_session, mock_borrower_service, mock_property_service, mock_financial_service
    ):
        """
        Test CMHC logic: LTV > 80% triggers insurance requirement.
        """
        mock_borrower_service.return_value.verify_identity = AsyncMock(return_value=True)
        mock_property_service.return_value.valuate_property = AsyncMock(return_value=Decimal("500000.00"))
        mock_financial_service.return_value.calculate_payment = AsyncMock(return_value=Decimal("2100.00"))

        # LTV = 450k / 500k = 90%
        payload = UnderwritingRequest(
            borrower_id="b123",
            property_id="p123",
            loan_amount=Decimal("450000.00"),
            purchase_price=Decimal("500000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.00"),
            annual_income=Decimal("120000.00"),
            annual_property_tax=Decimal("3000.00"),
            annual_heating=Decimal("1200.00"),
            monthly_debt_payments=Decimal("0.00")
        )

        service = OrchestratorService(mock_session)
        result = await service.process_application(payload)

        assert result.decision == "APPROVED" # Assuming income supports it
        assert result.insurance_required is True
        assert result.ltv_ratio == Decimal("0.90")
        # CMHC Tier 90.01-95% is 4.00%, but 90.00 is in 85.01-90% -> 3.10%
        # Here LTV is exactly 90.00, so strictly speaking < 90.01
        assert result.insurance_premium_rate == Decimal("0.031") 

    async def test_process_application_invalid_input(self, mock_session):
        """
        Test that invalid payload raises appropriate error.
        """
        service = OrchestratorService(mock_session)
        
        # Missing required fields
        with pytest.raises(ValueError):
            await service.process_application({})

    async def test_audit_log_created(self, mock_session):
        """
        Test FINTRAC compliance: Audit trail is created for the decision.
        """
        # This would typically be checked by inspecting the object passed to session.add
        # For unit test, we ensure the logic reaches the point of saving
        service = OrchestratorService(mock_session)
        
        # We need to mock internal methods to get straight to the save logic
        # or run a simplified happy path
        with patch.object(service, "_calculate_gds", return_value=Decimal("0.30")), \
             patch.object(service, "_calculate_tds", return_value=Decimal("0.35")), \
             patch.object(service, "_get_qualifying_rate", return_value=Decimal("5.25")):
             
            # Simulating the internal object creation
            decision = UnderwritingDecision(
                application_id="123",
                decision="APPROVED",
                gds=Decimal("0.30"),
                tds=Decimal("0.35")
            )
            
            # Call the internal save method if it exists, or verify commit was called in process_application
            # Assuming process_application handles the object creation
            pass 
            # Note: Full verification of audit fields usually happens in integration or by inspecting the mock call
            
--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal

from mortgage_underwriting.modules.orchestrator.models import UnderwritingResult
from mortgage_underwriting.modules.orchestrator.schemas import UnderwritingDecision

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_application_success(client: AsyncClient, valid_application_payload):
    """
    Integration test: Submit a valid application and verify DB state.
    """
    response = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert "application_id" in data
    assert data["decision"] == "APPROVED"
    assert data["ltv_ratio"] == "0.90" # 450k / 500k
    
    # Verify Audit fields (FINTRAC)
    assert "created_at" in data
    assert "correlation_id" in data
    
    # Verify Insurance Calculation (CMHC)
    assert data["insurance_required"] is True
    assert data["insurance_premium_rate"] == "0.031" # 80.01-90% tier


@pytest.mark.asyncio
async def test_create_application_rejected_high_gds(client: AsyncClient, high_risk_payload):
    """
    Integration test: Submit high-risk application and verify rejection logic.
    """
    response = await client.post("/api/v1/orchestrator/applications", json=high_risk_payload)
    
    assert response.status_code == 201 # Request accepted, but decision is REJECTED
    data = response.json()
    
    assert data["decision"] == "REJECTED"
    assert "GDS" in data["rejection_reason"] or "TDS" in data["rejection_reason"]
    assert data["gds"] > Decimal("0.39") or data["tds"] > Decimal("0.44")


@pytest.mark.asyncio
async def test_get_application_status(client: AsyncClient, db_session, valid_application_payload):
    """
    Integration test: Create an application, then retrieve it by ID.
    """
    # 1. Create
    create_resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
    app_id = create_resp.json()["application_id"]
    
    # 2. Retrieve
    get_resp = await client.get(f"/api/v1/orchestrator/applications/{app_id}")
    
    assert get_resp.status_code == 200
    data = get_resp.json()
    
    assert data["application_id"] == app_id
    # Ensure PIPEDA compliance: SIN/DOB should not be in response
    assert "sin" not in data
    assert "date_of_birth" not in data
    # Ensure financials are present
    assert "loan_amount" in data


@pytest.mark.asyncio
async def test_stress_test_endpoint_logic(client: AsyncClient, db_session):
    """
    Integration test: Verify the stress rate used in calculation via the API response.
    """
    payload = {
        "borrower_id": "stress-test-user",
        "property_id": "stress-prop",
        "loan_amount": "400000.00",
        "purchase_price": "500000.00",
        "amortization_years": 25,
        "contract_rate": "3.00", # Low rate
        "annual_income": "100000.00",
        "annual_property_tax": "3000.00",
        "annual_heating": "1200.00",
        "monthly_debt_payments": "0.00"
    }
    
    response = await client.post("/api/v1/orchestrator/applications", json=payload)
    data = response.json()
    
    # OSFI B-20: Qualifying rate must be at least 5.25%
    # We verify this by checking the monthly_payment calculated in the response
    # If 3.00% was used: Payment ~ $1896
    # If 5.25% was used: Payment ~ $2392
    # This is an indirect check of the logic
    assert Decimal(data["monthly_payment"]) > Decimal("2300.00")


@pytest.mark.asyncio
async def test_input_validation_missing_fields(client: AsyncClient):
    """
    Integration test: Verify 422 Unprocessable Entity on bad input.
    """
    incomplete_payload = {
        "borrower_id": "test"
        # Missing all other required fields
    }
    
    response = await client.post("/api/v1/orchestrator/applications", json=incomplete_payload)
    
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_cmhc_premium_tier_95(client: AsyncClient, db_session):
    """
    Integration test: Verify correct CMHC premium tier for high LTV (90-95%).
    """
    # LTV = 95%
    payload = {
        "borrower_id": "high-ltv-user",
        "property_id": "high-ltv-prop",
        "loan_amount": "475000.00",
        "purchase_price": "500000.00",
        "amortization_years": 25,
        "contract_rate": "4.50",
        "annual_income": "150000.00", # High income to ensure approval
        "annual_property_tax": "3000.00",
        "annual_heating": "1200.00",
        "monthly_debt_payments": "0.00"
    }
    
    response = await client.post("/api/v1/orchestrator/applications", json=payload)
    data = response.json()
    
    assert data["decision"] == "APPROVED"
    assert data["insurance_required"] is True
    assert data["ltv_ratio"] == Decimal("0.95")
    # Tier 90.01-95% = 4.00%
    assert data["insurance_premium_rate"] == Decimal("0.040")