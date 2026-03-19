--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# Import paths based on project structure
from mortgage_underwriting.modules.orchestrator.routes import router as orchestrator_router
from mortgage_underwriting.common.database import Base

# Using SQLite for integration test speed, usually project would use Test Postgres
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

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(orchestrator_router, prefix="/api/v1/orchestrator")
    return app

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_db_session():
    """Mock DB session for unit tests"""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    return session

@pytest.fixture
def valid_application_payload():
    return {
        "borrower_id": "12345",
        "property_id": "prop-99",
        "loan_amount": "450000.00",
        "contract_rate": "4.50",
        "amortization_years": 25,
        "down_payment": "90000.00"
    }

@pytest.fixture
def mock_borrower_service():
    service = AsyncMock()
    # Simulate a borrower with specific income/debts
    service.get_borrower_summary.return_value = {
        "annual_income": Decimal("120000.00"),
        "monthly_debts": Decimal("500.00"), # Non-housing
        "credit_score": 750
    }
    return service

@pytest.fixture
def mock_property_service():
    service = AsyncMock()
    # Simulate property value
    service.get_property_details.return_value = {
        "value": Decimal("540000.00"),
        "address": "123 Maple Dr",
        "type": "detached"
    }
    return service

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, call
from mortgage_underwriting.modules.orchestrator.services import OrchestratorService
from mortgage_underwriting.modules.orchestrator.exceptions import UnderwritingError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestOrchestratorService:

    @pytest.mark.asyncio
    async def test_process_application_success_approved(self, mock_db_session, mock_borrower_service, mock_property_service):
        """
        Test successful underwriting where GDS/TDS are within limits.
        Loan: 450k, Rate: 4.5%, Income: 120k.
        Qualifying Rate: max(4.5 + 2, 5.25) = 6.5%.
        Monthly Payment (approx 25y @ 6.5): ~3050.
        Property Tax (est): 3500/yr -> ~291/mo.
        Heating (est): 150/mo.
        Total Housing: 3050 + 291 + 150 = 3491.
        GDS = (3491 * 12) / 120000 = 34.9% (Pass < 39%)
        TDS = ((3491 + 500) * 12) / 120000 = 39.9% (Pass < 44%)
        """
        payload = {
            "borrower_id": "bor-1",
            "property_id": "prop-1",
            "loan_amount": Decimal("450000.00"),
            "contract_rate": Decimal("4.50"),
            "amortization_years": 25,
            "down_payment": Decimal("90000.00")
        }

        # Mock calculation logic helper inside service or verify logic flow
        with patch('mortgage_underwriting.modules.orchestrator.services.BorrowerService', return_value=mock_borrower_service), \
             patch('mortgage_underwriting.modules.orchestrator.services.PropertyService', return_value=mock_property_service):
            
            service = OrchestratorService(mock_db_session)
            result = await service.process_application(payload)

            assert result["decision"] == "Approved"
            assert result["gds_ratio"] <= Decimal("0.39")
            assert result["tds_ratio"] <= Decimal("0.44")
            assert "qualifying_rate" in result

    @pytest.mark.asyncio
    async def test_process_application_decline_high_gds(self, mock_db_session, mock_borrower_service, mock_property_service):
        """
        Test OSFI B-20 compliance: GDS limit 39%.
        Scenario: Low income relative to housing costs.
        """
        # Override borrower to have low income
        mock_borrower_service.get_borrower_summary.return_value = {
            "annual_income": Decimal("50000.00"),
            "monthly_debts": Decimal("0.00"),
            "credit_score": 800
        }

        payload = {
            "borrower_id": "bor-2",
            "property_id": "prop-2",
            "loan_amount": Decimal("400000.00"),
            "contract_rate": Decimal("5.00"),
            "amortization_years": 25,
            "down_payment": Decimal("80000.00")
        }

        with patch('mortgage_underwriting.modules.orchestrator.services.BorrowerService', return_value=mock_borrower_service), \
             patch('mortgage_underwriting.modules.orchestrator.services.PropertyService', return_value=mock_property_service):
            
            service = OrchestratorService(mock_db_session)
            result = await service.process_application(payload)

            assert result["decision"] == "Declined"
            assert "GDS" in result["reasons"]

    @pytest.mark.asyncio
    async def test_process_application_decline_high_tds(self, mock_db_session, mock_borrower_service, mock_property_service):
        """
        Test OSFI B-20 compliance: TDS limit 44%.
        Scenario: High external debt.
        """
        # Override borrower to have massive external debt
        mock_borrower_service.get_borrower_summary.return_value = {
            "annual_income": Decimal("100000.00"),
            "monthly_debts": Decimal("4000.00"), # High debt
            "credit_score": 700
        }

        payload = {
            "borrower_id": "bor-3",
            "property_id": "prop-3",
            "loan_amount": Decimal("300000.00"),
            "contract_rate": Decimal("3.00"),
            "amortization_years": 25,
            "down_payment": Decimal("60000.00")
        }

        with patch('mortgage_underwriting.modules.orchestrator.services.BorrowerService', return_value=mock_borrower_service), \
             patch('mortgage_underwriting.modules.orchestrator.services.PropertyService', return_value=mock_property_service):
            
            service = OrchestratorService(mock_db_session)
            result = await service.process_application(payload)

            assert result["decision"] == "Declined"
            assert "TDS" in result["reasons"]

    @pytest.mark.asyncio
    async def test_calculate_qualifying_rate_stress_test(self):
        """
        Test OSFI B-20 Stress Test logic:
        Qualifying Rate = max(contract_rate + 2%, 5.25%)
        """
        service = OrchestratorService(AsyncMock())

        # Case 1: Contract rate is low (e.g., 3.0). 3.0 + 2 = 5.0. Floor is 5.25.
        rate_1 = service._calculate_qualifying_rate(Decimal("3.00"))
        assert rate_1 == Decimal("5.25")

        # Case 2: Contract rate is high (e.g., 5.0). 5.0 + 2 = 7.0. Max is 7.0.
        rate_2 = service._calculate_qualifying_rate(Decimal("5.00"))
        assert rate_2 == Decimal("7.00")

        # Case 3: Boundary (3.25). 3.25 + 2 = 5.25. Max is 5.25.
        rate_3 = service._calculate_qualifying_rate(Decimal("3.25"))
        assert rate_3 == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_insurance_required_cmhc_logic(self, mock_db_session):
        """
        Test CMHC logic: LTV > 80% requires insurance.
        LTV = Loan / Property Value
        """
        # Loan 400k, Value 500k -> LTV 80% -> No insurance
        assert not OrchestratorService._check_insurance_required(Decimal("400000"), Decimal("500000"))
        
        # Loan 400001, Value 500k -> LTV > 80% -> Insurance
        assert OrchestratorService._check_insurance_required(Decimal("400001"), Decimal("500000"))

        # Loan 475k, Value 500k -> LTV 95% -> Insurance
        assert OrchestratorService._check_insurance_required(Decimal("475000"), Decimal("500000"))

    @pytest.mark.asyncio
    async def test_service_exception_borrower_not_found(self, mock_db_session, mock_borrower_service, mock_property_service):
        """
        Test handling of upstream dependency failures.
        """
        mock_borrower_service.get_borrower_summary.side_effect = AppException("Borrower not found")

        payload = {
            "borrower_id": "ghost",
            "property_id": "prop-1",
            "loan_amount": Decimal("100.00"),
            "contract_rate": Decimal("3.00"),
            "amortization_years": 25,
            "down_payment": Decimal("10.00")
        }

        with patch('mortgage_underwriting.modules.orchestrator.services.BorrowerService', return_value=mock_borrower_service), \
             patch('mortgage_underwriting.modules.orchestrator.services.PropertyService', return_value=mock_property_service):
            
            service = OrchestratorService(mock_db_session)
            
            with pytest.raises(AppException) as exc_info:
                await service.process_application(payload)
            
            assert "Borrower not found" in str(exc_info.value)

