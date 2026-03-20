--- conftest.py ---
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from typing import AsyncGenerator, Dict, Any

# Import the module under test components
from mortgage_underwriting.modules.client_intake.models import Applicant, Application
from mortgage_underwriting.modules.client_intake.routes import router as client_intake_router
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings

# Use an in-memory SQLite database for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def app(db_session: AsyncSession) -> FastAPI:
    """
    Sets up the FastAPI app with the client intake router and overrides the dependency.
    """
    app = FastAPI()
    app.include_router(client_intake_router, prefix="/api/v1/client-intake", tags=["Client Intake"])

    # Dependency override
    async def override_get_db():
        yield db_session

    from mortgage_underwriting.common.database import get_async_session
    app.dependency_overrides[get_async_session] = override_get_db

    yield app

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an AsyncClient for testing endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def valid_applicant_data() -> Dict[str, Any]:
    """
    Valid payload for creating an applicant.
    PIPEDA: SIN is included here but should be encrypted/hashed before DB storage.
    """
    return {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "1985-05-20",
        "sin": "123456782", # Valid Luhn check example
        "email": "jane.doe@example.com",
        "phone_number": "4165550199",
        "address": {
            "street": "123 Maple Ave",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M4W1A5"
        }
    }

@pytest.fixture
def valid_application_data() -> Dict[str, Any]:
    """
    Valid payload for creating an application.
    Financial values must be strings for JSON, parsed as Decimals in backend.
    """
    return {
        "applicant_id": 1, # Will be replaced in tests dynamically
        "loan_amount": "450000.00",
        "property_value": "600000.00",
        "down_payment": "150000.00",
        "amortization_years": 25,
        "interest_rate": "5.00",
        "annual_income": "120000.00",
        "property_tax": "3000.00",
        "heating_cost": "1200.00",
        "other_debt": "500.00"
    }

