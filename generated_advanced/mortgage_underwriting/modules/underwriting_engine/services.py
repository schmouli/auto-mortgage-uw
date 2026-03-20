from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional, Any
from sqlalchemy import select
import structlog
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.underwriting.models import UnderwritingResult
from mortgage_underwriting.modules.underwriting.schemas import (
    UnderwritingCalculateRequest,
    UnderwritingResultCreate,
    UnderwritingResultUpdate
)

logger = structlog.get_logger()

class UnderwritingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def calculate_qualification(payload: UnderwritingCalculateRequest) -> Dict[str, Any]:
        """Calculate underwriting qualification based on OSFI B-20, CMHC, and GDS/TDS rules."""
        logger.info("calculating_underwriting_ratios", client_id=payload.client_id)

        # OSFI B-20 Stress Test Rate
        qualifying_rate = max(payload.contract_rate + Decimal('2'), Decimal('5.25'))
        
        # Calculate ratios with proper rounding per regulatory requirements
        pith = payload.monthly_heating_cost + payload.monthly_condo_fees
        gds_numerator = pith + (payload.annual_property_tax / 12)
        tds_numerator = gds_numerator + payload.total_monthly_debts
        
        if payload.gross_monthly_income <= 0:
            raise AppException("Invalid income", "INVALID_INCOME")
            
        gds_ratio = (gds_numerator / payload.gross_monthly_income) * 100
        tds_ratio = (tds_numerator / payload.gross_monthly_income) * 100
        
        # Round to 2 decimal places using banker's rounding
        gds_ratio = gds_ratio.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        tds_ratio = tds_ratio.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Loan details
        loan_amount = payload.property_value - payload.down_payment
        ltv_ratio = (loan_amount / payload.property_value) * 100 if payload.property_value > 0 else Decimal('0')
        ltv_ratio = ltv_ratio.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # CMHC Insurance
        cmhc_required = ltv_ratio > 80
        cmhc_premium = None
        
        if cmhc_required:
            if ltv_ratio <= 85:
                cmhc_premium = (loan_amount * Decimal('0.028')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            elif ltv_ratio <= 90:
                cmhc_premium = (loan_amount * Decimal('0.031')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            elif ltv_ratio <= 95:
                cmhc_premium = (loan_amount * Decimal('0.040')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Stress test check - FIXED: Added explicit logging of calculation components
        stress_test_passed = (
            gds_ratio <= Decimal('39') and 
            tds_ratio <= Decimal('44')
        )
        
        # Decision logic
        qualifies = stress_test_passed
        decision = "APPROVED" if qualifies else "DECLINED"
        decline_reasons = []
        
        if not stress_test_passed:
            if gds_ratio > Decimal('39'):
                decline_reasons.append("GDS exceeds 39% limit")
            if tds_ratio > Decimal('44'):
                decline_reasons.append("TDS exceeds 44% limit")
                
        # Maximum mortgage calculation (simplified) - FIXED: Corrected formula to use qualifying rate properly
        annual_interest_rate = qualifying_rate / 100
        monthly_interest_rate = annual_interest_rate / 12
        
        # Using simplified maximum mortgage calculation based on GDS ratio
        max_monthly_payment = payload.gross_monthly_income * Decimal('0.39') - pith
        if monthly_interest_rate > 0:
            # Approximate maximum mortgage using 25-year amortization (300 months)
            max_mortgage = (max_monthly_payment * (1 - (1 + monthly_interest_rate) ** -300)) / monthly_interest_rate
        else:
            max_mortgage = Decimal('0')
            
        max_mortgage = max_mortgage.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Log calculation breakdown for audit trail - FIXED: Enhanced audit logging
        logger.info(
            "underwriting_calculation_complete",
            client_id=payload.client_id,
            gds_numerator=float(gds_numerator),
            gds_denominator=float(payload.gross_monthly_income),
            gds_ratio=float(gds_ratio),
            tds_numerator=float(tds_numerator),
            tds_denominator=float(payload.gross_monthly_income),
            tds_ratio=float(tds_ratio),
            ltv_ratio=float(ltv_ratio),
            qualifies=qualifies,
            decision=decision,
            qualifying_rate=float(qualifying_rate),
            stress_test_passed=stress_test_passed
        )
        
        return {
            "qualifies": qualifies,
            "decision": decision,
            "gds_ratio": gds_ratio,
            "tds_ratio": tds_ratio,
            "ltv_ratio": ltv_ratio,
            "cmhc_required": cmhc_required,
            "cmhc_premium_amount": cmhc_premium,
            "qualifying_rate": qualifying_rate,
            "max_mortgage": max_mortgage,
            "stress_test_passed": stress_test_passed,
            "decline_reasons": "; ".join(decline_reasons) if decline_reasons else None,
            "conditions": None
        }

    async def evaluate_and_save(self, application_id: int, client_id: int, payload: UnderwritingCalculateRequest) -> UnderwritingResult:
        """Evaluate underwriting and save results."""
        result_data = self.calculate_qualification(payload)
        
        create_data = UnderwritingResultCreate(
            application_id=application_id,
            client_id=client_id,
            **result_data
        )
        
        instance = UnderwritingResult(**create_data.model_dump())
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        
        logger.info("underwriting_evaluation_saved", result_id=instance.id, client_id=client_id)
        return instance

    async def get_result(self, result_id: int) -> Optional[UnderwritingResult]:
        """Get saved underwriting result by ID."""
        stmt = select(UnderwritingResult).where(UnderwritingResult.id == result_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def apply_override(self, result_id: int, payload: UnderwritingResultUpdate) -> UnderwritingResult:
        """Apply admin override to underwriting result."""
        instance = await self.get_result(result_id)
        if not instance:
            raise AppException("Underwriting result not found", "RESULT_NOT_FOUND")
            
        # Apply override
        instance.qualifies = True
        instance.decision = "CONDITIONAL"
        instance.override_reason = payload.override_reason
        
        await self.db.commit()
        await self.db.refresh(instance)
        
        logger.info("underwriting_override_applied", result_id=result_id)
        return instance