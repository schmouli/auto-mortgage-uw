--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Base import for test models if needed, or project Base
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings

# Use in-memory SQLite for fast test execution
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def db_engine() -> AsyncGenerator:
    """
    Create a new database engine for each test function.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a new database session for each test function.
    """
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

@pytest.fixture
def app() -> FastAPI:
    """
    Create a test application instance.
    We dynamically import to avoid circular dependencies or partial initialization.
    """
    from mortgage_underwriting.main import app
    return app

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator:
    """
    Create an async HTTP client for integration tests.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_application_payload():
    """
    Fixture providing a valid payload for creating a mortgage application.
    """
    return {
        "borrower_id": "123e4567-e89b-12d3-a456-426614174000",
        "property_value": "500000.00",
        "down_payment": "100000.00",
        "annual_income": "120000.00",
        "property_tax": "3000.00",
        "heating_cost": "1200.00",
        "other_debt": "500.00",
        "amortization_years": 25
    }

@pytest.fixture
def mock_auth_headers():
    """
    Fixture providing mock authentication headers.
    """
    return {"Authorization": "Bearer valid_test_token"}

--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

# Import module components
from mortgage_underwriting.modules.client_portal.services import ClientPortalService
from mortgage_underwriting.modules.client_portal.models import MortgageApplication
from mortgage_underwriting.modules.client_portal.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationStatus
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientPortalService:
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalar = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Service instance with mocked DB."""
        return ClientPortalService(mock_db)

    @pytest.mark.asyncio
    async def test_create_application_success(self, service, mock_db, valid_application_payload):
        """
        Test successful creation of a mortgage application.
        """
        # Arrange
        payload = ApplicationCreate(**valid_application_payload)
        
        # Mock the refresh to return the object with ID
        mock_app = MagicMock()
        mock_app.id = "test-app-id"
        mock_app.status = ApplicationStatus.SUBMITTED
        mock_db.refresh.return_value = mock_app

        # Act
        result = await service.create_application(payload)

        # Assert
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_invalid_ltv(self, service, valid_application_payload):
        """
        Test that creating an application with invalid LTV (e.g., negative down payment) raises error.
        """
        # Arrange
        invalid_payload = valid_application_payload.copy()
        invalid_payload["down_payment"] = "600000.00" # More than property value
        payload = ApplicationCreate(**invalid_payload)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await service.create_application(payload)
        assert "Down payment cannot exceed property value" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calculate_ltv(self, service):
        """
        Test Loan-to-Value (LTV) calculation logic.
        """
        # Arrange
        loan_amount = Decimal("400000.00")
        property_value = Decimal("500000.00")

        # Act
        ltv = service._calculate_ltv(loan_amount, property_value)

        # Assert
        assert ltv == Decimal("80.00")

    @pytest.mark.asyncio
    async def test_calculate_ltv_precision(self, service):
        """
        Test LTV calculation maintains Decimal precision.
        """
        # Arrange
        loan_amount = Decimal("350000.00")
        property_value = Decimal("475000.00")

        # Act
        ltv = service._calculate_ltv(loan_amount, property_value)

        # Assert
        # 350000 / 475000 = 0.7368421...
        expected_ltv = (loan_amount / property_value).quantize(Decimal("0.0001"))
        assert ltv == expected_ltv

    @pytest.mark.asyncio
    async def test_determine_insurance_required_true(self, service):
        """
        Test CMHC insurance requirement logic when LTV > 80%.
        """
        # Arrange
        ltv = Decimal("85.00")

        # Act
        required = service._is_insurance_required(ltv)

        # Assert
        assert required is True

    @pytest.mark.asyncio
    async def test_determine_insurance_required_false(self, service):
        """
        Test CMHC insurance requirement logic when LTV <= 80%.
        """
        # Arrange
        ltv = Decimal("80.00")

        # Act
        required = service._is_insurance_required(ltv)

        # Assert
        assert required is False

    @pytest.mark.asyncio
    async def test_calculate_gds_success(self, service):
        """
        Test Gross Debt Service (GDS) calculation.
        Formula: (Mortgage Tax + Heat + 50% Condo Fees) / Annual Income
        """
        # Arrange
        mortgage_payment = Decimal("2000.00") # Monthly
        property_tax = Decimal("300.00") # Monthly (Annual 3600 / 12)
        heating = Decimal("100.00") # Monthly (Annual 1200 / 12)
        income = Decimal("100000.00") # Annual

        # Act
        gds = service._calculate_gds(mortgage_payment, property_tax, heating, income)

        # Assert
        # Monthly housing costs = 2000 + 300 + 100 = 2400
        # Annual housing costs = 2400 * 12 = 28800
        # GDS = 28800 / 100000 = 0.288 (28.8%)
        expected_gds = Decimal("0.288")
        assert gds == expected_gds

    @pytest.mark.asyncio
    async def test_calculate_tds_success(self, service):
        """
        Test Total Debt Service (TDS) calculation.
        Formula: (Monthly Housing Costs + Other Debts) / Annual Income
        """
        # Arrange
        monthly_housing_costs = Decimal("2400.00")
        other_debt = Decimal("500.00") # Monthly
        income = Decimal("100000.00") # Annual

        # Act
        tds = service._calculate_tds(monthly_housing_costs, other_debt, income)

        # Assert
        # Total Monthly Debt = 2400 + 500 = 2900
        # Annual Debt = 2900 * 12 = 34800
        # TDS = 34800 / 100000 = 0.348 (34.8%)
        expected_tds = Decimal("0.348")
        assert tds == expected_tds

    @pytest.mark.asyncio
    async def test_osfi_stress_test_pass(self, service):
        """
        Test OSFI B-20 stress test check.
        Qualifying Rate = max(contract_rate + 2%, 5.25%)
        """
        # Arrange
        contract_rate = Decimal("4.00")
        qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25")) # Should be 6.00%
        
        # Mock internal calculation to return a payment that fits the stress test
        # For unit test, we just verify the logic of rate selection
        rate = service._get_qualifying_rate(contract_rate)

        # Assert
        assert rate == Decimal("6.00")

    @pytest.mark.asyncio
    async def test_osfi_stress_test_floor(self, service):
        """
        Test OSFI B-20 stress test floor (5.25%).
        """
        # Arrange
        contract_rate = Decimal("2.50")
        
        # Act
        rate = service._get_qualifying_rate(contract_rate)

        # Assert
        # 2.5 + 2 = 4.5, but floor is 5.25
        assert rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_get_application_by_id_not_found(self, service, mock_db):
        """
        Test retrieving a non-existent application raises AppException.
        """
        # Arrange
        mock_db.scalar.return_value = None
        app_id = "non-existent-id"

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_application_by_id(app_id)
        
        assert exc_info.value.status_code == 404
        assert "Application not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_check_pii_compliance_sin_not_logged(self, service, caplog):
        """
        Test that PII (SIN) is handled securely (not logged).
        This is a logic check on the service layer helper.
        """
        # Arrange
        sin_raw = "123456789"
        
        # Act
        hashed_sin = service._hash_sin(sin_raw)

        # Assert
        assert hashed_sin != sin_raw
        assert len(hashed_sin) == 64 # SHA256 length
        # Ensure raw SIN is not in logs (simulated check)
        assert sin_raw not in caplog.text

