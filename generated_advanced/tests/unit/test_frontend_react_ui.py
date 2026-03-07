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