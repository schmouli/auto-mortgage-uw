from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, List
from xml.etree import ElementTree as ET

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.exceptions import NotFoundError
from mortgage_underwriting.modules.policy.models import LenderPolicy
from mortgage_underwriting.modules.policy.schemas import (
    LenderPolicyMetadata,
    LenderPolicyDetail,
    LenderPolicyListResponse,
    PolicyEvaluationRequest,
    PolicyEvaluationResponse,
    PolicyUpdateRequest
)

logger = structlog.get_logger()


class PolicyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_policies(
        self, page: int = 1, size: int = 50, is_active: Optional[bool] = None
    ) -> LenderPolicyListResponse:
        """List all loaded lender policies with pagination."""
        logger.info("listing_policies", page=page, size=size, is_active=is_active)
        size = min(size, 100)  # Cap at 100 per page
        offset = (page - 1) * size

        stmt = select(LenderPolicy)
        if is_active is not None:
            stmt = stmt.where(LenderPolicy.is_active == is_active)
        stmt = stmt.offset(offset).limit(size)

        result = await self.db.execute(stmt)
        items = [
            LenderPolicyMetadata.model_validate(policy) for policy in result.scalars().all()
        ]

        count_stmt = select(func.count()).select_from(LenderPolicy)
        if is_active is not None:
            count_stmt = count_stmt.where(LenderPolicy.is_active == is_active)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        return LenderPolicyListResponse(
            items=items,
            total=total,
            page=page,
            size=size
        )

    async def get_policy(self, lender_id: str) -> LenderPolicyDetail:
        """Retrieve detailed policy configuration for a specific lender."""
        logger.info("retrieving_policy", lender_id=lender_id)
        stmt = select(LenderPolicy).where(LenderPolicy.lender_id == lender_id)
        result = await self.db.execute(stmt)
        policy = result.scalar_one_or_none()
        if not policy:
            logger.error("policy_not_found", lender_id=lender_id)
            raise NotFoundError(f"Policy not found for lender ID: {lender_id}")
        return LenderPolicyDetail.model_validate(policy)

    async def update_policy(self, lender_id: str, payload: PolicyUpdateRequest) -> LenderPolicyDetail:
        """Update or create lender policy from XML content."""
        logger.info("updating_policy", lender_id=lender_id)
        parsed_config = self._parse_xml_to_dict(payload.xml_content)
        
        stmt = select(LenderPolicy).where(LenderPolicy.lender_id == lender_id)
        result = await self.db.execute(stmt)
        policy = result.scalar_one_or_none()

        if policy:
            policy.version = payload.version
            policy.xml_content = payload.xml_content
            policy.parsed_config = parsed_config
        else:
            policy = LenderPolicy(
                lender_id=lender_id,
                lender_name=self._extract_lender_name(payload.xml_content),
                version=payload.version,
                xml_content=payload.xml_content,
                parsed_config=parsed_config
            )
            self.db.add(policy)
        
        await self.db.commit()
        await self.db.refresh(policy)
        return LenderPolicyDetail.model_validate(policy)

    async def evaluate_policy(self, request: PolicyEvaluationRequest) -> PolicyEvaluationResponse:
        """Evaluate an application against a lender's policy rules."""
        logger.info("evaluating_policy", lender_id=request.lender_id)
        policy_detail = await self.get_policy(request.lender_id)
        parsed_config = policy_detail.policy_config
        violations: List[str] = []
        details: Dict[str, Any] = {}

        # Extract key values from input data
        applicant_credit_score = request.applicant_data.get('credit_score')
        property_type = request.property_data.get('type')
        
        # Calculate financial ratios using Decimal
        loan_amount = Decimal(str(request.loan_data.get('amount', 0)))
        property_value = Decimal(str(request.property_data.get('value', 1)))
        
        if property_value != 0:
            ltv_ratio = (loan_amount / property_value * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            ltv_ratio = Decimal('0')
            
        gds_ratio = Decimal(str(request.loan_data.get('gds_ratio', 0)))
        tds_ratio = Decimal(str(request.loan_data.get('tds_ratio', 0)))
        amortization_years = request.loan_data.get('amortization_years')

        # Check credit score minimum
        min_score = parsed_config['credit_score']['min']
        if applicant_credit_score < min_score:
            violations.append(f"Credit score {applicant_credit_score} below minimum {min_score}")
        details['credit_score_check'] = {
            'required': min_score,
            'provided': applicant_credit_score,
            'passed': applicant_credit_score >= min_score
        }

        # Check property type
        allowed_types = parsed_config['property_types']['allowed']
        excluded_types = parsed_config['property_types'].get('excluded', [])
        if property_type in excluded_types or property_type not in allowed_types:
            violations.append(f"Property type '{property_type}' not allowed")
        details['property_type_check'] = {
            'allowed': allowed_types,
            'excluded': excluded_types,
            'provided': property_type,
            'passed': property_type not in excluded_types and property_type in allowed_types
        }

        # Check LTV limits
        max_insured = Decimal(str(parsed_config['ltv']['max_insured']))
        max_conventional = Decimal(str(parsed_config['ltv']['max_conventional']))
        is_insured = ltv_ratio > Decimal('80')  # Simplified assumption
        max_allowed_ltv = max_insured if is_insured else max_conventional
        if ltv_ratio > max_allowed_ltv:
            violations.append(f"LTV ratio {ltv_ratio}% exceeds maximum {max_allowed_ltv}%")
        details['ltv_check'] = {
            'max_allowed': float(max_allowed_ltv),
            'calculated': float(ltv_ratio),
            'passed': ltv_ratio <= max_allowed_ltv
        }

        # Check GDS/TDS ratios
        max_gds = Decimal(str(parsed_config['gds']['max']))
        max_tds = Decimal(str(parsed_config['tds']['max']))
        if gds_ratio > max_gds:
            violations.append(f"GDS ratio {gds_ratio}% exceeds maximum {max_gds}%")
        if tds_ratio > max_tds:
            violations.append(f"TDS ratio {tds_ratio}% exceeds maximum {max_tds}%")
        details['ratio_checks'] = {
            'gds': {'max': float(max_gds), 'provided': float(gds_ratio), 'passed': gds_ratio <= max_gds},
            'tds': {'max': float(max_tds), 'provided': float(tds_ratio), 'passed': tds_ratio <= max_tds}
        }

        # Check amortization limit
        max_amortization = parsed_config['amortization_max']['insured' if is_insured else 'conventional']
        if amortization_years > max_amortization:
            violations.append(f"Amortization {amortization_years} years exceeds maximum {max_amortization} years")
        details['amortization_check'] = {
            'max_allowed': max_amortization,
            'provided': amortization_years,
            'passed': amortization_years <= max_amortization
        }

        return PolicyEvaluationResponse(
            compliant=len(violations) == 0,
            violations=violations,
            details=details
        )

    def _parse_xml_to_dict(self, xml_content: str) -> Dict[str, Any]:
        """Parse XML content into structured dictionary."""
        try:
            root = ET.fromstring(xml_content)
            return self._element_to_dict(root)
        except ET.ParseError as e:
            logger.error("xml_parse_error", error=str(e))
            raise ValueError(f"Invalid XML format: {str(e)}")

    def _element_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element tree to dictionary recursively."""
        result = {}
        if element.attrib:
            result.update(element.attrib)
        if element.text and element.text.strip():
            if len(element) == 0:
                return element.text.strip()
            else:
                result['text'] = element.text.strip()
        for child in element:
            child_data = self._element_to_dict(child)
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        return result

    def _extract_lender_name(self, xml_content: str) -> str:
        """Extract lender name from XML content."""
        try:
            root = ET.fromstring(xml_content)
            name_element = root.find('.//name')
            if name_element is not None and name_element.text:
                return name_element.text.strip()
            return "Unknown Lender"
        except ET.ParseError:
            return "Unknown Lender"