@pytest.fixture
def mock_encryption_service():
    """
    Mocks the encryption service for unit tests.
    """
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.encrypt_pii.return_value = "encrypted_string_v1"
    mock.hash_sin.return_value = "hashed_sin_abc123"
    return mock
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientIntakeService
from mortgage_underwriting.modules.client_intake.schemas import ApplicantCreate, ApplicationCreate
from mortgage_underwriting.modules.client_intake.exceptions import DuplicateApplicantError, InvalidApplicationDataError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientIntakeService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return ClientIntakeService(mock_db)

    @pytest.mark.asyncio
    async def test_create_applicant_success(self, service, mock_db, valid_applicant_data, mock_encryption_service):
        """
        Test successful applicant creation ensuring PIPEDA compliance (hashing/encryption).
        """
        payload = ApplicantCreate(**valid_applicant_data)
        
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii", return_value="enc_sin") as mock_enc, \
             patch("mortgage_underwriting.modules.client_intake.services.hash_sin", return_value="hash_sin"):
            
            result = await service.create_applicant(payload)

            assert result.first_name == "Jane"
            assert result.last_name == "Doe"
            # Verify DB interactions
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once_with(result)
            # Verify PIPEDA: Check that encryption was called
            mock_enc.assert_called_once_with("123456782")

    @pytest.mark.asyncio
    async def test_create_applicant_duplicate_sin(self, service, mock_db, valid_applicant_data):
        """
        Test that creating a duplicate applicant (based on SIN hash) raises an error.
        """
        payload = ApplicantCreate(**valid_applicant_data)
        
        # Simulate IntegrityError from DB (Unique constraint on SIN hash)
        mock_db.commit.side_effect = IntegrityError("INSERT failed", {}, Exception())

        with pytest.raises(DuplicateApplicantError) as exc_info:
            await service.create_applicant(payload)
        
        assert "duplicate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_application_success(self, service, mock_db, valid_application_data):
        """
        Test successful application creation.
        """
        # Adjust payload to have a valid applicant_id reference context
        payload = ApplicationCreate(**valid_application_data)
        
        # Mock the applicant existence check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        result = await service.create_application(payload)

        assert result.loan_amount == Decimal("450000.00")
        assert result.annual_income == Decimal("120000.00")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_applicant_not_found(self, service, mock_db, valid_application_data):
        """
        Test that creating an application for a non-existent applicant raises an error.
        """
        payload = ApplicationCreate(**valid_application_data)
        
        # Mock applicant not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(InvalidApplicationDataError) as exc_info:
            await service.create_application(payload)
        
        assert "applicant" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_financials_negative_income(self, service, mock_db):
        """
        Test validation logic: Income cannot be negative.
        """
        invalid_data = {
            "applicant_id": 1,
            "loan_amount": "100000.00",
            "property_value": "200000.00",
            "down_payment": "100000.00",
            "amortization_years": 20,
            "interest_rate": "4.0",
            "annual_income": "-5000.00", # Invalid
            "property_tax": "2000.00",
            "heating_cost": "100.00",
            "other_debt": "0.00"
        }
        payload = ApplicationCreate(**invalid_data)
        
        with pytest.raises(InvalidApplicationDataError):
            await service.create_application(payload)

    @pytest.mark.asyncio
    async def test_validate_ltv_calculation(self, service, mock_db):
        """
        Test that LTV is calculated correctly during application creation.
        Loan 450k / Value 600k = 75%
        """
        payload = ApplicationCreate(**valid_application_data)
        
        # Mock applicant existence
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        result = await service.create_application(payload)

        # LTV = 450000 / 600000 = 0.75
        # Note: This assumes the model calculates it or the service does. 
        # Based on requirements, service logic handles this.
        expected_ltv = (Decimal("450000.00") / Decimal("600000.00")) * Decimal("100")
        assert result.ltv_ratio == expected_ltv

    @pytest.mark.asyncio
    async def test_get_applicant_by_id_success(self, service, mock_db):
        """
        Test retrieving an applicant by ID.
        """
        mock_applicant = MagicMock(id=1, first_name="John")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_applicant
        mock_db.execute.return_value = mock_result

        result = await service.get_applicant(1)

        assert result.first_name == "John"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_applicant_not_found(self, service, mock_db):
        """
        Test retrieving a non-existent applicant returns None.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.get_applicant(999)

        assert result is None

# Helper dictionary for valid_application_data in tests
valid_application_data = {
    "applicant_id": 1,
    "loan_amount": "450000.00",
    "property_value": "600000.00",
    "down_payment": "150000.00",
    "amortization_years": 25,
    "interest_rate": "5.00",
    "annual_income": "120000.00",
    "property_tax": "3000.00",
    "heating_cost": "1200.00",
    "other_debt": "500.00"
}
--- integration_tests ---
import pytest
from decimal import Decimal
from httpx import AsyncClient

from mortgage_underwriting.modules.client_intake.models import Applicant, Application

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_applicant_flow(self, client: AsyncClient, valid_applicant_data):
        """
        Test full flow: Create Applicant -> Verify Response -> Verify DB State.
        Ensures PIPEDA compliance (SIN not in response).
        """
        response = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify Response Structure
        assert "id" in data
        assert data["first_name"] == "Jane"
        assert data["last_name"] == "Doe"
        assert data["email"] == "jane.doe@example.com"
        
        # PIPEDA: Ensure raw SIN is NEVER returned
        assert "sin" not in data
        assert "123456782" not in str(data)
        
        # Verify Audit Fields (FINTRAC)
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_applicant_invalid_email(self, client: AsyncClient, valid_applicant_data):
        """
        Test validation error on invalid email.
        """
        invalid_data = valid_applicant_data.copy()
        invalid_data["email"] = "not-an-email"
        
        response = await client.post("/api/v1/client-intake/applicants", json=invalid_data)
        
        assert response.status_code == 422 # Pydantic validation error

    async def test_create_application_flow(self, client: AsyncClient, valid_applicant_data, valid_application_data, db_session):
        """
        Test full flow: Create Applicant -> Create Application -> Verify Calculations.
        """
        # 1. Create Applicant
        app_resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = app_resp.json()["id"]
        
        # 2. Create Application
        app_payload = valid_application_data.copy()
        app_payload["applicant_id"] = applicant_id
        
        resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        
        assert resp.status_code == 201
        data = resp.json()
        
        # Verify Financials are Decimal (represented as strings in JSON)
        assert Decimal(data["loan_amount"]) == Decimal("450000.00")
        assert Decimal(data["annual_income"]) == Decimal("120000.00")
        
        # Verify LTV Calculation
        # 450000 / 600000 = 0.75
        expected_ltv = Decimal("75.00")
        assert Decimal(data["ltv_ratio"]) == expected_ltv
        
        # Verify Insurance Requirement (CMHC Logic)
        # LTV 75% <= 80%, so no insurance required
        assert data["insurance_required"] is False
        assert data["insurance_premium"] == Decimal("0.00")

    async def test_create_application_high_ltv_triggers_insurance(self, client: AsyncClient, valid_applicant_data, db_session):
        """
        Test CMHC Logic: High LTV (>80%) triggers insurance requirement.
        """
        # Create Applicant
        app_resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = app_resp.json()["id"]
        
        # Create Application with 5% down (95% LTV)
        payload = {
            "applicant_id": applicant_id,
            "loan_amount": "475000.00",
            "property_value": "500000.00",
            "down_payment": "25000.00",
            "amortization_years": 25,
            "interest_rate": "5.00",
            "annual_income": "120000.00",
            "property_tax": "3000.00",
            "heating_cost": "1200.00",
            "other_debt": "0.00"
        }
        
        resp = await client.post("/api/v1/client-intake/applications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        
        # LTV = 95%
        assert Decimal(data["ltv_ratio"]) == Decimal("95.00")
        
        # CMHC: 90.01-95% = 4.00% premium
        # Premium is calculated on loan amount usually
        expected_premium = Decimal("475000.00") * Decimal("0.04")
        
        assert data["insurance_required"] is True
        assert Decimal(data["insurance_premium"]) == expected_premium

    async def test_get_application_by_id(self, client: AsyncClient, valid_applicant_data, valid_application_data):
        """
        Test retrieving an application.
        """
        # Setup
        app_resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = app_resp.json()["id"]
        
        app_payload = valid_application_data.copy()
        app_payload["applicant_id"] = applicant_id
        create_resp = await client.post("/api/v1/client-intake/applications", json=app_payload)
        application_id = create_resp.json()["id"]
        
        # Test Get
        get_resp = await client.get(f"/api/v1/client-intake/applications/{application_id}")
        
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == application_id
        assert data["applicant_id"] == applicant_id

    async def test_get_application_not_found(self, client: AsyncClient):
        """
        Test 404 for non-existent application.
        """
        resp = await client.get("/api/v1/client-intake/applications/99999")
        assert resp.status_code == 404

    async def test_update_applicant_contact_info(self, client: AsyncClient, valid_applicant_data):
        """
        Test updating applicant info (e.g., email change).
        """
        # Create
        create_resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = create_resp.json()["id"]
        
        # Update
        update_payload = {"email": "new.email@example.com"}
        update_resp = await client.patch(f"/api/v1/client-intake/applicants/{applicant_id}", json=update_payload)
        
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["email"] == "new.email@example.com"
        assert data["first_name"] == "Jane" # Other fields unchanged

    async def test_sin_is_hashed_in_db(self, client: AsyncClient, valid_applicant_data, db_session):
        """
        Verify PIPEDA compliance: SIN is hashed in the database, not plain text.
        """
        resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = resp.json()["id"]
        
        # Query DB directly to check storage format
        from sqlalchemy import select
        stmt = select(Applicant).where(Applicant.id == applicant_id)
        result = await db_session.execute(stmt)
        db_applicant = result.scalar_one()
        
        # Ensure the SIN field in DB is NOT the plain text "123456782"
        # It should be a hash (e.g., sha256 hex string length 64)
        assert db_applicant.sin != "123456782"
        assert len(db_applicant.sin) == 64 # Assuming SHA-256 hex output
        assert "123456782" not in db_applicant.sin

    async def test_financial_decimals_precision(self, client: AsyncClient, valid_applicant_data):
        """
        Ensure financial values maintain precision without float conversion errors.
        """
        app_resp = await client.post("/api/v1/client-intake/applicants", json=valid_applicant_data)
        applicant_id = app_resp.json()["id"]
        
        payload = {
            "applicant_id": applicant_id,
            "loan_amount": "123456.78", # High precision cents
            "property_value": "500000.00",
            "down_payment": "376543.22",
            "amortization_years": 25,
            "interest_rate": "3.99",
            "annual_income": "100200.50",
            "property_tax": "3000.01",
            "heating_cost": "1200.12",
            "other_debt": "0.01"
        }
        
        resp = await client.post("/api/v1/client-intake/applications", json=payload)
        assert resp.status_code == 201
        
        data = resp.json()
        # Verify strict decimal equality
        assert Decimal(data["loan_amount"]) == Decimal("123456.78")
        assert Decimal(data["annual_income"]) == Decimal("100200.50")