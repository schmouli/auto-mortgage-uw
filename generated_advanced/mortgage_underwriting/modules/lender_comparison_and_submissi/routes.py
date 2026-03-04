```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from database.session import get_db
from .services import LenderMatcherService, LenderSubmissionService, SubmissionPackageGenerator
from .schemas import (
    LenderResponse,
    LenderWithProductsResponse,
    LenderProductResponse,
    LenderSubmissionResponse,
    LenderSubmissionCreateRequest,
    LenderSubmissionUpdateRequest,
    LenderMatchRequest,
    MatchResultResponse,
    ApplicationMatchesResponse,
    SubmissionsListResponse
)
from .exceptions import (
    LenderNotFoundError,
    ProductNotFoundError,
    SubmissionNotFoundError,
    InvalidSubmissionStatusError
)

router = APIRouter(prefix="/lenders", tags=["Lender Management"])

# Dependency injection helpers
async def get_matcher_service(db: AsyncSession = Depends(get_db)) -> LenderMatcherService:
    return LenderMatcherService(db)

async def get_submission_service(db: AsyncSession = Depends(get_db)) -> LenderSubmissionService:
    return LenderSubmissionService(db)

async def get_package_generator(db: AsyncSession = Depends(get_db)) -> SubmissionPackageGenerator:
    return SubmissionPackageGenerator(db)


@router.get("/", response_model=List[LenderResponse], summary="List Active Lenders")
async def list_lenders(service: LenderMatcherService = Depends(get_matcher_service)):
    """
    Retrieve a list of all currently active lenders.
    
    Returns a collection of lender information including name, type, contact details,
    and operational status.
    """
    try:
        lenders = await service.get_all_active_lenders()
        return lenders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{lender_id}/products", response_model=LenderWithProductsResponse, summary="Get Lender Products")
async def get_lender_products(
    lender_id: int = Path(..., gt=0, description="Unique identifier of the lender"),
    service: LenderMatcherService = Depends(get_matcher_service)
):
    """
    Retrieve detailed information about a specific lender along with its active products.
    
    Includes complete lender profile plus associated lending products with terms,
    rates, and eligibility criteria.
    """
    try:
        # Fetch lender details
        result = await service.db.execute(
            service.db.query(Lender).filter(Lender.id == lender_id)
        )
        lender = result.scalar_one_or_none()
        
        if not lender:
            raise LenderNotFoundError(f"Lender with ID {lender_id} not found")
            
        # Fetch products
        products = await service.get_products_for_lender(lender_id)
        
        # Construct response
        response_data = {
            "id": lender.id,
            "name": lender.name,
            "type": lender.type,
            "is_active": lender.is_active,
            "logo_url": lender.logo_url,
            "submission_email": lender.submission_email,
            "notes": lender.notes,
            "created_at": lender.created_at,
            "updated_at": lender.updated_at,
            "products": [
                {
                    "id": p.id,
                    "lender_id": p.lender_id,
                    "product_name": p.product_name,
                    "mortgage_type": p.mortgage_type,
                    "term_years": p.term_years,
                    "rate": p.rate,
                    "rate_type": p.rate_type,
                    "max_ltv_insured": p.max_ltv_insured,
                    "max_ltv_conventional": p.max_ltv_conventional,
                    "max_amortization_insured": p.max_amortization_insured,
                    "max_amortization_conventional": p.max_amortization_conventional,
                    "min_credit_score": p.min_credit_score,
                    "max_gds": p.max_gds,
                    "max_tds": p.max_tds,
                    "allows_self_employed": p.allows_self_employed,
                    "allows_rental_income": p.allows_rental_income,
                    "allows_gifted_down_payment": p.allows_gifted_down_payment,
                    "prepayment_privilege_percent": p.prepayment_privilege_percent,
                    "portability": p.portability,
                    "assumability": p.assumability,
                    "is_active": p.is_active,
                    "effective_date": p.effective_date,
                    "expiry_date": p.expiry_date,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at
                } for p in products
            ]
        }
        
        return LenderWithProductsResponse(**response_data)
    except LenderNotFoundError:
        raise HTTPException(status_code=404, detail="Lender not found")
    except ProductNotFoundError:
        raise HTTPException(status_code=404, detail="No active products found for this lender")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match", response_model=ApplicationMatchesResponse, summary="Match Lenders to Application")
async def match_lenders(
    match_request: LenderMatchRequest,
    service: LenderMatcherService = Depends(get_matcher_service)
):
    """
    Find suitable lenders based on application parameters such as LTV, GDS/TDS ratios, and credit score.
    
    The system evaluates all active lenders and returns a ranked list of compatible products
    sorted by interest rate (lowest first).
    """
    try:
        matches = await service.match_lenders_to_application(match_request)
        return ApplicationMatchesResponse(matches=matches)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching failed: {str(e)}")


@router.get("/applications/{application_id}/lender-matches", response_model=ApplicationMatchesResponse, summary="Get Saved Matches")
async def get_saved_matches(
    application_id: int = Path(..., gt=0, description="Unique identifier of the mortgage application"),
    service: LenderMatcherService = Depends(get_matcher_service)
):
    """
    Retrieve previously computed lender matches for a specific application.
    
    Useful for reviewing past recommendations without re-running the matching algorithm.
    """
    # In practice, you might store these in a separate table/cache
    # For now we just run the matcher again with stored parameters
    # This assumes there's a way to retrieve original app data
    
    # Placeholder: simulate retrieving match parameters from application
    # In reality this would come from application data storage
    
    raise HTTPException(status_code=501, detail="Not implemented - requires integration with Applications module")


@router.post("/applications/{application_id}/submissions", response_model=LenderSubmissionResponse, summary="Create Submission Record")
async def create_submission(
    application_id: int = Path(..., gt=0, description="Unique identifier of the mortgage application"),
    submission_data: LenderSubmissionCreateRequest = None,
    service: LenderSubmissionService = Depends(get_submission_service)
):
    """
    Submit an application to a specific lender using a particular product offering.
    
    Creates a formal submission record which tracks communication with the lender
    and any resulting conditions or approvals.
    """
    try:
        submission = await service.create_submission(submission_data)
        return LenderSubmissionResponse.from_orm(submission)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create submission: {str(e)}")


@router.get("/applications/{application_id}/submissions", response_model=SubmissionsListResponse, summary="List Submissions")
async def list_submissions(
    application_id: int = Path(..., gt=0, description="Unique identifier of the mortgage application"),
    service: LenderSubmissionService = Depends(get_submission_service)
):
    """
    Retrieve all submission records related to a specific application.
    
    Shows history of lender interactions including pending, approved, declined, or countered offers.
    """
    try:
        submissions = await service.get_submissions_for_application(application_id)
        return SubmissionsListResponse(
            submissions=[LenderSubmissionResponse.from_orm(s) for s in submissions]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch submissions: {str(e)}")


@router.put("/applications/{application_id}/submissions/{submission_id}", response_model=LenderSubmissionResponse, summary="Update Submission Status")
async def update_submission_status(
    application_id: int = Path(..., gt=0, description="Unique identifier of the mortgage application"),
    submission_id: int = Path(..., gt=0, description="Unique identifier of the submission"),
    update_data: LenderSubmissionUpdateRequest = None,
    service: LenderSubmissionService = Depends(get_submission_service)
):
    """
    Update the status of a submission after receiving feedback from the lender.
    
    Allows updating key fields like approval status, rate offered, approved amount, and expiration date.
    """
    try:
        submission = await service.update_submission_status(submission_id, update_data)
        return LenderSubmissionResponse.from_orm(submission)
    except SubmissionNotFoundError:
        raise HTTPException(status_code=404, detail="Submission not found")
    except InvalidSubmissionStatusError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update submission: {str(e)}")
```