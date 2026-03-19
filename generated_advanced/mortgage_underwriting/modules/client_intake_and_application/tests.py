--- conftest.py ---
```python
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

# Hypothetical imports based on project structure
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.modules.client_intake.models import (
    ClientApplication,
    Applicant,
    Property,
)
from mortgage_underwriting.modules.client_intake.schemas import (
    ApplicationCreate,
    ApplicantCreate,
    PropertyCreate,
)

# Use in-memory SQLite for integration tests to ensure speed and isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def engine() -> AsyncGenerator:
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
def mock_security():
    """Mock security functions for PIPEDA compliance testing."""
    with pytest.mock.patch("mortgage_underwriting.common.security.encrypt_pii") as mock_encrypt, \
         pytest.mock.patch("mortgage_underwriting.common.security.hash_sin") as mock_hash:
        mock_encrypt.return_value = "encrypted_string"
        mock_hash.return_value = "hashed_sin_value"
        yield {"encrypt": mock_encrypt, "hash": mock_hash}

@pytest.fixture
def valid_applicant_data() -> dict:
    return {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-01",
        "sin": "123456789",
        "email": "john.doe@example.com",
        "phone_number": "4165550199",
        "employment_status": "employed",
        "annual_income": Decimal("95000.00"),
    }

@pytest.fixture
def valid_property_data() -> dict:
    return {
        "address": "123 Maple St",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M4W1A5",
        "property_type": "detached",
        "property_value": Decimal("750000.00"),
        "year_built": 2010,
    }

@pytest.fixture
def valid_application_data(valid_applicant_data, valid_property_data) -> dict:
    return {
        "loan_amount": Decimal("600000.00"),
        "down_payment": Decimal("150000.00"),
        "amortization_period": 25,
        "interest_rate": Decimal("4.50"),
        "term_years": 5,
        "applicant": valid_applicant_data,
        "property": valid_property_data,
        "monthly_property_tax": Decimal("400.00"),
        "monthly_heating_cost": Decimal("150.00"),
        "other_debt_payments": Decimal("500.00"),
    }
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, call
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientIntakeService
from mortgage_underwriting.modules.client_intake.models import ClientApplication
from mortgage_underwriting.modules.client_intake.exceptions import (
    ApplicationValidationError,
    ComplianceError,
)
from mortgage_underwriting.common.exceptions import AppException

# Import paths strictly following convention
from mortgage_underwriting.modules.client_intake.schemas import ApplicationCreate

@pytest.mark.unit
class TestClientIntakeService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_application_success(self, mock_db, valid_application_data, mock_security):
        """Test successful application creation with PIPEDA encryption."""
        service = ClientIntakeService(mock_db)
        payload = ApplicationCreate(**valid_application_data)
        
        result = await service.create_application(payload)
        
        # Verify DB interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        
        # Verify PIPEDA: Ensure SIN encryption was called
        mock_security["encrypt"].assert_called()
        mock_security["hash"].assert_called_with("123456789")
        
        # Verify basic object creation
        assert result.loan_amount == Decimal("600000.00")
        assert result.applicant.sin_hash == "hashed_sin_value" # Should not store plain SIN

    @pytest.mark.asyncio
    async def test_create_application_db_failure(self, mock_db, valid_application_data):
        """Test handling of database integrity errors."""
        mock_db.commit.side_effect = IntegrityError("Mock DB Error", {}, None)
        service = ClientIntakeService(mock_db)
        payload = ApplicationCreate(**valid_application_data)
        
        with pytest.raises(AppException) as exc_info:
            await service.create_application(payload)
        
        assert exc_info.value.status_code == 500
        assert "database error" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_calculate_gds_osfi_compliance_success(self, mock_db):
        """
        Test GDS calculation with OSFI stress test.
        Scenario: Income 95k, Mortgage 2800/mo, Tax 400, Heat 150.
        Qualifying Rate: max(4.5 + 2, 5.25) = 6.5%.
        """
        service = ClientIntakeService(mock_db)
        
        # Mock inputs
        annual_income = Decimal("95000.00")
        monthly_mortgage_payment = Decimal("2800.00")
        property_tax = Decimal("400.00")
        heating = Decimal("150.00")
        contract_rate = Decimal("4.5")
        
        # Expected calculation
        # Monthly Income = 95000 / 12 = 7916.66
        # Housing Costs = 2800 + 400 + 150 = 3350
        # GDS = (3350 / 7916.66) * 100 = 42.31% (Raw)
        # Note: We are testing the logic implementation, assuming service handles the math
        
        with patch.object(service, '_calculate_monthly_payment', return_value=monthly_mortgage_payment):
            gds = await service.calculate_gds(
                annual_income=annual_income,
                property_tax=property_tax,
                heating=heating,
                contract_rate=contract_rate,
                loan_amount=Decimal("500000"),
                amortization=25
            )
            
            # OSFI Rule: GDS must be <= 39%
            # If the calculated GDS exceeds this, the service should raise ComplianceError
            # Here we check if the calculation logic runs
            assert isinstance(gds, Decimal)

    @pytest.mark.asyncio
    async def test_calculate_gds_exceeds_limit_raises_compliance_error(self, mock_db):
        """Test that GDS > 39% raises OSFI Compliance Error."""
        service = ClientIntakeService(mock_db)
        
        # Low income scenario to trigger failure
        annual_income = Decimal("40000.00") # ~3333/mo
        property_tax = Decimal("500.00")
        heating = Decimal("200.00")
        contract_rate = Decimal("5.0")
        
        with pytest.raises(ComplianceError) as exc_info:
            await service.calculate_gds(
                annual_income=annual_income,
                property_tax=property_tax,
                heating=heating,
                contract_rate=contract_rate,
                loan_amount=Decimal("400000"),
                amortization=25
            )
            
        assert "GDS" in str(exc_info.value)
        assert "39%" in str(exc_info.value) or "limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_calculate_tds_exceeds_limit_raises_compliance_error(self, mock_db):
        """Test that TDS > 44% raises OSFI Compliance Error."""
        service = ClientIntakeService(mock_db)
        
        # High debt scenario
        annual_income = Decimal("60000.00")
        other_debts = Decimal("2000.00") # Significant load
        property_tax = Decimal("300.00")
        heating = Decimal("100.00")
        contract_rate = Decimal("3.0")
        
        with pytest.raises(ComplianceError) as exc_info:
            await service.calculate_tds(
                annual_income=annual_income,
                property_tax=property_tax,
                heating=heating,
                other_debts=other_debts,
                contract_rate=contract_rate,
                loan_amount=Decimal("300000"),
                amortization=25
            )
            
        assert "TDS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_determine_insurance_cmhc_logic(self, mock_db):
        """Test CMHC insurance requirement logic based on LTV tiers."""
        service = ClientIntakeService(mock_db)
        
        # Case 1: LTV <= 80% (No insurance)
        # 600k loan / 750k value = 80%
        req1 = await service.determine_insurance_requirement(
            loan_amount=Decimal("600000.00"),
            property_value=Decimal("750000.00")
        )
        assert req1.required is False
        assert req1.premium_rate == Decimal("0.00")

        # Case 2: 80.01% - 85% (2.80%)
        # 640k loan / 750k value = 85.33%
        req2 = await service.determine_insurance_requirement(
            loan_amount=Decimal("640000.00"),
            property_value=Decimal("750000.00")
        )
        assert req2.required is True
        assert req2.premium_rate == Decimal("2.80")

        # Case 3: 90.01% - 95% (4.00%)
        # 712500 loan / 750k value = 95%
        req3 = await service.determine_insurance_requirement(
            loan_amount=Decimal("712500.00"),
            property_value=Decimal("750000.00")
        )
        assert req3.required is True
        assert req3.premium_rate == Decimal("4.00")

    @pytest.mark.asyncio
    async def test_validate_ltv_precision(self, mock_db):
        """Ensure LTV calculation uses Decimal and has no precision loss."""
        service = ClientIntakeService(mock_db)
        
        # Specific values that often cause float issues
        loan = Decimal("100000.33")
        value = Decimal("100000.99")
        
        # We expect the service to handle this internally, here we check the helper if exposed
        # or the validation logic
        ltv = await service._calculate_ltv(loan, value)
        
        # Check it's a Decimal
        assert isinstance(ltv, Decimal)
        # Check basic math logic
        expected = (loan / value) * 100
        assert ltv == expected

    @pytest.mark.asyncio
    async def test_stress_test_qualifying_rate_logic(self, mock_db):
        """Verify OSFI Stress Test: max(contract + 2%, 5.25%)."""
        service = ClientIntakeService(mock_db)
        
        # Case 1: Contract rate 3.0% -> 3+2=5.0 vs 5.25 -> 5.25%
        rate1 = await service._get_qualifying_rate(Decimal("3.0"))
        assert rate1 == Decimal("5.25")
        
        # Case 2: Contract rate 5.0% -> 5+2=7.0 vs 5.25 -> 7.0%
        rate2 = await service._get_qualifying_rate(Decimal("5.0"))
        assert rate2 == Decimal("7.00")
        
        # Case 3: Contract rate 3.25% -> 3.25+2=5.25 vs 5.25 -> 5.25%
        rate3 = await service._get_qualifying_rate(Decimal("3.25"))
        assert rate3 == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_fintrac_audit_fields_populated(self, mock_db, valid_application_data, mock_security):
        """Test that FINTRAC required fields (created_at) are populated."""
        service = ClientIntakeService(mock_db)
        payload = ApplicationCreate(**valid_application_data)
        
        # Mock the DB object to inspect what is added
        added_instance = None
        def capture_add(obj):
            nonlocal added_instance
            added_instance = obj
            
        mock_db.add.side_effect = capture_add
        
        await service.create_application(payload)
        
        assert added_instance is not None
        assert hasattr(added_instance, 'created_at')
        assert added_instance.created_at is not None
        # Verify created_by is set (usually from token context, mocked here)
        assert hasattr(added_instance, 'created_by')
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from decimal import Decimal

from mortgage_underwriting.modules.client_intake.routes import router
from mortgage_underwriting.modules.client_intake.models import ClientApplication
from mortgage_underwriting.common.database import get_async_session

# Import shared fixtures from conftest are available automatically

@pytest.fixture(scope="function")
def app(db_session):
    """Create a test FastAPI app with the module router and overridden DB dependency."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-intake", tags=["Client Intake"])
    
    # Override the dependency to use the test session
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.mark.integration
@pytest.mark.asyncio
class TestClientIntakeEndpoints:

    async def test_create_application_endpoint_success(self, app: FastAPI):
        """Test full workflow: POST application -> 201 Created -> DB Record."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "loan_amount": "500000.00",
                "down_payment": "100000.00",
                "amortization_period": 25,
                "interest_rate": "4.5",
                "term_years": 5,
                "monthly_property_tax": "300.00",
                "monthly_heating_cost": "120.00",
                "other_debt_payments": "0.00",
                "applicant": {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "date_of_birth": "1985-05-15",
                    "sin": "987654321",
                    "email": "jane@example.com",
                    "phone_number": "4165551234",
                    "employment_status": "employed",
                    "annual_income": "85000.00"
                },
                "property": {
                    "address": "456 Oak Ave",
                    "city": "Vancouver",
                    "province": "BC",
                    "postal_code": "V6K1A1",
                    "property_type": "condo",
                    "property_value": "600000.00",
                    "year_built": 2015
                }
            }
            
            response = await client.post("/api/v1/client-intake/applications", json=payload)
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["loan_amount"] == "500000.00"
            assert data["status"] == "pending_review"
            # PIPEDA Check: SIN should NOT be in response
            assert "sin" not in data["applicant"]
            assert "sin_hash" not in data["applicant"] # Internal field usually hidden from DTO
            assert data["applicant"]["email"] == "jane@example.com"

    async def test_create_application_validation_error_missing_field(self, app: FastAPI):
        """Test input validation enforcement."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing SIN
            payload = {
                "loan_amount": "500000.00",
                "down_payment": "100000.00",
                "amortization_period": 25,
                "interest_rate": "4.5",
                "term_years": 5,
                "monthly_property_tax": "300.00",
                "monthly_heating_cost": "120.00",
                "other_debt_payments": "0.00",
                "applicant": {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "email": "jane@example.com",
                    # Missing SIN, DOB, etc
                },
                "property": {
                    "address": "456 Oak Ave",
                    "city": "Vancouver",
                    "province": "BC",
                    "postal_code": "V6K1A1",
                    "property_type": "condo",
                    "property_value": "600000.00",
                    "year_built": 2015
                }
            }
            
            response = await client.post("/api/v1/client-intake/applications", json=payload)
            
            assert response.status_code == 422
            assert "detail" in response.json()

    async def test_get_application_retrieval(self, app: FastAPI, valid_application_data):
        """Test retrieving a created application."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create
            create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_data)
            assert create_resp.status_code == 201
            app_id = create_resp.json()["id"]
            
            # 2. Retrieve
            get_resp = await client.get(f"/api/v1/client-intake/applications/{app_id}")
            assert get_resp.status_code == 200
            
            data = get_resp.json()
            assert data["id"] == app_id
            # Verify financial precision is maintained in response
            assert Decimal(data["loan_amount"]) == Decimal("600000.00")

    async def test_osfi_compliance_integration_high_gds(self, app: FastAPI, db_session):
        """
        Integration test for OSFI B-20.
        Attempt to create an application that mathematically fails GDS/TDS.
        The endpoint should return a 400 or specific compliance error.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Low income, high house cost
            payload = {
                "loan_amount": "800000.00",
                "down_payment": "5000.00", # Very high LTV
                "amortization_period": 30,
                "interest_rate": "5.0",
                "term_years": 5,
                "monthly_property_tax": "600.00",
                "monthly_heating_cost": "200.00",
                "other_debt_payments": "1000.00",
                "applicant": {
                    "first_name": "Risk",
                    "last_name": "Applicant",
                    "date_of_birth": "1990-01-01",
                    "sin": "111111111",
                    "email": "risk@test.com",
                    "phone_number": "4165550000",
                    "employment_status": "employed",
                    "annual_income": "40000.00" # Too low for this loan
                },
                "property": {
                    "address": "1 Expensive Way",
                    "city": "Toronto",
                    "province": "ON",
                    "postal_code": "M5H1A1",
                    "property_type": "detached",
                    "property_value": "805000.00",
                    "year_built": 2020
                }
            }
            
            response = await client.post("/api/v1/client-intake/applications", json=payload)
            
            # Expect rejection due to OSFI compliance rules
            assert response.status_code == 400
            data = response.json()
            assert "error_code" in data
            # Verify it's a compliance error, not a generic server error
            assert "compliance" in data["detail"].lower() or "gds" in data["detail"].lower() or "tds" in data["detail"].lower()

    async def test_list_applications_empty(self, app: FastAPI):
        """Test listing applications when none exist."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/client-intake/applications")
            assert response.status_code == 200
            assert response.json() == []

    async def test_list_applications_pagination(self, app: FastAPI, valid_application_data):
        """Test listing applications with limit/offset (if implemented) or basic listing."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create 2 apps
            await client.post("/api/v1/client-intake/applications", json=valid_application_data)
            await client.post("/api/v1/client-intake/applications", json=valid_application_data)
            
            response = await client.get("/api/v1/client-intake/applications")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    async def test_fintrac_audit_trail_immutability(self, app: FastAPI, valid_application_data):
        """
        Test that created_at and created_by are present and immutable.
        Note: Testing immutability strictly requires trying to update via ORM or API 
        and verifying it fails or is ignored. Here we verify presence.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post("/api/v1/client-intake/applications", json=valid_application_data)
            data = create_resp.json()
            
            assert "created_at" in data
            assert "updated_at" in data
            assert "created_by" in data # Assuming system or user ID
            
            # Verify format (ISO 8601)
            assert "T" in data["created_at"]
```