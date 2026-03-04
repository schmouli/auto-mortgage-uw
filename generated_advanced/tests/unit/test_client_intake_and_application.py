import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.modules.client_intake.schemas import ClientCreate, ApplicationCreate
from mortgage_underwriting.modules.client_intake.services import ClientIntakeService, ApplicationService
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientIntakeService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_create_client_success(self, mock_db, mock_security, valid_client_payload):
        # Arrange
        encrypt_mock, hash_mock = mock_security
        schema = ClientCreate(**valid_client_payload)
        service = ClientIntakeService(mock_db)
        
        # Mock the result of a potential existing user check (return None)
        mock_result = AsyncMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act
        result = await service.create_client(schema)

        # Assert
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        encrypt_mock.assert_called() # PIPEDA: Ensure encryption was attempted
        hash_mock.assert_called()    # PIPEDA: Ensure hashing was attempted
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_client_duplicate_sin_raises_exception(self, mock_db, valid_client_payload):
        # Arrange
        schema = ClientCreate(**valid_client_payload)
        service = ClientIntakeService(mock_db)
        
        # Mock existing client
        mock_existing_client = Client(id=1, sin_hash="hashed_sin")
        mock_result = AsyncMock()
        mock_result.first.return_value = mock_existing_client
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_client(schema)
        
        assert exc_info.value.error_code == "CLIENT_EXISTS"
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_client_by_id_success(self, mock_db):
        # Arrange
        client_id = 1
        service = ClientIntakeService(mock_db)
        mock_client = Client(id=client_id, first_name="Jane", last_name="Smith")
        
        mock_result = AsyncMock()
        mock_result.first.return_value = mock_client
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act
        result = await service.get_client(client_id)

        # Assert
        assert result is not None
        assert result.id == client_id

    @pytest.mark.asyncio
    async def test_get_client_not_found_raises(self, mock_db):
        # Arrange
        service = ClientIntakeService(mock_db)
        mock_result = AsyncMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_client(999)
        assert exc_info.value.status_code == 404


@pytest.mark.unit
class TestApplicationService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.scalars = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_create_application_success(self, mock_db, valid_application_payload):
        # Arrange
        # Ensure Decimal is used for financial values
        payload = valid_application_payload.copy()
        payload["requested_amount"] = Decimal(payload["requested_amount"])
        payload["property_value"] = Decimal(payload["property_value"])
        
        schema = ApplicationCreate(**payload)
        service = ApplicationService(mock_db)

        # Mock client existence check
        mock_client = Client(id=1, first_name="John")
        mock_result = AsyncMock()
        mock_result.first.return_value = mock_client
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act
        result = await service.create_application(schema)

        # Assert
        assert result.requested_amount == Decimal("450000.00")
        assert result.property_value == Decimal("500000.00")
        assert result.status == "PENDING"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_client_not_found_raises(self, mock_db, valid_application_payload):
        # Arrange
        payload = valid_application_payload.copy()
        payload["requested_amount"] = Decimal(payload["requested_amount"])
        payload["property_value"] = Decimal(payload["property_value"])
        
        schema = ApplicationCreate(**payload)
        service = ApplicationService(mock_db)

        # Mock client not found
        mock_result = AsyncMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.scalars.return_value = mock_result

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_application(schema)
        assert exc_info.value.error_code == "CLIENT_NOT_FOUND"
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_ltv_logic_high_ratio(self, mock_db):
        # Arrange
        # CMHC Logic: LTV > 80% triggers insurance
        service = ApplicationService(mock_db)
        amount = Decimal("450000.00")
        value = Decimal("500000.00")
        
        # Act
        ltv = service.calculate_ltv(amount, value)

        # Assert
        # 450000 / 500000 = 0.9 (90%)
        assert ltv == Decimal("0.90")
        # In a real scenario, this would trigger insurance_required = True logic

    @pytest.mark.asyncio
    async def test_validate_ltv_logic_conventional(self, mock_db):
        # Arrange
        service = ApplicationService(mock_db)
        amount = Decimal("400000.00")
        value = Decimal("500000.00")
        
        # Act
        ltv = service.calculate_ltv(amount, value)

        # Assert
        # 400000 / 500000 = 0.8 (80%)
        assert ltv == Decimal("0.80")

    @pytest.mark.asyncio
    async def test_application_invalid_zero_amount_raises(self, mock_db, valid_application_payload):
        # Arrange
        payload = valid_application_payload.copy()
        payload["requested_amount"] = Decimal("0.00")
        payload["property_value"] = Decimal("500000.00")
        
        schema = ApplicationCreate(**payload)
        service = ApplicationService(mock_db)

        # Act & Assert
        with pytest.raises(ValueError): # Or AppException depending on implementation
            await service.create_application(schema)