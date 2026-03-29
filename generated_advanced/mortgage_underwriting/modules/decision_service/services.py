from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from uuid import UUID

from sqlalchemy import select
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.decision.models import DecisionRecord
from mortgage_underwriting.modules.decision.schemas import (
    DecisionEvaluateRequest,
    DecisionEvaluateResponse,
    RatioBreakdown,
    ExceptionItem
)

logger = structlog.get_logger()


class DecisionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def evaluate(self, payload: DecisionEvaluateRequest) -> DecisionEvaluateResponse:
        """Execute deterministic underwriting decision engine.
        
        Applies OSFI B-20 stress test and calculates GDS/TDS/LTV ratios.
        """
        logger.info("decision_evaluate_start", application_id=payload.application_id)
        
        # Calculate stress test rate per OSFI B-20
        stress_rate = max(payload.loan_data.contract_rate + Decimal('2'), Decimal('5.25'))
        
        # Calculate monthly payments using standard formula
        monthly_interest = payload.loan_data.contract_rate / Decimal('12') / Decimal('100')
        stress_monthly_interest = stress_rate / Decimal('12') / Decimal('100')
        n_payments = payload.loan_data.amortization_years * 12
        
        # Standard mortgage payment calculation
        if monthly_interest == 0:
            monthly_payment = payload.loan_data.mortgage_amount / Decimal(n_payments)
        else:
            monthly_payment = payload.loan_data.mortgage_amount * (
                monthly_interest * (1 + monthly_interest) ** n_payments
            ) / ((1 + monthly_interest) ** n_payments - 1)
            
        # Stress-tested payment
        if stress_monthly_interest == 0:
            stress_payment = payload.loan_data.mortgage_amount / Decimal(n_payments)
        else:
            stress_payment = payload.loan_data.mortgage_amount * (
                stress_monthly_interest * (1 + stress_monthly_interest) ** n_payments
            ) / ((1 + stress_monthly_interest) ** n_payments - 1)
        
        # Calculate ratios with proper rounding
        gross_monthly_income = payload.borrower_data.gross_annual_income / Decimal('12')
        total_debt_payments = payload.borrower_data.monthly_non_housing_debt + sum(
            d.monthly_payment for d in payload.existing_debts
        )
        
        # Round ratios to two decimal places as per financial standards
        gds = (stress_payment / gross_monthly_income) * Decimal('100')
        gds = gds.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        tds = ((stress_payment + total_debt_payments) / gross_monthly_income) * Decimal('100')
        tds = tds.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        ltv = (payload.loan_data.mortgage_amount / payload.property_data.property_value) * Decimal('100')
        ltv = ltv.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Apply regulatory limits
        policy_flags = []
        exceptions = []
        
        if gds > Decimal('39'):
            policy_flags.append("gds_limit_exceeded")
        if tds > Decimal('44'):
            policy_flags.append("tds_limit_exceeded")
        if ltv > Decimal('95'):
            exceptions.append({
                "code": "ltv_too_high",
                "message": "Maximum LTV exceeded (95%)",
                "severity": "error"
            })
        
        # Determine CMHC insurance requirement
        cmhc_required = ltv > Decimal('80')
        
        # Final decision logic
        if gds <= Decimal('39') and tds <= Decimal('44') and ltv <= Decimal('95'):
            decision = "approved"
            confidence = Decimal('0.95')
        elif gds <= Decimal('42') and tds <= Decimal('47') and ltv <= Decimal('95'):
            decision = "conditional"
            confidence = Decimal('0.75')
            policy_flags.append("marginal_approval")
        else:
            decision = "declined"
            confidence = Decimal('0.90')
            
        # Prepare audit trail
        audit_trail = {
            "rules_evaluated": [
                "osfi_b20_stress_test",
                "gds_limit_check",
                "tds_limit_check",
                "ltv_limit_check",
                "cmhc_insurance_check"
            ],
            "timestamp": str(datetime.utcnow()),
            "model_version": "1.0.0"
        }
        
        # Create database record
        record = DecisionRecord(
            application_id=payload.application_id,
            decision=decision,
            confidence_score=confidence,
            gds_ratio=gds,
            tds_ratio=tds,
            ltv_ratio=ltv,
            cmhc_required=cmhc_required,
            stress_test_rate=stress_rate,
            policy_flags=policy_flags,
            exceptions=exceptions,
            audit_trail=audit_trail
        )
        
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        
        logger.info("decision_evaluate_complete", 
                   application_id=payload.application_id,
                   decision=decision,
                   gds=float(gds),
                   tds=float(tds))
        
        return DecisionEvaluateResponse(
            application_id=payload.application_id,
            decision=decision,
            confidence_score=confidence,
            ratios=RatioBreakdown(gds=gds, tds=tds, ltv=ltv),
            cmhc_required=cmhc_required,
            stress_test_rate=stress_rate,
            policy_flags=policy_flags,
            exceptions=[ExceptionItem(**e) for e in exceptions],
            audit_trail=audit_trail
        )

    async def get_decision(self, application_id: UUID) -> DecisionRecord:
        """Retrieve a decision record by application ID."""
        stmt = select(DecisionRecord).where(DecisionRecord.application_id == application_id)
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        
        if not record:
            raise AppException(f"No decision found for application {application_id}")
            
        return record

    async def get_audit_trail(self, application_id: UUID) -> Dict[str, Any]:
        """Get full audit trail for a decision."""
        record = await self.get_decision(application_id)
        return record.audit_trail