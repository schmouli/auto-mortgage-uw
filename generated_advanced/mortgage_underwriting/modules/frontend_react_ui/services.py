import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any
from datetime import datetime

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.mortgage.models import MortgageApplication, ComplianceAuditLog
from mortgage_underwriting.modules.mortgage.schemas import (
    MortgageApplicationCreate, 
    GDSCalculationRequest, 
    TDSCalculationRequest,
    RatioCalculationResponse,
    InsuranceEligibilityRequest,
    InsuranceEligibilityResponse
)

logger = structlog.get_logger()


class ComplianceException(AppException):
    """Raised when compliance requirements are not met"""
    pass


class MortgageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_application(
        self, 
        payload: MortgageApplicationCreate, 
        user_id: str
    ) -> MortgageApplication:
        """
        Submit a new mortgage application with compliance checks.
        
        Args:
            payload: Application data
            user_id: ID of user submitting the application
            
        Returns:
            Created mortgage application
            
        Raises:
            ComplianceException: If application fails compliance checks
        """
        try:
            logger.info("submitting_mortgage_application", client_id=payload.client_id, user_id=user_id)
            
            # Create the application record
            application_data = payload.model_dump()
            application_data['created_by'] = user_id
            
            application = MortgageApplication(**application_data)
            self.db.add(application)
            await self.db.commit()
            await self.db.refresh(application)
            
            # Log compliance event
            await self._log_compliance_event(
                application.id, 
                "APPLICATION_SUBMITTED", 
                f"Application submitted by {user_id}"
            )
            
            return application
        except Exception as e:
            logger.error("application_submission_failed", error=str(e))
            raise ComplianceException(f"Failed to submit application: {str(e)}")

    async def _log_compliance_event(
        self, 
        application_id: int, 
        event_type: str, 
        details: str
    ) -> None:
        """
        Log a compliance-related event.
        
        Args:
            application_id: ID of the mortgage application
            event_type: Type of compliance event
            details: Event details
        """
        logger.info("logging_compliance_event", application_id=application_id, event_type=event_type)
        log_entry = ComplianceAuditLog(
            application_id=application_id,
            event_type=event_type,
            details=details
        )
        self.db.add(log_entry)
        await self.db.commit()

    async def calculate_ratios(
        self, 
        request: GDSCalculationRequest
    ) -> RatioCalculationResponse:
        """
        Calculate GDS and TDS ratios with OSFI B-20 stress test.
        
        Args:
            request: Request containing financial information
            
        Returns:
            Calculated ratios and compliance status
            
        Raises:
            ComplianceException: If calculation fails
        """
        try:
            logger.info("calculating_ratios", gross_income=float(request.gross_income))
            
            # Calculate qualifying rate per OSFI B-20
            qualifying_rate = max(
                request.interest_rate + Decimal('2.0'), 
                Decimal('5.25')
            )
            
            # Calculate GDS components
            monthly_property_tax = request.property_taxes / Decimal('12')
            monthly_heating = request.heating_costs
            monthly_condo_fees = request.condo_fees
            
            # GDS calculation using contract rate
            gds_monthly_housing_costs = (
                monthly_property_tax + 
                monthly_heating + 
                monthly_condo_fees +
                (request.interest_rate / Decimal('100') / Decimal('12') * request.gross_income)
            )
            
            # GDS calculation using qualifying rate (for stress test)
            gds_monthly_housing_costs_stress = (
                monthly_property_tax + 
                monthly_heating + 
                monthly_condo_fees +
                (qualifying_rate / Decimal('100') / Decimal('12') * request.gross_income)
            )
            
            # Calculate GDS ratio
            gds_ratio = (gds_monthly_housing_costs / request.gross_income) * Decimal('100')
            gds_ratio_stress = (gds_monthly_housing_costs_stress / request.gross_income) * Decimal('100')
            
            # Use the higher of the two for compliance check
            final_gds_ratio = max(gds_ratio, gds_ratio_stress)
            gds_limit_met = final_gds_ratio > Decimal('39')
            
            # Calculate TDS components
            total_monthly_debt = request.monthly_debt_payments
            
            # TDS calculation using contract rate
            tds_monthly_debt = (
                gds_monthly_housing_costs + 
                total_monthly_debt
            )
            
            # TDS calculation using qualifying rate (stress test)
            tds_monthly_debt_stress = (
                gds_monthly_housing_costs_stress + 
                total_monthly_debt
            )
            
            # Calculate TDS ratio
            tds_ratio = (tds_monthly_debt / request.gross_income) * Decimal('100')
            tds_ratio_stress = (tds_monthly_debt_stress / request.gross_income) * Decimal('100')
            
            # Use the higher of the two for compliance check
            final_tds_ratio = max(tds_ratio, tds_ratio_stress)
            tds_limit_met = final_tds_ratio > Decimal('44')
            
            # Prepare calculation breakdown for audit trail
            calculation_breakdown = {
                "gross_income": float(request.gross_income),
                "contract_rate": float(request.interest_rate),
                "qualifying_rate": float(qualifying_rate),
                "monthly_property_tax": float(monthly_property_tax),
                "monthly_heating": float(monthly_heating),
                "monthly_condo_fees": float(monthly_condo_fees),
                "gds_ratio": float(gds_ratio),
                "gds_ratio_stress": float(gds_ratio_stress),
                "final_gds_ratio": float(final_gds_ratio),
                "gds_limit_met": gds_limit_met,
                "total_monthly_debt": float(total_monthly_debt),
                "tds_ratio": float(tds_ratio),
                "tds_ratio_stress": float(tds_ratio_stress),
                "final_tds_ratio": float(final_tds_ratio),
                "tds_limit_met": tds_limit_met
            }
            
            # Log compliance event
            await self._log_compliance_event(
                0,  # No specific application yet
                "RATIO_CALCULATION", 
                f"GDS: {final_gds_ratio}, TDS: {final_tds_ratio}"
            )
            
            return RatioCalculationResponse(
                gds_ratio=final_gds_ratio,
                tds_ratio=final_tds_ratio,
                qualifying_rate=qualifying_rate,
                gds_limit_met=gds_limit_met,
                tds_limit_met=tds_limit_met,
                calculation_breakdown=calculation_breakdown
            )
        except Exception as e:
            logger.error("ratio_calculation_failed", error=str(e))
            raise ComplianceException(f"Failed to calculate ratios: {str(e)}")

    async def check_insurance_eligibility(
        self, 
        request: InsuranceEligibilityRequest
    ) -> InsuranceEligibilityResponse:
        """
        Check mortgage insurance eligibility based on CMHC requirements.
        
        Args:
            request: Request containing loan and property information
            
        Returns:
            Insurance eligibility and premium information
            
        Raises:
            ComplianceException: If calculation fails
        """
        try:
            logger.info("checking_insurance_eligibility", loan_amount=float(request.loan_amount))
            
            # Calculate LTV ratio
            ltv_ratio = (request.loan_amount / request.property_value) * Decimal('100')
            
            # Determine if insurance is required
            insurance_required = ltv_ratio > Decimal('80')
            
            if not insurance_required:
                return InsuranceEligibilityResponse(
                    insurance_required=False,
                    ltv_ratio=ltv_ratio
                )
            
            # Determine premium percentage based on CMHC tiers
            if ltv_ratio > Decimal('90.01'):
                premium_percentage = Decimal('4.00')
            elif ltv_ratio > Decimal('85.01'):
                premium_percentage = Decimal('3.10')
            elif ltv_ratio > Decimal('80.01'):
                premium_percentage = Decimal('2.80')
            else:
                premium_percentage = Decimal('0.00')  # Should not happen due to insurance_required check
            
            # Calculate premium amount
            premium_amount = request.loan_amount * (premium_percentage / Decimal('100'))
            
            # Log compliance event
            await self._log_compliance_event(
                0,  # No specific application yet
                "INSURANCE_ELIGIBILITY_CHECK", 
                f"LTV: {ltv_ratio}, Premium: {premium_percentage}%"
            )
            
            return InsuranceEligibilityResponse(
                insurance_required=True,
                ltv_ratio=ltv_ratio,
                premium_percentage=premium_percentage,
                premium_amount=premium_amount
            )
        except Exception as e:
            logger.error("insurance_check_failed", error=str(e))
            raise ComplianceException(f"Failed to check insurance eligibility: {str(e)}")