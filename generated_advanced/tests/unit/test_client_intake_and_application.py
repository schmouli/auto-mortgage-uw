import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

# Import paths based on project structure
from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.modules.client_intake.exceptions import (
    ClientNotFoundException,
    InvalidApplicationDataException,
    DuplicateClientException
)
from mortgage_underwriting.modules.client_intake.schemas import ClientCreate, ApplicationCreate

@pytest.mark.unit
class TestClientService:

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
        mock_enc, mock_hash = mock_security
        payload = ClientCreate(**valid_client_payload)
        
        # Mock the result of a potential duplicate check
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        
        service = ClientService(mock_db)

        # Act
        result = await service.create_client(payload)

        # Assert
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        # Verify SIN was encrypted
        assert result.sin == "encrypted_string"
        # Verify DOB was handled (and potentially encrypted based on implementation)
        assert result.date_of_birth == payload.date_of_birth
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_create_client_duplicate_sin(self, mock_db, valid_client_payload):
        # Arrange
        payload = ClientCreate(**valid_client_payload)
        
        # Mock DB returning an existing client (duplicate)
        mock_existing_client = MagicMock()
        mock_existing_client.id = 999
        mock_result = MagicMock()
        mock_result.first.return_value = mock_existing_client
        mock_db.execute.return_value = mock_result
        
        service = ClientService(mock_db)

        # Act & Assert
        with pytest.raises(DuplicateClientException) as exc_info:
            await service.create_client(payload)
        
        assert "already exists" in str(exc_info.value)
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_client_by_id_success(self, mock_db):
        # Arrange
        client_id = 1
        mock_client = MagicMock()
        mock_client.id = client_id
        mock_client.first_name = "Jane"
        
        mock_result = MagicMock()
        mock_result.first.return_value = mock_client
        mock_db.execute.return_value = mock_result
        
        service = ClientService(mock_db)

        # Act
        result = await service.get_client(client_id)

        # Assert
        assert result.id == client_id
        assert result.first_name == "Jane"

    @pytest.mark.asyncio
    async def test_get_client_not_found(self, mock_db):
        # Arrange
        client_id = 999
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        
        service = ClientService(mock_db)

        # Act & Assert
        with pytest.raises(ClientNotFoundException):
            await service.get_client(client_id)


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
        payload = ApplicationCreate(**valid_application_payload)
        
        # Mock client lookup
        mock_client = MagicMock()
        mock_client.id = 1
        mock_client.first_name = "John"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute.return_value = mock_result
        
        service = ApplicationService(mock_db)

        # Act
        result = await service.create_application(payload)

        # Assert
        assert result.loan_amount == Decimal("400000.00")
        assert result.client_id == 1
        # Ensure Decimal type is preserved
        assert isinstance(result.loan_amount, Decimal)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_client_not_found(self, mock_db, valid_application_payload):
        # Arrange
        payload = ApplicationCreate(**valid_application_payload)
        
        # Mock client lookup returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        service = ApplicationService(mock_db)

        # Act & Assert
        with pytest.raises(ClientNotFoundException):
            await service.create_application(payload)

    @pytest.mark.asyncio
    async def test_create_application_invalid_ltv(self, mock_db, valid_application_payload):
        # Arrange
        # Modify payload to have 0 down payment (100% LTV), which should fail validation
        invalid_payload = valid_application_payload.copy()
        invalid_payload["down_payment"] = "0.00"
        invalid_payload["loan_amount"] = "500000.00"
        
        payload = ApplicationCreate(**invalid_payload)
        
        # Mock client lookup (pass validation to fail logic)
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute.return_value = mock_result
        
        service = ApplicationService(mock_db)

        # Act & Assert
        # Assuming service validates LTV logic (e.g., max 95%)
        with pytest.raises(InvalidApplicationDataException) as exc_info:
            await service.create_application(payload)
        
        assert "LTV" in str(exc_info.value) or "Loan to Value" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_gds_tds_logic(self, mock_db):
        # Arrange
        # Test the calculation logic helper (if exposed or part of create)
        # GDS = (PIT + Heat) / Income
        # TDS = (PIT + Heat + Other) / Income
        
        income = Decimal("5000.00")
        mortgage_payment = Decimal("1500.00")
        property_tax = Decimal("300.00")
        heating = Decimal("100.00")
        other_debt = Decimal("500.00")
        
        service = ApplicationService(mock_db)
        
        # Act
        gds = service._calculate_gds(mortgage_payment, property_tax, heating, income)
        tds = service._calculate_tds(mortgage_payment, property_tax, heating, other_debt, income)
        
        # Assert
        # (1500 + 300 + 100) / 5000 = 1900 / 5000 = 0.38 (38%)
        assert gds == Decimal("0.38")
        # (1900 + 500) / 5000 = 2400 / 5000 = 0.48 (48%)
        assert tds == Decimal("0.48")