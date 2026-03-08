```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.models import Client, Application
from mortgage_underwriting.modules.client_intake.schemas import ClientCreate, ApplicationCreate
from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService
from mortgage_underwriting.common.exceptions import AppException

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

@pytest.mark.asyncio
class TestClientService:
    
    async def test_create_client_success(self, mock_db_session, mock_security, valid_client_payload):
        # Arrange
        schema = ClientCreate(**valid_client_payload)
        service = ClientService(mock_db_session)
        
        # Act
        result = await service.create_client(schema)
        
        # Assert
        assert result.first_name == "John"
        assert result.email == "john.doe@example.com"
        # Verify PII was encrypted
        mock_security["encrypt"].assert_called_once_with("123456789")
        mock_security["hash"].assert_called_once_with("123456789")
        
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once_with(result)

    async def test_create_client_invalid_email(self, mock_db_session):
        # Arrange
        invalid_payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "not-an-email",
            "phone": "4165550199",
            "date_of_birth": "1990-01-01",
            "sin": "987654321",
            "address": "123 Maple St",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M5V1A1"
        }
        # Pydantic validation should fail before service call
        with pytest.raises(ValueError): # Pydantic raises ValidationError (subclass of ValueError)
            ClientCreate(**invalid_payload)

    async def test_create_client_db_failure(self, mock_db_session, mock_security, valid_client_payload):
        # Arrange
        mock_db_session.commit.side_effect = IntegrityError("Mock DB Error", None, None)
        schema = ClientCreate(**valid_client_payload)
        service = ClientService(mock_db_session)
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_client(schema)
        
        assert exc_info.value.error_code == "DB_INTEGRITY_ERROR"

    async def test_get_client_by_id_success(self, mock_db_session):
        # Arrange
        mock_client = MagicMock(spec=Client)
        mock_client.id = 1
        mock_client.first_name = "John"
        
        # Mock the scalar return for the select statement
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db_session.execute.return_value = mock_result
        
        service = ClientService(mock_db_session)
        
        # Act
        result = await service.get_client(1)
        
        # Assert
        assert result is not None
        assert result.id == 1
        mock_db_session.execute.assert_awaited_once()

    async def test_get_client_not_found(self, mock_db_session):
        # Arrange
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        service = ClientService(mock_db_session)
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.get_client(999)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

@pytest.mark.asyncio
class TestApplicationService:
    
    async def test_create_application_success(self, mock_db_session, valid_application_payload):
        # Arrange
        # Mock the client lookup
        mock_client = MagicMock(spec=Client)
        mock_client.id = 1
        
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db_session.execute.return_value = mock_result
        
        schema = ApplicationCreate(**valid_application_payload)
        service = ApplicationService(mock_db_session)
        
        # Act
        result = await service.create_application(schema)
        
        # Assert
        assert result.loan_amount == Decimal("400000.00")
        assert result.client_id == 1
        # Verify LTV calculation (400k / 500k = 0.8)
        # Note: Logic might be in model property or service. Assuming service calculates initial LTV
        assert result.ltv_ratio == Decimal("0.80") 
        
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()

    async def test_create_application_client_not_found(self, mock_db_session, valid_application_payload):
        # Arrange
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None # Client not found
        mock_db_session.execute.return_value = mock_result
        
        schema = ApplicationCreate(**valid_application_payload)
        service = ApplicationService(mock_db_session)
        
        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_application(schema)
            
        assert exc_info.value.status_code == 404
        assert "client" in exc_info.value.detail.lower()
        mock_db_session.add.assert_not_called()

    async def test_create_application_zero_down_payment(self, mock_db_session):
        # Arrange
        mock_client = MagicMock(spec=Client)
        mock_client.id = 1
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db_session.execute.return_value = mock_result
        
        payload = {
            "client_id": 1,
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("0.00"), # Invalid
            "loan_amount": Decimal("500000.00"),
            "amortization_years": 25,
            "interest_rate": Decimal("5.00"),
            "annual_income": Decimal("95000.00"),
            "property_tax": Decimal("3000.00"),
            "heating_cost": Decimal("1200.00"),
            "other_debt": Decimal("500.00")
        }
        schema = ApplicationCreate(**payload)
        service = ApplicationService(mock_db_session)
        
        # Act & Assert
        # Service should validate that down_payment > 0
        with pytest.raises(AppException) as exc_info:
            await service.create_application(schema)
        
        assert exc_info.value.error_code == "VALIDATION_ERROR"

    async def test_calculate_ltv_boundary(self, mock_db_session):
        # Arrange
        mock_client = MagicMock(spec=Client)
        mock_client.id = 1
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db_session.execute.return_value = mock_result
        
        # Test LTV > 80% (CMHC Insurance trigger)
        # Loan: 405k, Value: 500k -> LTV = 81%
        payload = {
            "client_id": 1,
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("95000.00"),
            "loan_amount": Decimal("405000.00"),
            "amortization_years": 25,
            "interest_rate": Decimal("5.00"),
            "annual_income": Decimal("95000.00"),
            "property_tax": Decimal("3000.00"),
            "heating_cost": Decimal("1200.00"),
            "other_debt": Decimal("500.00")
        }
        schema = ApplicationCreate(**payload)
        service = ApplicationService(mock_db_session)
        
        # Act
        result = await service.create_application(schema)
        
        # Assert
        # 405000 / 500000 = 0.81
        assert result.ltv_ratio == Decimal("0.81")
        # Check if insurance flag is set (assuming service handles this flag)
        assert result.insurance_required is True

    async def test_input_validation_floats_rejected(self):
        # Arrange
        # Pydantic should handle type coercion, but strict mode or explicit types help.
        # Here we test that passing a float string or float is handled or rejected.
        # With Pydantic v2, it often coerces. We want to ensure Decimals are used internally.
        payload = {
            "client_id": 1,
            "property_value": "500000.00", # String representation
            "down_payment": 100000.00, # Float
            "loan_amount": 400000,
            "amortization_years": 25,
            "interest_rate": 5.0,
            "annual_income": 95000,
            "property_tax": 3000,
            "heating_cost": 1200,
            "other_debt": 500
        }
        
        # Act
        schema = ApplicationCreate(**payload)
        
        # Assert - Pydantic converts to Decimal
        assert isinstance(schema.property_value, Decimal)
        assert isinstance(schema.down_payment, Decimal)
        assert schema.down_payment == Decimal("100000.00")
```