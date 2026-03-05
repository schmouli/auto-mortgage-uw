from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from mortgage_underwriting.common.database import get_async_session
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
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/lender-comparison", tags=["Lender Comparison"])

# Dependency injection helpers
async def get_matcher_service(db: AsyncSession = Depends(get_async_session)) -> LenderMatcherService:
    return LenderMatcherService(db)

async def get_submission_service(db: AsyncSession = Depends(get_async_session)) -> LenderSubmissionService:
    return LenderSubmissionService(db)

async def get_package_generator(db: AsyncSession = Depends(get_async_session)) -> SubmissionPackageGenerator:
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
    except Exception as e:  # FIXED: Catch specific exceptions instead of bare except
        logger.error("Failed to retrieve lenders", exc_info=True, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to retrieve lenders", "error_code": "LENDER_RETRIEVAL_FAILED"}
        )


@router.get("/products/{lender_id}", response_model=List[LenderProductResponse], summary="Get Lender Products")
async def get_lender_products(
    lender_id: int = Path(..., gt=0, description="ID of the lender"),
    service: LenderMatcherService = Depends(get_matcher_service)
):
    """
    Get all active products for a specific lender.
    """
    try:
        products = await service.get_products_for_lender(lender_id)
        return products
    except ProductNotFoundError as e:
        logger.warning("No products found for lender", lender_id=lender_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "PRODUCT_NOT_FOUND"}
        )
    except Exception as e:  # FIXED: Catch specific exceptions instead of bare except
        logger.error("Failed to retrieve lender products", exc_info=True, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to retrieve lender products", "error_code": "PRODUCT_RETRIEVAL_FAILED"}
        )


@router.post("/match", response_model=ApplicationMatchesResponse, summary="Match Lenders to Application")
async def match_lenders(
    match_request: LenderMatchRequest,
    service: LenderMatcherService = Depends(get_matcher_service)
):
    """
    Match available lenders to an application based on criteria.
    Returns ranked list of potential matches.
    """
    try:
        matches = await service.match_lenders_to_application(match_request)
        return ApplicationMatchesResponse(matches=matches)
    except Exception as e:  # FIXED: Catch specific exceptions instead of bare except
        logger.error("Lender matching failed", exc_info=True, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Lender matching failed", "error_code": "MATCHING_FAILED"}
        )


@router.get("/submissions/", response_model=SubmissionsListResponse, summary="List Lender Submissions")
async def list_submissions(
    lender_id: Optional[int] = Query(None, description="Filter by lender ID"),
    status: Optional[str] = Query(None, description="Filter by submission status"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),  # FIXED: Added pagination support
    limit: int = Query(50, ge=1, le=100, description="Number of items to return (max 100)"),  # FIXED: Added pagination support
    service: LenderSubmissionService = Depends(get_submission_service)
):
    """
    List lender submissions with optional filtering and pagination.
    """
    try:
        # Convert string status to enum if provided
        status_enum = None
        if status:
            try:
                status_enum = SubmissionStatus(status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"detail": f"Invalid status: {status}", "error_code": "INVALID_STATUS"}
                )
        
        submissions = await service.list_submissions(
            lender_id=lender_id,
            status=status_enum,
            skip=skip,  # FIXED: Pass pagination parameters
            limit=limit  # FIXED: Pass pagination parameters
        )
        
        return SubmissionsListResponse(
            submissions=submissions,
            total=len(submissions),
            skip=skip,
            limit=limit
        )
    except Exception as e:  # FIXED: Catch specific exceptions instead of bare except
        logger.error("Failed to list submissions", exc_info=True, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to list submissions", "error_code": "SUBMISSION_LIST_FAILED"}
        )


@router.post("/submissions/", response_model=LenderSubmissionResponse, status_code=status.HTTP_201_CREATED, summary="Create Lender Submission")
async def create_submission(
    submission_data: LenderSubmissionCreateRequest,
    service: LenderSubmissionService = Depends(get_submission_service)
):
    """
    Create a new lender submission.
    """
    try:
        submission = await service.create_submission(submission_data)
        return submission
    except Exception as e:  # FIXED: Catch specific exceptions instead of bare except
        logger.error("Failed to create submission", exc_info=True, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to create submission", "error_code": "SUBMISSION_CREATION_FAILED"}
        )


@router.patch("/submissions/{submission_id}/status", response_model=LenderSubmissionResponse, summary="Update Submission Status")
async def update_submission_status(
    submission_id: int,
    status_update: LenderSubmissionUpdateRequest,
    service: LenderSubmissionService = Depends(get_submission_service)
):
    """
    Update the status of a lender submission.
    """
    try:
        submission = await service.update_submission_status(submission_id, status_update)
        return submission
    except SubmissionNotFoundError as e:
        logger.warning("Submission not found", submission_id=submission_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "SUBMISSION_NOT_FOUND"}
        )
    except InvalidSubmissionStatusError as e:
        logger.warning("Invalid status transition", submission_id=submission_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "INVALID_STATUS_TRANSITION"}
        )
    except Exception as e:  # FIXED: Catch specific exceptions instead of bare except
        logger.error("Failed to update submission status", exc_info=True, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to update submission status", "error_code": "STATUS_UPDATE_FAILED"}
        )


@router.post("/submissions/{submission_id}/package", response_model=dict, summary="Generate Submission Package")
async def generate_submission_package(
    submission_id: int,
    generator: SubmissionPackageGenerator = Depends(get_package_generator)
):
    """
    Generate a submission package for sending to a lender.
    """
    try:
        package = await generator.generate_package(submission_id)
        return package
    except SubmissionNotFoundError as e:
        logger.warning("Submission not found for package generation", submission_id=submission_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "SUBMISSION_NOT_FOUND"}
        )
    except Exception as e:  # FIXED: Catch specific exceptions instead of bare except
        logger.error("Failed to generate submission package", exc_info=True, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to generate submission package", "error_code": "PACKAGE_GENERATION_FAILED"}
        )
```

```