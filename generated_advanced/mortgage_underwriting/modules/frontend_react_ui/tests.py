--- conftest.py ---
import pytest
from decimal import Decimal
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Mock imports for the module under test
# In a real scenario, these would be the actual imports
from mortgage_underwriting.modules.frontend_react_ui.models import UIConfig
from mortgage_underwriting.modules.frontend_react_ui.routes import router
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.config import settings

# Use in-memory SQLite for testing speed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
AsyncTestingSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

Base = declarative_base()

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

@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    """
    Creates a test FastAPI app with the frontend router attached.
    Overrides the database dependency.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/frontend", tags=["Frontend"])

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for integration tests.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def valid_prequalification_payload() -> dict:
    """
    Valid payload for the pre-qualification calculator endpoint.
    """
    return {
        "annual_income": Decimal("95000.00"),
        "property_tax": Decimal("3000.00"),
        "heating_cost": Decimal("1200.00"),
        "condo_fees": Decimal("0.00"),
        "debt_payments": Decimal("450.00"),
        "mortgage_rate": Decimal("4.50"),
        "amortization_years": 25,
        "down_payment": Decimal("50000.00")
    }

@pytest.fixture
def valid_config_payload() -> dict:
    """
    Valid payload for updating UI configuration.
    """
    return {
        "theme": "dark",
        "language": "en-CA",
        "notifications_enabled": True
    }
--- unit_tests ---
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.frontend_react_ui.services import FrontendService
from mortgage_underwriting.modules.frontend_react_ui.schemas import (
    PrequalificationRequest,
    PrequalificationResponse,
    UIConfigCreate,
    UIConfigResponse
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestFrontendService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_calculate_prequalification_success(self, mock_db):
        """
        Test successful calculation of max mortgage amount.
        Verifies OSFI B-20 stress test application (max(contract_rate + 2%, 5.25%)).
        """
        service = FrontendService(mock_db)
        payload = PrequalificationRequest(
            annual_income=Decimal("100000.00"),
            property_tax=Decimal("3600.00"),
            heating_cost=Decimal("1200.00"),
            debt_payments=Decimal("500.00"),
            mortgage_rate=Decimal("4.0"), # Contract rate
            amortization_years=25,
            down_payment=Decimal("20000.00")
        )

        result = await service.calculate_prequalification(payload)

        # Qualifying rate should be max(4.0 + 2, 5.25) = 6.0%
        assert result.qualifying_rate == Decimal("6.00")
        assert result.max_mortgage_amount > Decimal("0")
        assert result.gds_ratio <= Decimal("0.39")
        assert result.tds_ratio <= Decimal("0.44")
        assert result.insurance_required is True # Assuming LTV > 80% logic applies here

    @pytest.mark.asyncio
    async def test_calculate_prequalification_stress_test_floor(self, mock_db):
        """
        Test that the qualifying rate respects the 5.25% floor.
        """
        service = FrontendService(mock_db)
        payload = PrequalificationRequest(
            annual_income=Decimal("100000.00"),
            property_tax=Decimal("3600.00"),
            heating_cost=Decimal("1200.00"),
            debt_payments=Decimal("0.00"),
            mortgage_rate=Decimal("2.5"), # Contract rate low
            amortization_years=25,
            down_payment=Decimal("20000.00")
        )

        result = await service.calculate_prequalification(payload)

        # Qualifying rate should be max(2.5 + 2, 5.25) = 5.25%
        assert result.qualifying_rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_calculate_prequalification_tds_exceeds_limit(self, mock_db):
        """
        Test that high debt payments reduce the max mortgage amount to keep TDS <= 44%.
        """
        service = FrontendService(mock_db)
        payload = PrequalificationRequest(
            annual_income=Decimal("100000.00"),
            property_tax=Decimal("3600.00"),
            heating_cost=Decimal("1200.00"),
            debt_payments=Decimal("5000.00"), # High debt
            mortgage_rate=Decimal("4.0"),
            amortization_years=25,
            down_payment=Decimal("20000.00")
        )

        result = await service.calculate_prequalification(payload)

        # TDS should be exactly at or just below the limit (44%)
        # Decimal comparison requires precision
        assert result.tds_ratio <= Decimal("0.44")
        # Max mortgage should be significantly reduced or zero
        assert result.max_mortgage_amount >= Decimal("0.00")

    @pytest.mark.asyncio
    async def test_save_user_preferences_success(self, mock_db):
        """
        Test saving UI configuration to the database.
        """
        service = FrontendService(mock_db)
        config_payload = UIConfigCreate(
            user_id="user_123",
            theme="light",
            language="fr-CA"
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None # No existing config
        mock_db.execute.return_value = mock_result

        result = await service.save_user_preferences(config_payload)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        assert result.theme == "light"

    @pytest.mark.asyncio
    async def test_save_user_preferences_db_error(self, mock_db):
        """
        Test handling of database errors during save.
        """
        service = FrontendService(mock_db)
        config_payload = UIConfigCreate(
            user_id="user_123",
            theme="light",
            language="en-CA"
        )

        mock_db.commit.side_effect = SQLAlchemyError("Database connection failed")

        with pytest.raises(AppException) as exc_info:
            await service.save_user_preferences(config_payload)

        assert exc_info.value.status_code == 500
        assert "Failed to save preferences" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_product_list(self, mock_db):
        """
        Test retrieval of available mortgage products for the UI dropdown.
        """
        service = FrontendService(mock_db)
        
        # Mock DB response
        mock_products = MagicMock()
        mock_products.id = 1
        mock_products.name = "Fixed 5-Year"
        mock_products.rate = Decimal("4.99")
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_products]
        mock_db.execute.return_value = mock_result

        products = await service.get_product_list()

        assert len(products) == 1
        assert products[0]["name"] == "Fixed 5-Year"
        assert isinstance(products[0]["rate"], Decimal)

    def test_validate_down_payment_minimum(self):
        """
        Test validation logic for minimum down payment (CMHC rules: 5% for first 500k).
        """
        service = FrontendService(AsyncMock()) # DB not needed for pure logic check
        
        purchase_price = Decimal("500000.00")
        down_payment = Decimal("20000.00") # 4% - should fail
        
        is_valid, msg = service.validate_down_payment(purchase_price, down_payment)
        assert is_valid is False
        assert "minimum" in msg.lower()

    def test_validate_down_payment_success(self):
        """
        Test successful down payment validation.
        """
        service = FrontendService(AsyncMock())
        
        purchase_price = Decimal("500000.00")
        down_payment = Decimal("25000.00") # 5% - should pass
        
        is_valid, msg = service.validate_down_payment(purchase_price, down_payment)
        assert is_valid is True
--- integration_tests ---
import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy import select

from mortgage_underwriting.modules.frontend_react_ui.models import UIConfig
from mortgage_underwriting.common.database import get_async_session

@pytest.mark.integration
class TestFrontendRoutes:

    async def test_calculate_prequalification_endpoint(self, client: AsyncClient):
        """
        Integration test for the prequalification calculator endpoint.
        Verifies request/response contract and OSFI B-20 compliance.
        """
        response = await client.post(
            "/api/v1/frontend/calculate",
            json={
                "annual_income": "85000.00",
                "property_tax": "2400.00",
                "heating_cost": "1200.00",
                "condo_fees": "0.00",
                "debt_payments": "300.00",
                "mortgage_rate": "3.5",
                "amortization_years": 25,
                "down_payment": "40000.00"
            }
        )

        assert response.status_code == 200
        data = response.json()
        
        assert "max_mortgage_amount" in data
        assert "qualifying_rate" in data
        assert "gds_ratio" in data
        assert "tds_ratio" in data
        assert "insurance_required" in data
        
        # Verify Decimal precision is maintained in JSON response (string representation)
        assert isinstance(data["max_mortgage_amount"], str)
        assert Decimal(data["max_mortgage_amount"]) > 0
        
        # Verify qualifying rate logic (Contract 3.5 + 2 = 5.5 > 5.25)
        assert Decimal(data["qualifying_rate"]) == Decimal("5.50")

    async def test_calculate_prequalification_invalid_input(self, client: AsyncClient):
        """
        Test validation error handling for malformed requests.
        """
        response = await client.post(
            "/api/v1/frontend/calculate",
            json={
                "annual_income": "-50000", # Negative income
                "mortgage_rate": "3.5",
                "amortization_years": 30
            }
        )

        assert response.status_code == 422 # Unprocessable Entity

    async def test_get_ui_config_default(self, client: AsyncClient):
        """
        Test retrieving default UI configuration when no user-specific config exists.
        """
        response = await client.get(
            "/api/v1/frontend/config",
            params={"user_id": "new_user_999"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "light" # Default
        assert data["language"] == "en-CA" # Default

    async def test_save_and_retrieve_ui_config(self, client: AsyncClient, db_session):
        """
        Multi-step workflow: Save config, then retrieve it to verify persistence.
        """
        user_id = "integration_test_user"
        
        # Step 1: Save Config
        save_response = await client.post(
            "/api/v1/frontend/config",
            json={
                "user_id": user_id,
                "theme": "dark",
                "language": "fr-CA",
                "notifications_enabled": False
            }
        )
        assert save_response.status_code == 201

        # Step 2: Retrieve Config
        get_response = await client.get(
            "/api/v1/frontend/config",
            params={"user_id": user_id}
        )
        assert get_response.status_code == 200
        data = get_response.json()
        
        assert data["theme"] == "dark"
        assert data["language"] == "fr-CA"
        assert data["notifications_enabled"] is False

    async def test_update_existing_config(self, client: AsyncClient, db_session):
        """
        Test updating an existing configuration record.
        """
        user_id = "update_test_user"
        
        # Initial creation
        await client.post(
            "/api/v1/frontend/config",
            json={"user_id": user_id, "theme": "light", "language": "en-CA"}
        )

        # Update
        update_response = await client.put(
            f"/api/v1/frontend/config/{user_id}",
            json={"theme": "high_contrast", "language": "en-CA"}
        )
        assert update_response.status_code == 200
        
        # Verify update
        get_response = await client.get(
            "/api/v1/frontend/config",
            params={"user_id": user_id}
        )
        data = get_response.json()
        assert data["theme"] == "high_contrast"

    async def test_health_check_endpoint(self, client: AsyncClient):
        """
        Test the health check endpoint used by the React frontend.
        """
        response = await client.get("/api/v1/frontend/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "frontend-adapter"}

    async def test_get_provinces_list(self, client: AsyncClient):
        """
        Test retrieval of static data (Provinces) for dropdowns.
        Ensures data minimization (only code and name).
        """
        response = await client.get("/api/v1/frontend/static-data/provinces")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify structure
        assert "code" in data[0]
        assert "name" in data[0]
        # Ensure no sensitive data is leaked
        assert "tax_rate" not in data[0] 

    async def test_calculate_with_high_ltv_triggers_insurance(self, client: AsyncClient):
        """
        Test CMHC logic: Low down payment (High LTV) should trigger insurance requirement.
        """
        response = await client.post(
            "/api/v1/frontend/calculate",
            json={
                "annual_income": "100000.00",
                "property_tax": "3000.00",
                "heating_cost": "1000.00",
                "condo_fees": "0.00",
                "debt_payments": "0.00",
                "mortgage_rate": "4.0",
                "amortization_years": 25,
                "down_payment": "5000.00" # Very low down payment
            }
        )

        assert response.status_code == 200
        data = response.json()
        # LTV > 80% logic check
        assert data["insurance_required"] is True
        # Check if premium rate is applied (approximate check)
        assert Decimal(data["insurance_premium"]) > Decimal("0.00")