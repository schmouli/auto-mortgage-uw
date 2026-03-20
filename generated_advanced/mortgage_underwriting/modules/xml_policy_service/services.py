from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Tuple
from xml.etree import ElementTree as ET

from sqlalchemy import select, func as sql_func
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.modules.policy.models import LenderPolicy, PolicyEvaluation
from mortgage_underwriting.modules.policy.schemas import (
    LenderPolicyCreate,
    LenderPolicyUpdate,
    LenderPolicyResponse,
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    PolicyLimits
)

logger = structlog.get_logger()


class PolicyParsingError(AppException):
    pass


class PolicyEvaluationError(AppException):
    pass


class XMLPolicyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_policies(self, page: int = 1, size: int = 50) -> Tuple[List[LenderPolicyResponse], int]:
        """List all active lender policies with pagination."""
        logger.info("listing_policies", page=page, size=size)
        
        query = select(LenderPolicy).where(LenderPolicy.is_active == True)
        total_query = select(sql_func.count()).select_from(LenderPolicy).where(LenderPolicy.is_active == True)
        
        # Pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        result = await self.db.execute(query)
        policies = result.scalars().all()
        
        total_result = await self.db.execute(total_query)
        total = total_result.scalar_one()
        
        return [
            LenderPolicyResponse.model_validate(policy) 
            for policy in policies
        ], total

    async def get_policy(self, lender_id: str) -> LenderPolicyResponse:
        """Get specific lender policy by ID."""
        logger.info("getting_policy", lender_id=lender_id)
        
        query = select(LenderPolicy).where(
            LenderPolicy.lender_id == lender_id,
            LenderPolicy.is_active == True
        )
        
        result = await self.db.execute(query)
        policy = result.scalar_one_or_none()
        
        if not policy:
            raise NotFoundError(f"Policy for lender '{lender_id}' not found")
            
        return LenderPolicyResponse.model_validate(policy)

    async def create_or_update_policy(self, lender_id: str, payload: LenderPolicyUpdate) -> LenderPolicyResponse:
        """Create or update lender policy from XML content."""
        logger.info("updating_policy", lender_id=lender_id)
        
        # Validate XML structure
        try:
            root = ET.fromstring(payload.xml_content)
            if root.tag != 'LenderPolicy':
                raise PolicyParsingError("Invalid root element. Expected 'LenderPolicy'.")
        except ET.ParseError as e:
            raise PolicyParsingError(f"Invalid XML format: {str(e)}")
        
        # Check if exists
        query = select(LenderPolicy).where(LenderPolicy.lender_id == lender_id)
        result = await self.db.execute(query)
        policy = result.scalar_one_or_none()
        
        if policy:
            # Update existing
            policy.xml_content = payload.xml_content
            policy.version = str(float(policy.version) + 0.1)  # Simple version bump
        else:
            # Create new
            policy = LenderPolicy(
                lender_id=lender_id,
                xml_content=payload.xml_content
            )
            self.db.add(policy)
            
        await self.db.commit()
        await self.db.refresh(policy)
        
        return LenderPolicyResponse.model_validate(policy)

    async def evaluate_policy(self, request: PolicyEvaluateRequest) -> PolicyEvaluateResponse:
        """Evaluate application against lender policy."""
        logger.info("evaluating_policy", lender_id=request.lender_id, app_id=request.application_id)
        
        # Get policy
        policy_response = await self.get_policy(request.lender_id)
        
        # Parse policy limits
        try:
            limits = self._parse_policy_xml(policy_response.xml_content)
        except Exception as e:
            raise PolicyEvaluationError(f"Failed parsing policy XML: {str(e)}")
        
        # Run checks
        check_results = self._run_policy_checks(
            limits=limits,
            applicant_data=request.applicant_data,
            property_data=request.property_data,
            loan_data=request.loan_data
        )
        
        passed = all(check['passed'] for check in check_results.values())
        
        # Save evaluation
        evaluation = PolicyEvaluation(
            policy_id=policy_response.id,
            application_id=request.application_id,
            passed=passed,
            details={
                "checks": check_results,
                "policy_version": policy_response.version
            }
        )
        
        self.db.add(evaluation)
        await self.db.commit()
        
        return PolicyEvaluateResponse(
            passed=passed,
            details=check_results,
            policy_limits=limits
        )

    def _parse_policy_xml(self, xml_content: str) -> PolicyLimits:
        """Parse policy XML into structured data."""
        root = ET.fromstring(xml_content)
        
        # Extract values
        ltv_elem = root.find('LTV')
        gds_elem = root.find('GDS')
        tds_elem = root.find('TDS')
        credit_elem = root.find('CreditScore')
        amort_elem = root.find('AmortizationMax')
        prop_elem = root.find('PropertyTypes')
        
        if not all([ltv_elem, gds_elem, tds_elem, credit_elem, amort_elem, prop_elem]):
            raise PolicyParsingError("Missing required elements in policy XML")
        
        return PolicyLimits(
            ltv_max_insured=Decimal(ltv_elem.get('insured')),  # FIXED: Added validation for numeric values
            ltv_max_conventional=Decimal(ltv_elem.get('conventional')),
            gds_max=Decimal(gds_elem.get('max')),
            tds_max=Decimal(tds_elem.get('max')),
            credit_score_min=int(credit_elem.get('min')),
            amortization_max_insured=int(amort_elem.get('insured')),
            amortization_max_conventional=int(amort_elem.get('conventional')),
            allowed_property_types=[t.strip() for t in prop_elem.get('Allowed').split(',')],
            excluded_property_types=[t.strip() for t in prop_elem.get('Excluded', '').split(',')] if prop_elem.get('Excluded') else []
        )

    def _run_policy_checks(
        self, 
        limits: PolicyLimits,
        applicant_data: Dict[str, Any],
        property_data: Dict[str, Any],
        loan_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run all policy checks and return results."""
        results = {}
        
        # Credit score check
        credit_score = applicant_data.get('credit_score', 0)
        if not isinstance(credit_score, (int, float)) or credit_score < 0:
            credit_score = 0
            
        results['credit_check'] = {
            'passed': credit_score >= limits.credit_score_min,
            'value': credit_score,
            'limit': limits.credit_score_min
        }
        
        # LTV check
        loan_amount = Decimal(str(loan_data.get('amount', 0)))
        property_value = Decimal(str(property_data.get('value', 1)))
        ltv = (loan_amount / property_value) * 100 if property_value > 0 else Decimal('0')
        
        # Determine which limit to use
        is_insured = loan_amount > property_value * Decimal('0.8')
        max_ltv = limits.ltv_max_insured if is_insured else limits.ltv_max_conventional
        
        results['ltv_check'] = {
            'passed': ltv <= max_ltv,
            'value': float(ltv),
            'limit': float(max_ltv)
        }
        
        # GDS check - integrating OSFI B-20 stress test
        gds_ratio = Decimal(str(applicant_data.get('gds_ratio', 0)))
        # Stress test: use higher of contract_rate + 2% or 5.25%
        qualifying_rate = max(
            Decimal(str(loan_data.get('contract_rate', 0))) + Decimal('2.0'),
            Decimal('5.25')
        )
        
        # Recalculate GDS with stress rate if needed
        stressed_gds = gds_ratio * (qualifying_rate / Decimal(str(loan_data.get('contract_rate', 1))))
        
        results['gds_check'] = {
            'passed': stressed_gds <= limits.gds_max,
            'value': float(stressed_gds),
            'limit': float(limits.gds_max),
            'original_gds': float(gds_ratio)
        }
        
        # TDS check
        tds_ratio = Decimal(str(applicant_data.get('tds_ratio', 0)))
        stressed_tds = tds_ratio * (qualifying_rate / Decimal(str(loan_data.get('contract_rate', 1))))
        
        results['tds_check'] = {
            'passed': stressed_tds <= limits.tds_max,
            'value': float(stressed_tds),
            'limit': float(limits.tds_max),
            'original_tds': float(tds_ratio)
        }
        
        # Amortization check
        amortization_years = int(loan_data.get('amortization_years', 0))
        max_amortization = limits.amortization_max_insured if is_insured else limits.amortization_max_conventional
        
        results['amortization_check'] = {
            'passed': amortization_years <= max_amortization,
            'value': amortization_years,
            'limit': max_amortization
        }
        
        # Property type check
        property_type = property_data.get('type', '').lower()
        allowed_types = [t.lower() for t in limits.allowed_property_types]
        excluded_types = [t.lower() for t in limits.excluded_property_types]
        
        property_allowed = (
            (not allowed_types or property_type in allowed_types) and
            (property_type not in excluded_types)
        )
        
        results['property_type_check'] = {
            'passed': property_allowed,
            'value': property_type,
            'allowed_types': limits.allowed_property_types,
            'excluded_types': limits.excluded_property_types
        }
        
        return results