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