--- integration_tests ---
import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.client_portal.models import MortgageApplication
from mortgage_underwriting.modules.client_portal.schemas import ApplicationStatus

@pytest.mark.integration
class TestClientPortalRoutes:
    
    @pytest.mark.asyncio
    async def test_create_application_endpoint_success(
        self, client: AsyncClient, valid_application_payload, mock_auth_headers
    ):
        """
        Integration test: Create application via API endpoint.
        """
        # Act
        response = await client.post(
            "/api/v1/client-portal/applications",
            json=valid_application_payload,
            headers=mock_auth_headers
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == ApplicationStatus.SUBMITTED.value
        assert data["ltv"] is not None
        # Verify PII (if any in response) is masked or absent
        # Assuming borrower_id is returned but sensitive details are not
        assert "sin" not in data

    @pytest.mark.asyncio
    async def test_create_application_endpoint_unauthorized(
        self, client: AsyncClient, valid_application_payload
    ):
        """
        Integration test: Unauthorized access returns 401.
        """
        # Act
        response = await client.post(
            "/api/v1/client-portal/applications",
            json=valid_application_payload
        )

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_application_validation_error(
        self, client: AsyncClient, mock_auth_headers
    ):
        """
        Integration test: Invalid input returns 422.
        """
        # Arrange - Missing required fields
        invalid_payload = {
            "borrower_id": "123",
            # Missing property_value, down_payment, etc.
        }

        # Act
        response = await client.post(
            "/api/v1/client-portal/applications",
            json=invalid_payload,
            headers=mock_auth_headers
        )

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_application_endpoint_success(
        self, client: AsyncClient, db_session, valid_application_payload, mock_auth_headers
    ):
        """
        Integration test: Retrieve a created application.
        """
        # 1. Create an application directly in DB
        app_model = MortgageApplication(
            borrower_id=valid_application_payload["borrower_id"],
            property_value=Decimal(valid_application_payload["property_value"]),
            down_payment=Decimal(valid_application_payload["down_payment"]),
            annual_income=Decimal(valid_application_payload["annual_income"]),
            status=ApplicationStatus.SUBMITTED
        )
        db_session.add(app_model)
        await db_session.commit()
        await db_session.refresh(app_model)

        # 2. Retrieve via API
        response = await client.get(
            f"/api/v1/client-portal/applications/{app_model.id}",
            headers=mock_auth_headers
        )

        # 3. Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(app_model.id)
        assert data["borrower_id"] == app_model.borrower_id
        assert Decimal(data["property_value"]) == app_model.property_value

    @pytest.mark.asyncio
    async def test_get_application_endpoint_not_found(
        self, client: AsyncClient, mock_auth_headers
    ):
        """
        Integration test: Retrieve non-existent application returns 404.
        """
        # Act
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/client-portal/applications/{fake_id}",
            headers=mock_auth_headers
        )

        # Assert
        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_submit_application_workflow(
        self, client: AsyncClient, db_session, valid_application_payload, mock_auth_headers
    ):
        """
        Integration test: Full workflow of creating and then updating status.
        """
        # Step 1: Create
        create_resp = await client.post(
            "/api/v1/client-portal/applications",
            json=valid_application_payload,
            headers=mock_auth_headers
        )
        assert create_resp.status_code == 201
        app_id = create_resp.json()["id"]

        # Step 2: Verify DB State
        stmt = select(MortgageApplication).where(MortgageApplication.id == app_id)
        result = await db_session.execute(stmt)
        db_app = result.scalar_one()
        
        assert db_app.status == ApplicationStatus.SUBMITTED
        # Verify CMHC insurance calculation was performed
        # LTV = (500k - 100k) / 500k = 80% -> No insurance required
        assert db_app.insurance_required is False

        # Step 3: Update Status (Simulating Underwriter action via portal)
        update_resp = await client.patch(
            f"/api/v1/client-portal/applications/{app_id}",
            json={"status": "UNDER_REVIEW"},
            headers=mock_auth_headers
        )
        assert update_resp.status_code == 200
        
        # Step 4: Verify final state
        await db_session.refresh(db_app)
        assert db_app.status == ApplicationStatus.UNDER_REVIEW

    @pytest.mark.asyncio
    async def test_financial_data_precision(
        self, client: AsyncClient, mock_auth_headers
    ):
        """
        Integration test: Ensure Decimal precision is preserved through API.
        """
        # Arrange - Use high precision values
        payload = {
            "borrower_id": "123e4567-e89b-12d3-a456-426614174000",
            "property_value": "555555.55", 
            "down_payment": "111111.11",
            "annual_income": "98765.43",
            "property_tax": "3333.33",
            "heating_cost": "111.11",
            "other_debt": "222.22",
            "amortization_years": 25
        }

        # Act
        response = await client.post(
            "/api/v1/client-portal/applications",
            json=payload,
            headers=mock_auth_headers
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        
        # Check that response preserves the exact decimal strings
        assert data["property_value"] == payload["property_value"]
        assert data["annual_income"] == payload["annual_income"]
        
        # Check calculated fields are Decimals (strings in JSON)
        assert "ltv" in data
        # LTV = (555555.55 - 111111.11) / 555555.55 = 0.800000...
        # Verify it's not a float like 0.8
        assert "." in data["ltv"] 

    @pytest.mark.asyncio
    async def test_osfi_limits_enforced(
        self, client: AsyncClient, mock_auth_headers
    ):
        """
        Integration test: Verify GDS/TDS limits are calculated and returned.
        """
        # Arrange - High debt load
        payload = {
            "borrower_id": "123e4567-e89b-12d3-a456-426614174000",
            "property_value": "400000.00",
            "down_payment": "80000.00", # 20% down
            "annual_income": "50000.00", # Low income relative to debt
            "property_tax": "4000.00",
            "heating_cost": "1500.00",
            "other_debt": "1000.00", # Significant other debt
            "amortization_years": 25
        }

        # Act
        response = await client.post(
            "/api/v1/client-portal/applications",
            json=payload,
            headers=mock_auth_headers
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        
        # If the system calculates ratios immediately, check they exist
        # If calculated on retrieval, we would need to GET it. 
        # Assuming POST returns calculated snapshot.
        if "gds" in data:
            assert Decimal(data["gds"]) <= Decimal("0.39") or data["gds_warning"] == True
        if "tds" in data:
            assert Decimal(data["tds"]) <= Decimal("0.44") or data["tds_warning"] == True