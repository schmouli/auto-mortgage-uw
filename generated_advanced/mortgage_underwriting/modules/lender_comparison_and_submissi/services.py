```python
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc
from decimal import Decimal
import logging

from .models import Lender, LenderProduct, LenderSubmission, SubmissionStatus
from .schemas import (
    LenderMatchRequest,
    MatchResultResponse,
    LenderSubmissionCreateRequest,
    LenderSubmissionUpdateRequest
)
from .exceptions import (
    LenderNotFoundError,
    ProductNotFoundError,
    SubmissionNotFoundError,
    InvalidSubmissionStatusError
)


logger = logging.getLogger(__name__)


class LenderMatcherService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_all_active_lenders(self) -> List[Lender]:
        """Retrieve all active lenders."""
        result = await self.db.execute(
            select(Lender).where(Lender.is_active == True)
        )
        return result.scalars().all()

    async def get_products_for_lender(self, lender_id: int) -> List[LenderProduct]:
        """Get all active products for a specific lender."""
        result = await self.db.execute(
            select(LenderProduct)
            .where(and_(LenderProduct.lender_id == lender_id, LenderProduct.is_active == True))
        )
        products = result.scalars().all()
        
        if not products:
            raise ProductNotFoundError(f"No active products found for lender {lender_id}")
            
        return products

    async def match_lenders_to_application(
        self, 
        match_request: LenderMatchRequest
    ) -> List[MatchResultResponse]:
        """
        Match lenders based on application criteria and return ranked list by rate.
        Filters out products that don't meet basic thresholds.
        """
        # First get all active lenders and their products
        lenders_result = await self.db.execute(
            select(Lender).where(Lender.is_active == True)
        )
        lenders = lenders_result.scalars().all()
        
        matched_results = []
        
        for lender in lenders:
            products_result = await self.db.execute(
                select(LenderProduct)
                .where(and_(
                    LenderProduct.lender_id == lender.id,
                    LenderProduct.is_active == True,
                    LenderProduct.min_credit_score <= match_request.credit_score,
                    LenderProduct.max_gds >= match_request.gds_ratio,
                    LenderProduct.max_tds >= match_request.tds_ratio
                ))
            )
            products = products_result.scalars().all()
            
            for product in products:
                # Determine applicable LTV limit based on insurance status
                max_ltv = product.max_ltv_insured if match_request.ltv_ratio > 80 else product.max_ltv_conventional
                
                # Skip if LTV exceeds limit
                if match_request.ltv_ratio > max_ltv:
                    continue
                    
                # Check employment/income flags
                if match_request.is_self_employed and not product.allows_self_employed:
                    continue
                if match_request.has_rental_income and not product.allows_rental_income:
                    continue
                if match_request.gifted_down_payment and not product.allows_gifted_down_payment:
                    continue
                
                # Build flags for special conditions
                flags = []
                if product.prepayment_privilege_percent and product.prepayment_privilege_percent > 0:
                    flags.append(f"Prepayment up to {product.prepayment_privilege_percent}%")
                if product.portability:
                    flags.append("Portable")
                if product.assumability:
                    flags.append("Assumable")
                
                matched_results.append(MatchResultResponse(
                    product_id=product.id,
                    lender_id=lender.id,
                    product_name=product.product_name,
                    lender_name=lender.name,
                    rate=product.rate,
                    term_years=product.term_years,
                    max_ltv_insured=product.max_ltv_insured,
                    max_ltv_conventional=product.max_ltv_conventional,
                    max_amortization_insured=product.max_amortization_insured,
                    max_amortization_conventional=product.max_amortization_conventional,
                    flags=flags
                ))
        
        # Sort by lowest rate first
        matched_results.sort(key=lambda x: x.rate)
        
        logger.info(f"Found {len(matched_results)} matching products for application {match_request.application_id}")
        return matched_results


class SubmissionPackageGenerator:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def generate_package(self, application_id: int) -> Dict[str, Any]:
        """
        Generate submission package including summary, UW results, documents, FINTRAC info, and broker notes.
        This would integrate with other modules like Applications, Documents, etc.
        For now we'll provide a placeholder structure.
        """
        # Placeholder implementation - in real system this would pull from multiple sources
        
        package = {
            "summary": {
                "application_id": application_id,
                "submission_date": "TBD",
                "borrower_info": {},
                "property_info": {},
                "loan_details": {}
            },
            "uw_results": {
                "credit_check": "Pending",
                "income_verification": "Pending",
                "asset_verification": "Pending"
            },
            "documents": [
                {"name": "Application Form", "status": "Included"},
                {"name": "Credit Report", "status": "Pending"},
                {"name": "Income Verification", "status": "Pending"}
            ],
            "fintrac": {
                "transaction_type": "Mortgage",
                "amount": "To be confirmed",
                "reporting_required": True
            },
            "broker_notes": "Please review terms carefully before submitting."
        }
        
        logger.debug(f"Generated submission package for application {application_id}")
        return package


class LenderSubmissionService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_submission(self, submission_data: LenderSubmissionCreateRequest) -> LenderSubmission:
        """Create a new lender submission record."""
        submission = LenderSubmission(**submission_data.dict(exclude_unset=True))
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        
        logger.info(f"Created submission {submission.id} for application {submission.application_id}")
        return submission

    async def update_submission_status(
        self, 
        submission_id: int, 
        update_data: LenderSubmissionUpdateRequest
    ) -> LenderSubmission:
        """Update the status and details of an existing submission."""
        result = await self.db.execute(
            select(LenderSubmission).where(LenderSubmission.id == submission_id)
        )
        submission = result.scalar_one_or_none()
        
        if not submission:
            raise SubmissionNotFoundError(f"Submission with ID {submission_id} not found")
        
        # Validate status transition
        valid_transitions = {
            SubmissionStatus.PENDING: [SubmissionStatus.APPROVED, SubmissionStatus.DECLINED, SubmissionStatus.COUNTERED],
            SubmissionStatus.APPROVED: [],
            SubmissionStatus.DECLINED: [],
            SubmissionStatus.COUNTERED: [SubmissionStatus.APPROVED, SubmissionStatus.DECLINED]
        }
        
        current_status = submission.status
        new_status = update_data.status
        
        if new_status != current_status and new_status not in valid_transitions.get(current_status, []):
            raise InvalidSubmissionStatusError(
                f"Cannot change status from {current_status.value} to {new_status.value}"
            )
        
        # Apply updates
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(submission, field, value)
            
        await self.db.commit()
        await self.db.refresh(submission)
        
        logger.info(f"Updated submission {submission_id} status to {new_status.value}")
        return submission

    async def get_submissions_for_application(self, application_id: int) -> List[LenderSubmission]:
        """Retrieve all submissions for a given application."""
        result = await self.db.execute(
            select(LenderSubmission)
            .where(LenderSubmission.application_id == application_id)
            .order_by(desc(LenderSubmission.submitted_at))
        )
        return result.scalars().all()
```