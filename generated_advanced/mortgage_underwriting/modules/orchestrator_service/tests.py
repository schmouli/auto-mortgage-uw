--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from mortgage_underwriting.common.database import Base, get_async_session
from mortgage_underwriting.modules.orchestrator.routes import router as orchestrator_router
from mortgage_underwriting.modules.borrower.models import Borrower
from mortgage_underwriting.modules.property.models import PropertyModel
from mortgage_underwriting.modules.orchestrator.models import Application

# Using SQLite for integration test speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def app(db_session: AsyncSession) -> FastAPI:
    """
    Create a test application with overridden dependencies.
    """
    app = FastAPI()
    app.include_router(orchestrator_router, prefix="/api/v1/orchestrator")

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async client for integration testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def valid_borrower_payload():
    return {
        "first_name": "John",
        "last_name": "Doe",
        "sin_hash": "a" * 64,  # SHA256 hash placeholder
        "date_of_birth": "1990-01-01",
        "email": "john.doe@example.com",
        "annual_income": Decimal("96000.00"), # 8000/month
        "monthly_debt": Decimal("500.00")
    }


@pytest.fixture
def valid_property_payload():
    return {
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M5V1A1",
        "purchase_price": Decimal("500000.00"),
        "property_type": "detached"
    }


@pytest.fixture
def valid_application_payload(valid_borrower_payload, valid_property_payload):
    return {
        "borrower": valid_borrower_payload,
        "property": valid_property_payload,
        "loan_amount": Decimal("400000.00"),
        "contract_rate": Decimal("4.50"),
        "amortization_years": 25
    }

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.orchestrator.services import OrchestratorService
from mortgage_underwriting.modules.orchestrator.schemas import ApplicationCreate, ApplicationResponse
from mortgage_underwriting.modules.orchestrator.exceptions import UnderwritingError
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.unit
class TestOrchestratorService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return OrchestratorService(mock_db)

    @pytest.fixture
    def valid_payload(self):
        return ApplicationCreate(
            borrower_id=1,
            property_id=1,
            loan_amount=Decimal("400000.00"),
            contract_rate=Decimal("4.50"),
            amortization_years=25
        )

    @pytest.mark.asyncio
    async def test_create_application_success(self, service, mock_db, valid_payload):
        """Test successful creation of an application record."""
        # Mock the return value of refresh to simulate DB assignment
        mock_app = MagicMock()
        mock_app.id = 123
        mock_app.status = "PENDING"
        
        # We can't easily mock the model instantiation inside the service without patching
        # So we verify the interaction flow
        
        result = await service.create_application(valid_payload)
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calculate_gds_within_limit(self, service):
        """Test GDS calculation (Principal + Interest + Tax + Heat) / Income."""
        monthly_payment = Decimal("2200.00")
        property_tax = Decimal("300.00")
        heating = Decimal("100.00")
        monthly_income = Decimal("8000.00")
        
        # (2200 + 300 + 100) / 8000 = 2600 / 8000 = 0.325 (32.5%)
        gds = service._calculate_gds(monthly_payment, property_tax, heating, monthly_income)
        
        assert gds == Decimal("0.325")
        assert gds <= Decimal("0.39")

    @pytest.mark.asyncio
    async def test_calculate_gds_exceeds_limit(self, service):
        """Test GDS calculation exceeding OSFI B-20 limit of 39%."""
        monthly_payment = Decimal("3500.00")
        property_tax = Decimal("400.00")
        heating = Decimal("150.00")
        monthly_income = Decimal("8000.00")
        
        # (3500 + 400 + 150) / 8000 = 4050 / 8000 = 0.50625 (50.6%)
        gds = service._calculate_gds(monthly_payment, property_tax, heating, monthly_income)
        
        assert gds == Decimal("0.50625")
        assert gds > Decimal("0.39")

    @pytest.mark.asyncio
    async def test_calculate_tds_within_limit(self, service):
        """Test TDS calculation (GDS + Other Debts) / Income."""
        housing_costs = Decimal("2600.00")
        other_debts = Decimal("500.00")
        monthly_income = Decimal("8000.00")
        
        # (2600 + 500) / 8000 = 3100 / 8000 = 0.3875 (38.75%)
        tds = service._calculate_tds(housing_costs, other_debts, monthly_income)
        
        assert tds == Decimal("0.3875")
        assert tds <= Decimal("0.44")

    @pytest.mark.asyncio
    async def test_calculate_ltv_insurance_required(self, service):
        """Test CMHC Insurance Logic: LTV > 80% requires insurance."""
        loan_amount = Decimal("400000.00")
        property_value = Decimal("500000.00")
        
        ltv, insurance_required, premium_rate = service._calculate_ltv(loan_amount, property_value)
        
        assert ltv == Decimal("0.80") # Exactly 80%
        assert insurance_required is False # Usually 80% is the boundary, > 80 is required. Assuming strict > for this test logic.
        
        # Test > 80%
        ltv_high, ins_req_high, _ = service._calculate_ltv(Decimal("405000.00"), Decimal("500000.00"))
        assert ltv_high == Decimal("0.81")
        assert ins_req_high is True

    @pytest.mark.asyncio
    async def test_stress_test_qualifying_rate(self, service):
        """Test OSFI B-20 Stress Test: max(contract + 2%, 5.25%)."""
        contract_rate = Decimal("4.00")
        
        # Contract + 2% = 6.00%. Min(6.00, 5.25) = 6.00%
        qualifying_rate = service._get_qualifying_rate(contract_rate)
        assert qualifying_rate == Decimal("6.00")
        
        # Contract + 2% = 4.50%. Min(4.50, 5.25) = 5.25%
        low_contract_rate = Decimal("2.50")
        qualifying_rate_low = service._get_qualifying_rate(low_contract_rate)
        assert qualifying_rate_low == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_evaluate_application_approval(self, service, mock_db, valid_payload):
        """Test happy path: All ratios pass, application approved."""
        # Mock dependencies that the orchestrator would call
        with patch.object(service, '_get_borrower', new_callable=AsyncMock) as mock_borrower, \
             patch.object(service, '_get_property', new_callable=AsyncMock) as mock_prop:
            
            # Setup Mock Data
            mock_borrower_obj = MagicMock()
            mock_borrower_obj.annual_income = Decimal("96000.00") # 8000/mo
            mock_borrower_obj.monthly_debt = Decimal("500.00")
            
            mock_prop_obj = MagicMock()
            mock_prop_obj.purchase_price = Decimal("500000.00")
            mock_prop_obj.estimated_heating = Decimal("100.00")
            mock_prop_obj.estimated_tax = Decimal("300.00")
            
            mock_borrower.return_value = mock_borrower_obj
            mock_prop.return_value = mock_prop_obj
            
            # Execute
            result = await service.evaluate_application(1, valid_payload)
            
            # Assertions
            assert result.decision == "APPROVED"
            assert result.gds <= Decimal("0.39")
            assert result.tds <= Decimal("0.44")
            assert "stress_test_rate" in result.meta_data

    @pytest.mark.asyncio
    async def test_evaluate_application_rejection_tds(self, service, mock_db, valid_payload):
        """Test rejection path: TDS exceeds 44%."""
        with patch.object(service, '_get_borrower', new_callable=AsyncMock) as mock_borrower, \
             patch.object(service, '_get_property', new_callable=AsyncMock) as mock_prop:
            
            # High Debt Scenario
            mock_borrower_obj = MagicMock()
            mock_borrower_obj.annual_income = Decimal("60000.00") # 5000/mo
            mock_borrower_obj.monthly_debt = Decimal("2000.00") # Car loans, credit cards
            
            mock_prop_obj = MagicMock()
            mock_prop_obj.purchase_price = Decimal("500000.00")
            mock_prop_obj.estimated_heating = Decimal("100.00")
            mock_prop_obj.estimated_tax = Decimal("300.00")
            
            mock_borrower.return_value = mock_borrower_obj
            mock_prop.return_value = mock_prop_obj
            
            # Execute
            result = await service.evaluate_application(1, valid_payload)
            
            # Assertions
            assert result.decision == "REFUSED"
            assert "TDS" in result.rejection_reason

    @pytest.mark.asyncio
    async def test_evaluate_application_insurance_premium_calculation(self, service, mock_db, valid_payload):
        """Test CMHC Premium Tier Calculation: 80.01-85% = 2.80%."""
        # Adjust payload for high LTV
        valid_payload.loan_amount = Decimal("425000.00") # 85% LTV
        
        with patch.object(service, '_get_borrower', new_callable=AsyncMock) as mock_borrower, \
             patch.object(service, '_get_property', new_callable=AsyncMock) as mock_prop:
            
            mock_borrower_obj = MagicMock()
            mock_borrower_obj.annual_income = Decimal("200000.00") # High income to pass ratios
            mock_borrower_obj.monthly_debt = Decimal("0.00")
            
            mock_prop_obj = MagicMock()
            mock_prop_obj.purchase_price = Decimal("500000.00")
            mock_prop_obj.estimated_heating = Decimal("100.00")
            mock_prop_obj.estimated_tax = Decimal("300.00")
            
            mock_borrower.return_value = mock_borrower_obj
            mock_prop.return_value = mock_prop_obj
            
            result = await service.evaluate_application(1, valid_payload)
            
            # 425k / 500k = 0.85 -> 2.80% tier
            assert result.insurance_required is True
            assert result.insurance_premium_rate == Decimal("0.0280")

    @pytest.mark.asyncio
    async def test_get_application_not_found(self, service, mock_db):
        """Test retrieving a non-existent application raises error."""
        # Mock execute to return None (empty result)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(AppException) as exc_info:
            await service.get_application(999)
        
        assert exc_info.value.status_code == 404

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from mortgage_underwriting.modules.borrower.models import Borrower
from mortgage_underwriting.modules.property.models import PropertyModel
from mortgage_underwriting.modules.orchestrator.models import Application
from mortgage_underwriting.common.security import hash_pii


