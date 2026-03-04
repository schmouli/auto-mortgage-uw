```python
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from .models import UnderwritingApplication, DeclineReason, Condition, OverrideRecord
from .schemas import (
    UnderwritingInputBase,
    UnderwritingResultBase,
    DeclineReasonOut,
    ConditionOut
)
from .exceptions import ApplicationNotFoundError, InvalidOverrideError


class UnderwritingService:
    @staticmethod
    def calculate_qualifying_rate(contract_rate: Decimal) -> Decimal:
        """Calculate OSFI B-20 qualifying rate"""
        option1 = contract_rate + Decimal('0.02')  # +2%
        return max(option1, Decimal('0.0525'))  # Max of option1 or 5.25%

    @staticmethod
    def calculate_gds(
        principal_interest_tax_heating: Decimal,
        condo_fee: Optional[Decimal],
        gross_income: Decimal
    ) -> Decimal:
        """Calculate Gross Debt Service ratio"""
        housing_costs = principal_interest_tax_heating
        if condo_fee:
            housing_costs += condo_fee * Decimal('0.5')
        
        if gross_income == 0:
            return Decimal('0')
            
        return (housing_costs / gross_income).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_tds(
        principal_interest_tax_heating: Decimal,
        condo_fee: Optional[Decimal],
        total_debts: Decimal,
        gross_income: Decimal
    ) -> Decimal:
        """Calculate Total Debt Service ratio"""
        total_obligations = principal_interest_tax_heating + total_debts
        if condo_fee:
            total_obligations += condo_fee * Decimal('0.5')
            
        if gross_income == 0:
            return Decimal('0')
            
        return (total_obligations / gross_income).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_ltv(property_price: Decimal, down_payment: Decimal) -> Decimal:
        """Calculate Loan-to-Value ratio"""
        if property_price == 0:
            return Decimal('0')
        return ((property_price - down_payment) / property_price).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

    @staticmethod
    def get_cmhc_rules(ltv: Decimal, property_price: Decimal) -> Tuple[bool, Decimal]:
        """Determine CMHC requirement and premium based on LTV and property price"""
        # Determine minimum down payment percentage based on price
        if property_price <= Decimal('500000'):
            min_down_percent = Decimal('0.05')
        elif property_price <= Decimal('1000000'):
            # 5% on first $500K + 10% on remainder
            min_down = Decimal('25000') + (property_price - Decimal('500000')) * Decimal('0.10')
            min_down_percent = min_down / property_price
        elif property_price <= Decimal('1500000'):
            min_down_percent = Decimal('0.10')
        else:
            min_down_percent = Decimal('0.20')

        min_down_amount = (property_price * min_down_percent).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # If down payment is less than required, CMHC is needed
        cmhc_required = down_payment < min_down_amount
        
        # Calculate premium only if CMHC is required
        if not cmhc_required:
            return False, Decimal('0')
            
        ltv_percent = ltv * 100
        if ltv_percent <= Decimal('80'):
            return True, Decimal('0')  # No premium for LTV <= 80%
        elif ltv_percent <= Decimal('85'):
            return True, Decimal('0.0280')
        elif ltv_percent <= Decimal('90'):
            return True, Decimal('0.0310')
        elif ltv_percent <= Decimal('95'):
            return True, Decimal('0.0400')
        else:
            # LTV over 95% should be declined
            return True, Decimal('0')

    @staticmethod
    def calculate_max_mortgage(
        gross_income: Decimal,
        qualifying_rate: Decimal,
        property_tax_monthly: Decimal,
        heating_cost_monthly: Decimal,
        condo_fee_monthly: Optional[Decimal],
        total_debts_monthly: Decimal
    ) -> Decimal:
        """Calculate maximum mortgage based on qualifying rate"""
        # GDS limit: 39% of gross income for housing costs
        gds_limit = gross_income * Decimal('0.39')
        
        # TDS limit: 44% of gross income for all obligations
        tds_limit = gross_income * Decimal('0.44')
        
        # Housing costs without mortgage payment
        base_housing_costs = property_tax_monthly + heating_cost_monthly
        if condo_fee_monthly:
            base_housing_costs += condo_fee_monthly * Decimal('0.5')
            
        # Maximum monthly mortgage payment under GDS
        max_monthly_gds = gds_limit - base_housing_costs
        
        # All other obligations for TDS
        other_obligations = total_debts_monthly
        if condo_fee_monthly:
            other_obligations += condo_fee_monthly * Decimal('0.5')
            
        # Maximum monthly mortgage payment under TDS
        max_monthly_tds = tds_limit - other_obligations
        
        # Take the lesser of both limits
        max_monthly_payment = min(max_monthly_gds, max_monthly_tds)
        
        # Convert to annual and then to maximum mortgage using qualifying rate
        if qualifying_rate == 0:
            return Decimal('0')
            
        annual_payment = max_monthly_payment * 12
        # Simple calculation: Principal + Interest = Payment => Principal = Payment / Rate
        # This is simplified; actual mortgage calculations would use amortization formula
        max_mortgage = (annual_payment / qualifying_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return max_mortgage if max_mortgage > 0 else Decimal('0')

    @classmethod
    async def run_underwriting(cls, db: AsyncSession, data: UnderwritingInputBase) -> UnderwritingResultBase:
        """Run complete underwriting analysis"""
        # Calculate qualifying rate
        qualifying_rate = cls.calculate_qualifying_rate(data.contract_rate)
        
        # Calculate PITH (Principal + Interest + Tax + Heating) using qualifying rate
        # For this calculation we'll approximate P+I as a function of loan amount and rate
        # In reality, this would require iterative calculation or lookup tables
        loan_amount = data.property_price - data.down_payment
        monthly_interest = (loan_amount * qualifying_rate / 12).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        pith = monthly_interest + data.property_tax_monthly + data.heating_cost_monthly
        
        # Calculate ratios
        gds_ratio = cls.calculate_gds(pith, data.condo_fee_monthly, data.gross_monthly_income)
        tds_ratio = cls.calculate_tds(
            pith, data.condo_fee_monthly, data.total_debts_monthly, data.gross_monthly_income
        )
        ltv_ratio = cls.calculate_ltv(data.property_price, data.down_payment)
        
        # Determine CMHC requirements
        cmhc_required, cmhc_premium_rate = cls.get_cmhc_rules(ltv_ratio, data.property_price)
        cmhc_premium_amount = None
        if cmhc_required and cmhc_premium_rate > 0:
            loan_without_insurance = data.property_price - data.down_payment
            cmhc_premium_amount = (
                loan_without_insurance * cmhc_premium_rate
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Calculate maximum mortgage
        max_mortgage = cls.calculate_max_mortgage(
            data.gross_monthly_income,
            qualifying_rate,
            data.property_tax_monthly,
            data.heating_cost_monthly,
            data.condo_fee_monthly,
            data.total_debts_monthly
        )
        
        # Check stress test
        stress_test_passed = qualifying_rate >= data.contract_rate
        
        # Determine qualification
        decline_reasons = []
        conditions = []
        
        # Check GDS (max 39%)
        if gds_ratio > Decimal('0.39'):
            decline_reasons.append({
                "reason_code": "HIGH_GDS",
                "description": "Gross Debt Service ratio exceeds maximum of 39%"
            })
        
        # Check TDS (max 44%)
        if tds_ratio > Decimal('0.44'):
            decline_reasons.append({
                "reason_code": "HIGH_TDS",
                "description": "Total Debt Service ratio exceeds maximum of 44%"
            })
        
        # Check LTV limits
        ltv_percent = ltv_ratio * 100
        if ltv_percent > Decimal('95'):
            decline_reasons.append({
                "reason_code": "HIGH_LTV",
                "description": "Loan to Value ratio exceeds maximum of 95%"
            })
        
        # Check stress test
        if not stress_test_passed:
            decline_reasons.append({
                "reason_code": "STRESS_TEST_FAIL",
                "description": "Failed OSFI B-20 stress test"
            })
        
        # Determine decision
        if len(decline_reasons) == 0:
            qualifies = True
            decision = "APPROVED"
        elif len(decline_reasons) <= 2 and max_mortgage > 0:
            qualifies = False
            decision = "CONDITIONAL"
            conditions.append({
                "condition_text": "Reduce loan amount to meet debt service ratios",
                "is_met": False
            })
        else:
            qualifies = False
            decision = "DECLINED"
        
        return UnderwritingResultBase(
            qualifies=qualifies,
            decision=decision,
            gds_ratio=gds_ratio,
            tds_ratio=tds_ratio,
            ltv_ratio=ltv_ratio,
            cmhc_required=cmhc_required,
            cmhc_premium_amount=cmhc_premium_amount,
            qualifying_rate=qualifying_rate,
            max_mortgage=max_mortgage,
            decline_reasons=[DeclineReasonOut(**r) for r in decline_reasons],
            conditions=[ConditionOut(**c) for c in conditions],
            stress_test_passed=stress_test_passed
        )

    @classmethod
    async def evaluate_and_save(
        cls, 
        db: AsyncSession, 
        application_id: str, 
        data: UnderwritingInputBase,
        changed_by: str
    ) -> UnderwritingResultBase:
        """Run underwriting evaluation and save results"""
        result = await cls.run_underwriting(db, data)
        
        # Create or update application record
        stmt = select(UnderwritingApplication).where(
            UnderwritingApplication.application_id == application_id
        )
        result_db = await db.execute(stmt)
        application = result_db.scalar_one_or_none()
        
        if not application:
            application = UnderwritingApplication(
                application_id=application_id,
                changed_by=changed_by
            )
            db.add(application)
        
        # Update application fields
        application.gross_monthly_income = data.gross_monthly_income
        application.property_tax_monthly = data.property_tax_monthly
        application.heating_cost_monthly = data.heating_cost_monthly
        application.condo_fee_monthly = data.condo_fee_monthly
        application.total_debts_monthly = data.total_debts_monthly
        application.property_price = data.property_price
        application.down_payment = data.down_payment
        application.contract_rate = data.contract_rate
        
        application.qualifies = result.qualifies
        application.decision = result.decision
        application.gds_ratio = result.gds_ratio
        application.tds_ratio = result.tds_ratio
        application.ltv_ratio = result.ltv_ratio
        application.cmhc_required = result.cmhc_required
        application.cmhc_premium_amount = result.cmhc_premium_amount
        application.qualifying_rate = result.qualifying_rate
        application.max_mortgage = result.max_mortgage
        application.stress_test_passed = result.stress_test_passed
        application.changed_by = changed_by
        
        await db.flush()
        
        # Clear existing decline reasons and conditions
        await db.execute(
            DeclineReason.__table__.delete().where(
                DeclineReason.application_id == application.id
            )
        )
        await db.execute(
            Condition.__table__.delete().where(
                Condition.application_id == application.id
            )
        )
        
        # Add new decline reasons
        for reason in result.decline_reasons:
            db.add(DeclineReason(
                application_id=application.id,
                reason_code=reason.reason_code,
                description=reason.description
            ))
        
        # Add new conditions
        for condition in result.conditions:
            db.add(Condition(
                application_id=application.id,
                condition_text=condition.condition_text,
                is_met=condition.is_met
            ))
        
        await db.commit()
        await db.refresh(application)
        
        # Re-fetch with relationships
        stmt = select(UnderwritingApplication).where(
            UnderwritingApplication.id == application.id
        ).outerjoin(DeclineReason).outerjoin(Condition)
        
        result_db = await db.execute(stmt)
        application_with_relations = result_db.unique().scalar_one()
        
        return UnderwritingResultBase(
            qualifies=application_with_relations.qualifies,
            decision=application_with_relations.decision,
            gds_ratio=application_with_relations.gds_ratio,
            tds_ratio=application_with_relations.tds_ratio,
            ltv_ratio=application_with_relations.ltv_ratio,
            cmhc_required=application_with_relations.cmhc_required,
            cmhc_premium_amount=application_with_relations.cmhc_premium_amount,
            qualifying_rate=application_with_relations.qualifying_rate,
            max_mortgage=application_with_relations.max_mortgage,
            decline_reasons=[
                DeclineReasonOut(reason_code=r.reason_code, description=r.description)
                for r in application_with_relations.decline_reasons
            ],
            conditions=[
                ConditionOut(condition_text=c.condition_text, is_met=c.is_met)
                for c in application_with_relations.conditions
            ],
            stress_test_passed=application_with_relations.stress_test_passed
        )

    @classmethod
    async def get_result(cls, db: AsyncSession, application_id: str) -> UnderwritingResultBase:
        """Get saved underwriting result"""
        stmt = select(UnderwritingApplication).where(
            UnderwritingApplication.application_id == application_id
        ).outerjoin(DeclineReason).outerjoin(Condition)
        
        result = await db.execute(stmt)
        application = result.unique().scalar_one_or_none()
        
        if not application:
            raise ApplicationNotFoundError(f"Application {application_id} not found")
        
        return UnderwritingResultBase(
            qualifies=application.qualifies,
            decision=application.decision,
            gds_ratio=application.gds_ratio,
            tds_ratio=application.tds_ratio,
            ltv_ratio=application.ltv_ratio,
            cmhc_required=application.cmhc_required,
            cmhc_premium_amount=application.cmhc_premium_amount,
            qualifying_rate=application.qualifying_rate,
            max_mortgage=application.max_mortgage,
            decline_reasons=[
                DeclineReasonOut(reason_code=r.reason_code, description=r.description)
                for r in application.decline_reasons
            ],
            conditions=[
                ConditionOut(condition_text=c.condition_text, is_met=c.is_met)
                for c in application.conditions
            ],
            stress_test_passed=application.stress_test_passed
        )

    @classmethod
    async def create_override(
        cls, 
        db: AsyncSession, 
        application_id: str, 
        override_data: dict,
        user_role: str
    ) -> None:
        """Create admin override record"""
        if user_role != "admin":
            raise InvalidOverrideError("Only administrators can override underwriting decisions")
        
        stmt = select(UnderwritingApplication).where(
            UnderwritingApplication.application_id == application_id
        )
        result = await db.execute(stmt)
        application = result.scalar_one_or_none()
        
        if not application:
            raise ApplicationNotFoundError(f"Application {application_id} not found")
        
        override_record = OverrideRecord(
            application_id=application.id,
            overridden_by=override_data["overridden_by"],
            reason=override_data["reason"]
        )
        
        db.add(override_record)
        await db.commit()
```