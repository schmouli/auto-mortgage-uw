import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from mortgage_underwriting.modules.underwriting_engine.services import UnderwritingService
from mortgage_underwriting.modules.underwriting_engine.schemas import (
    UnderwritingRequest,
    UnderwritingDecisionResponse,
    DecisionStatus
)
from mortgage_underwriting.common.exceptions import AppException

@pytest.mark.unit
class TestUnderwritingServiceCalculations:

    @pytest.mark.asyncio
    async def test_calculate_qualifying_rate_stress_test_b20(self):
        """
        Test OSFI B-20 Stress Test Logic:
        Qualifying Rate = max(contract_rate + 2%, 5.25%)
        """
        # Case 1: Contract rate 3.5% -> Qualifying 5.5% (Floor 5.25%)
        rate_1 = UnderwritingService._calculate_qualifying_rate(Decimal("3.50"))
        assert rate_1 == Decimal("5.50")

        # Case 2: Contract rate 4.0% -> Qualifying 6.0%
        rate_2 = UnderwritingService._calculate_qualifying_rate(Decimal("4.00"))
        assert rate_2 == Decimal("6.00")

        # Case 3: Contract rate 7.0% -> Qualifying 9.0%
        rate_3 = UnderwritingService._calculate_qualifying_rate(Decimal("7.00"))
        assert rate_3 == Decimal("9.00")

        # Case 4: Contract rate 3.0% -> Qualifying 5.25% (Floor hit)
        rate_4 = UnderwritingService._calculate_qualifying_rate(Decimal("3.00"))
        assert rate_4 == Decimal("5.25")

    @pytest.mark.asyncio
    async def test_calculate_gds(self):
        """
        Test Gross Debt Service Ratio: (Mortgage + Tax + Heat) / Annual Income
        Limit: GDS <= 39%
        """
        # Monthly Mortgage: 2120, Tax: 250, Heat: 150 -> Total Monthly: 2520
        # Annual Housing: 30240. Income: 100000. GDS: 30.24%
        gds = UnderwritingService._calculate_gds(
            mortgage_payment=Decimal("2120.00"),
            property_tax=Decimal("250.00"),
            heating=Decimal("150.00"),
            annual_income=Decimal("100000.00")
        )
        assert gds == Decimal("0.3024")

    @pytest.mark.asyncio
    async def test_calculate_tds(self):
        """
        Test Total Debt Service Ratio: (Housing + Other Debts) / Annual Income
        Limit: TDS <= 44%
        """
        # Monthly Housing: 2520. Other Debt: 500. Total Monthly: 3020.
        # Annual Debt: 36240. Income: 100000. TDS: 36.24%
        tds = UnderwritingService._calculate_tds(
            housing_costs_monthly=Decimal("2520.00"),
            other_debts_monthly=Decimal("500.00"),
            annual_income=Decimal("100000.00")
        )
        assert tds == Decimal("0.3624")

    @pytest.mark.asyncio
    async def test_calculate_ltv(self):
        """
        Test Loan to Value ratio.
        """
        ltv = UnderwritingService._calculate_ltv(
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00")
        )
        assert ltv == Decimal("0.80")

    @pytest.mark.asyncio
    async def test_determine_cmhc_insurance_required(self):
        """
        Test CMHC Logic:
        IF LTV > 80% THEN insurance_required = True
        Tiers:
        80.01-85% = 2.80%
        85.01-90% = 3.10%
        90.01-95% = 4.00%
        """
        # Case 1: LTV 80% -> No Insurance
        premium_1 = UnderwritingService._calculate_cmhc_premium(
            loan_amount=Decimal("400000.00"),
            property_value=Decimal("500000.00")
        )
        assert premium_1 == Decimal("0.00")

        # Case 2: LTV 85% -> 2.80% on loan amount
        # Loan 425k, Value 500k. Premium = 425000 * 0.028 = 11900
        premium_2 = UnderwritingService._calculate_cmhc_premium(
            loan_amount=Decimal("425000.00"),
            property_value=Decimal("500000.00")
        )
        assert premium_2 == Decimal("11900.00")

        # Case 3: LTV 90% -> 3.10%
        premium_3 = UnderwritingService._calculate_cmhc_premium(
            loan_amount=Decimal("450000.00"),
            property_value=Decimal("500000.00")
        )
        assert premium_3 == Decimal("13950.00")

        # Case 4: LTV 95% -> 4.00%
        premium_4 = UnderwritingService._calculate_cmhc_premium(
            loan_amount=Decimal("475000.00"),
            property_value=Decimal("500000.00")
        )
        assert premium_4 == Decimal("19000.00")

