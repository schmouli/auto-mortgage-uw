--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.modules.client_intake.routes import router
from mortgage_underwriting.main import app

# Using SQLite for integration tests as permitted by prompt for speed/isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Integration test client with DB session dependency override.
    """
    # We need to override the dependency in the actual app
    # Assuming get_async_session is the dependency name in common/database.py
    from mortgage_underwriting.common.database import get_async_session
    
    async def override_get_async_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_async_session
    
    # Ensure router is included (if not already in main app setup)
    app.include_router(router, prefix="/api/v1/client-intake", tags=["Client Intake"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

@pytest.fixture
def valid_client_payload():
    return {
        "first_name": "John",
        "last_name": "Doe",
        "sin": "123456789", # Will be encrypted
        "dob": "1990-01-01",
        "email": "john.doe@example.com",
        "phone": "4165550199"
    }

@pytest.fixture
def valid_application_payload():
    return {
        "client_id": 1, # Will be replaced in tests
        "loan_amount": "450000.00",
        "property_value": "500000.00",
        "annual_income": "120000.00",
        "property_tax": "3000.00",
        "heating_cost": "1200.00",
        "condo_fees": "0.00",
        "other_debts": "500.00",
        "contract_rate": "4.50"
    }
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.modules.client_intake.schemas import ApplicationCreate, ClientCreate
from mortgage_underwriting.modules.client_intake.exceptions import (
    GDSLimitExceededError,
    TDSLimitExceededError,
    LTVLimitExceededError
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def client_payload(self):
        return ClientCreate(
            first_name="Jane",
            last_name="Smith",
            sin="987654321",
            dob="1985-05-15",
            email="jane@example.com",
            phone="4165551234"
        )

    @pytest.mark.asyncio
    async def test_create_client_success(self, mock_db, client_payload):
        """Test successful client creation with PII encryption mocked."""
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "encrypted_hash"
            
            service = ClientService(mock_db)
            result = await service.create_client(client_payload)

            assert result.first_name == "Jane"
            assert result.sin == "encrypted_hash"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_create_client_db_failure(self, mock_db, client_payload):
        """Test handling of database integrity errors (e.g. duplicate email)."""
        mock_db.commit.side_effect = IntegrityError("Mock", "Mock", "Mock")
        
        with pytest.raises(AppException) as exc_info:
            service = ClientService(mock_db)
            await service.create_client(client_payload)
        
        assert exc_info.value.error_code == "DB_INTEGRITY_ERROR"


@pytest.mark.unit
class TestApplicationServiceCalculations:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def app_payload(self):
        # Loan: 400k, Rate: 5%, 25yr amortization -> Monthly P&I approx $2338
        # Income: 100k -> Monthly: 8333
        # Tax: 300/yr, Heat: 100/mo, Condo: 0
        return ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("100000.00"),
            property_tax=Decimal("3000.00"),
            heating_cost=Decimal("1200.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("5.00")
        )

    @pytest.mark.asyncio
    async def test_calculate_gds_within_limit(self, mock_db, app_payload):
        service = ApplicationService(mock_db)
        
        # GDS = (Mortgage + Tax + Heat + 50% Condo) / Income
        # Qualifying Rate: Max(5% + 2%, 5.25%) = 7.0%
        # Monthly P&I at 7% for 400k is approx $2820
        # Monthly Costs = 2820 + 250 + 100 = 3170
        # Monthly Income = 8333.33
        # GDS = 3170 / 8333.33 = 38.04% (Passes < 39%)
        
        # We verify the service logic runs without raising exception
        # (Actual math implementation is inside the service, we test the outcome)
        result = await service.create_application(app_payload)
        assert result.gds_ratio < Decimal("39.00")

    @pytest.mark.asyncio
    async def test_calculate_gds_exceeds_limit(self, mock_db):
        # Create payload with high housing costs relative to income
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("60000.00"), # Low income
            property_tax=Decimal("6000.00"),
            heating_cost=Decimal("500.00"),
            condo_fees=Decimal("800.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("5.00")
        )
        
        service = ApplicationService(mock_db)
        
        with pytest.raises(GDSLimitExceededError) as exc_info:
            await service.create_application(payload)
        
        assert "GDS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calculate_tds_exceeds_limit(self, mock_db):
        # Create payload with high debts
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("80000.00"),
            property_tax=Decimal="3000.00",
            heating_cost=Decimal("100.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("3000.00"), # Significant debt
            contract_rate=Decimal("5.00")
        )
        
        service = ApplicationService(mock_db)
        
        with pytest.raises(TDSLimitExceededError) as exc_info:
            await service.create_application(payload)
        
        assert "TDS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calculate_ltv_insurance_required_tier_1(self, mock_db):
        # 80.01% - 85% -> 2.80%
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("401000.00"), # 80.2% of 500k
            property_value=Decimal("500000.00"),
            annual_income=Decimal("200000.00"), # High income to pass GDS/TDS
            property_tax=Decimal("1000.00"),
            heating_cost=Decimal("100.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("4.00")
        )
        
        service = ApplicationService(mock_db)
        result = await service.create_application(payload)
        
        assert result.ltv_ratio == Decimal("80.20")
        assert result.insurance_required is True
        assert result.insurance_premium_rate == Decimal("0.0280")

    @pytest.mark.asyncio
    async def test_calculate_ltv_insurance_required_tier_3(self, mock_db):
        # 90.01% - 95% -> 4.00%
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("475000.00"), # 95% of 500k
            property_value=Decimal("500000.00"),
            annual_income=Decimal("200000.00"),
            property_tax=Decimal("1000.00"),
            heating_cost=Decimal("100.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("4.00")
        )
        
        service = ApplicationService(mock_db)
        result = await service.create_application(payload)
        
        assert result.ltv_ratio == Decimal("95.00")
        assert result.insurance_required is True
        assert result.insurance_premium_rate == Decimal("0.0400")

    @pytest.mark.asyncio
    async def test_ltv_exceeds_maximum(self, mock_db):
        # > 95% is invalid for standard insured
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("480000.00"), # 96%
            property_value=Decimal("500000.00"),
            annual_income=Decimal("200000.00"),
            property_tax=Decimal("1000.00"),
            heating_cost=Decimal("100.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("4.00")
        )
        
        service = ApplicationService(mock_db)
        
        with pytest.raises(LTVLimitExceededError):
            await service.create_application(payload)

    @pytest.mark.asyncio
    async def test_stress_test_rate_calculation(self, mock_db):
        # Contract rate 3.0% -> Qualifying should be 5.25% (floor)
        payload = ApplicationCreate(
            client_id=1,
            loan_amount=Decimal("300000.00"),
            property_value=Decimal("500000.00"),
            annual_income=Decimal("150000.00"),
            property_tax=Decimal("1000.00"),
            heating_cost=Decimal("100.00"),
            condo_fees=Decimal("0.00"),
            other_debts=Decimal("0.00"),
            contract_rate=Decimal("3.00") # Low rate
        )
        
        with patch("mortgage_underwriting.modules.client_intake.services.calculate_monthly_payment") as mock_calc:
            # We expect the service to call calc with rate 5.25% (0.0525)
            service = ApplicationService(mock_db)
            await service.create_application(payload)
            
            # Check that the calculation was called with the stress rate
            # The second argument to calculate_monthly_payment is the annual rate
            call_args = mock_calc.call_args
            assert call_args is not None
            qualifying_rate_used = call_args[0][1]
            assert qualifying_rate_used == Decimal("0.0525") # 5.25% floor

--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.client_intake.models import Client

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeAPI:

    async def test_create_client_success(self, client: AsyncClient, valid_client_payload):
        """Test creating a client via API."""
        response = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["id"] == 1
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert "sin" not in data  # PIPEDA: SIN must not be exposed
        assert "dob" not in data  # PIPEDA: DOB must not be exposed
        assert data["email"] == "john.doe@example.com"

    async def test_create_client_validation_error(self, client: AsyncClient):
        """Test validation error on invalid input."""
        invalid_payload = {
            "first_name": "", # Invalid
            "last_name": "Doe",
            "sin": "123",
            "email": "not-an-email"
        }
        
        response = await client.post("/api/v1/client-intake/clients", json=invalid_payload)
        assert response.status_code == 422

    async def test_create_application_workflow(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        """
        Test multi-step workflow:
        1. Create Client
        2. Create Application for that Client
        3. Verify OSFI B-20 and CMHC logic in response
        """
        # Step 1: Create Client
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        assert client_resp.status_code == 201
        client_id = client_resp.json()["id"]

        # Step 2: Create Application
        # Adjust payload to use the new client_id
        app_payload = valid_application_payload.copy()
        app_payload["client_id"] = client_id
        
        app_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        assert app_resp.status_code == 201
        app_data = app_resp.json()

        # Step 3: Verify Response Data
        assert app_data["id"] > 0
        assert app_data["client_id"] == client_id
        assert app_data["status"] == "SUBMITTED"
        
        # Verify LTV Calculation (CMHC)
        # Loan 450k / Value 500k = 90%
        assert app_data["ltv_ratio"] == "90.00"
        assert app_data["insurance_required"] is True
        assert app_data["insurance_premium_rate"] == "0.0310" # 3.10% tier
        
        # Verify Ratios (OSFI B-20)
        # These are calculated in service, here we check they exist and are formatted
        assert "gds_ratio" in app_data
        assert "tds_ratio" in app_data
        assert Decimal(app_data["gds_ratio"]) <= Decimal("39.00")
        assert Decimal(app_data["tds_ratio"]) <= Decimal("44.00")

    async def test_create_application_gds_rejection(self, client: AsyncClient, valid_client_payload):
        """Test that application fails if GDS > 39%."""
        # Create Client
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]

        # Create Application with low income to trigger GDS failure
        # High Loan, Low Income
        payload = {
            "client_id": client_id,
            "loan_amount": "800000.00",
            "property_value": "850000.00",
            "annual_income": "50000.00", # Too low for 800k loan
            "property_tax": "5000.00",
            "heating_cost": "2000.00",
            "condo_fees": "500.00",
            "other_debts": "0.00",
            "contract_rate": "5.00"
        }

        response = await client.post("/api/v1/client-intake/applications", json=payload)
        
        # Expecting 400 Bad Request or 422 depending on implementation detail
        # Service raises GDSLimitExceededError -> handled by exception handler -> 400
        assert response.status_code == 400
        assert "GDS" in response.json()["detail"]

    async def test_get_application_by_id(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        """Test retrieving an application."""
        # Setup
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]
        
        app_payload = valid_application_payload.copy()
        app_payload["client_id"] = client_id
        app_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        app_id = app_resp.json()["id"]

        # Test Get
        get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
        assert get_resp.status_code == 200
        
        data = get_resp.json()
        assert data["id"] == app_id
        assert data["loan_amount"] == "450000.00"

    async def test_get_application_not_found(self, client: AsyncClient):
        """Test 404 when application does not exist."""
        response = await client.get("/api/v1/client-intake/applications/99999")
        assert response.status_code == 404

    async def test_fintrac_audit_fields_present(self, client: AsyncClient, valid_client_payload, valid_application_payload):
        """Test that created_at/updated_at are present for audit trail."""
        # Create Client
        client_resp = await client.post("/api/v1/client-intake/clients", json=valid_client_payload)
        client_id = client_resp.json()["id"]

        # Create Application
        app_payload = valid_application_payload.copy()
        app_payload["client_id"] = client_id
        app_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        
        data = app_resp.json()
        assert "created_at" in data
        assert "updated_at" in data
        # ISO 8601 format check roughly
        assert "T" in data["created_at"]