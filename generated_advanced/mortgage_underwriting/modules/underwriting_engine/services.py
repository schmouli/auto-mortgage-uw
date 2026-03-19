from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import ValidationError
from mortgage_underwriting.modules.applications.models import Application
from mortgage_underwriting.modules.underwriting.models import UnderwritingResult, UnderwritingOverride
from mortgage_underwriting.modules.underwriting.schemas import (
    UnderwritingCalculationRequest,
    UnderwritingResultBase,
    UnderwritingResultCreate,
    UnderwritingOverrideCreate,
    UnderwritingOverrideResponse
)

logger = structlog.get_logger()


class UnderwritingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def calculate_qualification(self, payload: UnderwritingCalculationRequest) -> UnderwritingResultBase:
        """Calculate qualification without saving to database."""
        logger.info("underwriting_calculation_started", property_value=float(payload.property_value))
        
        # Calculate ratios and values
        try:
            result = self._perform_underwriting_calculations(payload)
        except ValidationError as e:
            logger.error("underwriting_calculation_failed", error=str(e))
            raise ValidationError(f"Failed to perform underwriting calculations: {str(e)}")
        
        logger.info("underwriting_calculation_completed", 
                   qualifies=result.qualifies, 
                   decision=result.decision,
                   gds_ratio=float(result.gds_ratio),
                   tds_ratio=float(result.tds_ratio))
        
        return result

    async def evaluate_and_save(self, payload: UnderwritingCalculationRequest, application_id: int) -> UnderwritingResult:
        """Evaluate underwriting and save result to database."""
        logger.info("underwriting_evaluation_started", application_id=application_id)
        
        # Verify application exists
        stmt = select(Application).where(Application.id == application_id)
        result = await self.db.execute(stmt)
        application = result.scalar_one_or_none()
        if not application:
            raise ValidationError(f"Application with ID {application_id} not found")
        
        # Perform calculations
        calc_result = self._perform_underwriting_calculations(payload)
        
        # Create model instance
        uw_result = UnderwritingResult(
            application_id=application_id,
            qualifies=calc_result.qualifies,
            decision=calc_result.decision,
            gds_ratio=calc_result.gds_ratio,
            tds_ratio=calc_result.tds_ratio,
            ltv_ratio=calc_result.ltv_ratio,
            cmhc_required=calc_result.cmhc_required,
            cmhc_premium_amount=calc_result.cmhc_premium_amount,
            qualifying_rate=calc_result.qualifying_rate,
            max_mortgage=calc_result.max_mortgage,
            decline_reasons=calc_result.decline_reasons,
            conditions=calc_result.conditions,
            stress_test_passed=calc_result.stress_test_passed
        )
        
        self.db.add(uw_result)
        await self.db.commit()
        await self.db.refresh(uw_result)
        
        logger.info("underwriting_evaluation_saved", result_id=uw_result.id)
        return uw_result

    async def get_result(self, result_id: int) -> Optional[UnderwritingResult]:
        """Retrieve a saved underwriting result."""
        stmt = select(UnderwritingResult).where(UnderwritingResult.id == result_id).options(selectinload(UnderwritingResult.overrides))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_override(self, payload: UnderwritingOverrideCreate, user_id: Optional[int] = None) -> UnderwritingOverrideResponse:
        """Create an admin override for an underwriting result."""
        logger.info("underwriting_override_requested", result_id=payload.result_id, approved=payload.approved)
        
        # Verify result exists
        stmt = select(UnderwritingResult).where(UnderwritingResult.id == payload.result_id)
        result = await self.db.execute(stmt)
        uw_result = result.scalar_one_or_none()
        if not uw_result:
            raise ValidationError(f"Underwriting result with ID {payload.result_id} not found")
        
        # Create override
        override = UnderwritingOverride(
            result_id=payload.result_id,
            created_by=user_id,
            reason=payload.reason,
            approved=payload.approved
        )
        
        self.db.add(override)
        await self.db.commit()
        await self.db.refresh(override)
        
        logger.info("underwriting_override_created", override_id=override.id)
        return UnderwritingOverrideResponse.model_validate(override)

    def _calculate_mortgage_payment(self, principal: Decimal, annual_rate: Decimal, years: int) -> Decimal:
        """Calculate monthly mortgage payment using standard formula."""
        if principal <= 0:
            raise ValidationError("Principal must be positive")
        if annual_rate < 0:
            raise ValidationError("Interest rate cannot be negative")
        if years <= 0:
            raise ValidationError("Amortization years must be positive")
            
        n = years * 12
        r = annual_rate / 12
        
        if r == 0:
            return principal / n
            
        payment = principal * (r * (1 + r)**n) / ((1 + r)**n - 1)
        return payment.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def _perform_underwriting_calculations(self, payload: UnderwritingCalculationRequest) -> UnderwritingResultBase:
        """Core underwriting calculation logic."""
        # Constants
        MAX_GDS = Decimal('0.39')
        MAX_TDS = Decimal('0.44')
        
        # Validate inputs
        if payload.property_value <= 0:
            raise ValidationError("Property value must be greater than zero")
        if payload.loan_amount <= 0:
            raise ValidationError("Loan amount must be greater than zero")
        if payload.gross_monthly_income <= 0:
            raise ValidationError("Gross monthly income must be greater than zero")
        
        # Calculate qualifying rate (OSFI B-20)
        stress_test_rate = max(payload.contract_rate + Decimal('0.02'), Decimal('0.0525'))
        
        # Calculate monthly payments
        monthly_tax = payload.property_taxes_annual / Decimal('12')
        total_monthly_housing = payload.heating_costs_monthly + monthly_tax
        
        # Add condo fees if applicable
        if payload.condo_fees_monthly and payload.condo_fees_monthly > 0:
            total_monthly_housing += payload.condo_fees_monthly
            pith_with_condo = payload.heating_costs_monthly + monthly_tax + (payload.condo_fees_monthly * Decimal('0.5'))
        else:
            pith_with_condo = payload.heating_costs_monthly + monthly_tax
            
        # Calculate GDS ratio
        if payload.gross_monthly_income == 0:
            raise ValidationError("Gross monthly income cannot be zero")
        gds_numerator = pith_with_condo
        gds_ratio = (gds_numerator / payload.gross_monthly_income).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        
        # Calculate TDS ratio
        tds_numerator = pith_with_condo + payload.monthly_debt_payments
        tds_ratio = (tds_numerator / payload.gross_monthly_income).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        
        # Calculate LTV ratio
        if payload.property_value == 0:
            raise ValidationError("Property value cannot be zero")
        ltv_ratio = (payload.loan_amount / payload.property_value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        
        # Determine CMHC insurance requirements
        cmhc_required = ltv_ratio > Decimal('0.80')
        cmhc_premium = Decimal('0.00')
        
        if cmhc_required:
            if ltv_ratio <= Decimal('0.85'):
                cmhc_premium_rate = Decimal('0.0280')
            elif ltv_ratio <= Decimal('0.90'):
                cmhc_premium_rate = Decimal('0.0310')
            elif ltv_ratio <= Decimal('0.95'):
                cmhc_premium_rate = Decimal('0.0400')
            else:
                raise ValidationError("LTV exceeds maximum insurable limit of 95%")
                
            cmhc_premium = (payload.loan_amount * cmhc_premium_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Stress test check
        stress_payment = self._calculate_mortgage_payment(payload.loan_amount + cmhc_premium, stress_test_rate, payload.amortization_years)
        gross_stress_payment = stress_payment + pith_with_condo
        stress_gds = (gross_stress_payment / payload.gross_monthly_income).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        stress_tds = ((gross_stress_payment + payload.monthly_debt_payments) / payload.gross_monthly_income).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        
        stress_test_passed = stress_gds <= MAX_GDS and stress_tds <= MAX_TDS
        
        # Decision logic
        qualifies = stress_test_passed and gds_ratio <= MAX_GDS and tds_ratio <= MAX_TDS
        decline_reasons = []
        conditions = []
        
        if not stress_test_passed:
            decline_reasons.append("Failed stress test")
        if gds_ratio > MAX_GDS:
            decline_reasons.append("GDS ratio exceeds maximum allowed")
        if tds_ratio > MAX_TDS:
            decline_reasons.append("TDS ratio exceeds maximum allowed")
        
        if ltv_ratio > Decimal('0.80'):
            conditions.append("Mortgage insurance required due to high LTV")
            
        if qualifies and not decline_reasons:
            decision = "APPROVED"
        elif qualifies and decline_reasons:
            decision = "CONDITIONAL"
        else:
            decision = "DECLINED"
            
        # Calculate maximum mortgage (reverse calculation based on GDS limit)
        max_monthly_housing = (payload.gross_monthly_income * MAX_GDS) - payload.monthly_debt_payments
        max_mortgage_payment = max_monthly_housing - pith_with_condo
        
        # Reverse engineer maximum mortgage amount
        if max_mortgage_payment > 0:
            # Simplified approximation - in practice would use mortgage formula
            max_mortgage = (max_mortgage_payment * payload.amortization_years * 12).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            max_mortgage = Decimal('0.00')
        
        return UnderwritingResultBase(
            qualifies=qualifies,
            decision=decision,
            gds_ratio=gds_ratio,
            tds_ratio=tds_ratio,
            ltv_ratio=ltv_ratio,
            cmhc_required=cmhc_required,
            cmhc_premium_amount=cmhc_premium,
            qualifying_rate=stress_test_rate,
            max_mortgage=max_mortgage,
            decline_reasons=decline_reasons if decline_reasons else None,
            conditions=conditions if conditions else None,
            stress_test_passed=stress_test_passed
        )