--- integration_tests ---
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from mortgage_underwriting.modules.orchestrator.models import Application
from decimal import Decimal

@pytest.mark.integration
class TestOrchestratorRoutes:

    @pytest.mark.asyncio
    async def test_create_application_and_approve(self, client: AsyncClient, db_session: AsyncSession):
        """
        Full workflow: Submit application -> Orchestrator processes -> Returns Decision
        """
        payload = {
            "borrower_id": "int-bor-1",
            "property_id": "int-prop-1",
            "loan_amount": "500000.00",
            "contract_rate": "4.00",
            "amortization_years": 25,
            "down_payment": "100000.00"
        }

        # Note: This test assumes the orchestrator has access to mockable or real data 
        # for the borrower/property. In a real integration test, we might seed those tables first.
        # Here we test the API contract and the persistence of the Application record.
        
        response = await client.post("/api/v1/orchestrator/apply", json=payload)
        
        # Assert API Response
        assert response.status_code in [201, 202] # Accepted or Created immediately
        
        data = response.json()
        assert "id" in data
        assert "status" in data
        
        # Verify Database Record (FINTRAC: Audit trail)
        stmt = select(Application).where(Application.id == data["id"])
        result = await db_session.execute(stmt)
        app_record = result.scalar_one_or_none()
        
        assert app_record is not None
        assert app_record.borrower_id == "int-bor-1"
        assert app_record.loan_amount == Decimal("500000.00")
        assert app_record.created_at is not None # Audit trail requirement

    @pytest.mark.asyncio
    async def test_get_application_status(self, client: AsyncClient, db_session: AsyncSession):
        """
        Test retrieving a specific application status.
        """
        # Create an application directly in DB
        new_app = Application(
            borrower_id="bor-status",
            property_id="prop-status",
            loan_amount=Decimal("200000.00"),
            contract_rate=Decimal("3.5"),
            amortization_years=20,
            down_payment=Decimal("40000.00"),
            status="Completed",
            decision="Approved"
        )
        db_session.add(new_app)
        await db_session.commit()
        await db_session.refresh(new_app)

        response = await client.get(f"/api/v1/orchestrator/applications/{new_app.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(new_app.id)
        assert data["status"] == "Completed"
        assert data["decision"] == "Approved"
        # Ensure PII is not leaked (SIN/DOB not in response)
        assert "sin" not in data
        assert "date_of_birth" not in data

    @pytest.mark.asyncio
    async def test_create_application_validation_error(self, client: AsyncClient):
        """
        Test input validation: Negative loan amount should be rejected immediately.
        """
        payload = {
            "borrower_id": "bor-1",
            "property_id": "prop-1",
            "loan_amount": "-50000.00", # Invalid
            "contract_rate": "4.00",
            "amortization_years": 25,
            "down_payment": "10000.00"
        }

        response = await client.post("/api/v1/orchestrator/apply", json=payload)
        
        assert response.status_code == 422 # Unprocessable Entity
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_get_non_existent_application(self, client: AsyncClient):
        """
        Test 404 handling.
        """
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/v1/orchestrator/applications/{fake_id}")
        
        assert response.status_code == 404

# Import select for the integration test
from sqlalchemy import select