```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.lender_comparison.services import (
    LenderComparisonService,
    SubmissionService,
)
from mortgage_underwriting.modules.lender_comparison.models import Lender, LenderProduct, Submission
from mortgage_underwriting.modules.lender_comparison.exceptions import (
    NoLendersFoundError,
    SubmissionAPIError,
    ComplianceError,
)

@pytest.mark.unit
class TestLenderComparisonService:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_lender_products(self):
        return [
            LenderProduct(
                id=1,
                lender_id=1,
                lender_name="Bank A",
                product_name="Prime 5yr",
                min_credit_score=700,
                max_ltv_ratio=Decimal("0.80"),
                min_income=Decimal("60000.00"),
                interest_rate=Decimal("4.99"),
                max_amortization_years=25,
                insurance_required=False,
            ),
            LenderProduct(
                id=2,
                lender_id=2,
                lender_name="Bank B",
                product_name="Flex 5yr",
                min_credit_score=650,
                max_ltv_ratio=Decimal("0.95"),
                min_income=Decimal("50000.00"),
                interest_rate=Decimal("5.25"),
                max_amortization_years=30,
                insurance_required=True,
            )
        ]

    @pytest.mark.asyncio
    async def test_find_matching_products_success(self, mock_db, mock_lender_products):
        # Arrange
        service = LenderComparisonService(mock_db)
        
        # Mock the result of executing a query to return our mock products
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_lender_products
        mock_db.execute.return_value = mock_result

        application_data = {
            "credit_score": 720,
            "loan_amount": Decimal("400000.00"),
            "property_value": Decimal("500000.00"), # 80% LTV
            "annual_income": Decimal("80000.00")
        }

        # Act
        matches = await service.find_matching_products(application_data)

        # Assert
        assert len(matches) == 2
        assert matches[0].lender_name == "Bank A"
        assert matches[1].lender_name == "Bank B"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_find_matching_products_filters_by_ltv(self, mock_db, mock_lender_products):
        # Arrange
        service = LenderComparisonService(mock_db)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_lender_products
        mock_db.execute.return_value = mock_result

        # High LTV scenario (90%)
        application_data = {
            "credit_score": 720,
            "loan_amount": Decimal("450000.00"),
            "property_value": Decimal("500000.00"),
            "annual_income": Decimal("80000.00")
        }

        # Act
        matches = await service.find_matching_products(application_data)

        # Assert - Bank A max LTV is 80%, should be filtered out
        assert len(matches) == 1
        assert matches[0].lender_name == "Bank B"

    @pytest.mark.asyncio
    async def test_find_matching_products_no_matches_raises(self, mock_db):
        # Arrange
        service = LenderComparisonService(mock_db)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [] # No products in DB
        mock_db.execute.return_value = mock_result

        application_data = {
            "credit_score": 500, # Very low score
            "loan_amount": Decimal("100.00"),
            "property_value": Decimal("1000.00"),
            "annual_income": Decimal("1000.00")
        }

        # Act & Assert
        with pytest.raises(NoLendersFoundError):
            await service.find_matching_products(application_data)

    @pytest.mark.asyncio
    async def test_calculate_ltv_boundary_check(self, mock_db):
        # Arrange
        service = LenderComparisonService(mock_db)
        
        # LTV = 80.00 (Exact boundary for 80% cap)
        ltv = service._calculate_ltv(Decimal("80000"), Decimal("100000"))
        assert ltv == Decimal("0.80")

        # LTV = 80.01 (Over boundary)
        ltv = service._calculate_ltv(Decimal("80001"), Decimal("100000"))
        assert ltv == Decimal("0.80001")


@pytest.mark.unit
class TestSubmissionService:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def submission_payload(self):
        return {
            "product_id": 1,
            "applicant_id": "app_123",
            "data": {"loan_amount": "100000"}
        }

    @pytest.mark.asyncio
    async def test_submit_to_lender_success(self, mock_db, submission_payload):
        # Arrange
        service = SubmissionService(mock_db)
        
        # Mock the external HTTP call
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_response.json.return_value = {"reference_id": "LENDER_REF_999"}
            mock_post.return_value = mock_response

            # Act
            result = await service.submit_to_lender(
                product_id=1,
                payload=submission_payload["data"],
                endpoint_url="https://api.lender.com/submit"
            )

            # Assert
            assert result.status == "SUBMITTED"
            assert result.external_reference_id == "LENDER_REF_999"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_to_lender_api_failure(self, mock_db, submission_payload):
        # Arrange
        service = SubmissionService(mock_db)
        
        with patch("httpx.AsyncClient.post") as mock_post:
            # Simulate 500 Internal Server Error from Lender
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_post.return_value = mock_response

            # Act & Assert
            with pytest.raises(SubmissionAPIError):
                await service.submit_to_lender(
                    product_id=1,
                    payload=submission_payload["data"],
                    endpoint_url="https://api.lender.com/submit"
                )
            
            # Ensure DB transaction was rolled back or not committed for failed state
            mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_validate_compliance_stress_test_enforced(self, mock_db):
        # Arrange
        service = SubmissionService(mock_db)
        
        # Scenario: Contract rate 3.0%, Stress test floor is 5.25%
        # Logic should calculate qualifying rate at 5.25%
        contract_rate = Decimal("3.00")
        qualifying_rate = service._calculate_qualifying_rate(contract_rate)
        
        # Assert
        assert qualifying_rate == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_validate_compliance_gds_limit(self, mock_db):
        # Arrange
        service = SubmissionService(mock_db)
        
        monthly_income = Decimal("5000.00")
        # Housing costs: Mortgage 2000 + Tax 300 + Heat 150 = 2450
        # GDS = 2450 / 5000 = 49% (Over 39% limit)
        housing_costs = Decimal("2450.00") 
        
        # Act & Assert
        with pytest.raises(ComplianceError) as exc_info:
            service._validate_gds(monthly_income, housing_costs)
        
        assert "GDS exceeds limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_compliance_tds_limit(self, mock_db):
        # Arrange
        service = SubmissionService(mock_db)
        
        monthly_income = Decimal("5000.00")
        # Total Debts: Housing 2000 + Other 500 = 2500
        # TDS = 2500 / 5000 = 50% (Over 44% limit)
        total_debts = Decimal("2500.00")
        
        # Act & Assert
        with pytest.raises(ComplianceError) as exc_info:
            service._validate_tds(monthly_income, total_debts)
            
        assert "TDS exceeds limit" in str(exc_info.value)
```