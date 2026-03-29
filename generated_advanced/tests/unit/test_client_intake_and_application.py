```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientIntakeService
from mortgage_underwriting.modules.client_intake.models import Application
from mortgage_underwriting.modules.client_intake.schemas import ApplicationCreate
from mortgage_underwriting.common.exceptions import AppException

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

@pytest.mark.asyncio
class TestClientIntakeService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def valid_payload_dict(self):
        return {
            "borrower_first_name": "Test",
            "borrower_last_name": "User",
            "borrower_email": "test@example.com",
            "borrower_sin": "123456789",
            "borrower_dob": "1990-01-01",
            "property_address": "1 Test St",
            "property_value": Decimal("500000.00"),
            "down_payment": Decimal("100000.00"),
            "loan_amount": Decimal("400000.00"),
            "income_annual": Decimal("80000.00"),
            "employment_status": "employed",
            "credit_score": 720
        }

    @pytest.fixture
    def application_create_schema(self, valid_payload_dict):
        return ApplicationCreate(**valid_payload_dict)

    async def test_create_application_success(self, mock_db, application_create_schema):
        """Test successful creation of an application."""
        # Mock the return value of refresh
        mock_app_instance = Application(id=1, status="DRAFT")
        mock_db.refresh.return_value = None
        mock_db.add.side_effect = lambda x: setattr(x, 'id', 1) # Simulate ID assignment

        service = ClientIntakeService(mock_db)
        
        result = await service.create_application(application_create_schema)

        # Verify DB interactions
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        
        # Verify result
        assert result is not None
        assert result.borrower_first_name == "Test"
        assert result.status == "DRAFT"

    @patch('mortgage_underwriting.modules.client_intake.services.encrypt_pii')
    @patch('mortgage_underwriting.modules.client_intake.services.hash_value')
    async def test_create_application_sanitizes_pii(self, mock_hash, mock_encrypt, mock_db, application_create_schema):
        """Test that PII (SIN, DOB) is processed by security functions."""
        mock_hash.return_value = "hashed_sin_123"
        mock_encrypt.return_value = "encrypted_dob_456"
        
        service = ClientIntakeService(mock_db)
        await service.create_application(application_create_schema)

        # Verify security helpers were called
        mock_hash.assert_called_once_with("123456789")
        mock_encrypt.assert_called_once_with("1990-01-01")

    async def test_create_application_missing_sin_raises_validation_error(self, mock_db):
        """Test that missing SIN raises a validation error."""
        invalid_payload = {
            "borrower_first_name": "No",
            "borrower_last_name": "Sin",
            "borrower_email": "nosin@example.com",
            "property_address": "1 No Sin St",
            "property_value": Decimal("100000.00"),
            "down_payment": Decimal("20000.00"),
            "loan_amount": Decimal("80000.00"),
            "income_annual": Decimal("50000.00"),
            "employment_status": "employed",
            "credit_score": 700
        }
        
        # Pydantic validation should fail before service logic
        with pytest.raises(ValueError): # Or Pydantic ValidationError
            ApplicationCreate(**invalid_payload)

    async def test_create_application_negative_income_raises_error(self, mock_db):
        """Test that negative income is rejected."""
        invalid_payload = {
            "borrower_first_name": "Poor",
            "borrower_last_name": "User",
            "borrower_email": "poor@example.com",
            "borrower_sin": "111111111",
            "borrower_dob": "2000-01-01",
            "property_address": "2 Poor St",
            "property_value": Decimal("100000.00"),
            "down_payment": Decimal("20000.00"),
            "loan_amount": Decimal("80000.00"),
            "income_annual": Decimal("-5000.00"), # Invalid
            "employment_status": "employed",
            "credit_score": 600
        }

        with pytest.raises(ValueError):
             ApplicationCreate(**invalid_payload)

    async def test_get_application_by_id_success(self, mock_db):
        """Test retrieving an application by ID."""
        # Mock the result
        mock_app = Application(
            id=1, 
            borrower_first_name="Get", 
            borrower_last_name="Me",
            status="DRAFT"
        )
        
        # Setup mock execute result
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = mock_app
        mock_db.execute.return_value = result_mock

        service = ClientIntakeService(mock_db)
        result = await service.get_application_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.borrower_first_name == "Get"

    async def test_get_application_by_id_not_found(self, mock_db):
        """Test retrieving a non-existent application returns None."""
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        service = ClientIntakeService(mock_db)
        result = await service.get_application_by_id(999)

        assert result is None

    async def test_update_application_status_success(self, mock_db):
        """Test updating application status (e.g., Draft -> Submitted)."""
        mock_app = Application(id=1, status="DRAFT")
        
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = mock_app
        mock_db.execute.return_value = result_mock

        service = ClientIntakeService(mock_db)
        updated_app = await service.update_application_status(1, "SUBMITTED")

        assert updated_app.status == "SUBMITTED"
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    async def test_update_application_status_invalid_transition(self, mock_db):
        """Test that invalid status transitions are handled."""
        # Start with APPROVED (final state)
        mock_app = Application(id=1, status="APPROVED")
        
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = mock_app
        mock_db.execute.return_value = result_mock

        service = ClientIntakeService(mock_db)
        
        with pytest.raises(AppException) as exc_info:
            await service.update_application_status(1, "DRAFT")
        
        assert "Invalid status transition" in str(exc_info.value.detail)

    async def test_calculate_ltv_boundary_checks(self, mock_db):
        """Test LTV calculation logic within service if applicable (or helper)."""
        # Assuming service has a helper or logic to check LTV during creation
        payload = {
            "borrower_first_name": "LTV",
            "borrower_last_name": "Check",
            "borrower_email": "ltv@example.com",
            "borrower_sin": "555555555",
            "borrower_dob": "1985-05-05",
            "property_address": "3 LTV Ln",
            "property_value": Decimal("100000.00"),
            "down_payment": Decimal("5000.00"), # 95% LTV
            "loan_amount": Decimal("95000.00"),
            "income_annual": Decimal("100000.00"),
            "employment_status": "employed",
            "credit_score": 800
        }
        
        schema = ApplicationCreate(**payload)
        
        # If service validates max LTV (e.g., 95%)
        # This test assumes validation logic exists in service
        service = ClientIntakeService(mock_db)
        
        # Expect success at boundary
        mock_db.add.side_effect = lambda x: setattr(x, 'id', 1)
        result = await service.create_application(schema)
        assert result is not None

    async def test_high_risk_ltv_rejection(self, mock_db):
        """Test rejection of LTV > 95%."""
        payload = {
            "borrower_first_name": "High",
            "borrower_last_name": "Risk",
            "borrower_email": "high@example.com",
            "borrower_sin": "666666666",
            "borrower_dob": "1990-10-10",
            "property_address": "4 Risk Rd",
            "property_value": Decimal("100000.00"),
            "down_payment": Decimal("4000.00"), # 96% LTV
            "loan_amount": Decimal("96000.00"),
            "income_annual": Decimal("100000.00"),
            "employment_status": "employed",
            "credit_score": 800
        }
        
        schema = ApplicationCreate(**payload)
        service = ClientIntakeService(mock_db)
        
        with pytest.raises(AppException) as exc_info:
            await service.create_application(schema)
        
        assert "LTV exceeds maximum" in str(exc_info.value.detail)

    async def test_database_integrity_error_handling(self, mock_db, application_create_schema):
        """Test handling of DB integrity errors (e.g., duplicate SIN)."""
        # Simulate IntegrityError from DB
        mock_db.commit.side_effect = IntegrityError("INSERT INTO application", {}, Exception())
        
        service = ClientIntakeService(mock_db)
        
        with pytest.raises(AppException) as exc_info:
            await service.create_application(application_create_schema)
        
        assert exc_info.value.status_code == 409 # Conflict
        mock_db.rollback.assert_awaited_once()
```