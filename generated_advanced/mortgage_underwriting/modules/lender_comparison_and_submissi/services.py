from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc
from decimal import Decimal
import structlog

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


logger = structlog.get_logger(__name__)


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
            select(Lender)
            .join(LenderProduct)
            .where(and_(
                Lender.is_active == True,
                LenderProduct.is_active == True,
                LenderProduct.mortgage_type == match_request.mortgage_type.value,
                LenderProduct.term_years >= match_request.min_term_years if match_request.min_term_years else True,
                LenderProduct.max_ltv_insured >= match_request.ltv_ratio if match_request.insurance_required else 
                LenderProduct.max_ltv_conventional >= match_request.ltv_ratio
            ))
        )
        matching_lenders = lenders_result.scalars().all()

        # Build match results with scoring
        matches = []
        for lender in matching_lenders:
            try:
                products = await self.get_products_for_lender(lender.id)
                for product in products:
                    # Score based on rate competitiveness and other factors
                    score = 100 - float(product.rate)  # Lower rate = higher score
                    
                    match = MatchResultResponse(
                        lender_id=lender.id,
                        lender_name=lender.name,
                        lender_type=lender.type,
                        product_id=product.id,
                        product_name=product.product_name,
                        rate=float(product.rate),
                        term_years=product.term_years,
                        score=score,
                        notes=product.notes
                    )
                    matches.append(match)
            except ProductNotFoundError:
                # Skip lenders with no matching products
                continue

        # Sort by score descending (best matches first)
        matches.sort(key=lambda x: x.score, reverse=True)
        return matches[:10]  # Return top 10 matches


class LenderSubmissionService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_submission_by_id(self, submission_id: int) -> LenderSubmission:
        """Retrieve a specific submission by ID."""
        result = await self.db.execute(
            select(LenderSubmission).where(LenderSubmission.id == submission_id)
        )
        submission = result.scalar_one_or_none()
        
        if not submission:
            raise SubmissionNotFoundError(f"Submission with ID {submission_id} not found")
            
        return submission

    async def list_submissions(
        self, 
        lender_id: Optional[int] = None, 
        status: Optional[SubmissionStatus] = None,
        skip: int = 0,  # FIXED: Added pagination parameters
        limit: int = 100  # FIXED: Added pagination parameters with reasonable default
    ) -> List[LenderSubmission]:
        """List submissions with optional filtering and pagination."""
        query = select(LenderSubmission)
        
        # Apply filters
        if lender_id:
            query = query.where(LenderSubmission.lender_id == lender_id)
        if status:
            query = query.where(LenderSubmission.status == status)
            
        # Apply pagination
        query = query.offset(skip).limit(min(limit, 100))  # FIXED: Enforce max limit of 100
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_submission(self, submission_data: LenderSubmissionCreateRequest) -> LenderSubmission:
        """Create a new lender submission."""
        submission = LenderSubmission(
            lender_id=submission_data.lender_id,
            lender_rate_id=submission_data.lender_rate_id,
            application_id=submission_data.application_id,
            reference_number=submission_data.reference_number,
            notes=submission_data.notes
        )
        
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        
        logger.info("lender_submission_created", submission_id=submission.id)
        return submission

    async def update_submission_status(
        self, 
        submission_id: int, 
        status_update: LenderSubmissionUpdateRequest
    ) -> LenderSubmission:
        """Update the status of a submission."""
        submission = await self.get_submission_by_id(submission_id)
        
        # Validate status transition
        if submission.status == SubmissionStatus.DECLINED and status_update.status != SubmissionStatus.COUNTERED:
            raise InvalidSubmissionStatusError("Cannot change status of declined submission except to countered")
            
        submission.status = status_update.status
        if status_update.responded_at:
            submission.responded_at = status_update.responded_at
            
        await self.db.commit()
        await self.db.refresh(submission)
        
        logger.info("lender_submission_updated", submission_id=submission.id, new_status=submission.status)
        return submission


class SubmissionPackageGenerator:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def generate_package(self, submission_id: int) -> Dict[str, Any]:
        """Generate submission package data for a lender."""
        submission = await LenderSubmissionService(self.db).get_submission_by_id(submission_id)
        
        # In a real implementation, this would fetch application data and format it
        # according to the lender's requirements
        package_data = {
            "submission_id": submission.id,
            "lender_id": submission.lender_id,
            "application_id": submission.application_id,
            "reference_number": submission.reference_number,
            "generated_at": datetime.utcnow().isoformat(),
            "status": submission.status
        }
        
        # Update submission with package data
        submission.package_data = str(package_data)
        await self.db.commit()
        
        logger.info("submission_package_generated", submission_id=submission_id)
        return package_data
```

```