from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.mortgage.services import MortgageService
from mortgage_underwriting.modules.mortgage.schemas import (
    MortgageApplicationCreate,
    MortgageApplicationResponse,
    MortgageApplicationUpdate,
    GDSCalculationRequest,
    TDSCalculationRequest,
    RatioCalculationResponse,
    InsuranceEligibilityRequest,
    InsuranceEligibilityResponse
)

router = APIRouter(prefix="/api/v1/mortgage", tags=["Mortgage Applications"])


@router.post(
    "/applications/", 
    response_model=MortgageApplicationResponse, 
    status_code=status.HTTP_201_CREATED
)
async def submit_mortgage_application(
    payload: MortgageApplicationCreate,
    user_id: str = "test-user",  # In real implementation, extract from auth token
    db: AsyncSession = Depends(get_async_session),
):
    """
    Submit a new mortgage application.
    
    Raises:
        400: If validation fails
        422: If data format is incorrect
    """
    try:
        service = MortgageService(db)
        return await service.submit_application(payload, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": str(e),
                "error_code": "APPLICATION_SUBMISSION_ERROR"
            }
        )


@router.post(
    "/calculate-ratios/gds", 
    response_model=RatioCalculationResponse
)
async def calculate_gds_ratio(
    request: GDSCalculationRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Calculate Gross Debt Service (GDS) ratio with stress test.
    
    Raises:
        400: If calculation fails
    """
    try:
        service = MortgageService(db)
        return await service.calculate_ratios(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": str(e),
                "error_code": "GDS_CALCULATION_ERROR"
            }
        )


@router.post(
    "/calculate-ratios/tds", 
    response_model=RatioCalculationResponse
)
async def calculate_tds_ratio(
    request: TDSCalculationRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Calculate Total Debt Service (TDS) ratio with stress test.
    
    Raises:
        400: If calculation fails
    """
    try:
        service = MortgageService(db)
        return await service.calculate_ratios(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": str(e),
                "error_code": "TDS_CALCULATION_ERROR"
            }
        )


@router.post(
    "/insurance-eligibility", 
    response_model=InsuranceEligibilityResponse
)
async def check_insurance_eligibility(
    request: InsuranceEligibilityRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Check mortgage insurance eligibility based on LTV ratio.
    
    Raises:
        400: If calculation fails
    """
    try:
        service = MortgageService(db)
        return await service.check_insurance_eligibility(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": str(e),
                "error_code": "INSURANCE_ELIGIBILITY_ERROR"
            }
        )