@pytest.mark.unit
class TestUnderwritingServiceLogic:

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_approve_application_happy_path(self, mock_db):
        """
        Test a standard application that meets all criteria.
        """
        payload = UnderwritingRequest(
            applicant={
                "first_name": "Jane",
                "last_name": "Smith",
                "sin_hash": "hash123",
                "date_of_birth": "1985-05-20"
            },
            property={
                "address": "456 Oak Ave",
                "city": "Vancouver",
                "province": "BC",
                "postal_code": "V6K1A1",
                "value": Decimal("600000.00"),
                "annual_property_tax":Decimal("3600.00"),
                "estimated_heating_cost": Decimal("120.00")
            },
            financial={
                "annual_income": Decimal("150000.00"),
                "down_payment": Decimal("120000.00"),
                "loan_amount": Decimal("480000.00"),
                "amortization_years": 25,
                "contract_rate": Decimal("4.0"),
                "other_debt_payments": Decimal("0.00")
            }
        )

        service = UnderwritingService(mock_db)
        result = await service.assess_application(payload)

        assert result.status == DecisionStatus.APPROVED
        assert result.gds <= Decimal("0.39")
        assert result.tds <= Decimal("0.44")
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_reject_high_gds(self, mock_db):
        """
        Test rejection when GDS > 39%.
        """
        payload = UnderwritingRequest(
            applicant={
                "first_name": "Risk",
                "last_name": "Taker",
                "sin_hash": "hash999",
                "date_of_birth": "1990-01-01"
            },
            property={
                "address": "789 High St",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M5V1A1",
                "value": Decimal("500000.00"),
                "annual_property_tax": Decimal("6000.00"), # High tax
                "estimated_heating_cost": Decimal("500.00") # High heat
            },
            financial={
                "annual_income": Decimal("60000.00"), # Low income
                "down_payment": Decimal("100000.00"),
                "loan_amount": Decimal("400000.00"),
                "amortization_years": 25,
                "contract_rate": Decimal("5.0"),
                "other_debt_payments": Decimal("0.00")
            }
        )

        service = UnderwritingService(mock_db)
        result = await service.assess_application(payload)

        assert result.status == DecisionStatus.REJECTED
        assert "GDS" in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_reject_high_tds(self, mock_db):
        """
        Test rejection when TDS > 44%.
        """
        payload = UnderwritingRequest(
            applicant={
                "first_name": "Debt",
                "last_name": "Loader",
                "sin_hash": "hash888",
                "date_of_birth": "1980-01-01"
            },
            property={
                "address": "321 Debt Ln",
                "city": "Calgary",
                "province": "AB",
                "postal_code": "T2P1A1",
                "value": Decimal("400000.00"),
                "annual_property_tax": Decimal("2400.00"),
                "estimated_heating_cost": Decimal("100.00")
            },
            financial={
                "annual_income": Decimal("80000.00"),
                "down_payment": Decimal("80000.00"),
                "loan_amount": Decimal("320000.00"),
                "amortization_years": 25,
                "contract_rate": Decimal("4.5"),
                "other_debt_payments": Decimal("2000.00") # Significant other debt
            }
        )

        service = UnderwritingService(mock_db)
        result = await service.assess_application(payload)

        assert result.status == DecisionStatus.REJECTED
        assert "TDS" in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_pipeda_compliance_no_sin_in_response(self, mock_db):
        """
        Ensure SIN is never returned in the response object.
        """
        payload = UnderwritingRequest(
            applicant={
                "first_name": "Private",
                "last_name": "Person",
                "sin_hash": "secret_hash",
                "date_of_birth": "1995-07-07"
            },
            property={
                "address": "999 Secure Way",
                "city": "Ottawa",
                "province": "ON",
                "postal_code": "K1A0A1",
                "value": Decimal("300000.00"),
                "annual_property_tax": Decimal("2000.00"),
                "estimated_heating_cost": Decimal("100.00")
            },
            financial={
                "annual_income": Decimal("90000.00"),
                "down_payment": Decimal("60000.00"),
                "loan_amount": Decimal("240000.00"),
                "amortization_years": 20,
                "contract_rate": Decimal("3.5"),
                "other_debt_payments": Decimal("0.00")
            }
        )

        service = UnderwritingService(mock_db)
        result = await service.assess_application(payload)

        # Pydantic model should not have the field, or it should be None/excluded
        assert not hasattr(result, 'sin') or getattr(result, 'sin', None) is None
        assert result.applicant_first_name == "Private"