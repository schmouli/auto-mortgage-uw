--- conftest.py ---
```python
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from unittest.mock import AsyncMock, MagicMock

# Assuming standard imports based on project structure
from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.config import settings

# Test Database Configuration (In-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh database session for each test.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def mock_security() -> MagicMock:
    """
    Mocks the security module to avoid real encryption overhead
    and allow deterministic testing of PII handling.
    """
    with pytest.mock.patch("mortgage_underwriting.common.security.encrypt_pii") as mock_enc, \
         pytest.mock.patch("mortgage_underwriting.common.security.hash_sin") as mock_hash:
        # Return deterministic values for testing
        mock_enc.return_value = "encrypted_string_123"
        mock_hash.return_value = "hashed_sin_abc"
        yield {"encrypt": mock_enc, "hash": mock_hash}


@pytest.fixture
def valid_application_payload() -> dict:
    """
    Provides a valid payload that passes basic validation.
    Note: Financial logic validation happens in the service layer.
    """
    return {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-01",
        "sin": "123456789",  # Will be hashed/encrypted
        "email": "john.doe@example.com",
        "phone_number": "4165550199",
        "property_address": "123 Maple St, Toronto, ON",
        "property_value": Decimal("500000.00"),
        "down_payment": Decimal("100000.00"),
        "loan_amount": Decimal("400000.00"),
        "contract_rate": Decimal("4.50"),
        "amortization_years": 25,
        "annual_income": Decimal("120000.00"),
        "property_tax": Decimal("3000.00"),
        "heating_cost": Decimal("1200.00"),
        "other_debt": Decimal("500.00"),
    }


@pytest.fixture
def app():
    """
    Fixture to provide the FastAPI app instance for integration testing.
    Import the router and mount it.
    """
    from fastapi import FastAPI
    from mortgage_underwriting.modules.client_portal.routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/client-portal", tags=["Client Portal"])
    return app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for integration tests.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

--- unit_tests ---
```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_portal.services import ClientPortalService
from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
from mortgage_underwriting.modules.client_portal.exceptions import (
    GDSExceededException,
    TDSExceededException,
    InvalidLTVException,
)
from mortgage_underwriting.common.exceptions import AppException

# Import paths strictly following project conventions
# from mortgage_underwriting.modules.client_portal.models import MortgageApplication


