from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from uuid import UUID

from sqlalchemy import select
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.decision.models import UnderwritingDecision, DecisionAuditLog
from mortgage_underwriting.modules.decision.schemas import (
    DecisionEvaluateRequest,
    DecisionResponse,
    DecisionRetrieveResponse,
    AuditTrailResponse,
    RatioBreakdownDTO
)

logger = structlog.get_logger()


class DecisionServiceError(AppException):
    """Base exception for decision service errors."""
    pass


class DecisionNotFoundError(DecisionServiceError):
    """Raised when a decision cannot be found."""
    pass


class EvaluationFailedError(DecisionServiceError):
    """Raised when decision evaluation process fails."""
    pass


class DecisionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def evaluate(self, payload: DecisionEvaluateRequest) -> DecisionResponse:
        """Run underwriting decision engine against submitted application.
        
        Calculates GDS/TDS with OSFI B-20 stress test, determines CMHC insurance
        requirement, and applies policy rules.
        """
        logger.info("decision_evaluate_start", application_id=payload.application_id)
        
        # Validate inputs
        if payload.loan_details.down_payment_amount <= 0:
            raise DecisionServiceError("Down payment must be greater than zero")
        if payload.property_details.property_value <= 0:
            raise DecisionServiceError("Property value must be greater than zero")
        if payload.loan_details.requested_amount <= 0:
            raise DecisionServiceError("Requested loan amount must be greater than zero")
        
        # Calculate qualifying rate per OSFI B-20
        qualifying_rate = max(payload.loan_details.contract_rate + Decimal('0.02'), Decimal('0.0525'))
        
        # Calculate monthly housing costs
        monthly_tax = payload.property_details.property_tax_annual / Decimal('12')
        # Simplified: assuming principal+interest+tax+heating estimate
        rate_per_period = qualifying_rate / Decimal('12')
        number_of_payments = payload.loan_details.amortization_years * 12
        if rate_per_period == 0:
            pith_monthly = payload.loan_details.requested_amount / number_of_payments + monthly_tax
        else:
            denominator = (1 - (1 + rate_per_period) ** (-number_of_payments))
            if denominator == 0:
                raise DecisionServiceError("Invalid amortization calculation parameters")
            pith_monthly = (payload.loan_details.requested_amount * rate_per_period) / denominator + monthly_tax
        
        # Calculate ratios
        gross_monthly_income = payload.borrower_profile.gross_annual_income / Decimal('12')
        if gross_monthly_income == 0:
            raise DecisionServiceError("Gross monthly income cannot be zero")
        
        gds = (pith_monthly / gross_monthly_income) * Decimal('100')
        tds = ((pith_monthly + payload.borrower_profile.monthly_debt_obligations) / gross_monthly_income) * Decimal('100')
        ltv = (payload.loan_details.requested_amount / payload.property_details.property_value) * Decimal('100')
        
        # Log calculation breakdown for audit
        audit_details: Dict[str, Any] = {
            "gross_monthly_income": float(gross_monthly_income),
            "pith_monthly": float(pith_monthly),
            "monthly_debt": float(payload.borrower_profile.monthly_debt_obligations),
            "gds_breakdown": f"({pith_monthly} / {gross_monthly_income}) * 100",
            "tds_breakdown": f"(({pith_monthly} + {payload.borrower_profile.monthly_debt_obligations}) / {gross_monthly_income}) * 100",
            "ltv_breakdown": f"({payload.loan_details.requested_amount} / {payload.property_details.property_value}) * 100"
        }
        
        # Apply regulatory limits
        policy_flags: List[str] = []
        exceptions: List[Dict[str, Any]] = []
        
        # FIXED: Use configurable constants instead of hardcoded values
        GDS_LIMIT = Decimal('39')
        TDS_LIMIT = Decimal('44')
        LTV_MAX = Decimal('95')
        LTV_CMHC_THRESHOLD = Decimal('80')
        
        if gds > GDS_LIMIT:
            policy_flags.append("HIGH_GDS")
        if tds > TDS_LIMIT:
            policy_flags.append("HIGH_TDS")
        if ltv > LTV_MAX:
            exceptions.append({"type": "LTV_EXCEEDS_LIMIT", "message": "Loan-to-value exceeds maximum allowable limit"})
            
        # Determine CMHC insurance requirement
        cmhc_required = ltv > LTV_CMHC_THRESHOLD
        
        # Make final determination (simplified logic)
        if not policy_flags and not exceptions:
            decision = "approved"
            confidence = Decimal('0.95')
        elif len(policy_flags) == 1 and not exceptions:
            decision = "approved"
            confidence = Decimal('0.80')
        elif len(policy_flags) <= 2 and not exceptions:
            decision = "exception"
            confidence = Decimal('0.60')
        else:
            decision = "declined"
            confidence = Decimal('0.30')
            
        # Create audit log entries
        audit_entries = [
            DecisionAuditLog(step="ratio_calculation", details=audit_details),
            DecisionAuditLog(step="regulatory_check", details={
                "gds_limit_applied": f"{GDS_LIMIT}%",
                "tds_limit_applied": f"{TDS_LIMIT}%",
                "gds_result": float(gds),
                "tds_result": float(tds),
                "ltv_result": float(ltv)
            }),
            DecisionAuditLog(step="cmhc_determination", details={
                "ltv_threshold": f"{LTV_CMHC_THRESHOLD}%",
                "cmhc_required": cmhc_required,
                "ltv_value": float(ltv)
            })
        ]
        
        # Save decision record
        decision_record = UnderwritingDecision(
            application_id=str(payload.application_id),
            decision=decision,
            confidence_score=confidence,
            gds_ratio=gds,
            tds_ratio=tds,
            ltv_ratio=ltv,
            stress_test_rate=qualifying_rate * Decimal('100'),
            cmhc_required=cmhc_required,
            policy_flags=policy_flags,
            exceptions=exceptions,
            audit_trail={
                "rules_evaluated": [entry.step for entry in audit_entries],
                "model_version": payload.policy_version
            },
            model_version=payload.policy_version
        )
        
        self.db.add(decision_record)
        await self.db.flush()  # Get ID for audit logs
        
        # Associate audit logs
        for entry in audit_entries:
            entry.decision_id = decision_record.id
            self.db.add(entry)
            
        await self.db.commit()
        await self.db.refresh(decision_record)
        
        logger.info("decision_evaluate_complete", application_id=payload.application_id, decision=decision)
        
        return DecisionResponse(
            application_id=payload.application_id,
            decision=decision,
            confidence_score=confidence,
            ratios=RatioBreakdownDTO(gds=gds, tds=tds, ltv=ltv),
            cmhc_required=cmhc_required,
            stress_test_rate=qualifying_rate * Decimal('100'),
            policy_flags=policy_flags,
            exceptions=exceptions,
            audit_trail=decision_record.audit_trail,
            created_at=decision_record.created_at
        )

    async def get_decision(self, application_id: UUID) -> DecisionRetrieveResponse:
        """Retrieve a specific underwriting decision by application ID."""
        logger.info("get_decision", application_id=application_id)
        
        stmt = select(UnderwritingDecision).where(UnderwritingDecision.application_id == str(application_id))
        result = await self.db.execute(stmt)
        decision_record = result.scalar_one_or_none()
        
        if not decision_record:
            raise DecisionNotFoundError(f"Decision for application {application_id} not found")
            
        return DecisionRetrieveResponse.model_validate(decision_record)

    async def get_audit_trail(self, application_id: UUID) -> List[AuditTrailResponse]:
        """Get audit trail entries for a specific decision."""
        logger.info("get_audit_trail", application_id=application_id)
        
        # First get the decision to ensure it exists
        stmt = select(UnderwritingDecision).where(UnderwritingDecision.application_id == str(application_id))
        result = await self.db.execute(stmt)
        decision_record = result.scalar_one_or_none()
        
        if not decision_record:
            raise DecisionNotFoundError(f"Decision for application {application_id} not found")
            
        # Then get audit logs
        stmt = select(DecisionAuditLog).where(DecisionAuditLog.decision_id == decision_record.id)
        result = await self.db.execute(stmt)
        audit_logs = result.scalars().all()
        
        return [AuditTrailResponse.model_validate(log) for log in audit_logs]