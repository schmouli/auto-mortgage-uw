import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.modules.client_intake.schemas import ClientCreate, ApplicationCreate
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientService:

    @pytest.mark.asyncio
    async def test_create_client_success(self, mock_db_session, mock_encryption_service, client_payload_dict):
        # Arrange
        mock_enc, mock_hash = mock_encryption_service
        payload = ClientCreate(**client_payload_dict)
        service = ClientService(mock_db_session)
        
        # Mock the DB refresh to return an object with an ID
        def mock_refresh(obj):
            obj.id = 1
            obj.created_at = "2023-01-01T00:00:00"
            
        mock_db_session.refresh.side_effect = mock_refresh

        # Act
        result = await service.create_client(payload)

        # Assert
        assert result.id == 1
        assert result.first_name == "John"
        assert result.email == "john.doe@example.com"
        # Ensure SIN was encrypted, not stored plain
        mock_enc.assert_called_once_with("123456789")
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_client_duplicate_email_raises(self, mock_db_session, mock_encryption_service, client_payload_dict):
        # Arrange
        payload = ClientCreate(**client_payload_dict)
        service = ClientService(mock_db_session)
        
        # Simulate DB integrity error (e.g., unique constraint violation)
        mock_db_session.commit.side_effect = IntegrityError("INSERT", {}, Exception())

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_client(payload)
        
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_client_by_id_success(self, mock_db_session):
        # Arrange
        service = ClientService(mock_db_session)
        mock_client = Client(
            id=1,
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            encrypted_sin="enc...",
            hashed_sin="hash...",
            date_of_birth="1990-01-01"
        )
        mock_db_session.scalar.return_value = mock_client

        # Act
        result = await service.get_client(1)

        # Assert
        assert result.first_name == "Jane"
        assert result.id == 1
        mock_db_session.scalar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_client_not_found_raises(self, mock_db_session):
        # Arrange
        service = ClientService(mock_db_session)
        mock_db_session.scalar.return_value = None

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_client(999)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

@pytest.mark.unit
class TestApplicationService:

    @pytest.mark.asyncio
    async def test_create_application_success(self, mock_db_session, application_payload_dict):
        # Arrange
        payload = ApplicationCreate(**application_payload_dict)
        service = ApplicationService(mock_db_session)
        
        # Mock Client existence check
        mock_client = Client(id=1, first_name="John", last_name="Doe", email="john@example.com", encrypted_sin="x", hashed_sin="y")
        mock_db_session.scalar.return_value = mock_client

        def mock_refresh(obj):
            obj.id = 101
            obj.created_at = "2023-01-01T00:00:00"
            
        mock_db_session.refresh.side_effect = mock_refresh

        # Act
        result = await service.create_application(payload)

        # Assert
        assert result.id == 101
        assert result.loan_amount == Decimal("600000.00")
        assert result.property_value == Decimal("750000.00")
        # Check Decimal precision is maintained
        assert result.down_payment == Decimal("150000.00")
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_client_not_found(self, mock_db_session, application_payload_dict):
        # Arrange
        payload = ApplicationCreate(**application_payload_dict)
        service = ApplicationService(mock_db_session)
        
        # Mock client not found
        mock_db_session.scalar.return_value = None

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_application(payload)
        
        assert exc_info.value.status_code == 404
        assert "client" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_application_invalid_ltv_logic(self, mock_db_session, application_payload_dict):
        # Arrange
        # Modify payload to make Down Payment > Property Value (Impossible LTV)
        invalid_payload = application_payload_dict.copy()
        invalid_payload['down_payment'] = Decimal("800000.00") # Higher than property value
        invalid_payload['loan_amount'] = Decimal("-50000.00") # Negative loan
        
        payload = ApplicationCreate(**invalid_payload)
        service = ApplicationService(mock_db_session)
        
        # Mock client exists
        mock_client = Client(id=1, first_name="John", last_name="Doe", email="john@example.com", encrypted_sin="x", hashed_sin="y")
        mock_db_session.scalar.return_value = mock_client

        # Act & Assert
        # The service should validate that Loan Amount + Down Payment = Property Value (approx) or basic logic
        # For this test, we assume validation happens in Pydantic or Service
        with pytest.raises(ValueError) as exc_info:
            await service.create_application(payload)
        
        assert "invalid financials" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_update_application_status(self, mock_db_session):
        # Arrange
        service = ApplicationService(mock_db_session)
        mock_app = Application(
            id=1,
            client_id=1,
            status="submitted",
            loan_amount=Decimal("100000.00"),
            property_value=Decimal("100000.00")
        )
        mock_db_session.scalar.return_value = mock_app

        # Act
        result = await service.update_status(application_id=1, new_status="under_review")

        # Assert
        assert result.status == "under_review"
        mock_db_session.commit.assert_awaited_once()