import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.modules.orchestrator.services import OrchestratorService
from mortgage_underwriting.modules.orchestrator.schemas import ApplicationCreate, ApplicationResponse
from mortgage_underwriting.modules.orchestrator.exceptions import UnderwritingError
from mortgage_underwriting.common.exceptions import AppException


@pytest.mark.unit
class TestOrchestratorService:
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return OrchestratorService(mock_db)

    @pytest.fixture
    def valid_payload(self):
        return ApplicationCreate(
            borrower_id=1,
            property_id=1,
            loan_amount=Decimal("400000.00"),
            contract_rate=Decimal("4.50"),
            amortization_years=25
        )

    @pytest.mark.asyncio
    async def test_create_application_success(self, service, mock_db, valid_payload):
        """Test successful creation of an application record."""
        # Mock the return value of refresh to simulate DB assignment
        mock_app = MagicMock()
        mock_app.id = 123
        mock_app.status = "PENDING"
        
        # We can't easily mock the model instantiation inside the service without patching
        # So we verify the interaction flow
        
        result = await service.create_application(valid_payload)
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calculate_gds_within_limit(self, service):
        """Test GDS calculation (Principal + Interest + Tax + Heat) / Income."""
        monthly_payment = Decimal("2200.00")
        property_tax = Decimal("300.00")
        heating = Decimal("100.00")
        monthly_income = Decimal("8000.00")
        
        # (2200 + 300 + 100) / 8000 = 2600 / 8000 = 0.325 (32.5%)
        gds = service._calculate_gds(monthly_payment, property_tax, heating, monthly_income)
        
        assert gds == Decimal("0.325")
        assert gds <= Decimal("0.39")

    @pytest.mark.asyncio
    async def test_calculate_gds_exceeds_limit(self, service):
        """Test GDS calculation exceeding OSFI B-20 limit of 39%."""
        monthly_payment = Decimal("3500.00")
        property_tax = Decimal("400.00")
        heating = Decimal("150.00")
        monthly_income = Decimal("8000.00")
        
        # (3500 + 400 + 150) / 8000 = 4050 / 8000 = 0.50625 (50.6%)
        gds = service._calculate_gds(monthly_payment, property_tax, heating, monthly_income)
        
        assert gds == Decimal("0.50625")
        assert gds > Decimal("0.39")

    @pytest.mark.asyncio
    async def test_calculate_tds_within_limit(self, service):
        """Test TDS calculation (GDS + Other Debts) / Income."""
        housing_costs = Decimal("2600.00")
        other_debts = Decimal("500.00")
        monthly_income = Decimal("8000.00")
        
        # (2600 + 500) / 8000 = 3100 / 8000 = 0.3875 (38.75%)
        tds = service._calculate_tds(housing_costs, other_debts, monthly_income)
        
        assert tds == Decimal("0.3875")
        assert tds <= Decimal("0.44")

    @pytest.mark.asyncio
    async def test_calculate_ltv_insurance_required(self, service):
        """Test CMHC Insurance Logic: LTV > 80% requires insurance."""
        loan_amount = Decimal("400000.00")
        property_value = Decimal("500000.00")
        
        ltv, insurance_required, premium_rate = service._calculate_ltv(loan_amount, property_value)
        
        assert ltv == Decimal("0.80") # Exactly 80%
        assert insurance_required is False # Usually 80% is the boundary, > 80 is required. Assuming strict > for this test logic.
        
        # Test > 80%
        ltv_high, ins_req_high, _ = service._calculate_ltv(Decimal("405000.00"), Decimal("500000.00"))
        assert ltv_high == Decimal("0.81")
        assert ins_req_high is True

    @pytest.mark.asyncio
    async def test_stress_test_qualifying_rate(self, service):
        """Test OSFI B-20 Stress Test: max(contract + 2%, 5.25%)."""
        contract_rate = Decimal("4.00")
        
        # Contract + 2% = 6.00%. Min(6.00, 5.25) = 6.00%
        qualifying_rate = service._get_qualifying_rate(contract_rate)
        assert qualifying_rate == Decimal("6.00")
        
        # Contract + 2% = 4.50%. Min(4.50, 5.25) = 5.25%
        low_contract_rate = Decimal("2.50")
        qualifying_rate_low = service._get_qualifying_rate(low_contract_rate)
        assert qualifying_rate_low == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_evaluate_application_approval(self, service, mock_db, valid_payload):
        """Test happy path: All ratios pass, application approved."""
        # Mock dependencies that the orchestrator would call
        with patch.object(service, '_get_borrower', new_callable=AsyncMock) as mock_borrower, \
             patch.object(service, '_get_property', new_callable=AsyncMock) as mock_prop:
            
            # Setup Mock Data
            mock_borrower_obj = MagicMock()
            mock_borrower_obj.annual_income = Decimal("96000.00") # 8000/mo
            mock_borrower_obj.monthly_debt = Decimal("500.00")
            
            mock_prop_obj = MagicMock()
            mock_prop_obj.purchase_price = Decimal("500000.00")
            mock_prop_obj.estimated_heating = Decimal("100.00")
            mock_prop_obj.estimated_tax = Decimal("300.00")
            
            mock_borrower.return_value = mock_borrower_obj
            mock_prop.return_value = mock_prop_obj
            
            # Execute
            result = await service.evaluate_application(1, valid_payload)
            
            # Assertions
            assert result.decision == "APPROVED"
            assert result.gds <= Decimal("0.39")
            assert result.tds <= Decimal("0.44")
            assert "stress_test_rate" in result.meta_data

    @pytest.mark.asyncio
    async def test_evaluate_application_rejection_tds(self, service, mock_db, valid_payload):
        """Test rejection path: TDS exceeds 44%."""
        with patch.object(service, '_get_borrower', new_callable=AsyncMock) as mock_borrower, \
             patch.object(service, '_get_property', new_callable=AsyncMock) as mock_prop:
            
            # High Debt Scenario
            mock_borrower_obj = MagicMock()
            mock_borrower_obj.annual_income = Decimal("60000.00") # 5000/mo
            mock_borrower_obj.monthly_debt = Decimal("2000.00") # Car loans, credit cards
            
            mock_prop_obj = MagicMock()
            mock_prop_obj.purchase_price = Decimal("500000.00")
            mock_prop_obj.estimated_heating = Decimal("100.00")
            mock_prop_obj.estimated_tax = Decimal("300.00")
            
            mock_borrower.return_value = mock_borrower_obj
            mock_prop.return_value = mock_prop_obj
            
            # Execute
            result = await service.evaluate_application(1, valid_payload)
            
            # Assertions
            assert result.decision == "REFUSED"
            assert "TDS" in result.rejection_reason

    @pytest.mark.asyncio
    async def test_evaluate_application_insurance_premium_calculation(self, service, mock_db, valid_payload):
        """Test CMHC Premium Tier Calculation: 80.01-85% = 2.80%."""
        # Adjust payload for high LTV
        valid_payload.loan_amount = Decimal("425000.00") # 85% LTV
        
        with patch.object(service, '_get_borrower', new_callable=AsyncMock) as mock_borrower, \
             patch.object(service, '_get_property', new_callable=AsyncMock) as mock_prop:
            
            mock_borrower_obj = MagicMock()
            mock_borrower_obj.annual_income = Decimal("200000.00") # High income to pass ratios
            mock_borrower_obj.monthly_debt = Decimal("0.00")
            
            mock_prop_obj = MagicMock()
            mock_prop_obj.purchase_price = Decimal("500000.00")
            mock_prop_obj.estimated_heating = Decimal("100.00")
            mock_prop_obj.estimated_tax = Decimal("300.00")
            
            mock_borrower.return_value = mock_borrower_obj
            mock_prop.return_value = mock_prop_obj
            
            result = await service.evaluate_application(1, valid_payload)
            
            # 425k / 500k = 0.85 -> 2.80% tier
            assert result.insurance_required is True
            assert result.insurance_premium_rate == Decimal("0.0280")

    @pytest.mark.asyncio
    async def test_get_application_not_found(self, service, mock_db):
        """Test retrieving a non-existent application raises error."""
        # Mock execute to return None (empty result)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(AppException) as exc_info:
            await service.get_application(999)
        
        assert exc_info.value.status_code == 404