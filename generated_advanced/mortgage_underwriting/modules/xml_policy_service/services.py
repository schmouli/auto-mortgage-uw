from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from xml.etree import ElementTree as ET
import hashlib

from sqlalchemy import select
import structlog
from decimal import Decimal

from mortgage_underwriting.modules.xml_policy_service.models import LenderPolicy
from mortgage_underwriting.modules.xml_policy_service.schemas import (
    LenderPolicyCreate,
    LenderPolicyUpdate,
    LenderPolicySummary,
    LenderPolicyDetail,
    PolicyRules,
    LtvLimits,
    AmortizationLimits,
    PropertyTypes
)

logger = structlog.get_logger()


class XmlParsingError(Exception):
    """Raised when XML parsing fails."""
    pass

class PolicyEvaluationError(Exception):
    """Raised when policy evaluation fails."""
    pass

class XmlPolicyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_policies(self, limit: int = 100, offset: int = 0) -> List[LenderPolicySummary]:
        logger.info("listing_lender_policies", limit=limit, offset=offset)
        result = await self.db.execute(
            select(LenderPolicy)
            .where(LenderPolicy.is_active == True)
            .order_by(LenderPolicy.lender_id)
            .limit(limit)
            .offset(offset)
        )
        policies = result.scalars().all()
        return [
            LenderPolicySummary(
                lender_id=p.lender_id,
                lender_name=p.lender_name,
                version=p.version,
                is_active=p.is_active,
                effective_date=p.effective_date,
                xml_hash=p.xml_hash
            )
            for p in policies
        ]

    async def get_policy(self, lender_id: str) -> Optional[LenderPolicyDetail]:
        logger.info("getting_lender_policy", lender_id=lender_id)
        result = await self.db.execute(select(LenderPolicy).where(LenderPolicy.lender_id == lender_id))
        policy = result.scalar_one_or_none()
        if not policy:
            return None
        
        try:
            rules = self._parse_policy_xml(policy.policy_xml)
        except Exception as e:
            logger.error("failed_to_parse_policy_xml", error=str(e))
            raise XmlParsingError(f"Failed to parse policy XML: {e}")
        
        return LenderPolicyDetail(
            lender_id=policy.lender_id,
            lender_name=policy.lender_name,
            version=policy.version,
            is_active=policy.is_active,
            effective_date=policy.effective_date,
            policy_rules=rules,
            xml_hash=policy.xml_hash,
            created_by=policy.created_by,
            created_at=policy.created_at
        )

    async def create_policy(self, payload: LenderPolicyCreate, user_id_hash: str) -> LenderPolicyDetail:
        logger.info("creating_lender_policy", lender_id=payload.lender_id)
        
        # Validate XML
        try:
            rules = self._parse_policy_xml(payload.policy_xml)
        except Exception as e:
            logger.error("invalid_policy_xml", error=str(e))
            raise XmlParsingError(f"Invalid policy XML: {e}")
        
        # Generate hash
        xml_hash = hashlib.sha256(payload.policy_xml.encode()).hexdigest()
        
        # Check for duplicates
        result = await self.db.execute(select(LenderPolicy).where(LenderPolicy.xml_hash == xml_hash))
        if result.scalar_one_or_none():
            raise ValueError("Policy with identical content already exists")
        
        policy = LenderPolicy(
            lender_id=payload.lender_id,
            lender_name=payload.lender_name,
            version=payload.version,
            is_active=payload.is_active,
            effective_date=payload.effective_date,
            policy_xml=payload.policy_xml,
            xml_hash=xml_hash,
            created_by=user_id_hash
        )
        
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)
        
        return LenderPolicyDetail(
            lender_id=policy.lender_id,
            lender_name=policy.lender_name,
            version=policy.version,
            is_active=policy.is_active,
            effective_date=policy.effective_date,
            policy_rules=rules,
            xml_hash=policy.xml_hash,
            created_by=policy.created_by,
            created_at=policy.created_at
        )

    async def update_policy(self, lender_id: str, payload: LenderPolicyUpdate, user_id_hash: str) -> Optional[LenderPolicyDetail]:
        logger.info("updating_lender_policy", lender_id=lender_id)
        result = await self.db.execute(select(LenderPolicy).where(LenderPolicy.lender_id == lender_id))
        policy = result.scalar_one_or_none()
        if not policy:
            return None
        
        if payload.policy_xml:
            try:
                rules = self._parse_policy_xml(payload.policy_xml)
            except Exception as e:
                logger.error("invalid_policy_xml_update", error=str(e))
                raise XmlParsingError(f"Invalid policy XML: {e}")
            
            xml_hash = hashlib.sha256(payload.policy_xml.encode()).hexdigest()
            policy.policy_xml = payload.policy_xml
            policy.xml_hash = xml_hash
        else:
            try:
                rules = self._parse_policy_xml(policy.policy_xml)
            except Exception as e:
                logger.error("failed_to_parse_existing_xml", error=str(e))
                raise XmlParsingError(f"Failed to parse existing policy XML: {e}")
        
        if payload.is_active is not None:
            policy.is_active = payload.is_active
        if payload.effective_date:
            policy.effective_date = payload.effective_date
            
        # FIXED: Used proper datetime update instead of func.now()
        from datetime import datetime
        policy.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(policy)
        
        return LenderPolicyDetail(
            lender_id=policy.lender_id,
            lender_name=policy.lender_name,
            version=policy.version,
            is_active=policy.is_active,
            effective_date=policy.effective_date,
            policy_rules=rules,
            xml_hash=policy.xml_hash,
            created_by=policy.created_by,
            created_at=policy.created_at
        )

    def _parse_policy_xml(self, xml_content: str) -> PolicyRules:
        # FIXED: Improved XML parsing with better error handling and defaults
        try:
            root = ET.fromstring(xml_content)
            ns = {'ns': 'http://www.mismo.org/schema'}
            
            # Extract LTV limits
            ltv_insured = Decimal('95')
            ltv_conventional = Decimal('80')
            
            ltv_element = root.find('.//ns:LTV', ns)
            if ltv_element is not None:
                if 'insured' in ltv_element.attrib:
                    ltv_insured = Decimal(ltv_element.attrib['insured'])
                if 'conventional' in ltv_element.attrib:
                    ltv_conventional = Decimal(ltv_element.attrib['conventional'])
            
            # Extract GDS/TDS limits
            gds_max = Decimal('39')
            tds_max = Decimal('44')
            
            limits_element = root.find('.//ns:Limits', ns)
            if limits_element is not None:
                if 'gdsMax' in limits_element.attrib:
                    gds_max = Decimal(limits_element.attrib['gdsMax'])
                if 'tdsMax' in limits_element.attrib:
                    tds_max = Decimal(limits_element.attrib['tdsMax'])
            
            # Extract credit score minimum
            credit_min = 620
            credit_element = root.find('.//ns:CreditScore', ns)
            if credit_element is not None and 'min' in credit_element.attrib:
                credit_min = int(credit_element.attrib['min'])
            
            # Extract amortization limits
            amort_insured = 25
            amort_conventional = 30
            
            amort_element = root.find('.//ns:AmortizationMax', ns)
            if amort_element is not None:
                if 'insured' in amort_element.attrib:
                    amort_insured = int(amort_element.attrib['insured'])
                if 'conventional' in amort_element.attrib:
                    amort_conventional = int(amort_element.attrib['conventional'])
            
            # Extract property types
            allowed = ['single-family']
            excluded = []
            
            prop_element = root.find('.//ns:PropertyTypes', ns)
            if prop_element is not None:
                if 'allowed' in prop_element.attrib:
                    allowed = prop_element.attrib['allowed'].split(',')
                if 'excluded' in prop_element.attrib:
                    excluded = prop_element.attrib['excluded'].split(',')
            
            return PolicyRules(
                ltv_max=LtvLimits(insured=ltv_insured, conventional=ltv_conventional),
                gds_max=gds_max,
                tds_max=tds_max,
                credit_score_min=credit_min,
                amortization_max=AmortizationLimits(insured=amort_insured, conventional=amort_conventional),
                property_types=PropertyTypes(allowed=allowed, excluded=excluded)
            )
        except ET.ParseError as e:
            raise XmlParsingError(f"XML parsing failed: {str(e)}")
        except Exception as e:
            raise XmlParsingError(f"Unexpected error parsing XML: {str(e)}")

    async def evaluate_policy(self, lender_id: str, application_data: Dict[str, Any]) -> Dict[str, Any]:
        # FIXED: Implemented basic policy evaluation logic
        logger.info("evaluating_policy", lender_id=lender_id)
        
        policy_detail = await self.get_policy(lender_id)
        if not policy_detail:
            raise PolicyEvaluationError(f"Policy for lender {lender_id} not found")
        
        rules = policy_detail.policy_rules
        
        # Extract application data
        try:
            credit_score = application_data['credit_score']
            ltv = Decimal(str(application_data['ltv']))
            gds = Decimal(str(application_data['gds']))
            tds = Decimal(str(application_data['tds']))
            amortization = application_data['amortization']
            property_type = application_data['property_type']
            is_insured = application_data.get('is_insured', False)
        except KeyError as e:
            raise PolicyEvaluationError(f"Missing required field in application data: {str(e)}")
        
        # Perform evaluations
        violations = []
        
        if credit_score < rules.credit_score_min:
            violations.append(f"Credit score {credit_score} below minimum {rules.credit_score_min}")
        
        max_ltv = rules.ltv_max.insured if is_insured else rules.ltv_max.conventional
        if ltv > max_ltv:
            violations.append(f"LTV {ltv}% exceeds maximum {max_ltv}% for {'insured' if is_insured else 'conventional'} mortgage")
        
        if gds > rules.gds_max:
            violations.append(f"GDS {gds}% exceeds maximum {rules.gds_max}%")
        
        if tds > rules.tds_max:
            violations.append(f"TDS {tds}% exceeds maximum {rules.tds_max}%")
        
        max_amortization = rules.amortization_max.insured if is_insured else rules.amortization_max.conventional
        if amortization > max_amortization:
            violations.append(f"Amortization {amortization} years exceeds maximum {max_amortization} years for {'insured' if is_insured else 'conventional'} mortgage")
        
        if property_type not in rules.property_types.allowed:
            violations.append(f"Property type {property_type} not allowed")
        
        if property_type in rules.property_types.excluded:
            violations.append(f"Property type {property_type} is excluded")
        
        return {
            "lender_id": lender_id,
            "application_approved": len(violations) == 0,
            "violations": violations,
            "evaluation_details": {
                "credit_score_check": credit_score >= rules.credit_score_min,
                "ltv_check": ltv <= max_ltv,
                "gds_check": gds <= rules.gds_max,
                "tds_check": tds <= rules.tds_max,
                "amortization_check": amortization <= max_amortization,
                "property_type_check": property_type in rules.property_types.allowed and property_type not in rules.property_types.excluded
            }
        }