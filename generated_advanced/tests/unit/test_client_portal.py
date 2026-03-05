import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_portal.services import ClientPortalService
from mortgage_underwriting.modules.client_portal.schemas import ApplicationCreate
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientPortalService:

    @pytest.mark.asyncio
    async def test_submit_application_success(self, mock_db_session, mock_application_payload):
        # Arrange
        payload = ApplicationCreate(**mock_application_payload)
        service = ClientPortalService(mock_db_session)
        
        # Mock the encryption and hashing helpers
        with patch("mortgage_underwriting.modules.client_portal.services.encrypt_pii", return_value="encrypted_sin"), \
             patch("mortgage_underwriting.modules.client_portal.services.hash_sin", return_value="hashed_sin"), \
             patch("mortgage_underwriting.modules.client_portal.services.validate_ltv", return_value=True):

            # Act
            result = await service.submit_application(payload)

            # Assert
            assert result is not None
            assert result.loan_amount == Decimal("450000.00")
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_application_encryption_called(self, mock_db_session, mock_application_payload):
        # Arrange
        payload = ApplicationCreate(**mock_application_payload)
        service = ClientPortalService(mock_db_session)

        with patch("mortgage_underwriting.modules.client_portal.services.encrypt_pii") as mock_encrypt, \
             patch("mortgage_underwriting.modules.client_portal.services.hash_sin") as mock_hash, \
             patch("mortgage_underwriting.modules.client_portal.services.validate_ltv", return_value=True):

            # Act
            await service.submit_application(payload)

            # Assert - PIPEDA Compliance
            mock_encrypt.assert_called_once_with("123456789")
            mock_hash.assert_called_once_with("123456789")

    @pytest.mark.asyncio
    async def test_submit_application_invalid_ltv_raises_error(self, mock_db_session):
        # Arrange
        # LTV = 95.01% (High Risk) or 0% (Bad Data)
        payload_data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "sin": "987654321",
            "loan_amount": "95001.00",
            "property_value": "100000.00",
            "annual_income": "50000.00",
            "down_payment": "4999.00"
        }
        payload = ApplicationCreate(**payload_data)
        service = ClientPortalService(mock_db_session)

        with patch("mortgage_underwriting.modules.client_portal.services.validate_ltv", return_value=False):
            # Act & Assert
            with pytest.raises(AppException) as exc_info:
                await service.submit_application(payload)
            
            assert exc_info.value.error_code == "INVALID_LTV"
            mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_calculate_premium_cmhc_tiers(self):
        # Arrange
        service = ClientPortalService(AsyncMock())
        
        # Act & Assert - CMHC Compliance
        # Tier 1: 80.01% - 85.00% -> 2.80%
        ltv_82 = Decimal("0.82")
        premium = service._calculate_insurance_premium(ltv_82)
        assert premium == Decimal("0.0280")

        # Tier 2: 85.01% - 90.00% -> 3.10%
        ltv_88 = Decimal("0.88")
        premium = service._calculate_insurance_premium(ltv_88)
        assert premium == Decimal("0.0310")

        # Tier 3: 90.01% - 95.00% -> 4.00%
        ltv_92 = Decimal("0.92")
        premium = service._calculate_insurance_premium(ltv_92)
        assert premium == Decimal("0.0400")

        # No Insurance
        ltv_80 = Decimal("0.80")
        premium = service._calculate_insurance_premium(ltv_80)
        assert premium == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_osfi_stress_test_qualifying_rate(self):
        # Arrange
        service = ClientPortalService(AsyncMock())
        
        # Scenario 1: Contract rate is 3.0%. Qualifying = max(3.0 + 2.0, 5.25) = 5.25%
        contract_rate = Decimal("0.03")
        qualifying = service._get_qualifying_rate(contract_rate)
        assert qualifying == Decimal("0.0525")

        # Scenario 2: Contract rate is 6.0%. Qualifying = max(6.0 + 2.0, 5.25) = 8.0%
        contract_rate_high = Decimal("0.06")
        qualifying_high = service._get_qualifying_rate(contract_rate_high)
        assert qualifying_high == Decimal("0.08")

    @pytest.mark.asyncio
    async def test_calculate_gds_osfi_limits(self):
        # Arrange
        service = ClientPortalService(AsyncMock())
        monthly_income = Decimal("10000.00")
        property_tax = Decimal("300.00")
        heating = Decimal("150.00")
        # Qualifying rate 5.25%
        monthly_mortgage_payment = Decimal("3500.00") 
        
        # Act
        gds = service._calculate_gds(
            monthly_mortgage_payment, 
            property_tax, 
            heating, 
            monthly_income
        )
        
        # Assert (3500 + 300 + 150) / 10000 = 0.395 -> 39.5%
        expected_gds = Decimal("0.395")
        assert gds == expected_gds
        
        # Check limit enforcement logic (Service should raise or flag if > 39%)
        # Assuming service returns bool or raises, here testing calculation
        assert gds > Decimal("0.39") # Over limit

    @pytest.mark.asyncio
    async def test_get_application_by_id_not_found(self, mock_db_session):
        # Arrange
        service = ClientPortalService(mock_db_session)
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # Act
        result = await service.get_application(999)
        
        # Assert
        assert result is None
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_application_sin_immutable(self, mock_db_session):
        # Arrange
        service = ClientPortalService(mock_db_session)
        existing_app = MagicMock()
        existing_app.sin_hash = "old_hash"
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = existing_app
        
        update_data = {"sin": "999999999"} # Attempt to change SIN
        
        # Act
        with pytest.raises(AppException) as exc_info:
            await service.update_application(1, update_data)
            
        assert exc_info.value.error_code == "IMMUTABLE_FIELD"
        mock_db_session.commit.assert_not_awaited()