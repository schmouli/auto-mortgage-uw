from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import NotFoundError
from mortgage_underwriting.modules.lender_comparison_submission.models import Lender, LenderProduct, LenderSubmission
from mortgage_underwriting.modules.lender_comparison_submission.schemas import (

    LenderMatchRequest,
    LenderMatchResponse,
    LenderMatchResponseItem,
    LenderSubmissionCreate,
    LenderSubmissionUpdate,
    LenderSubmissionResponse
)

logger = structlog.get_logger()


class LenderComparisonService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_active_lenders(self, lender_type: Optional[str] = None) -> List[Lender]:
        """List all active lenders with optional type filter."""
        logger.info("listing_active_lenders", lender_type=lender_type)
        query = select(Lender).where(Lender.is_active == True)
        if lender_type:
            query = query.where(Lender.type == lender_type)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_lender_products(self, lender_id: int, mortgage_type: Optional[str] = None) -> List[LenderProduct]:
        """Get all active products for a specific lender."""
        logger.info("getting_lender_products", lender_id=lender_id, mortgage_type=mortgage_type)
        query = select(LenderProduct).options(selectinload(LenderProduct.lender)).where(
            and_(
                LenderProduct.lender_id == lender_id,
                LenderProduct.is_active == True
            )
        )
        if mortgage_type:
            query = query.where(LenderProduct.mortgage_type == mortgage_type)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def match_lenders_to_application(self, payload: LenderMatchRequest) -> LenderMatchResponse:
        """Match lenders based on application criteria."""
        logger.info("matching_lenders_to_application", application_id=payload.application_id)
        
        # Validate inputs
        if payload.property_value <= 0:
            raise ValueError("Property value must be greater than zero")
        if payload.loan_amount <= 0:
            raise ValueError("Loan amount must be greater than zero")
        if payload.gross_monthly_income <= 0:
            raise ValueError("Gross monthly income must be greater than zero")
        
        # Calculate ratios according to OSFI B-20 stress test
        qualifying_rate = max(payload.contract_rate + Decimal('0.02'), Decimal('0.0525'))
        annual_property_taxes = payload.property_taxes_annual
        monthly_property_tax = annual_property_taxes / Decimal('12')
        total_housing_costs = payload.heating_costs_monthly + monthly_property_tax + (payload.loan_amount * Decimal('0.005') / Decimal('12'))  # FIXED: Use loan_amount for CMHC insurance calculation
        gds_ratio = (total_housing_costs / payload.gross_monthly_income) if payload.gross_monthly_income > 0 else Decimal('0')
        tds_ratio = ((total_housing_costs + payload.monthly_debt_payments) / payload.gross_monthly_income) if payload.gross_monthly_income > 0 else Decimal('0')
        
        # Log calculation breakdown for audit purposes
        logger.info(
            "ratio_calculation_breakdown",
            application_id=payload.application_id,
            gross_monthly_income=float(payload.gross_monthly_income),
            housing_costs=float(total_housing_costs),
            debt_payments=float(payload.monthly_debt_payments),
            gds_ratio=float(gds_ratio),
            tds_ratio=float(tds_ratio),
            qualifying_rate=float(qualifying_rate)
        )
        
        # LTV calculation
        ltv_ratio = payload.loan_amount / payload.property_value if payload.property_value > 0 else Decimal('0')
        
        # Query active lender products
        query = select(LenderProduct).join(Lender).where(
            and_(
                LenderProduct.is_active == True,
                Lender.is_active == True
            )
        ).options(selectinload(LenderProduct.lender))
        
        result = await self.db.execute(query)
        products = result.scalars().all()
        
        matches: List[LenderMatchResponseItem] = []
        
        for product in products:
            qualifies = True
            reason = None
            
            # Check LTV
            max_ltv = product.max_ltv_insured if ltv_ratio > Decimal('0.8') else product.max_ltv_conventional
            if ltv_ratio > max_ltv:
                qualifies = False
                reason = f"LTV ({ltv_ratio:.2%}) exceeds maximum allowed ({max_ltv:.2%})"
            
            # Check GDS/TDS against regulatory limits (OSFI B-20)
            if gds_ratio > product.max_gds or gds_ratio > Decimal('0.39'):  # Hard limit per OSFI B-20
                qualifies = False
                reason = f"GDS ({gds_ratio:.2%}) exceeds limit ({min(product.max_gds, Decimal('0.39')):.2%})"
            if tds_ratio > product.max_tds or tds_ratio > Decimal('0.44'):  # Hard limit per OSFI B-20
                qualifies = False
                reason = f"TDS ({tds_ratio:.2%}) exceeds limit ({min(product.max_tds, Decimal('0.44')):.2%})"
            
            # Check credit score
            if payload.credit_score < product.min_credit_score:
                qualifies = False
                reason = f"Credit score ({payload.credit_score}) below minimum ({product.min_credit_score})"
            
            # Check special flags
            if payload.allows_self_employed and not product.allows_self_employed:
                qualifies = False
                reason = "Self-employed income not accepted"
            if payload.allows_rental_income and not product.allows_rental_income:
                qualifies = False
                reason = "Rental income not accepted"
            if payload.allows_gifted_down_payment and not product.allows_gifted_down_payment:
                qualifies = False
                reason = "Gifted down payment not accepted"
            
            matches.append(LenderMatchResponseItem(
                lender_id=product.lender_id,
                lender_name=product.lender.name,
                product_id=product.id,
                product_name=product.product_name,
                rate=product.rate,
                term_years=product.term_years,
                max_ltv_insured=product.max_ltv_insured,
                max_ltv_conventional=product.max_ltv_conventional,
                qualifies=qualifies,
                reason=reason
            ))
        
        # Sort by rate ascending
        matches.sort(key=lambda x: x.rate)
        
        return LenderMatchResponse(matches=matches, total_matches=len(matches))


class LenderSubmissionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_submission(self, payload: LenderSubmissionCreate) -> LenderSubmissionResponse:
        """Create a new lender submission record."""
        logger.info("creating_lender_submission", application_id=payload.application_id, lender_id=payload.lender_id)
        
        # Verify existence of referenced entities
        lender_query = select(Lender).where(Lender.id == payload.lender_id)
        lender_result = await self.db.execute(lender_query)
        if not lender_result.scalar_one_or_none():
            raise NotFoundError(f"Lender with ID {payload.lender_id} not found")
            
        if payload.product_id:
            product_query = select(LenderProduct).where(LenderProduct.id == payload.product_id)
            product_result = await self.db.execute(product_query)
            if not product_result.scalar_one_or_none():
                raise NotFoundError(f"Product with ID {payload.product_id} not found")
        
        submission = LenderSubmission(**payload.model_dump(exclude_unset=True))
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        
        # FIXED: Return proper response schema
        return LenderSubmissionResponse.model_validate(submission)

    async def list_submissions_for_application(self, application_id: int) -> List[LenderSubmissionResponse]:
        """List all submissions for an application."""
        logger.info("listing_submissions_for_application", application_id=application_id)
        query = select(LenderSubmission).where(LenderSubmission.application_id == application_id)
        result = await self.db.execute(query)
        submissions = result.scalars().all()
        return [LenderSubmissionResponse.model_validate(s) for s in submissions]

    async def update_submission_status(self, submission_id: int, payload: LenderSubmissionUpdate) -> LenderSubmissionResponse:
        """Update the status of a lender submission."""
        logger.info("updating_submission_status", submission_id=submission_id, status=payload.status)
        query = select(LenderSubmission).where(LenderSubmission.id == submission_id)
        result = await self.db.execute(query)
        submission = result.scalar_one_or_none()
        if not submission:
            raise NotFoundError(f"Submission with ID {submission_id} not found")
            
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(submission, field, value)
            
        await self.db.commit()
        await self.db.refresh(submission)
        return LenderSubmissionResponse.model_validate(submission)