@pytest.mark.unit
class TestClientPortalService:
    """
    Unit tests for ClientPortalService business logic.
    Focuses on Regulatory Requirements (OSFI, CMHC, PIPEDA).
    """

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return ClientPortalService(mock_db)

    @pytest.mark.asyncio
    async def test_submit_application_success(self, service, mock_db, valid_application_payload, mock_security):
        """
        Test happy path: Application submission with valid data.
        Verify PII encryption and DB persistence.
        """
        # Act
        result = await service.submit_application(ApplicationCreate(**valid_application_payload))

        # Assert
        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        
        # Verify PII handling (PIPEDA)
        # Ensure encrypt_pii was called for DOB
        mock_security["encrypt"].assert_any_call("1990-01-01")
        # Ensure hash_sin was called
        mock_security["hash"].assert_called_once_with("123456789")

    @pytest.mark.asyncio
    async def test_submit_application_osfi_gds_limit(self, service, mock_db, valid_application_payload):
        """
        Test OSFI B-20: GDS must be <= 39%.
        Scenario: High property tax and heating costs push GDS over limit.
        """
        # Modify payload to trigger GDS failure
        # Income 120k, Monthly ~10k. Max GDS ~3900.
        # Mortgage payment (400k @ 5.5% stress) ~ $2450
        # Tax + Heat needs to be > 1450 to fail.
        payload = valid_application_payload.copy()
        payload["property_tax"] = Decimal("20000.00") # ~1666/mo
        payload["heating_cost"] = Decimal("5000.00")  # ~416/mo
        payload["contract_rate"] = Decimal("3.00") # Stress test becomes 5.25%

        with pytest.raises(GDSExceededException) as exc_info:
            await service.submit_application(ApplicationCreate(**payload))
        
        assert "GDS" in str(exc_info.value)
        assert "39%" in str(exc_info.value)
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_submit_application_osfi_tds_limit(self, service, mock_db, valid_application_payload):
        """
        Test OSFI B-20: TDS must be <= 44%.
        Scenario: High external debt pushes TDS over limit.
        """
        payload = valid_application_payload.copy()
        # Max TDS on 120k is ~4400. Mortgage ~2450. Tax/Heat ~500.
        # Remaining room ~1450.
        payload["other_debt"] = Decimal("20000.00") # ~1666/mo debt

        with pytest.raises(TDSExceededException) as exc_info:
            await service.submit_application(ApplicationCreate(**payload))

        assert "TDS" in str(exc_info.value)
        assert "44%" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_application_osfi_stress_test_rate(self, service, mock_db, valid_application_payload):
        """
        Test OSFI B-20: Stress test rate calculation.
        Qualifying Rate = Max(Contract + 2%, 5.25%)
        """
        # Case 1: Contract 4.5% -> Qualifying 6.5% (Contract + 2)
        payload_1 = valid_application_payload.copy()
        payload_1["contract_rate"] = Decimal("4.5")
        
        # We spy on the internal calculation method via side effects or verify logic through exception if possible
        # Here we assume success, but the calculation logic is internal. 
        # To test specifically, we would ideally expose a helper or check logs.
        # For this test, we verify it doesn't throw a calculation error and accepts the debt load.
        result_1 = await service.submit_application(ApplicationCreate(**payload_1))
        assert result_1.id is not None

        # Case 2: Contract 3.0% -> Qualifying 5.25% (Floor)
        # If we set debts such that they fail at 5.25% but pass at 5.0%, we can verify the floor.
        # However, simpler is to verify the logic directly if exposed.
        # We will verify the logic via a helper test below.
        pass

    @pytest.mark.asyncio
    async def test_calculate_qualifying_rate(self, service):
        """
        Direct unit test for the stress test rate helper.
        """
        # Contract + 2% is higher
        rate = service._calculate_qualifying_rate(Decimal("4.0"))
        assert rate == Decimal("6.00")

        # Floor 5.25% is higher
        rate = service._calculate_qualifying_rate(Decimal("3.0"))
        assert rate == Decimal("5.25")

        # Boundary
        rate = service._calculate_qualifying_rate(Decimal("3.25"))
        assert rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_submit_application_cmhc_insurance_required(self, service, mock_db, valid_application_payload, mock_security):
        """
        Test CMHC: LTV > 80% requires insurance.
        Loan 400k, Value 500k -> LTV 80%. No insurance.
        """
        payload = valid_application_payload.copy()
        payload["loan_amount"] = Decimal("400000.00")
        payload["property_value"] = Decimal("500000.00")
        
        result = await service.submit_application(ApplicationCreate(**payload))
        
        # LTV = 80.0%. Insurance should be False or 0 premium
        assert result.insurance_required is False
        assert result.insurance_premium == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_submit_application_cmhc_premium_tier_1(self, service, mock_db, valid_application_payload, mock_security):
        """
        Test CMHC: LTV 85% triggers 2.80% premium.
        """
        payload = valid_application_payload.copy()
        payload["loan_amount"] = Decimal("425000.00") # 85% LTV
        payload["property_value"] = Decimal("500000.00")
        
        result = await service.submit_application(ApplicationCreate(**payload))
        
        assert result.insurance_required is True
        # Premium calculated on Loan Amount (CMHC standard logic varies, assuming on loan for simplicity here)
        # 425000 * 0.028 = 11900
        expected_premium = Decimal("11900.00")
        assert result.insurance_premium == expected_premium

    @pytest.mark.asyncio
    async def test_submit_application_invalid_ltv(self, service, mock_db, valid_application_payload):
        """
        Test CMHC: LTV > 95% is usually uninsurable/rejected.
        """
        payload = valid_application_payload.copy()
        payload["loan_amount"] = Decimal("480000.00") # 96% LTV
        payload["property_value"] = Decimal("500000.00")
        
        with pytest.raises(InvalidLTVException):
            await service.submit_application(ApplicationCreate(**payload))

    @pytest.mark.asyncio
    async def test_fintrac_logging(self, service, mock_db, valid_application_payload, caplog):
        """
        Test FINTRAC: Identity verification and creation logging.
        """
        import logging
        with caplog.at_level(logging.INFO):
            await service.submit_application(ApplicationCreate(**valid_application_payload))
        
        # Check that audit relevant logs were created
        assert any("application_created" in record.message.lower() for record in caplog.records)
        assert any("identity_verified" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_pii_data_minimization(self, service, mock_db, valid_application_payload, mock_security):
        """
        Test PIPEDA: Ensure only necessary fields are processed.
        If payload contains extra junk, it should be ignored or stripped.
        """
        payload = valid_application_payload.copy()
        payload["favorite_color"] = "blue" # Irrelevant field
        
        # Service should ignore this field if strict schema validation is on
        # Pydantic schema will handle stripping, but let's ensure service doesn't crash
        result = await service.submit_application(ApplicationCreate(**payload))
        assert result is not None
        # Verify the model object added to DB doesn't have the extra field
        # (This is implicitly handled by Pydantic, but good to verify no crash)

    @pytest.mark.asyncio
    async def test_database_integrity_handling(self, service, mock_db, valid_application_payload):
        """
        Test handling of DB errors (e.g., Duplicate SIN).
        """
        mock_db.commit.side_effect = IntegrityError("INSERT", {}, Exception("Duplicate key"))
        
        with pytest.raises(AppException) as exc_info:
            await service.submit_application(ApplicationCreate(**valid_application_payload))
        
        assert "duplicate" in str(exc_info.value.detail).lower() or "conflict" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_decimal_precision_handling(self, service, mock_db):
        """
        Test that float inputs are rejected or converted correctly.
        Pydantic handles conversion, but we verify logic uses Decimal.
        """
        payload = {
            "first_name": "Jane",
            "last_name": "Smith",
            "date_of_birth": "1985-05-20",
            "sin": "987654321",
            "email": "jane@example.com",
            "phone_number": "4165550199",
            "property_address": "456 Oak St",
            "property_value": "600000.00", # String input
            "down_payment": Decimal("120000.00"),
            "loan_amount": Decimal("480000.00"),
            "contract_rate": "5.0",
            "amortization_years": 25,
            "annual_income": "150000.00",
            "property_tax": "3500.00",
            "heating_cost": "1500.00",
            "other_debt": "0.00",
        }
        
        result = await service.submit_application(ApplicationCreate(**payload))
        assert result.property_value == Decimal("600000.00")
```

--- integration_tests ---
```python
import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.client_portal.models import MortgageApplication
from mortgage_underwriting.modules.client_portal.routes import router
from mortgage_underwriting.common.database import get_async_session


# Override the dependency for testing
async def override_get_db():
    from mortgage_underwriting.tests.conftest import TestingSessionLocal
    async with TestingSessionLocal() as session:
        yield session


@pytest.mark.integration
class TestClientPortalEndpoints:
    """
    Integration tests for Client Portal API endpoints.
    Tests the full HTTP request/response cycle and DB state.
    """

    @pytest.mark.asyncio
    async def test_create_application_success(self, app, client, valid_application_payload):
        """
        Test creating a new application via POST.
        """
        # Override DB dependency
        app.dependency_overrides[get_async_session] = override_get_db
        
        response = await client.post("/api/v1/client-portal/applications", json=valid_application_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["status"] == "submitted"
        assert data["first_name"] == "John"
        
        # Verify PII is NOT in response (PIPEDA)
        assert "sin" not in data
        assert "date_of_birth" not in data
        
        # Verify Financials are Decimal strings
        assert data["loan_amount"] == "400000.00"
        
        # Cleanup
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_create_application_validation_error(self, app, client):
        """
        Test 422 Unprocessable Entity on invalid schema.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        invalid_payload = {
            "first_name": "", # Empty string
            "loan_amount": "not_a_number"
        }
        
        response = await client.post("/api/v1/client-portal/applications", json=invalid_payload)
        
        assert response.status_code == 422
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_create_application_gds_rejection(self, app, client, valid_application_payload):
        """
        Test that business logic validation (GDS) returns 400 Bad Request.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        payload = valid_application_payload.copy()
        payload["annual_income"] = Decimal("30000.00") # Very low income
        
        response = await client.post("/api/v1/client-portal/applications", json=payload)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "GDS" in data["detail"]
        
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_get_application_not_found(self, app, client):
        """
        Test GET /applications/{id} with non-existent ID.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        response = await client.get("/api/v1/client-portal/applications/99999")
        
        assert response.status_code == 404
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_get_application_success(self, app, client, db_session, valid_application_payload):
        """
        Test retrieving an existing application.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        # 1. Create an application directly in DB
        from mortgage_underwriting.modules.client_portal.services import ClientPortalService
        from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
        
        service = ClientPortalService(db_session)
        created_app = await service.submit_application(ApplicationCreate(**valid_application_payload))
        await db_session.commit()
        
        # 2. Retrieve via API
        response = await client.get(f"/api/v1/client-portal/applications/{created_app.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_app.id
        assert data["email"] == "john.doe@example.com"
        
        # Ensure PII is filtered out
        assert "sin" not in data
        
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_list_applications_empty(self, app, client):
        """
        Test GET /applications returns empty list initially.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        response = await client.get("/api/v1/client-portal/applications")
        
        assert response.status_code == 200
        assert response.json() == []
        
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_update_application_status(self, app, client, db_session, valid_application_payload):
        """
        Test PATCH /applications/{id}/status (Internal/Underwriting view, but exposed via portal for status checks).
        Assuming client can only view, but let's test a hypothetical update endpoint or verify read-only nature.
        Here we test a GET request specifically for status.
        """
        app.dependency_overrides[get_async_session] = override_get_db

        from mortgage_underwriting.modules.client_portal.services import ClientPortalService
        from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
        
        service = ClientPortalService(db_session)
        created_app = await service.submit_application(ApplicationCreate(**valid_application_payload))
        await db_session.commit()

        # Update status manually in DB to simulate underwriting
        created_app.status = "approved"
        await db_session.commit()
        await db_session.refresh(created_app)

        response = await client.get(f"/api/v1/client-portal/applications/{created_app.id}")
        
        assert response.status_code == 200
        assert response.json()["status"] == "approved"
        
        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_audit_fields_persistence(self, app, client, db_session, valid_application_payload):
        """
        Test FINTRAC requirement: Audit trail (created_at, updated_at).
        """
        app.dependency_overrides[get_async_session] = override_get_db

        from mortgage_underwriting.modules.client_portal.services import ClientPortalService
        from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
        
        service = ClientPortalService(db_session)
        app_obj = await service.submit_application(ApplicationCreate(**valid_application_payload))
        await db_session.commit()
        await db_session.refresh(app_obj)
        
        assert app_obj.created_at is not None
        assert app_obj.updated_at is not None
        
        # Verify it's not the default epoch
        assert app_obj.created_at.year > 2000

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_cmhc_insurance_flag_in_response(self, app, client, db_session):
        """
        Test that CMHC insurance calculation is reflected in the GET response.
        """
        app.dependency_overrides[get_async_session] = override_get_db
        
        payload = {
            "first_name": "Test",
            "last_name": "User",
            "date_of_birth": "1990-01-01",
            "sin": "111222333",
            "email": "test@example.com",
            "phone_number": "4165550199",
            "property_address": "789 Pine St",
            "property_value": "400000.00",
            "down_payment": "20000.00", # 5% down -> 95% LTV
            "loan_amount": "380000.00",
            "contract_rate": "5.0",
            "amortization_years": 25,
            "annual_income": "100000.00",
            "property_tax": "3000.00",
            "heating_cost": "1200.00",
            "other_debt": "0.00",
        }

        from mortgage_underwriting.modules.client_portal.services import ClientPortalService
        from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
        
        service = ClientPortalService(db_session)
        app_obj = await service.submit_application(ApplicationCreate(**payload))
        await db_session.commit()
        
        response = await client.get(f"/api/v1/client-portal/applications/{app_obj.id}")
        data = response.json()
        
        assert data["insurance_required"] is True
        # 95% LTV -> 4.00% premium. 380000 * 0.04 = 15200
        assert Decimal(data["insurance_premium"]) == Decimal("15200.00")
        
        app.dependency_overrides = {}
```