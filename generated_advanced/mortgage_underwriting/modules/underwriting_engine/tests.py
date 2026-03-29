--- conftest.py ---
```python
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator, Generator

# Pytest configuration for async support
pytest_plugins = ("pytest_asyncio",)

# Database Setup for Testing
# Using SQLite in-memory for isolation and speed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
AsyncTestSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    Handles creation and dropping of tables.
    """
    # Import models here to ensure they are registered with Base.metadata
    # We assume the actual models exist in the project structure
    from mortgage_underwriting.modules.borrower.models import Borrower
    from mortgage_underwriting.modules.property.models import Property
    from mortgage_underwriting.modules.underwriting_engine.models import UnderwritingDecision

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncTestSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def sample_borrower_data():
    """Valid borrower data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "credit_score": 750,
        "annual_income": Decimal("120000.00"),
        "monthly_debt": Decimal("500.00"),
    }

@pytest.fixture
def sample_property_data():
    """Valid property data for testing."""
    return {
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M4W1A5",
        "property_value": Decimal("800000.00"),
    }

@pytest.fixture
def sample_mortgage_request():
    """Valid mortgage application payload for Underwriting Engine."""
    return {
        "borrower_id": 1, # Assumed ID after creation
        "property_id": 1, # Assumed ID after creation
        "loan_amount": Decimal("640000.00"), # 80% LTV
        "down_payment": Decimal("160000.00"),
        "amortization_years": 25,
        "contract_rate": Decimal("4.50"),
        "property_tax_annual": Decimal("4000.00"),
        "heating_cost_monthly": Decimal("150.00"),
        "condo_fees_monthly": Decimal("0.00"),
    }

@pytest.fixture
def app():
    """
    Fixture to provide the FastAPI app for integration testing.
    Constructs the app with the specific router.
    """
    from fastapi import FastAPI
    from mortgage_underwriting.modules.underwriting_engine.routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/underwriting", tags=["underwriting"])
    return app
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

# Import module components
from mortgage_underwriting.modules.underwriting_engine.services import UnderwritingService
from mortgage_underwriting.modules.underwriting_engine.schemas import (
    UnderwritingRequest,
    UnderwritingDecisionResponse,
    DecisionEnum
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestUnderwritingServiceCalculations:
    """
    Tests for the core calculation logic of the Underwriting Engine.
    Focuses on OSFI B-20 compliance, CMHC logic, and GDS/TDS.
    """

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_session):
        return UnderwritingService(mock_session)

    def test_calculate_stress_rate_osfi_floor(self, service):
        """
        Test OSFI B-20 Stress Test: 
        Contract 3.0% + 2% = 5.0%. 
        Qualifying rate must be max(5.0%, 5.25%) = 5.25%.
        """
        contract_rate = Decimal("3.00")
        expected_rate = Decimal("5.25")
        result = service._calculate_stress_rate(contract_rate)
        assert result == expected_rate

    def test_calculate_stress_rate_contract_plus_two(self, service):
        """
        Test OSFI B-20 Stress Test:
        Contract 5.0% + 2% = 7.0%.
        Qualifying rate must be max(7.0%, 5.25%) = 7.0%.
        """
        contract_rate = Decimal("5.00")
        expected_rate = Decimal("7.00")
        result = service._calculate_stress_rate(contract_rate)
        assert result == expected_rate

    def test_calculate_gds_success(self, service):
        """
        Test GDS Calculation:
        (Mortgage Pmt + Tax + Heat + 50% Condo) / Income
        """
        monthly_mortgage = Decimal("2500.00")
        property_tax = Decimal("4000.00") / 12
        heat = Decimal("150.00")
        condo = Decimal("0.00")
        income = Decimal("100000.00") / 12
        
        # (2500 + 333.33 + 150) / 8333.33 = 2983.33 / 8333.33 = ~35.8%
        result = service._calculate_gds(monthly_mortgage, property_tax, heat, condo, income)
        
        # Using Decimal for precision
        expected_numerator = monthly_mortgage + (Decimal("4000.00")/12) + heat
        expected = (expected_numerator / income) * Decimal("100")
        
        assert result == expected
        assert result < Decimal("39.00")

    def test_calculate_tds_success(self, service):
        """
        Test TDS Calculation:
        (Housing costs + Other Debts) / Income
        """
        housing_costs = Decimal("3000.00")
        other_debts = Decimal("500.00")
        income = Decimal("100000.00") / 12

        # (3000 + 500) / 8333.33 = 3500 / 8333.33 = 42.0%
        result = service._calculate_tds(housing_costs, other_debts, income)
        
        expected = ((housing_costs + other_debts) / income) * Decimal("100")
        assert result == expected
        assert result < Decimal("44.00")

    def test_calculate_ltv_boundary(self, service):
        """
        Test LTV calculation at 80% boundary.
        Loan 640k / Value 800k = 80%
        """
        loan_amount = Decimal("640000.00")
        property_value = Decimal("800000.00")
        
        result = service._calculate_ltv(loan_amount, property_value)
        assert result == Decimal("80.00")

    def test_calculate_ltv_high_ratio(self, service):
        """
        Test LTV > 80% (High Ratio).
        Loan 500k / Value 600k = 83.33%
        """
        loan_amount = Decimal("500000.00")
        property_value = Decimal("600000.00")
        
        result = service._calculate_ltv(loan_amount, property_value)
        assert result == Decimal("83.33")

    def test_determine_cmhc_insurance_required(self, service):
        """Test CMHC logic: LTV > 80% requires insurance."""
        ltv = Decimal("85.00")
        loan_amount = Decimal("500000.00")
        
        is_required, premium = service._determine_insurance(ltv, loan_amount)
        
        assert is_required is True
        # Premium tier 80.01-85% is 2.80%
        # 500,000 * 0.028 = 14,000
        expected_premium = loan_amount * Decimal("0.0280")
        assert premium == expected_premium

    def test_determine_cmhc_insurance_not_required(self, service):
        """Test CMHC logic: LTV <= 80% does not require insurance."""
        ltv = Decimal("80.00")
        loan_amount = Decimal("500000.00")
        
        is_required, premium = service._determine_insurance(ltv, loan_amount)
        
        assert is_required is False
        assert premium == Decimal("0.00")

    def test_cmhc_premium_tier_90_95(self, service):
        """Test CMHC Premium Tier: 90.01-95% = 4.00%"""
        ltv = Decimal("92.00")
        loan_amount = Decimal("400000.00")
        
        is_required, premium = service._determine_insurance(ltv, loan_amount)
        
        assert is_required is True
        expected_premium = loan_amount * Decimal("0.0400")
        assert premium == expected_premium

@pytest.mark.unit
class TestUnderwritingServiceLogic:
    """Tests for the orchestration and decision logic."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_session):
        return UnderwritingService(mock_session)

    @pytest.mark.asyncio
    async def test_evaluate_application_approved(self, service, mock_session):
        """
        Happy Path: Application meets all criteria.
        """
        payload = UnderwritingRequest(
            borrower_id=1,
            property_id=1,
            loan_amount=Decimal("500000.00"),
            down_payment=Decimal("100000.00"), # 83% LTV
            amortization_years=25,
            contract_rate=Decimal("4.0"),
            annual_income=Decimal("120000.00"),
            monthly_debts=Decimal("200.00"),
            property_tax_annual=Decimal("3600.00"),
            heating_monthly=Decimal("100.00"),
            condo_fees_monthly=Decimal("0.00")
        )
        
        # Mock borrower/property fetching (simplified for unit test of logic)
        # In a real unit test, we might mock the repository calls inside the service
        # Here we assume the service calculates based on payload provided or mocks internal fetches
        
        # Mocking the DB save
        mock_result = MagicMock()
        mock_result.id = 123
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None

        # We need to mock the internal fetch of borrower/property if the service does it
        # Assuming payload has all necessary data for this specific unit test design
        
        # For this exercise, let's assume the service method takes the payload and context
        # and returns the decision object directly without full DB dependency logic 
        # or we mock the repository calls.
        
        # Simulating the logic flow:
        # 1. LTV = 83.33% (High Ratio)
        # 2. Stress Rate = Max(6%, 5.25%) = 6%
        # 3. Mortgage Payment (approx) at 6% on 500k over 25y -> ~$3,200
        # 4. GDS = (3200 + 300 + 100) / 10000 = 36% (Pass < 39)
        # 5. TDS = (3600 + 200) / 10000 = 38% (Pass < 44)
        # 6. Decision: APPROVED
        
        # If the service implementation requires fetching IDs from DB:
        with patch.object(service, '_get_borrower', return_value=MagicMock(annual_income=Decimal("120000.00"), monthly_debt=Decimal("200.00"), credit_score=720)):
            with patch.object(service, '_get_property', return_value=MagicMock(property_value=Decimal("600000.00"))):
                 result = await service.evaluate_application(payload)

        assert result.decision == DecisionEnum.APPROVED
        assert result.gds_ratio < Decimal("39.00")
        assert result.tds_ratio < Decimal("44.00")
        assert result.insurance_required is True

    @pytest.mark.asyncio
    async def test_evaluate_application_rejected_high_tds(self, service):
        """
        Rejection Path: TDS exceeds 44% limit.
        """
        payload = UnderwritingRequest(
            borrower_id=1,
            property_id=1,
            loan_amount=Decimal("600000.00"),
            down_payment=Decimal("50000.00"), 
            amortization_years=25,
            contract_rate=Decimal("4.0"),
            annual_income=Decimal("80000.00"), # Lower income
            monthly_debts=Decimal("1500.00"), # High debts
            property_tax_annual=Decimal("5000.00"),
            heating_monthly=Decimal("200.00"),
            condo_fees_monthly=Decimal("500.00")
        )

        with patch.object(service, '_get_borrower', return_value=MagicMock(annual_income=Decimal("80000.00"), monthly_debt=Decimal("1500.00"), credit_score=720)):
            with patch.object(service, '_get_property', return_value=MagicMock(property_value=Decimal("650000.00"))):
                 result = await service.evaluate_application(payload)

        assert result.decision == DecisionEnum.REJECTED
        assert "TDS" in result.rejection_reason or "debt" in result.rejection_reason.lower()

    @pytest.mark.asyncio
    async def test_evaluate_application_rejected_low_credit(self, service):
        """
        Rejection Path: Credit score too low.
        """
        payload = UnderwritingRequest(
            borrower_id=1,
            property_id=1,
            loan_amount=Decimal("400000.00"),
            down_payment=Decimal("100000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.0"),
            annual_income=Decimal("200000.00"), # High income
            monthly_debts=Decimal("0.00"),
            property_tax_annual=Decimal("3000.00"),
            heating_monthly=Decimal("100.00"),
            condo_fees_monthly=Decimal("0.00")
        )

        # Mock low credit score
        with patch.object(service, '_get_borrower', return_value=MagicMock(annual_income=Decimal("200000.00"), monthly_debt=Decimal("0.00"), credit_score=550)):
            with patch.object(service, '_get_property', return_value=MagicMock(property_value=Decimal("500000.00"))):
                 result = await service.evaluate_application(payload)

        assert result.decision == DecisionEnum.REJECTED
        assert "credit" in result.rejection_reason.lower()

    def test_calculate_monthly_mortgage_payment(self, service):
        """Test standard mortgage payment calculation (P & I)."""
        principal = Decimal("500000.00")
        annual_rate = Decimal("0.05") # 5%
        months = 300 # 25 years
        
        # Using standard formula: M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # i = 0.05 / 12 = 0.004166...
        payment = service._calculate_payment(principal, annual_rate, months)
        
        # Expected approx: 2922.95
        assert payment > Decimal("2900.00")
        assert payment < Decimal("2950.00")
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from mortgage_underwriting.modules.borrower.models import Borrower
from mortgage_underwriting.modules.property.models import Property as PropertyModel
from mortgage_underwriting.modules.underwriting_engine.models import UnderwritingDecision

@pytest.mark.integration
@pytest.mark.asyncio
class TestUnderwritingEngineIntegration:
    """
    Integration tests for the Underwriting Engine API.
    Tests the full request lifecycle: API -> Service -> DB.
    """

    async def test_full_workflow_approve(self, app: "FastAPI", db_session: AsyncSession):
        """
        Test creating borrower, property, and then evaluating the mortgage.
        Expect APPROVED decision.
        """
        # 1. Setup Data in DB (Direct DB manipulation for setup)
        borrower = Borrower(
            first_name="Jane",
            last_name="Smith",
            sin_hash="hash123", # PII encrypted/hashed in real app
            date_of_birth="1990-01-01",
            credit_score=780,
            annual_income=Decimal("150000.00"),
            monthly_debt=Decimal("400.00")
        )
        db_session.add(borrower)
        await db_session.flush()
        
        property_obj = PropertyModel(
            address="456 Oak Ave",
            city="Vancouver",
            province="BC",
            postal_code="V6A1B2",
            property_value=Decimal("1000000.00")
        )
        db_session.add(property_obj)
        await db_session.flush()
        
        await db_session.commit()

        # 2. Call Underwriting API
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": borrower.id,
                    "property_id": property_obj.id,
                    "loan_amount": "800000.00", # 80% LTV
                    "down_payment": "200000.00",
                    "amortization_years": 25,
                    "contract_rate": "4.5",
                    "property_tax_annual": "6000.00",
                    "heating_cost_monthly": "200.00",
                    "condo_fees_monthly": "0.00"
                }
            )

        # 3. Assertions
        assert response.status_code == 201
        data = response.json()
        
        assert data["decision"] == "APPROVED"
        assert data["borrower_id"] == borrower.id
        assert data["insurance_required"] is False # LTV is 80%
        
        # Verify DB Record
        decision_record = await db_session.get(UnderwritingDecision, data["id"])
        assert decision_record is not None
        assert decision_record.decision == "APPROVED"

    async def test_full_workflow_reject_high_gds(self, app: "FastAPI", db_session: AsyncSession):
        """
        Test workflow where borrower is rejected due to high GDS.
        """
        # 1. Setup Data: High Property Tax/Low Income scenario
        borrower = Borrower(
            first_name="Low",
            last_name="Income",
            sin_hash="hash456",
            date_of_birth="1985-05-05",
            credit_score=700,
            annual_income=Decimal("60000.00"), # Low income
            monthly_debt=Decimal("0.00")
        )
        db_session.add(borrower)
        await db_session.flush()
        
        property_obj = PropertyModel(
            address="789 Pine Rd",
            city="Toronto",
            province="ON",
            postal_code="M5H2N2",
            property_value=Decimal("600000.00")
        )
        db_session.add(property_obj)
        await db_session.flush()
        
        await db_session.commit()

        # 2. Call API
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": borrower.id,
                    "property_id": property_obj.id,
                    "loan_amount": "550000.00", # High loan relative to income
                    "down_payment": "50000.00",
                    "amortization_years": 25,
                    "contract_rate": "5.0",
                    "property_tax_annual": "8000.00", # High tax
                    "heating_cost_monthly": "300.00",
                    "condo_fees_monthly": "500.00" # Condo fees
                }
            )

        # 3. Assertions
        assert response.status_code == 201 # API accepts request, logic rejects app
        data = response.json()
        
        assert data["decision"] == "REJECTED"
        assert "GDS" in data["rejection_reason"]
        assert data["gds_ratio"] > 39 # OSFI Limit

    async def test_get_decision_history(self, app: "FastAPI", db_session: AsyncSession):
        """
        Test retrieving the history of decisions for a specific borrower.
        """
        # 1. Setup Data
        borrower = Borrower(
            first_name="History",
            last_name="Test",
            sin_hash="hash789",
            date_of_birth="1992-02-02",
            credit_score=720,
            annual_income=Decimal("90000.00"),
            monthly_debt=Decimal("100.00")
        )
        db_session.add(borrower)
        await db_session.flush()
        
        property_obj = PropertyModel(
            address="321 Elm St",
            city="Montreal",
            province="QC",
            postal_code="H2X1Y1",
            property_value=Decimal("400000.00")
        )
        db_session.add(property_obj)
        await db_session.flush()
        await db_session.commit()

        # Create two decisions
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First Request
            await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": borrower.id,
                    "property_id": property_obj.id,
                    "loan_amount": "320000.00",
                    "down_payment": "80000.00",
                    "amortization_years": 20,
                    "contract_rate": "3.5",
                    "property_tax_annual": "3000.00",
                    "heating_cost_monthly": "120.00",
                    "condo_fees_monthly": "0.00"
                }
            )
            
            # Second Request (different loan)
            await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": borrower.id,
                    "property_id": property_obj.id,
                    "loan_amount": "350000.00",
                    "down_payment": "50000.00",
                    "amortization_years": 25,
                    "contract_rate": "4.0",
                    "property_tax_annual": "3000.00",
                    "heating_cost_monthly": "120.00",
                    "condo_fees_monthly": "0.00"
                }
            )

            # Get History
            response = await client.get(f"/api/v1/underwriting/decisions?borrower_id={borrower.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        # Check pagination or list structure
        assert all("decision" in item for item in data)

    async def test_invalid_input_validation(self, app: "FastAPI"):
        """
        Test that API rejects invalid payloads (422 Unprocessable Entity).
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing required field
            response = await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": 1,
                    # missing property_id
                    "loan_amount": "100000.00",
                }
            )
            
        assert response.status_code == 422

    async def test_cmhc_premium_calculation_integration(self, app: "FastAPI", db_session: AsyncSession):
        """
        Verify that the calculated insurance premium is saved correctly.
        Scenario: LTV 90% (Tier 3.10%).
        """
        borrower = Borrower(
            first_name="Premium",
            last_name="Check",
            sin_hash="hash999",
            date_of_birth="1988-08-08",
            credit_score=680,
            annual_income=Decimal("100000.00"),
            monthly_debt=Decimal("0.00")
        )
        db_session.add(borrower)
        await db_session.flush()
        
        property_obj = PropertyModel(
            address="555 Bay St",
            city="Toronto",
            province="ON",
            postal_code="M5J2M2",
            property_value=Decimal("500000.00")
        )
        db_session.add(property_obj)
        await db_session.flush()
        await db_session.commit()

        # Loan 450k on 500k value = 90% LTV
        # Premium 3.10% on 450k = 13,950
        loan_amount = Decimal("450000.00")
        expected_premium = loan_amount * Decimal("0.0310")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/underwriting/evaluate",
                json={
                    "borrower_id": borrower.id,
                    "property_id": property_obj.id,
                    "loan_amount": str(loan_amount),
                    "down_payment": "50000.00",
                    "amortization_years": 25,
                    "contract_rate": "5.0",
                    "property_tax_annual": "5000.00",
                    "heating_cost_monthly": "150.00",
                    "condo_fees_monthly": "0.00"
                }
            )

        assert response.status_code == 201
        data = response.json()
        
        assert data["insurance_required"] is True
        # Compare as Decimal to avoid float precision issues in JSON parsing
        assert Decimal(data["insurance_premium"]) == expected_premium
```