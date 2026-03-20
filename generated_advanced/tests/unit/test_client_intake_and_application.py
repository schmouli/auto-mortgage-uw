import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from mortgage_underwriting.modules.client_intake.services import ClientIntakeService
from mortgage_underwriting.modules.client_intake.schemas import ApplicantCreate, ApplicationCreate
from mortgage_underwriting.modules.client_intake.exceptions import DuplicateApplicantError, InvalidApplicationDataError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestClientIntakeService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return ClientIntakeService(mock_db)

    @pytest.mark.asyncio
    async def test_create_applicant_success(self, service, mock_db, valid_applicant_data, mock_encryption_service):
        """
        Test successful applicant creation ensuring PIPEDA compliance (hashing/encryption).
        """
        payload = ApplicantCreate(**valid_applicant_data)
        
        with patch("mortgage_underwriting.modules.client_intake.services.encrypt_pii", return_value="enc_sin") as mock_enc, \
             patch("mortgage_underwriting.modules.client_intake.services.hash_sin", return_value="hash_sin"):
            
            result = await service.create_applicant(payload)

            assert result.first_name == "Jane"
            assert result.last_name == "Doe"
            # Verify DB interactions
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once_with(result)
            # Verify PIPEDA: Check that encryption was called
            mock_enc.assert_called_once_with("123456782")

    @pytest.mark.asyncio
    async def test_create_applicant_duplicate_sin(self, service, mock_db, valid_applicant_data):
        """
        Test that creating a duplicate applicant (based on SIN hash) raises an error.
        """
        payload = ApplicantCreate(**valid_applicant_data)
        
        # Simulate IntegrityError from DB (Unique constraint on SIN hash)
        mock_db.commit.side_effect = IntegrityError("INSERT failed", {}, Exception())

        with pytest.raises(DuplicateApplicantError) as exc_info:
            await service.create_applicant(payload)
        
        assert "duplicate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_application_success(self, service, mock_db, valid_application_data):
        """
        Test successful application creation.
        """
        # Adjust payload to have a valid applicant_id reference context
        payload = ApplicationCreate(**valid_application_data)
        
        # Mock the applicant existence check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        result = await service.create_application(payload)

        assert result.loan_amount == Decimal("450000.00")
        assert result.annual_income == Decimal("120000.00")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_application_applicant_not_found(self, service, mock_db, valid_application_data):
        """
        Test that creating an application for a non-existent applicant raises an error.
        """
        payload = ApplicationCreate(**valid_application_data)
        
        # Mock applicant not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(InvalidApplicationDataError) as exc_info:
            await service.create_application(payload)
        
        assert "applicant" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_financials_negative_income(self, service, mock_db):
        """
        Test validation logic: Income cannot be negative.
        """
        invalid_data = {
            "applicant_id": 1,
            "loan_amount": "100000.00",
            "property_value": "200000.00",
            "down_payment": "100000.00",
            "amortization_years": 20,
            "interest_rate": "4.0",
            "annual_income": "-5000.00", # Invalid
            "property_tax": "2000.00",
            "heating_cost": "100.00",
            "other_debt": "0.00"
        }
        payload = ApplicationCreate(**invalid_data)
        
        with pytest.raises(InvalidApplicationDataError):
            await service.create_application(payload)

    @pytest.mark.asyncio
    async def test_validate_ltv_calculation(self, service, mock_db):
        """
        Test that LTV is calculated correctly during application creation.
        Loan 450k / Value 600k = 75%
        """
        payload = ApplicationCreate(**valid_application_data)
        
        # Mock applicant existence
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id=1)
        mock_db.execute.return_value = mock_result

        result = await service.create_application(payload)

        # LTV = 450000 / 600000 = 0.75
        # Note: This assumes the model calculates it or the service does. 
        # Based on requirements, service logic handles this.
        expected_ltv = (Decimal("450000.00") / Decimal("600000.00")) * Decimal("100")
        assert result.ltv_ratio == expected_ltv

    @pytest.mark.asyncio
    async def test_get_applicant_by_id_success(self, service, mock_db):
        """
        Test retrieving an applicant by ID.
        """
        mock_applicant = MagicMock(id=1, first_name="John")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_applicant
        mock_db.execute.return_value = mock_result

        result = await service.get_applicant(1)

        assert result.first_name == "John"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_applicant_not_found(self, service, mock_db):
        """
        Test retrieving a non-existent applicant returns None.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.get_applicant(999)

        assert result is None

# Helper dictionary for valid_application_data in tests
valid_application_data = {
    "applicant_id": 1,
    "loan_amount": "450000.00",
    "property_value": "600000.00",
    "down_payment": "150000.00",
    "amortization_years": 25,
    "interest_rate": "5.00",
    "annual_income": "120000.00",
    "property_tax": "3000.00",
    "heating_cost": "1200.00",
    "other_debt": "500.00"
}