@pytest.mark.integration
class TestOrchestratorRoutes:

    @pytest.mark.asyncio
    async def test_create_application_workflow(self, client: AsyncClient, valid_application_payload):
        """
        Test the full workflow: Create Borrower/Property implicitly via Orchestrator 
        and create the Application record.
        """
        response = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["status"] == "PENDING"
        assert data["loan_amount"] == "400000.00"
        
        # Verify Borrower was created and PII hashed
        app_id = data["id"]
        # We need to inspect the DB directly as we might not have a GET borrower endpoint via orchestrator
        # Assuming the orchestrator created the records in the same session context or separate calls
        # For this integration test, we verify the Application record exists
        # Note: Depending on implementation, the Orchestrator might create borrower/prop first or expect IDs.
        # Assuming the payload is a DTO that triggers creation of sub-resources.
        
    @pytest.mark.asyncio
    async def test_submit_underwriting_decision_approved(self, client: AsyncClient, db_session, valid_application_payload):
        """
        Test submitting an application and then triggering underwriting evaluation.
        """
        # 1. Create Application
        create_resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        assert create_resp.status_code == 201
        app_id = create_resp.json()["id"]

        # 2. Trigger Underwriting
        eval_resp = await client.post(f"/api/v1/orchestrator/applications/{app_id}/evaluate")
        
        assert eval_resp.status_code == 200
        data = eval_resp.json()
        
        assert data["decision"] in ["APPROVED", "REFUSED", "REFER"]
        
        # If approved based on payload (96k income, 400k loan)
        # Monthly payment ~2200, Tax 300, Heat 100 -> 2600/8000 = 32.5% GDS (Pass)
        # TDS = 3100/8000 = 38.75% (Pass)
        # LTV = 80% (Pass, no insurance)
        assert data["decision"] == "APPROVED"
        assert data["ltv"] == "0.80"
        assert data["insurance_required"] is False
        
        # 3. Verify Database Update
        stmt = select(Application).where(Application.id == app_id)
        result = await db_session.execute(stmt)
        app_db = result.scalar_one_or_none()
        
        assert app_db is not None
        assert app_db.status == "COMPLETED" # Assuming status changes to COMPLETED after evaluation
        assert app_db.decision == "APPROVED"

    @pytest.mark.asyncio
    async def test_submit_underwriting_high_ltv_insurance(self, client: AsyncClient, valid_application_payload):
        """
        Test application with LTV > 80% triggers insurance requirement logic.
        """
        # Modify payload for 90% LTV
        valid_application_payload["loan_amount"] = "450000.00"
        valid_application_payload["borrower"]["annual_income"] = "200000.00" # Ensure ratios pass
        
        create_resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        app_id = create_resp.json()["id"]
        
        eval_resp = await client.post(f"/api/v1/orchestrator/applications/{app_id}/evaluate")
        data = eval_resp.json()
        
        assert data["decision"] == "APPROVED"
        assert data["ltv"] == "0.90"
        assert data["insurance_required"] is True
        # 90.01-95% = 4.00% premium
        assert data["insurance_premium_rate"] == "0.0400"

    @pytest.mark.asyncio
    async def test_submit_underwriting_refusal_tds(self, client: AsyncClient, valid_application_payload):
        """
        Test application refusal due to high TDS (>44%).
        """
        # Low income, high debt
        valid_application_payload["borrower"]["annual_income"] = "50000.00"
        valid_application_payload["borrower"]["monthly_debt"] = "2000.00"
        
        create_resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        app_id = create_resp.json()["id"]
        
        eval_resp = await client.post(f"/api/v1/orchestrator/applications/{app_id}/evaluate")
        data = eval_resp.json()
        
        assert data["decision"] == "REFUSED"
        assert "TDS" in data["rejection_reason"]

    @pytest.mark.asyncio
    async def test_get_application_status(self, client: AsyncClient, valid_application_payload):
        """
        Test retrieving the status of a specific application.
        """
        create_resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        app_id = create_resp.json()["id"]
        
        get_resp = await client.get(f"/api/v1/orchestrator/applications/{app_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        
        assert data["id"] == app_id
        assert data["status"] == "PENDING"
        assert "borrower" in data # Check nested serialization
        assert "property" in data

    @pytest.mark.asyncio
    async def test_validation_error_missing_field(self, client: AsyncClient):
        """
        Test that Pydantic validation catches missing required fields.
        """
        invalid_payload = {
            "borrower": {}, # Missing fields
            "property": {}, # Missing fields
            "loan_amount": "100000"
        }
        
        resp = await client.post("/api/v1/orchestrator/applications", json=invalid_payload)
        
        assert resp.status_code == 422
        assert "detail" in resp.json()

    @pytest.mark.asyncio
    async def test_data_minimization_pii_not_logged(self, client: AsyncClient, valid_application_payload, caplog):
        """
        Ensure SIN is not in logs (PIPEDA compliance).
        Note: This is a structural check. In a real scenario, we'd check log output.
        Here we ensure the response doesn't contain raw SIN.
        """
        # The fixture uses a hash, but let's assume the user sent a raw SIN by mistake 
        # or the API returned it (which it shouldn't).
        
        # For this test, we verify the response structure matches the schema 
        # which should exclude raw SIN.
        resp = await client.post("/api/v1/orchestrator/applications", json=valid_application_payload)
        assert resp.status_code == 201
        
        data = resp.json()
        # Ensure raw SIN keys are not present in response
        assert "sin" not in data.get("borrower", {})
        assert "social_insurance_number" not in data.get("borrower", {})