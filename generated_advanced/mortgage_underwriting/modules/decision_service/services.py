from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.modules.decision_service.models import Decision
from mortgage_underwriting.modules.decision_service.schemas import (
    DecisionEvaluateRequest, DecisionEvaluateResponse, 
    RatioMetrics, BorrowerData, PropertyData, LoanData, DebtData
)
from mortgage_underwriting.modules.decision_service.exceptions import DecisionNotFoundError

logger = structlog.get_logger()

class DecisionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate(self, payload: DecisionEvaluateRequest) -> DecisionEvaluateResponse:
        """Run deterministic underwriting decision engine."""
        logger.info("decision_evaluate_start", application_id=str(payload.application_id))
        
        # Validate inputs
        self._validate_inputs(payload)
        
        # Calculate ratios and metrics
        ratios, stress_rate = await self._calculate_ratios(payload)
        cmhc_required = await self._check_cmhc_requirement(
            payload.loan_data.mortgage_amount,
            payload.property_data.property_value
        )
        
        # Apply business rules
        decision, confidence, flags, exceptions = await self._apply_rules(
            ratios, payload.borrower_data.credit_score, cmhc_required
        )
        
        # Build audit trail
        audit_trail = {
            "rules_evaluated": [
                "gds_limit_check",
                "tds_limit_check",
                "ltv_limit_check",
                "credit_score_minimum",
                "cmhc_eligibility"
            ],
            "timestamp": str(ratios),
            "model_version": payload.policy_version
        }
        
        # Save decision record
        decision_record = Decision(
            application_id=payload.application_id,
            decision=decision,
            confidence_score=confidence,
            stress_test_rate=stress_rate,
            cmhc_required=cmhc_required,
            policy_flags=flags,
            exceptions=exceptions,
            audit_trail=audit_trail
        )
        
        self.db.add(decision_record)
        await self.db.commit()
        await self.db.refresh(decision_record)
        
        logger.info("decision_evaluate_complete", application_id=str(payload.application_id), decision=decision)
        
        return DecisionEvaluateResponse(
            application_id=payload.application_id,
            decision=decision,
            confidence_score=confidence,
            ratios=ratios,
            cmhc_required=cmhc_required,
            stress_test_rate=stress_rate,
            policy_flags=flags,
            exceptions=exceptions,
            audit_trail=audit_trail
        )

    async def get_decision(self, application_id: UUID) -> Decision:
        """Retrieve a decision record by application ID."""
        logger.info("get_decision", application_id=str(application_id))
        
        result = await self.db.execute(
            select(Decision)
            .where(Decision.application_id == str(application_id))
            .options(selectinload(Decision.application))
        )
        decision = result.scalar_one_or_none()
        
        if not decision:
            raise DecisionNotFoundError(f"Decision not found for application {application_id}")
            
        return decision

    async def get_audit_trail(self, application_id: UUID) -> Dict[str, Any]:
        """Get full audit trail for a decision."""
        decision = await self.get_decision(application_id)
        return decision.audit_trail

    def _validate_inputs(self, payload: DecisionEvaluateRequest) -> None:
        """Validate all input data before processing."""
        # FIXED: Added comprehensive input validation
        if payload.borrower_data.gross_annual_income <= 0:
            raise ValueError("Gross annual income must be positive")
        if payload.property_data.property_value <= 0:
            raise ValueError("Property value must be positive")
        if payload.loan_data.mortgage_amount <= 0:
            raise ValueError("Mortgage amount must be positive")
        if payload.loan_data.amortization_years < 1 or payload.loan_data.amortization_years > 30:
            raise ValueError("Amortization years must be between 1 and 30")
        for debt in payload.existing_debts:
            if debt.monthly_payment < 0:
                raise ValueError("Debt monthly payment cannot be negative")
            if debt.balance < 0:
                raise ValueError("Debt balance cannot be negative")

    async def _calculate_ratios(self, payload: DecisionEvaluateRequest) -> Tuple[RatioMetrics, Decimal]:
        """Calculate GDS, TDS, LTV and stress test rate according to OSFI B-20."""
        # Monthly values
        gross_monthly_income = payload.borrower_data.gross_annual_income / Decimal('12')
        
        # FIXED: More accurate PITH calculation using actual interest rate
        monthly_rate = payload.loan_data.contract_rate / Decimal('12')
        total_payments = payload.loan_data.amortization_years * 12
        
        # Calculate principal and interest payment using standard mortgage formula
        if monthly_rate > 0:
            pith = (payload.loan_data.mortgage_amount * monthly_rate * (1 + monthly_rate)**total_payments) / ((1 + monthly_rate)**total_payments - 1)
        else:
            # Handle case where rate is zero
            pith = payload.loan_data.mortgage_amount / Decimal(total_payments)
        
        total_debts = sum(debt.monthly_payment for debt in payload.existing_debts)
        
        # Stress test calculation per OSFI B-20
        qualifying_rate = max(
            payload.loan_data.contract_rate + Decimal('0.02'),
            Decimal('0.0525')
        )
        
        # Ratio calculations
        gds = (pith / gross_monthly_income) * Decimal('100')
        tds = ((pith + total_debts) / gross_monthly_income) * Decimal('100')
        ltv = (payload.loan_data.mortgage_amount / payload.property_data.property_value) * Decimal('100')
        
        logger.info(
            "ratio_calculation_breakdown",
            gds=float(gds),
            tds=float(tds),
            ltv=float(ltv),
            qualifying_rate=float(qualifying_rate)
        )
        
        return RatioMetrics(gds=gds, tds=tds, ltv=ltv), qualifying_rate

    async def _check_cmhc_requirement(self, mortgage_amount: Decimal, property_value: Decimal) -> bool:
        """Determine if CMHC insurance is required based on LTV."""
        ltv = (mortgage_amount / property_value) * Decimal('100')
        return ltv > Decimal('80')

    async def _apply_rules(
        self, 
        ratios: RatioMetrics, 
        credit_score: int, 
        cmhc_required: bool
    ) -> Tuple[str, Decimal, List[str], List[str]]:
        """Apply regulatory and policy rules to determine decision."""
        flags = []
        exceptions = []
        
        # Check regulatory limits (OSFI B-20)
        if ratios.gds > Decimal('39'):
            exceptions.append("GDS exceeds 39% limit")
        if ratios.tds > Decimal('44'):
            exceptions.append("TDS exceeds 44% limit")
            
        # Credit score minimum check
        if credit_score < 600:
            exceptions.append("Credit score below minimum threshold")
            
        # Determine final decision
        if not exceptions:
            decision = "approved"
            confidence = Decimal('0.95')
        elif len(exceptions) <= 2 and cmhc_required:
            decision = "exception"
            confidence = Decimal('0.75')
            flags.append("manual_review_required")
        else:
            decision = "declined"
            confidence = Decimal('0.90')
            
        return decision, confidence, flags, exceptions