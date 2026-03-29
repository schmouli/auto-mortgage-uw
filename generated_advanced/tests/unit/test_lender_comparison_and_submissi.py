```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct, Submission, SubmissionStatus
from mortgage_underwriting.modules.lender_comparison.services import ComparisonService, SubmissionService
from mortgage_underwriting.modules.lender_comparison.exceptions import LenderUnavailableError, SubmissionFailedError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestComparisonService:
    
    @pytest.mark.asyncio
    async def test_compare_products_success(self, db_session, sample_lender_data, sample_product_data, sample_comparison_request):
        # Arrange
        lender = Lender(**sample_lender_data)
        db_session.add(lender)
        await db_session.flush()
        
        # Create two products
        prod1 = LenderProduct(**sample_product_data, lender_id=lender.id, rate=Decimal("5.00"))
        prod2 = LenderProduct(**sample_product_data, lender_id=lender.id, rate=Decimal("4.50"), product_name="Best Rate")
        db_session.add_all([prod1, prod2])
        await db_session.commit()
        
        service = ComparisonService(db_session)
        
        # Act
        results = await service.compare(sample_comparison_request)
        
        # Assert
        assert len(results) == 2
        # Results should be sorted by rate (ascending)
        assert results[0].rate == Decimal("4.50")
        assert results[1].rate == Decimal("5.00")
        assert results[0].monthly_payment > Decimal("0.00")

    @pytest.mark.asyncio
    async def test_compare_filters_by_ltv(self, db_session, sample_lender_data, sample_product_data):
        # Arrange
        lender = Lender(**sample_lender_data)
        db_session.add(lender)
        await db_session.flush()
        
        # Product with low max LTV
        low_ltv_prod = LenderProduct(**sample_product_data, lender_id=lender.id, max_ltv=Decimal("70.00"))
        db_session.add(low_ltv_prod)
        await db_session.commit()
        
        service = ComparisonService(db_session)
        
        # Request with 80% LTV (Loan 400k / Value 500k)
        request = MagicMock(
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00"),
            credit_score=750,
            province="BC",
            amortization_years=25
        )
        
        # Act
        results = await service.compare(request)
        
        # Assert
        assert len(results) == 0 # Should be filtered out because 80% > 70%

    @pytest.mark.asyncio
    async def test_compare_no_products_found(self, db_session):
        service = ComparisonService(db_session)
        request = MagicMock(
            loan_amount=Decimal("100000.00"),
            property_value=Decimal("200000.00"),
            credit_score=800,
            province="ON",
            amortization_years=20
        )
        
        results = await service.compare(request)
        assert results == []

    @pytest.mark.asyncio
    async def test_calculate_monthly_payment_accuracy(self):
        # M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        # P=100k, i=0.05/12, n=300 (25y)
        # Expected approx: 584.59
        principal = Decimal("100000.00")
        annual_rate = Decimal("0.05")
        months = 300
        
        payment = ComparisonService._calculate_payment(principal, annual_rate, months)
        
        # Using a rough delta for decimal comparison
        assert abs(payment - Decimal("584.59")) < Decimal("0.01")

@pytest.mark.unit
class TestSubmissionService:

    @pytest.mark.asyncio
    async def test_submit_to_lender_success(self, db_session, sample_lender_data, mock_http_client):
        # Arrange
        lender = Lender(**sample_lender_data)
        db_session.add(lender)
        await db_session.flush()
        
        product = LenderProduct(
            lender_id=lender.id,
            product_name="Fixed 5yr",
            rate=Decimal("4.5"),
            term_months=60,
            max_ltv=Decimal("80.00"),
            min_credit_score=600,
            insurance_required=False
        )
        db_session.add(product)
        await db_session.commit()
        
        submission_data = MagicMock(
            product_id=product.id,
            application_id="APP-999",
            borrower_json={"name": "John Doe"}
        )
        
        service = SubmissionService(db_session)
        
        # Act
        result = await service.submit(submission_data)
        
        # Assert
        assert result.status == SubmissionStatus.SUBMITTED
        assert result.external_reference_id == "EXT-12345"
        
        # Verify DB record
        await db_session.refresh(result)
        assert result.created_at is not None
        
        # Verify external call was made
        mock_http_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_to_lender_network_error(self, db_session, sample_lender_data):
        # Arrange
        lender = Lender(**sample_lender_data)
        db_session.add(lender)
        await db_session.flush()
        
        product = LenderProduct(
            lender_id=lender.id,
            product_name="Fixed 5yr",
            rate=Decimal("4.5"),
            term_months=60,
            max_ltv=Decimal("80.00"),
            min_credit_score=600,
            insurance_required=False
        )
        db_session.add(product)
        await db_session.commit()
        
        submission_data = MagicMock(
            product_id=product.id,
            application_id="APP-999",
            borrower_json={"name": "John Doe"}
        )
        
        # Mock httpx to raise an exception
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(side_effect=Exception("Network Down"))
            MockClient.return_value = mock_instance
            
            service = SubmissionService(db_session)
            
            # Act & Assert
            with pytest.raises(SubmissionFailedError):
                await service.submit(submission_data)
            
            # Verify status in DB is FAILED
            stmt = select(Submission).where(Submission.application_id == "APP-999")
            res = await db_session.execute(stmt)
            record = res.scalar_one()
            assert record.status == SubmissionStatus.FAILED

    @pytest.mark.asyncio
    async def test_submit_product_not_found(self, db_session):
        service = SubmissionService(db_session)
        submission_data = MagicMock(
            product_id=9999, # Non-existent
            application_id="APP-000",
            borrower_json={}
        )
        
        with pytest.raises(AppException):
            await service.submit(submission_data)
```