import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.client_intake.services import ClientIntakeService
from mortgage_underwriting.modules.client_intake.models import ClientApplication
from mortgage_underwriting.modules.client_intake.exceptions import ApplicationCreationError, InvalidInputError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientIntakeService:

    @pytest.fixture
    def mock_db_session(self):
        """Mock AsyncSession for unit tests."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.scalar = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_create_application_success(self, mock_db_session, valid_application_payload):
        """Test successful creation of a client application."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        
        # Mock the encryption behavior
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "encrypted_hash_123"
            
            # Act
            result = await service.create_application(ClientApplicationCreate(**valid_application_payload))

            # Assert
            assert isinstance(result, ClientApplication)
            assert result.first_name == "John"
            assert result.loan_amount == Decimal("400000.00")
            assert result.sin_hash == "encrypted_hash_123" # Verify PIPEDA encryption call
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_ltv_calculation(self, mock_db_session, high_ltv_payload):
        """Test that LTV is calculated correctly and CMHC flag is set if needed."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "hash"
            
            # Act
            result = await service.create_application(ClientApplicationCreate(**high_ltv_payload))

            # Assert
            # LTV = 450,000 / 500,000 = 0.90 (90%)
            expected_ltv = Decimal("0.90")
            assert result.ltv_ratio == expected_ltv
            # CMHC Requirement: > 80% LTV requires insurance
            assert result.insurance_required is True

    @pytest.mark.asyncio
    async def test_create_application_no_insurance_under_80_ltv(self, mock_db_session, valid_application_payload):
        """Test that insurance is not required if LTV <= 80%."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii") as mock_encrypt:
            mock_encrypt.return_value = "hash"
            
            # Act
            result = await service.create_application(ClientApplicationCreate(**valid_application_payload))

            # Assert
            # LTV = 400,000 / 500,000 = 0.80 (80%)
            expected_ltv = Decimal("0.80")
            assert result.ltv_ratio == expected_ltv
            assert result.insurance_required is False

    @pytest.mark.asyncio
    async def test_create_application_database_error(self, mock_db_session, valid_application_payload):
        """Test handling of database errors during commit."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        mock_db_session.commit.side_effect = SQLAlchemyError("DB Connection failed")

        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii"):
            # Act & Assert
            with pytest.raises(ApplicationCreationError):
                await service.create_application(ClientApplicationCreate(**valid_application_payload))
            
            # Ensure rollback is attempted on error
            mock_db_session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_application_by_id_success(self, mock_db_session):
        """Test retrieving an application by ID."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        app_id = uuid.uuid4()
        
        mock_app = ClientApplication(
            id=app_id,
            first_name="Test",
            last_name="User",
            loan_amount=Decimal("100000.00"),
            property_value=Decimal("200000.00"),
            ltv_ratio=Decimal("0.50"),
            sin_hash="hash",
            dob_encrypted="encrypted",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_app
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.get_application_by_id(app_id)

        # Assert
        assert result is not None
        assert result.id == app_id
        assert result.first_name == "Test"

    @pytest.mark.asyncio
    async def test_get_application_not_found(self, mock_db_session):
        """Test retrieving a non-existent application raises appropriate error."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        app_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_application_by_id(app_id)
        
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_validate_financials_zero_down_payment(self, mock_db_session):
        """Test validation logic for zero or negative down payment."""
        # Arrange
        service = ClientIntakeService(mock_db_session)
        invalid_payload = {
            "first_name": "Bad",
            "last_name": "Data",
            "date_of_birth": "1990-01-01",
            "sin": "000000000",
            "email": "bad@test.com",
            "phone_number": "0000000000",
            "property_address": "0 Nowhere St",
            "property_value": Decimal("100000.00"),
            "loan_amount": Decimal("100000.00"), # 100% LTV
            "down_payment": Decimal("0.00"),
            "employment_status": "employed",
            "annual_income": Decimal("50000.00")
        }

        # Act & Assert
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii"):
            with pytest.raises(InvalidInputError) as exc_info:
                await service.create_application(ClientApplicationCreate(**invalid_payload))
            
            assert "down payment" in str(exc_info.value.detail).lower()