from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import NotFoundError
from mortgage_underwriting.modules.lender.models import Lender, LenderProduct, LenderSubmission
from mortgage_underwriting.modules.lender.schemas import (
    LenderCreate,
    LenderUpdate,
    LenderProductCreate,
    LenderProductUpdate,
    LenderSubmissionCreate,
    LenderSubmissionUpdate,
    LenderMatchRequest,
    LenderMatchResult,
    SubmissionPackageRequest
)
from mortgage_underwriting.modules.application.models import MortgageApplication, UnderwritingResult

logger = structlog.get_logger()


class LenderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_lenders(self, skip: int = 0, limit: int = 100) -> List[Lender]:
        logger.info("fetching_lenders", skip=skip, limit=limit)
        result = await self.db.execute(
            select(Lender)
            .where(Lender.is_active == True)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_lender_products(self, lender_id: int, skip: int = 0, limit: int = 100) -> List[LenderProduct]:
        logger.info("fetching_lender_products", lender_id=lender_id, skip=skip, limit=limit)
        result = await self.db.execute(
            select(LenderProduct)
            .where(and_(LenderProduct.lender_id == lender_id, LenderProduct.is_active == True))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def match_lenders(self, payload: LenderMatchRequest) -> List[LenderMatchResult]:
        logger.info("matching_lenders", application_id=payload.application_id)
        
        # Calculate ratios for matching
        gds_numerator = payload.monthly_debts + payload.condo_fees
        gds_ratio = (gds_numerator / payload.gross_monthly_income) * 100 if payload.gross_monthly_income > 0 else Decimal('0')
        
        tds_numerator = payload.monthly_debts + payload.condo_fees
        tds_ratio = (tds_numerator / payload.gross_monthly_income) * 100 if payload.gross_monthly_income > 0 else Decimal('0')
        
        ltv_ratio = payload.ltv_ratio
        
        logger.info(
            "calculated_ratios",
            gds=gds_ratio,
            tds=tds_ratio,
            ltv=ltv_ratio
        )
        
        # Query matching products
        stmt = select(LenderProduct).join(Lender).where(
            and_(
                Lender.is_active == True,
                LenderProduct.is_active == True,
                LenderProduct.max_ltv_insured >= ltv_ratio,
                LenderProduct.max_gds >= gds_ratio,
                LenderProduct.max_tds >= tds_ratio,
                LenderProduct.min_credit_score <= payload.credit_score,
                (LenderProduct.allows_self_employed == True) if payload.is_self_employed else True,
                (LenderProduct.allows_rental_income == True) if payload.has_rental_income else True
            )
        ).order_by(LenderProduct.rate.asc())
        
        result = await self.db.execute(stmt)
        products = result.scalars().all()
        
        matches = []
        for product in products:
            match = LenderMatchResult(
                product_id=product.id,
                lender_id=product.lender_id,
                lender_name=product.lender.name,
                product_name=product.product_name,
                rate=product.rate,
                term_years=product.term_years,
                max_ltv_insured=product.max_ltv_insured,
                max_ltv_conventional=product.max_ltv_conventional,
                max_amortization_insured=product.max_amortization_insured,
                max_amortization_conventional=product.max_amortization_conventional,
                min_credit_score=product.min_credit_score,
                max_gds=product.max_gds,
                max_tds=product.max_tds,
                allows_self_employed=product.allows_self_employed,
                allows_rental_income=product.allows_rental_income,
                allows_gifted_down_payment=product.allows_gifted_down_payment,
                prepayment_privilege_percent=product.prepayment_privilege_percent,
                portability=product.portability,
                assumability=product.assumability,
                lender_conditions=None,
                notes=f"Matched based on LTV: {ltv_ratio}, GDS: {gds_ratio}, TDS: {tds_ratio}"
            )
            matches.append(match)
            
        logger.info("lender_matching_completed", matches_count=len(matches))
        return matches

    async def create_submission(self, payload: LenderSubmissionCreate) -> LenderSubmission:
        logger.info("creating_lender_submission", application_id=payload.application_id, lender_id=payload.lender_id)
        submission = LenderSubmission(**payload.model_dump(exclude_unset=True))
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    async def get_submissions(self, application_id: int, skip: int = 0, limit: int = 100) -> List[LenderSubmission]:
        logger.info("fetching_lender_submissions", application_id=application_id, skip=skip, limit=limit)
        result = await self.db.execute(
            select(LenderSubmission)
            .where(LenderSubmission.application_id == application_id)
            .options(selectinload(LenderSubmission.lender))
            .options(selectinload(LenderSubmission.product))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_submission(self, submission_id: int, payload: LenderSubmissionUpdate) -> LenderSubmission:
        logger.info("updating_lender_submission", submission_id=submission_id)
        result = await self.db.execute(
            select(LenderSubmission)
            .where(LenderSubmission.id == submission_id)
        )
        submission = result.scalar_one_or_none()
        if not submission:
            raise NotFoundError(f"Lender submission with ID {submission_id} not found")
            
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(submission, field, value)
            
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    async def generate_submission_package(self, payload: SubmissionPackageRequest) -> dict:
        logger.info("generating_submission_package", application_id=payload.application_id)
        
        # Fetch related data
        app_result = await self.db.execute(
            select(MortgageApplication)
            .where(MortgageApplication.id == payload.application_id)
        )
        application = app_result.scalar_one_or_none()
        if not application:
            raise NotFoundError(f"Application with ID {payload.application_id} not found")
            
        uw_result = await self.db.execute(
            select(UnderwritingResult)
            .where(UnderwritingResult.id == payload.uw_result_id)
        )
        underwriting = uw_result.scalar_one_or_none()
        if not underwriting:
            raise NotFoundError(f"Underwriting result with ID {payload.uw_result_id} not found")
            
        # Build package
        package = {
            "application": {
                "id": application.id,
                "purchase_price": application.purchase_price,
                "down_payment": application.down_payment,
                "property_address": application.property_address
            },
            "underwriting": {
                "qualifies": underwriting.qualifies,
                "decision": underwriting.decision,
                "gds_ratio": str(underwriting.gds_ratio),
                "tds_ratio": str(underwriting.tds_ratio),
                "ltv_ratio": str(underwriting.ltv_ratio)
            },
            "matched_products": [product.model_dump() for product in payload.matched_products],
            "broker_notes": payload.broker_notes
        }
        
        logger.info("submission_package_generated", application_id=payload.application_id)
        return package