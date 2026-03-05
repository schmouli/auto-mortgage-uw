```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Module Imports
from mortgage_underwriting.modules.lender_comparison.services import LenderComparisonService, SubmissionService
from mortgage_underwriting.modules.lender_comparison.exceptions import LenderNotFoundException, SubmissionValidationError
from mortgage_underwriting.modules.lender_comparison.schemas import LenderProductResponse, SubmissionResponse

# Mock Models
from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct, Submission

@pytest.mark.unit
class TestLenderComparisonService:
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_products(self):
        return [
            LenderProduct(
                id=1,
                lender_id=1,
                product_name="Prime 5yr",
                rate=Decimal("0.0499"),
                max_ltv=Decimal("80.00"),
                min_credit_score=680,
                insurance_required=False
            ),
            LenderProduct(
                id=2,
                lender_id=1,
                product_name="High Ratio",
                rate=Decimal("0.0520"),
                max_ltv=Decimal("95.00"),
                min_credit_score=650,
                insurance_required=True
            )
        ]

    @pytest.mark.asyncio
    async def test_compare_lenders_filters_by_ltv(self, mock_db, mock_products):
        # Setup Mock Result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_products
        mock_db.execute.return_value = mock_result

        service = LenderComparisonService(mock_db)
        
        # Request: 90% LTV
        result = await service.compare_lenders(
            loan_amount=Decimal("450000"),
            property_value=Decimal("500000"),
            credit_score=700,
            province="ON"
        )

        # Assertions
        assert len(result) == 2 # Both valid for 90% LTV
        # Verify the mock was called with correct filtering logic (conceptually)
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_compare_lenders_excludes_high_ltv_products(self, mock_db, mock_products):
        # Setup Mock Result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_products
        mock_db.execute.return_value = mock_result

        service = LenderComparisonService(mock_db)
        
        # Request: 85% LTV
        result = await service.compare_lenders(
            loan_amount=Decimal("425000"),
            property_value=Decimal("500000"),
            credit_score=700,
            province="ON"
        )

        # Assertions
        assert len(result) == 1
        assert result[0].max_ltv >= Decimal("85.00")

    @pytest.mark.asyncio
    async def test_compare_lenders_calculates_monthly_payment(self, mock_db):
        # Mock single product
        mock_product = LenderProduct(
            id=1,
            lender_id=1,
            product_name="Fixed",
            rate=Decimal("0.0500"), # 5%
            max_ltv=Decimal("80.00"),
            min_credit_score=600,
            insurance_required=False
        )
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_product]
        mock_db.execute.return_value = mock_result

        service = LenderComparisonService(mock_db)
        
        # 100k loan, 5% annual, 25 years (300 months)
        # M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # i = 0.05/12 = 0.00416666
        # n = 300
        # Expected approx 584.59
        result = await service.compare_lenders(
            loan_amount=Decimal("100000"),
            property_value=Decimal("125000"),
            credit_score=650,
            province="BC"
        )

        assert len(result) == 1
        # Check calculation exists and is Decimal
        assert result[0].estimated_monthly_payment is not None
        assert isinstance(result[0].estimated_monthly_payment, Decimal)
        # Rough check: 584.59
        assert result[0].estimated_monthly_payment > Decimal("580.00")
        assert result[0].estimated_monthly_payment < Decimal("590.00")

    @pytest.mark.asyncio
    async def test_compare_lenders_includes_insurance_premium(self, mock_db):
        # Mock product requiring insurance (CMHC)
        # LTV 90% -> Premium 3.10% (CMHC Rule)
        # Loan 100k. Premium 3100. Total loan 103100.
        mock_product = LenderProduct(
            id=1,
            lender_id=1,
            product_name="Insured",
            rate=Decimal("0.0500"),
            max_ltv=Decimal("95.00"),
            min_credit_score=600,
            insurance_required=True
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_product]
        mock_db.execute.return_value = mock_result

        service = LenderComparisonService(mock_db)
        
        # 90k loan, 100k value -> 90% LTV
        result = await service.compare_lenders(
            loan_amount=Decimal("90000"),
            property_value=Decimal("100000"),
            credit_score=650,
            province="ON"
        )
        
        assert len(result) == 1
        # Payment should be higher than non-insured 90k loan due to premium capitalization
        # Payment for 90k @ 5% is ~526. 
        # With 3.1% premium (2790), loan is 92790. Payment ~542.
        assert result[0].estimated_monthly_payment > Decimal("540.00")

    @pytest.mark.asyncio
    async def test_compare_lenders_no_results(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = LenderComparisonService(mock_db)
        
        result = await service.compare_lenders(
            loan_amount=Decimal("500000"),
            property_value=Decimal("500000"), # 100% LTV
            credit_score=800,
            province="ON"
        )

        assert len(result) == 0

@pytest.mark.unit
class TestSubmissionService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_lender_repo(self):
        with patch('mortgage_underwriting.modules.lender_comparison.services.LenderRepository') as repo:
            yield repo

    @pytest.mark.asyncio
    async def test_submit_application_success(self, mock_db, mock_lender_repo):
        # Setup mocks
        mock_lender = MagicMock()
        mock_lender.id = 1
        mock_lender.name = "Big Bank"
        mock_lender.api_endpoint = "https://bigbank.com/api"
        
        mock_lender_repo.return_value.get_by_id.return_value = mock_lender

        service = SubmissionService(mock_db)
        app_id = uuid4()
        
        # Mock external API call
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"reference": "EXT-123"}

            result = await service.submit_application(
                application_id=str(app_id),
                lender_id=1,
                user_id="user_123"
            )

            # Assertions
            assert isinstance(result, SubmissionResponse)
            assert result.status == "SUBMITTED"
            assert result.lender_name == "Big Bank"
            
            # FINTRAC: Verify audit fields
            mock_db.add.assert_called_once()
            added_obj = mock_db.add.call_args[0][0]
            assert isinstance(added_obj, Submission)
            assert added_obj.created_by == "user_123"
            assert added_obj.application_id == str(app_id)
            
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_application_lender_not_found(self, mock_db, mock_lender_repo):
        mock_lender_repo.return_value.get_by_id.return_value = None
        
        service = SubmissionService(mock_db)
        
        with pytest.raises(LenderNotFoundException) as exc_info:
            await service.submit_application(
                application_id=str(uuid4()),
                lender_id=999,
                user_id="user_123"
            )
        
        assert "Lender 999 not found" in str(exc_info.value)
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_submit_application_external_api_failure(self, mock_db, mock_lender_repo):
        mock_lender = MagicMock()
        mock_lender.id = 1
        mock_lender.name = "Bad Bank"
        mock_lender.api_endpoint = "https://badbank.com/api"
        mock_lender_repo.return_value.get_by_id.return_value = mock_lender

        service = SubmissionService(mock_db)

        with patch('httpx.AsyncClient.post') as mock_post:
            # Simulate 500 Internal Server Error
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = "Internal Error"

            with pytest.raises(SubmissionValidationError) as exc_info:
                await service.submit_application(
                    application_id=str(uuid4()),
                    lender_id=1,
                    user_id="user_123"
                )
            
            assert "Failed to submit" in str(exc_info.value)
            # Verify DB transaction was not committed for failed submission
            mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_submit_application_sanitizes_pii(self, mock_db, mock_lender_repo):
        # PIPEDA Check: Ensure SIN is not sent to external lender if payload contains it
        mock_lender = MagicMock()
        mock_lender.id = 1
        mock_lender.name = "Secure Bank"
        mock_lender.api_endpoint = "https://secure.com/api"
        mock_lender_repo.return_value.get_by_id.return_value = mock_lender

        service = SubmissionService(mock_db)

        with patch('mortgage_underwriting.modules.lender_comparison.services.get_application_details') as get_app:
            # Mock app details containing PII
            get_app.return_value = {
                "id": str(uuid4()),
                "sin": "123-456-789", # SENSITIVE
                "income": "100000",
                "first_name": "John",
                "last_name": "Doe"
            }

            with patch('httpx.AsyncClient.post') as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {"ref": "123"}

                await service.submit_application(
                    application_id=str(uuid4()),
                    lender_id=1,
                    user_id="user_123"
                )

                # Check the payload sent to external API
                call_args = mock_post.call_args
                sent_data = call_args.kwargs.get('json') or call_args[1].get('json')
                
                # Assert SIN is NOT in the payload
                assert "sin" not in sent_data
                assert "123-456-789" not in str(sent_data)
                # Assert normal fields are present
                assert sent_data["first_name"] == "John"
```