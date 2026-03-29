from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple
import json

from .models import UnderwritingResult, UnderwritingOverride
from .schemas import (
    UnderwritingCalculationRequest,
    UnderwritingEvaluationRequest,
    UnderwritingOverrideRequest,
    UnderwritingCalculationResponse,
    UnderwritingResultResponse,
)
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.modules.client.models import Client, MortgageApplication

logger = structlog.get_logger()


class UnderwritingService:
    """Business logic for mortgage underwriting calculations and evaluations."""
    
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
    
    def _calculate_qualifying_rate(self, contract_rate: Decimal) -> Decimal:
        """Calculate qualifying rate per OSFI B-20 guidelines.
        
        Qualifying rate = max(contract_rate + 2%, 5.25%)
        """
        stress_rate = contract_rate + Decimal('2.0')
        return max(stress_rate, Decimal('5.25'))
    
    def _calculate_gds_tds(
        self,
        gross_monthly_income: Decimal,
        pith_monthly: Decimal,
        monthly_debts: Decimal = Decimal('0'),
        condo_fees: Decimal = Decimal('0')
    ) -> Tuple[Decimal, Decimal]:
        """Calculate GDS and TDS ratios.
        
        GDS = (PITH + 50% condo fees) / Gross Monthly Income
        TDS = (PITH + all debts + 50% condo fees) / Gross Monthly Income
        """
        if gross_monthly_income <= 0:
            return Decimal('0'), Decimal('0')
            
        gds_numerator = pith_monthly + (condo_fees * Decimal('0.5'))
        tds_numerator = pith_monthly + monthly_debts + (condo_fees * Decimal('0.5'))
        
        gds_ratio = (gds_numerator / gross_monthly_income) * 100
        tds_ratio = (tds_numerator / gross_monthly_income) * 100
        
        logger.info(
            "calculated_ratios",
            gds_numerator=float(gds_numerator),
            tds_numerator=float(tds_numerator),
            gross_income=float(gross_monthly_income),
            gds_ratio=float(gds_ratio),
            tds_ratio=float(tds_ratio)
        )
        
        return gds_ratio.quantize(Decimal('0.01')), tds_ratio.quantize(Decimal('0.01'))
    
    def _calculate_max_mortgage(
        self,
        gross_monthly_income: Decimal,
        qualifying_rate: Decimal,
        gds_ratio_limit: Decimal = Decimal('39'),
        tds_ratio_limit: Decimal = Decimal('44'),
        condo_fees: Decimal = Decimal('0')
    ) -> Decimal:
        """Calculate maximum mortgage amount based on income and qualifying rate."""
        # Using GDS limit calculation
        max_monthly_payment_gds = (gross_monthly_income * gds_ratio_limit) / 100
        if condo_fees > 0:
            max_monthly_payment_gds -= (condo_fees * Decimal('0.5'))
        
        # Using TDS limit calculation
        max_monthly_payment_tds = (gross_monthly_income * tds_ratio_limit) / 100
        
        # Take the lesser of the two
        max_monthly_payment = min(max_monthly_payment_gds, max_monthly_payment_tds)
        
        # Convert to annual payment and then to principal
        annual_payment = max_monthly_payment * 12
        # Simplified calculation - in practice would use amortization formula
        # For 25 year amortization: P = A / ((r(1+r)^n)/((1+r)^n - 1)) where r=monthly_rate, n=300
        # Approximation here for demonstration
        if qualifying_rate > 0:
            max_mortgage = (annual_payment * 25) / (1 + (qualifying_rate / 100))
            return max_mortgage.quantize(Decimal('0.01'))
        
        return Decimal('0')
    
    def _calculate_cmhc_premium(self, ltv_ratio: Decimal) -> Tuple[bool, Optional[Decimal], Optional[Decimal]]:
        """Determine if CMHC insurance is required and calculate premium.
        
        Premium tiers:
        - 80.01-85% = 2.80%
        - 85.01-90% = 3.10%
        - 90.01-95% = 4.00%
        """
        if ltv_ratio <= 80:
            return False, None, None
        
        if ltv_ratio <= 85:
            return True, Decimal('2.80'), Decimal('0.028')
        elif ltv_ratio <= 90:
            return True, Decimal('3.10'), Decimal('0.031')
        elif ltv_ratio <= 95:
            return True, Decimal('4.00'), Decimal('0.04')
        else:
            # LTV > 95% should be declined
            return False, None, None
    
    def _determine_decision(
        self,
        gds_ratio: Decimal,
        tds_ratio: Decimal,
        stress_test_passed: bool,
        ltv_ratio: Decimal
    ) -> Tuple[str, List[str], List[str]]:
        """Determine underwriting decision and reasons."""
        decline_reasons: List[str] = []
        conditions: List[str] = []
        
        if not stress_test_passed:
            decline_reasons.append("Failed stress test")
        
        if gds_ratio > 39:
            decline_reasons.append("GDS ratio exceeds 39% limit")
        
        if tds_ratio > 44:
            decline_reasons.append("TDS ratio exceeds 44% limit")
        
        if ltv_ratio > 95:
            decline_reasons.append("LTV ratio exceeds 95% maximum")
        
        # High-ratio mortgages (LTV > 80%) require CMHC insurance
        if ltv_ratio > 80 and ltv_ratio <= 95:
            conditions.append("CMHC insurance required")
        
        if decline_reasons:
            return "DECLINED", decline_reasons, conditions
        elif conditions:
            return "CONDITIONAL", [], conditions
        else:
            return "APPROVED", [], []
    
    async def calculate(
        self,
        request: UnderwritingCalculationRequest
    ) -> UnderwritingCalculationResponse:
        """Perform underwriting calculations without saving results."""
        logger.info("calculating_underwriting", purchase_price=float(request.purchase_price))
        
        # Validate inputs
        if request.purchase_price <= 0:
            raise ValueError("Purchase price must be greater than zero")
        if request.down_payment <= 0:
            raise ValueError("Down payment must be greater than zero")
        if request.contract_rate <= 0:
            raise ValueError("Contract rate must be greater than zero")
        if request.gross_monthly_income <= 0:
            raise ValueError("Gross monthly income must be greater than zero")
        if request.down_payment >= request.purchase_price:
            raise ValueError("Down payment cannot exceed purchase price")
        
        # Calculate qualifying rate
        qualifying_rate = self._calculate_qualifying_rate(request.contract_rate)
        
        # Calculate PITH (Principal + Interest + Taxes + Heating)
        # Simplified: assuming taxes/heating included in monthly payment calculation
        # In practice would separate these out
        pith_monthly = (request.loan_amount * (qualifying_rate / 100)) / 12  # Very simplified
        
        # Calculate ratios
        gds_ratio, tds_ratio = self._calculate_gds_tds(
            request.gross_monthly_income,
            pith_monthly,
            request.monthly_debts,
            request.condo_fees
        )
        
        # Check stress test
        stress_test_passed = (
            gds_ratio <= 39 and 
            tds_ratio <= 44
        )
        
        # Determine if CMHC insurance is required
        cmhc_required, cmhc_premium_percent, cmhc_premium_rate = self._calculate_cmhc_premium(request.ltv_ratio)
        
        # Calculate CMHC premium amount
        cmhc_premium_amount = None
        if cmhc_required and cmhc_premium_rate:
            cmhc_premium_amount = (request.loan_amount * cmhc_premium_rate).quantize(Decimal('0.01'))
        
        # Calculate maximum mortgage
        max_mortgage = self._calculate_max_mortgage(
            request.gross_monthly_income,
            qualifying_rate,
            condo_fees=request.condo_fees
        )
        
        # Determine decision
        decision, decline_reasons, conditions = self._determine_decision(
            gds_ratio,
            tds_ratio,
            stress_test_passed,
            request.ltv_ratio
        )
        
        # Final qualification
        qualifies = decision != "DECLINED"
        
        return UnderwritingCalculationResponse(
            gds_ratio=gds_ratio,
            tds_ratio=tds_ratio,
            ltv_ratio=request.ltv_ratio,
            qualifies=qualifies,
            decision=decision,
            qualifying_rate=qualifying_rate,
            max_mortgage=max_mortgage,
            cmhc_required=cmhc_required,
            cmhc_premium_amount=cmhc_premium_amount,
            cmhc_premium_percent=cmhc_premium_percent,
            decline_reasons=decline_reasons,
            conditions=conditions,
            stress_test_passed=stress_test_passed
        )
    
    async def evaluate(
        self,
        request: UnderwritingEvaluationRequest
    ) -> UnderwritingResultResponse:
        """Evaluate application and save underwriting result."""
        logger.info("evaluating_underwriting", application_id=request.application_id)
        
        # Run calculation first
        calc_response = await self.calculate(request)
        
        # Create database record
        result = UnderwritingResult(
            application_id=request.application_id,
            client_id=request.client_id,
            gds_ratio=calc_response.gds_ratio,
            tds_ratio=calc_response.tds_ratio,
            ltv_ratio=calc_response.ltv_ratio,
            qualifies=calc_response.qualifies,
            decision=calc_response.decision,
            qualifying_rate=calc_response.qualifying_rate,
            max_mortgage=calc_response.max_mortgage,
            cmhc_required=calc_response.cmhc_required,
            cmhc_premium_amount=calc_response.cmhc_premium_amount,
            cmhc_premium_percent=calc_response.cmhc_premium_percent,
            decline_reasons=json.dumps(calc_response.decline_reasons) if calc_response.decline_reasons else None,
            conditions=json.dumps(calc_response.conditions) if calc_response.conditions else None,
            stress_test_passed=calc_response.stress_test_passed
        )
        
        self.db.add(result)
        await self.db.commit()
        await self.db.refresh(result)
        
        return UnderwritingResultResponse.model_validate(result)
    
    async def create_override(
        self,
        result_id: int,
        admin_user_id: int,
        request: UnderwritingOverrideRequest
    ) -> UnderwritingOverrideResponse:
        """Create admin override for underwriting result."""
        logger.info("creating_override", result_id=result_id, admin_user_id=admin_user_id)
        
        # Verify result exists
        stmt = select(UnderwritingResult).where(UnderwritingResult.id == result_id)
        result = await self.db.scalar(stmt)
        if not result:
            raise NotFoundError(f"Underwriting result with ID {result_id} not found")
        
        # Create override
        override = UnderwritingOverride(
            result_id=result_id,
            admin_user_id=admin_user_id,
            reason=request.reason
        )
        
        self.db.add(override)
        await self.db.commit()
        await self.db.refresh(override)
        
        return UnderwritingOverrideResponse.model_validate(override)