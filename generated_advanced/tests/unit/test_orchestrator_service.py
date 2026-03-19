import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, call
from mortgage_underwriting.modules.orchestrator.services import OrchestratorService
from mortgage_underwriting.modules.orchestrator.exceptions import UnderwritingError
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestOrchestratorService:

    @pytest.mark.asyncio
    async def test_process_application_success_approved(self, mock_db_session, mock_borrower_service, mock_property_service):
        """
        Test successful underwriting where GDS/TDS are within limits.
        Loan: 450k, Rate: 4.5%, Income: 120k.
        Qualifying Rate: max(4.5 + 2, 5.25) = 6.5%.
        Monthly Payment (approx 25y @ 6.5): ~3050.
        Property Tax (est): 3500/yr -> ~291/mo.
        Heating (est): 150/mo.
        Total Housing: 3050 + 291 + 150 = 3491.
        GDS = (3491 * 12) / 120000 = 34.9% (Pass < 39%)
        TDS = ((3491 + 500) * 12) / 120000 = 39.9% (Pass < 44%)
        """
        payload = {
            "borrower_id": "bor-1",
            "property_id": "prop-1",
            "loan_amount": Decimal("450000.00"),
            "contract_rate": Decimal("4.50"),
            "amortization_years": 25,
            "down_payment": Decimal("90000.00")
        }

        # Mock calculation logic helper inside service or verify logic flow
        with patch('mortgage_underwriting.modules.orchestrator.services.BorrowerService', return_value=mock_borrower_service), \
             patch('mortgage_underwriting.modules.orchestrator.services.PropertyService', return_value=mock_property_service):
            
            service = OrchestratorService(mock_db_session)
            result = await service.process_application(payload)

            assert result["decision"] == "Approved"
            assert result["gds_ratio"] <= Decimal("0.39")
            assert result["tds_ratio"] <= Decimal("0.44")
            assert "qualifying_rate" in result

    @pytest.mark.asyncio
    async def test_process_application_decline_high_gds(self, mock_db_session, mock_borrower_service, mock_property_service):
        """
        Test OSFI B-20 compliance: GDS limit 39%.
        Scenario: Low income relative to housing costs.
        """
        # Override borrower to have low income
        mock_borrower_service.get_borrower_summary.return_value = {
            "annual_income": Decimal("50000.00"),
            "monthly_debts": Decimal("0.00"),
            "credit_score": 800
        }

        payload = {
            "borrower_id": "bor-2",
            "property_id": "prop-2",
            "loan_amount": Decimal("400000.00"),
            "contract_rate": Decimal("5.00"),
            "amortization_years": 25,
            "down_payment": Decimal("80000.00")
        }

        with patch('mortgage_underwriting.modules.orchestrator.services.BorrowerService', return_value=mock_borrower_service), \
             patch('mortgage_underwriting.modules.orchestrator.services.PropertyService', return_value=mock_property_service):
            
            service = OrchestratorService(mock_db_session)
            result = await service.process_application(payload)

            assert result["decision"] == "Declined"
            assert "GDS" in result["reasons"]

    @pytest.mark.asyncio
    async def test_process_application_decline_high_tds(self, mock_db_session, mock_borrower_service, mock_property_service):
        """
        Test OSFI B-20 compliance: TDS limit 44%.
        Scenario: High external debt.
        """
        # Override borrower to have massive external debt
        mock_borrower_service.get_borrower_summary.return_value = {
            "annual_income": Decimal("100000.00"),
            "monthly_debts": Decimal("4000.00"), # High debt
            "credit_score": 700
        }

        payload = {
            "borrower_id": "bor-3",
            "property_id": "prop-3",
            "loan_amount": Decimal("300000.00"),
            "contract_rate": Decimal("3.00"),
            "amortization_years": 25,
            "down_payment": Decimal("60000.00")
        }

        with patch('mortgage_underwriting.modules.orchestrator.services.BorrowerService', return_value=mock_borrower_service), \
             patch('mortgage_underwriting.modules.orchestrator.services.PropertyService', return_value=mock_property_service):
            
            service = OrchestratorService(mock_db_session)
            result = await service.process_application(payload)

            assert result["decision"] == "Declined"
            assert "TDS" in result["reasons"]

    @pytest.mark.asyncio
    async def test_calculate_qualifying_rate_stress_test(self):
        """
        Test OSFI B-20 Stress Test logic:
        Qualifying Rate = max(contract_rate + 2%, 5.25%)
        """
        service = OrchestratorService(AsyncMock())

        # Case 1: Contract rate is low (e.g., 3.0). 3.0 + 2 = 5.0. Floor is 5.25.
        rate_1 = service._calculate_qualifying_rate(Decimal("3.00"))
        assert rate_1 == Decimal("5.25")

        # Case 2: Contract rate is high (e.g., 5.0). 5.0 + 2 = 7.0. Max is 7.0.
        rate_2 = service._calculate_qualifying_rate(Decimal("5.00"))
        assert rate_2 == Decimal("7.00")

        # Case 3: Boundary (3.25). 3.25 + 2 = 5.25. Max is 5.25.
        rate_3 = service._calculate_qualifying_rate(Decimal("3.25"))
        assert rate_3 == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_insurance_required_cmhc_logic(self, mock_db_session):
        """
        Test CMHC logic: LTV > 80% requires insurance.
        LTV = Loan / Property Value
        """
        # Loan 400k, Value 500k -> LTV 80% -> No insurance
        assert not OrchestratorService._check_insurance_required(Decimal("400000"), Decimal("500000"))
        
        # Loan 400001, Value 500k -> LTV > 80% -> Insurance
        assert OrchestratorService._check_insurance_required(Decimal("400001"), Decimal("500000"))

        # Loan 475k, Value 500k -> LTV 95% -> Insurance
        assert OrchestratorService._check_insurance_required(Decimal("475000"), Decimal("500000"))

    @pytest.mark.asyncio
    async def test_service_exception_borrower_not_found(self, mock_db_session, mock_borrower_service, mock_property_service):
        """
        Test handling of upstream dependency failures.
        """
        mock_borrower_service.get_borrower_summary.side_effect = AppException("Borrower not found")

        payload = {
            "borrower_id": "ghost",
            "property_id": "prop-1",
            "loan_amount": Decimal("100.00"),
            "contract_rate": Decimal("3.00"),
            "amortization_years": 25,
            "down_payment": Decimal("10.00")
        }

        with patch('mortgage_underwriting.modules.orchestrator.services.BorrowerService', return_value=mock_borrower_service), \
             patch('mortgage_underwriting.modules.orchestrator.services.PropertyService', return_value=mock_property_service):
            
            service = OrchestratorService(mock_db_session)
            
            with pytest.raises(AppException) as exc_info:
                await service.process_application(payload)
            
            assert "Borrower not found" in str(exc_info.value)