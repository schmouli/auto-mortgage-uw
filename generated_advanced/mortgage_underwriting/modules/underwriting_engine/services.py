from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import json

from sqlalchemy import select
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.underwriting.models import UnderwritingResult, UnderwritingOverride
from mortgage_underwriting.modules.underwriting.schemas import (

    UnderwritingCalculationRequest,
    UnderwritingEvaluationRequest,
    UnderwritingCalculationResponse,
    UnderwritingResultResponse,
    OverrideRequest,
    OverrideResponse,
    DeclineReasonSchema,
    ConditionSchema
)

logger = structlog.get_logger()


class UnderwritingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_qualification(self, payload: UnderwritingCalculationRequest) -> UnderwritingCalculationResponse:
        """Calculate qualification without saving to database.
        
        Args:
            payload: Calculation parameters
            
        Returns:
            UnderwritingCalculationResponse with qualification results
        """
        logger.info("uw_calculate_start", property_value=float(payload.property_value))
        
        # Calculate qualifying rate per OSFI B-20
        qualifying_rate = max(payload.contract_rate + Decimal('0.02'), Decimal('0.0525'))
        logger.debug("uw_stress_test_rate_calculated", rate=float(qualifying_rate))
        
        # Calculate GDS components
        pith = payload.monthly_property_tax + payload.monthly_heating
        condo_fee_component = payload.monthly_condo_fees * Decimal('0.5')
        gds_numerator = pith + condo_fee_component
        
        # Prevent division by zero
        if payload.gross_monthly_income <= 0:
            raise AppException("Invalid gross monthly income", "INVALID_INCOME")
            
        gds_ratio = (gds_numerator / payload.gross_monthly_income).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        logger.debug("uw_gds_calculated", numerator=float(gds_numerator), denominator=float(payload.gross_monthly_income), ratio=float(gds_ratio))
        
        # Calculate TDS components
        total_debt_payments = sum(debt.monthly_payment for debt in payload.other_monthly_debts)
        tds_numerator = gds_numerator + total_debt_payments
        tds_ratio = (tds_numerator / payload.gross_monthly_income).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        logger.debug("uw_tds_calculated", numerator=float(tds_numerator), denominator=float(payload.gross_monthly_income), ratio=float(tds_ratio))
        
        # Calculate LTV
        if payload.property_value <= 0:
            raise AppException("Property value must be greater than zero", "INVALID_PROPERTY_VALUE")
            
        ltv_ratio = (payload.loan_amount / payload.property_value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        logger.debug("uw_ltv_calculated", loan_amount=float(payload.loan_amount), property_value=float(payload.property_value), ratio=float(ltv_ratio))
        
        # Determine CMHC requirements
        cmhc_required = ltv_ratio > Decimal('0.80')
        cmhc_premium_amount = None
        cmhc_premium_rate = None
        
        if cmhc_required:
            # CMHC premium tiers
            if ltv_ratio > Decimal('0.90'):
                cmhc_premium_rate = Decimal('0.0400')  # 4.00%
            elif ltv_ratio > Decimal('0.85'):
                cmhc_premium_rate = Decimal('0.0310')  # 3.10%
            else:
                cmhc_premium_rate = Decimal('0.0280')  # 2.80%
            
            cmhc_premium_amount = (payload.loan_amount * cmhc_premium_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            logger.debug("uw_cmhc_premium_calculated", rate=float(cmhc_premium_rate), amount=float(cmhc_premium_amount))
        
        # Check stress test
        stress_test_passed = True
        decline_reasons: List[DeclineReasonSchema] = []
        conditions: List[ConditionSchema] = []
        
        # Apply regulatory limits
        if gds_ratio > Decimal('0.39'):
            stress_test_passed = False
            decline_reasons.append(DeclineReasonSchema(
                code="HIGH_GDS",
                message="Gross Debt Service ratio exceeds maximum allowed 39%"
            ))
            
        if tds_ratio > Decimal('0.44'):
            stress_test_passed = False
            decline_reasons.append(DeclineReasonSchema(
                code="HIGH_TDS",
                message="Total Debt Service ratio exceeds maximum allowed 44%"
            ))
            
        # Minimum down payment check based on CMHC rules
        down_payment_percent = (payload.down_payment_amount / payload.property_value) * 100
        
        if payload.property_value <= Decimal('500000'):
            min_down = Decimal('5')
        elif payload.property_value <= Decimal('1000000'):
            # 5% on first $500K + 10% on remainder
            min_down = (Decimal('25000') + (payload.property_value - Decimal('500000')) * Decimal('0.10')) / payload.property_value * 100
        else:
            min_down = Decimal('20')
            
        if down_payment_percent < min_down:
            stress_test_passed = False
            decline_reasons.append(DeclineReasonSchema(
                code="INSUFFICIENT_DOWN_PAYMENT",
                message=f"Minimum down payment of {min_down:.2f}% required but only {down_payment_percent:.2f}% provided"
            ))
        
        # Calculate maximum mortgage amount based on qualifying rate
        # Using formula: M = P * [r(1+r)^n] / [(1+r)^n - 1]
        # Where P = principal, r = monthly rate, n = number of payments
        
        # For simplicity, we'll use an approximation based on income
        # Maximum housing costs should not exceed 39% of gross income
        max_housing_cost = payload.gross_monthly_income * Decimal('0.39')
        # Convert qualifying rate to monthly
        monthly_rate = qualifying_rate / 12
        # Number of payments
        num_payments = payload.amortization_years * 12
        
        # Simplified calculation using present value of annuity
        if monthly_rate > 0:
            try:
                denominator = ((1 + monthly_rate) ** num_payments - 1) / (monthly_rate * (1 + monthly_rate) ** num_payments)
                max_mortgage_amount = (max_housing_cost * denominator).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except OverflowError:
                max_mortgage_amount = Decimal('0')
        else:
            max_mortgage_amount = payload.gross_monthly_income * Decimal('0.39') * num_payments
        
        # Decision logic
        if stress_test_passed and len(decline_reasons) == 0:
            decision = "APPROVED"
            qualifies = True
        elif len(decline_reasons) > 0 and any(reason.code in ['HIGH_GDS', 'HIGH_TDS'] for reason in decline_reasons):
            decision = "DECLINED"
            qualifies = False
        else:
            decision = "CONDITIONAL"
            qualifies = True
            
        # Add conditions for self-employed applicants
        if payload.is_self_employed and not payload.self_employed_income_verified:
            conditions.append(ConditionSchema(
                code="SELF_EMPLOYED_INCOME_VERIFICATION_REQUIRED",
                message="Self-employed income must be verified through additional documentation"
            ))
        
        logger.info("uw_calculation_complete", 
                   qualifies=qualifies, 
                   decision=decision, 
                   gds_ratio=float(gds_ratio), 
                   tds_ratio=float(tds_ratio),
                   ltv_ratio=float(ltv_ratio))
        
        return UnderwritingCalculationResponse(
            qualifies=qualifies,
            decision=decision,
            gds_ratio=gds_ratio,
            tds_ratio=tds_ratio,
            ltv_ratio=ltv_ratio,
            cmhc_required=cmhc_required,
            cmhc_premium_amount=cmhc_premium_amount,
            qualifying_rate=qualifying_rate,
            max_mortgage_amount=max_mortgage_amount,
            decline_reasons=decline_reasons,
            conditions=conditions,
            stress_test_passed=stress_test_passed
        )

    async def evaluate_and_save(self, payload: UnderwritingEvaluationRequest, user_id: int) -> UnderwritingResultResponse:
        """Evaluate underwriting criteria and save the result.
        
        Args:
            payload: Evaluation parameters including client/application IDs
            user_id: ID of the user performing the evaluation
            
        Returns:
            Saved underwriting result
        """
        logger.info("uw_evaluate_start", client_id=payload.client_id, application_id=payload.application_id)
        
        # Perform calculation
        calc_response = await self.calculate_qualification(UnderwritingCalculationRequest(
            property_value=payload.property_value,
            loan_amount=payload.loan_amount,
            contract_rate=payload.contract_rate,
            gross_monthly_income=payload.gross_monthly_income,
            monthly_property_tax=payload.monthly_property_tax,
            monthly_heating=payload.monthly_heating,
            monthly_condo_fees=payload.monthly_condo_fees,
            other_monthly_debts=payload.other_monthly_debts,
            rental_income=payload.rental_income,
            rental_property_expenses=payload.rental_property_expenses,
            is_self_employed=payload.is_self_employed,
            self_employed_income_verified=payload.self_employed_income_verified,
            down_payment_amount=payload.down_payment_amount,
            amortization_years=payload.amortization_years
        ))
        
        # Create model instance
        uw_result = UnderwritingResult(
            client_id=payload.client_id,
            application_id=payload.application_id,
            gds_ratio=calc_response.gds_ratio,
            tds_ratio=calc_response.tds_ratio,
            ltv_ratio=calc_response.ltv_ratio,
            qualifying_rate=calc_response.qualifying_rate,
            max_mortgage_amount=calc_response.max_mortgage_amount,
            cmhc_required=calc_response.cmhc_required,
            cmhc_premium_amount=calc_response.cmhc_premium_amount,
            qualifies=calc_response.qualifies,
            decision=calc_response.decision,
            decline_reasons=json.dumps([r.dict() for r in calc_response.decline_reasons]) if calc_response.decline_reasons else None,
            conditions=json.dumps([c.dict() for c in calc_response.conditions]) if calc_response.conditions else None,
            stress_test_passed=calc_response.stress_test_passed,
            created_by=user_id
        )
        
        # Save to database
        self.db.add(uw_result)
        await self.db.flush()
        await self.db.refresh(uw_result)
        
        logger.info("uw_evaluation_saved", result_id=uw_result.id)
        
        # Convert back to response schema
        return UnderwritingResultResponse(
            id=uw_result.id,
            client_id=uw_result.client_id,
            application_id=uw_result.application_id,
            gds_ratio=uw_result.gds_ratio,
            tds_ratio=uw_result.tds_ratio,
            ltv_ratio=uw_result.ltv_ratio,
            qualifying_rate=uw_result.qualifying_rate,
            max_mortgage_amount=uw_result.max_mortgage_amount,
            cmhc_required=uw_result.cmhc_required,
            cmhc_premium_amount=uw_result.cmhc_premium_amount,
            qualifies=uw_result.qualifies,
            decision=uw_result.decision,
            decline_reasons=[DeclineReasonSchema(**r) for r in json.loads(uw_result.decline_reasons)] if uw_result.decline_reasons else [],
            conditions=[ConditionSchema(**c) for c in json.loads(uw_result.conditions)] if uw_result.conditions else [],
            stress_test_passed=uw_result.stress_test_passed,
            created_at=uw_result.created_at,
            created_by=uw_result.created_by
        )

    async def get_result(self, result_id: int) -> UnderwritingResultResponse:
        """Get a saved underwriting result by ID.
        
        Args:
            result_id: ID of the underwriting result
            
        Returns:
            UnderwritingResultResponse
            
        Raises:
            AppException: If result not found
        """
        logger.info("uw_get_result", result_id=result_id)
        
        stmt = select(UnderwritingResult).where(UnderwritingResult.id == result_id)
        result = await self.db.execute(stmt)
        uw_result = result.scalar_one_or_none()
        
        if not uw_result:
            raise AppException("Underwriting result not found", "RESULT_NOT_FOUND")
            
        return UnderwritingResultResponse(
            id=uw_result.id,
            client_id=uw_result.client_id,
            application_id=uw_result.application_id,
            gds_ratio=uw_result.gds_ratio,
            tds_ratio=uw_result.tds_ratio,
            ltv_ratio=uw_result.ltv_ratio,
            qualifying_rate=uw_result.qualifying_rate,
            max_mortgage_amount=uw_result.max_mortgage_amount,
            cmhc_required=uw_result.cmhc_required,
            cmhc_premium_amount=uw_result.cmhc_premium_amount,
            qualifies=uw_result.qualifies,
            decision=uw_result.decision,
            decline_reasons=[DeclineReasonSchema(**r) for r in json.loads(uw_result.decline_reasons)] if uw_result.decline_reasons else [],
            conditions=[ConditionSchema(**c) for c in json.loads(uw_result.conditions)] if uw_result.conditions else [],
            stress_test_passed=uw_result.stress_test_passed,
            created_at=uw_result.created_at,
            created_by=uw_result.created_by
        )

    async def create_override(self, result_id: int, payload: OverrideRequest, user_id: int) -> OverrideResponse:
        """Create an admin override for an underwriting result.
        
        Args:
            result_id: ID of the underwriting result to override
            payload: Override details
            user_id: ID of the admin user creating the override
            
        Returns:
            OverrideResponse
            
        Raises:
            AppException: If result not found or invalid operation
        """
        logger.info("uw_create_override", result_id=result_id, user_id=user_id)
        
        # Get the existing result
        stmt = select(UnderwritingResult).where(UnderwritingResult.id == result_id)
        result = await self.db.execute(stmt)
        uw_result = result.scalar_one_or_none()
        
        if not uw_result:
            raise AppException("Underwriting result not found", "RESULT_NOT_FOUND")
            
        # Store previous decision
        previous_decision = uw_result.decision
        
        # Update the result
        uw_result.decision = payload.new_decision
        uw_result.qualifies = payload.new_decision != "DECLINED"
        
        # Create override record
        override = UnderwritingOverride(
            underwriting_result_id=result_id,
            overridden_by=user_id,
            reason=payload.reason,
            previous_decision=previous_decision,
            new_decision=payload.new_decision
        )
        
        self.db.add(override)
        await self.db.flush()
        await self.db.refresh(override)
        
        # Commit changes
        await self.db.commit()
        
        logger.info("uw_override_created", override_id=override.id)
        
        return OverrideResponse(
            id=override.id,
            underwriting_result_id=override.underwriting_result_id,
            overridden_by=override.overridden_by,
            reason=override.reason,
            previous_decision=override.previous_decision,
            new_decision=override.new_decision,
            created_at=override.created_at
        )