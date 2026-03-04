--- conftest.py ---
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import AsyncGenerator, Generator
from fastapi import FastAPI

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_intake.routes import router as client_intake_router
from mortgage_underwriting.common.config import settings

# Use an in-memory SQLite database for testing speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Fixture to create a fresh database session for each test."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def app() -> FastAPI:
    """Fixture to create a test FastAPI app."""
    app = FastAPI()
    app.include_router(client_intake_router, prefix="/api/v1/client-intake")
    return app


@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Fixture for an HTTPX AsyncClient to test endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def valid_client_payload() -> dict:
    """Fixture for valid client creation data."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "4165550199",
        "date_of_birth": "1985-05-15",
        "sin": "123456789",  # Will be encrypted
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M5V2H7"
    }


@pytest.fixture
def valid_application_payload() -> dict:
    """Fixture for valid application submission data."""
    return {
        "client_id": 1,  # Assumed ID after creation
        "loan_amount": "450000.00",
        "property_value": "550000.00",
        "down_payment": "100000.00",
        "amortization_years": 25,
        "contract_rate": "4.50",
        "annual_property_tax": "3500.00",
        "estimated_heating_cost": "150.00",
        "monthly_debt_obligations": "500.00", # Car loan
        "annual_income": "120000.00"
    }
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.modules.client_intake.schemas import ApplicationCreate, ClientCreate
from mortgage_underwriting.modules.client_intake.exceptions import (
    ClientNotFoundError, 
    ApplicationValidationError,
    RegulatoryComplianceError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_client_success(self, mock_db, valid_client_payload):
        """Test successful client creation with PII encryption."""
        service = ClientService(mock_db)
        
        # Mock the return of execute to simulate no existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "encrypted_hash"
            
            result = await service.create_client(ClientCreate(**valid_client_payload))
            
            assert result.email == "john.doe@example.com"
            assert result.sin_hash == "encrypted_hash"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_encrypt.assert_called_once_with("123456789")

    @pytest.mark.asyncio
    async def test_create_client_duplicate_email(self, mock_db, valid_client_payload):
        """Test failure when trying to create a client with an existing email."""
        service = ClientService(mock_db)
        
        # Mock existing client
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        with pytest.raises(AppException) as exc_info:
            await service.create_client(ClientCreate(**valid_client_payload))
        
        assert "already exists" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_client_by_id_not_found(self, mock_db):
        service = ClientService(mock_db)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ClientNotFoundError):
            await service.get_client(999)


@pytest.mark.unit
class TestApplicationService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_app_payload(self):
        return ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("450000.00"),
            property_value=Decimal("550000.00"),
            down_payment=Decimal("100000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.50"),
            annual_property_tax=Decimal("3500.00"),
            estimated_heating_cost=Decimal("150.00"),
            monthly_debt_obligations=Decimal("500.00"),
            annual_income=Decimal("120000.00")
        )

    @pytest.mark.asyncio
    async def test_submit_application_success(self, mock_db, mock_app_payload):
        """Test successful application submission and GDS/TDS calculation."""
        service = ApplicationService(mock_db)
        
        # Mock client exists
        mock_client = MagicMock(id=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute.return_value = mock_result

        result = await service.submit_application(mock_app_payload)

        assert result.loan_amount == Decimal("450000.00")
        assert result.application_status == "SUBMITTED"
        # Assert audit fields are set
        assert result.created_at is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_application_client_not_found(self, mock_db, mock_app_payload):
        service = ApplicationService(mock_db)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ClientNotFoundError):
            await service.submit_application(mock_app_payload)

    @pytest.mark.asyncio
    async def test_calculate_gds_osfi_compliance(self, mock_db, mock_app_payload):
        """Test GDS calculation respects OSFI B-20 stress test."""
        service = ApplicationService(mock_db)
        
        # Mock client
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        # Rate is 4.50%, Stress test should be max(6.50%, 5.25%) = 6.50%
        # Monthly payment calculation (approximate for logic check)
        # P = 450k, r = 6.5/1200, n = 300 -> M ~ 3000
        # Tax = 3500/12 = 291.67, Heat = 150
        # GDS = (M + Tax + Heat) / (120k/12)
        
        result = await service.submit_application(mock_app_payload)
        
        # Verify qualifying rate was used
        assert result.qualifying_rate == Decimal("6.50")
        assert result.gds_ratio is not None
        assert result.gds_ratio <= Decimal("39.00")

    @pytest.mark.asyncio
    async def test_calculate_tds_osfi_compliance(self, mock_db, mock_app_payload):
        """Test TDS calculation respects OSFI B-20 limits."""
        service = ApplicationService(mock_db)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        result = await service.submit_application(mock_app_payload)
        
        assert result.tds_ratio is not None
        # TDS includes the $500 debt obligations
        assert result.tds_ratio <= Decimal("44.00")

    @pytest.mark.asyncio
    async def test_submit_application_high_gds_raises_error(self, mock_db):
        """Test that high GDS > 39% triggers RegulatoryComplianceError."""
        service = ApplicationService(mock_db)
        
        # Create payload that will fail GDS (Low income, high costs)
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("800000.00"),
            property_value=Decimal("800000.00"),
            down_payment=Decimal("0.01"), # 100% LTV to force high payments
            amortization_years=25,
            contract_rate=Decimal("5.00"),
            annual_property_tax=Decimal("10000.00"),
            estimated_heating_cost=Decimal("500.00"),
            monthly_debt_obligations=Decimal("0.00"),
            annual_income=Decimal("30000.00") # Very low income
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        with pytest.raises(RegulatoryComplianceError) as exc_info:
            await service.submit_application(payload)
        
        assert "GDS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_submit_application_high_tds_raises_error(self, mock_db):
        """Test that high TDS > 44% triggers RegulatoryComplianceError."""
        service = ApplicationService(mock_db)
        
        # Create payload that passes GDS but fails TDS due to other debts
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("300000.00"),
            property_value=Decimal("400000.00"),
            down_payment=Decimal("100000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.00"),
            annual_property_tax=Decimal("3000.00"),
            estimated_heating_cost=Decimal("100.00"),
            monthly_debt_obligations=Decimal("5000.00"), # Massive debt
            annual_income=Decimal("80000.00")
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        with pytest.raises(RegulatoryComplianceError) as exc_info:
            await service.submit_application(payload)
        
        assert "TDS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_cmhc_insurance_logic_80_percent_ltv(self, mock_db):
        """Test CMHC logic: LTV <= 80% means no insurance."""
        service = ApplicationService(mock_db)
        
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"), # 80% LTV
            down_payment=Decimal("100000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.00"),
            annual_property_tax=Decimal("3000.00"),
            estimated_heating_cost=Decimal("100.00"),
            monthly_debt_obligations=Decimal("0.00"),
            annual_income=Decimal("100000.00")
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        result = await service.submit_application(payload)
        
        assert result.ltv_ratio == Decimal("80.00")
        assert result.insurance_required is False
        assert result.insurance_premium_amount == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_cmhc_insurance_logic_95_percent_ltv(self, mock_db):
        """Test CMHC logic: LTV > 80% requires insurance (Tier 90.01-95% = 4.00%)."""
        service = ApplicationService(mock_db)
        
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("475000.00"),
            property_value=Decimal("500000.00"), # 95% LTV
            down_payment=Decimal("25000.00"),
            amortization_years=25,
            contract_rate=Decimal("4.00"),
            annual_property_tax=Decimal("3000.00"),
            estimated_heating_cost=Decimal("100.00"),
            monthly_debt_obligations=Decimal("0.00"),
            annual_income=Decimal("100000.00")
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        result = await service.submit_application(payload)
        
        assert result.ltv_ratio == Decimal("95.00")
        assert result.insurance_required is True
        # Premium: 4.00% of loan amount
        assert result.insurance_premium_amount == (Decimal("475000.00") * Decimal("0.04"))

    @pytest.mark.asyncio
    async def test_pipeda_sin_not_logged(self, mock_db, mock_app_payload):
        """Ensure SIN is not passed through to logs or responses (handled by schema/model)."""
        service = ApplicationService(mock_db)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1, sin_hash="hashed_value")
        mock_db.execute.return_value = mock_result

        with patch("mortgage_underwriting.modules.client_intake.services.logger") as mock_logger:
            result = await service.submit_application(mock_app_payload)
            
            # Check logger calls
            for call in mock_logger.info.call_args_list:
                # Ensure raw SIN string is not in any log message
                assert "123456789" not in str(call)
                assert "sin" not in str(call).lower() or "hash" in str(call).lower()

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.client_intake.models import Client, Application
from sqlalchemy import select

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeFlow:

    async def test_create_client_and_retrieve(self, client: AsyncClient, valid_client_payload):
        """Test full flow of creating a client and retrieving them."""
        # 1. Create Client
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        assert response.status_code == 201
        
        data = response.json()
        assert "id" in data
        assert data["email"] == "john.doe@example.com"
        assert data["sin"] is None  # PIPEDA: SIN should not be returned
        assert "created_at" in data # FINTRAC: Audit trail
        
        client_id = data["id"]

        # 2. Retrieve Client
        response_get = await client.get(f"/api/v1/client-intake/clients/{client_id}")
        assert response_get.status_code == 200
        assert response_get.json()["email"] == "john.doe@example.com"

    async def test_submit_application_workflow(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        """Test creating a client then submitting an application."""
        # 1. Setup: Create Client
        create_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = create_resp.json()["id"]
        
        # 2. Submit Application
        valid_application_payload["client_id"] = client_id
        app_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
        
        assert app_resp.status_code == 201
        app_data = app_resp.json()
        
        assert app_data["client_id"] == client_id
        assert app_data["application_status"] == "SUBMITTED"
        assert app_data["insurance_required"] == False # 450/550 = 81.8% (Actually > 80% in this payload? No, 450/550 = 81.8%)
        # Wait, 450k loan / 550k value = 81.8%. Insurance IS required.
        # Let's verify calculation logic.
        
        # Recalculating expected values for assertion
        # LTV = 450000 / 550000 = 0.8181... -> 81.82%
        # Tier: 80.01-85% -> Premium 2.80%
        # Premium = 450000 * 0.028 = 12600
        
        assert app_data["ltv_ratio"] == "81.82"
        assert app_data["insurance_required"] is True
        assert Decimal(app_data["insurance_premium_amount"]) == Decimal("12600.00")

    async def test_submit_application_invalid_client_id(self, client: AsyncClient, valid_application_payload):
        """Test submitting application for non-existent client."""
        valid_application_payload["client_id"] = 99999
        response = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_regulatory_validation_high_gds_integration(self, client: AsyncClient, valid_client_payload):
        """Test integration endpoint rejects high GDS."""
        # Create Client
        create_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = create_resp.json()["id"]

        # Construct high risk payload
        high_risk_payload = {
            "client_id": client_id,
            "loan_amount": "900000.00",
            "property_value": "900000.00",
            "down_payment": "0.01",
            "amortization_years": 30,
            "contract_rate": "5.00",
            "annual_property_tax": "12000.00",
            "estimated_heating_cost": "300.00",
            "monthly_debt_obligations": "0.00",
            "annual_income": "50000.00"
        }

        response = await client.post("/api/v1/client-intake/applications", json=high_risk_payload)
        
        assert response.status_code == 400
        data = response.json()
        assert "RegulatoryComplianceError" in data.get("error_code", "") or "GDS" in data.get("detail", "")

    async def test_get_application_calculations(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        """Test retrieving an application shows calculated financial metrics."""
        # Create Client
        create_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = create_resp.json()["id"]

        # Create App
        valid_application_payload["client_id"] = client_id
        app_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_payload)
        app_id = app_resp.json()["id"]

        # Get App
        get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
        assert get_resp.status_code == 200
        
        data = get_resp.json()
        # Verify calculated fields exist
        assert "gds_ratio" in data
        assert "tds_ratio" in data
        assert "ltv_ratio" in data
        assert "qualifying_rate" in data
        
        # Verify Qualifying Rate Logic (Contract 4.5% + 2% = 6.5% vs 5.25% -> 6.5%)
        assert data["qualifying_rate"] == "6.50"

    async def test_list_applications_for_client(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        """Test filtering applications by client."""
        # Create Client 1
        c1_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        c1_id = c1_resp.json()["id"]
        
        # Create Client 2
        c2_payload = valid_client_payload.copy()
        c2_payload["email"] = "jane@example.com"
        c2_resp = await client.post("/api/v1/client-intake/clients", json=c2_payload)
        c2_id = c2_resp.json()["id"]

        # Create App for Client 1
        valid_application_payload["client_id"] = c1_id
        await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # Create App for Client 2
        valid_application_payload["client_id"] = c2_id
        await client.post("/api/v1/client-intake/applications", json=valid_application_payload)

        # List Apps for Client 1
        list_resp = await client.get(f"/api/v1/client-intake/applications?client_id={c1_id}")
        assert list_resp.status_code == 200
        
        apps = list_resp.json()
        assert len(apps) == 1
        assert apps[0]["client_id"] == c1_id

    async def test_audit_fields_immutability(self, client: AsyncClient, valid_client_payload, db_session):
        """Test that created_at is set and updated_at changes on update (if applicable)."""
        # Create Client
        create_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = create_resp.json()["id"]
        
        # Verify in DB
        stmt = select(Client).where(Client.id == client_id)
        result = await db_session.execute(stmt)
        db_client = result.scalar_one_or_none()
        
        assert db_client is not None
        assert db_client.created_at is not None
        assert db_client.updated_at is not None

        # Update Client (e.g., address change)
        update_resp = await client.patch(f"/api/v1/client-intake/clients/{client_id}", json={"address": "456 New St"})
        assert update_resp.status_code == 200
        
        # Refresh from DB
        await db_session.refresh(db_client)
        assert db_client.address == "456 New St"
        assert db_client.updated_at > db_client.created_at