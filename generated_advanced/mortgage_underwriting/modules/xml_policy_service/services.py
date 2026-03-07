from decimal import Decimal
from lxml import etree
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.modules.policy_xml.models import LenderPolicy
from mortgage_underwriting.modules.policy_xml.schemas import (
    LenderPolicyCreate, 
    LenderPolicyUpdate,
    LenderPolicyResponse,
    PolicyListResponse,
    PolicyEvaluationRequest,
    PolicyEvaluationResponse,
    LenderPolicyMetadata
)
from mortgage_underwriting.modules.policy_xml.exceptions import PolicyNotFoundError, InvalidPolicyXMLError

logger = structlog.get_logger()


class PolicyXMLService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_policies(
        self, 
        status: Optional[str] = None, 
        limit: int = 50, 
        offset: int = 0
    ) -> PolicyListResponse:
        """List lender policies with filtering and pagination."""
        logger.info("listing_policies", status=status, limit=limit, offset=offset)
        
        query = select(LenderPolicy)
        if status:
            query = query.where(LenderPolicy.status == status)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        # Apply pagination
        query = query.offset(offset).limit(min(limit, 200))
        result = await self.db.execute(query)
        policies = result.scalars().all()
        
        metadata_list = [
            LenderPolicyMetadata(
                lender_id=p.lender_id,
                lender_name=p.lender_name,
                policy_version=p.policy_version,
                status=p.status,
                effective_date=p.effective_date,
                created_at=p.created_at,
                evaluations_count=p.evaluations_count
            )
            for p in policies
        ]
        
        return PolicyListResponse(
            policies=metadata_list,
            total=total,
            limit=min(limit, 200),
            offset=offset
        )
    
    async def get_policy(self, lender_id: str, version: Optional[str] = None) -> LenderPolicyResponse:
        """Get specific lender policy by ID and optional version."""
        logger.info("getting_policy", lender_id=lender_id, version=version)
        
        query = select(LenderPolicy).where(LenderPolicy.lender_id == lender_id)
        if version:
            query = query.where(LenderPolicy.policy_version == version)
        else:
            query = query.where(LenderPolicy.status == 'active')
            
        result = await self.db.execute(query)
        policy = result.scalar_one_or_none()
        
        if not policy:
            raise PolicyNotFoundError(f"Policy not found for lender {lender_id}")
            
        return LenderPolicyResponse.model_validate(policy)
    
    async def create_policy(self, payload: LenderPolicyCreate) -> LenderPolicyResponse:
        """Create a new lender policy from XML content."""
        logger.info("creating_policy", lender_id=payload.lender_id)
        
        # Validate XML
        try:
            root = etree.fromstring(payload.xml_content)
            if root.tag != 'LenderPolicy':
                raise InvalidPolicyXMLError("Root element must be 'LenderPolicy'")
        except Exception as e:
            raise InvalidPolicyXMLError(f"Invalid XML content: {str(e)}")
        
        policy = LenderPolicy(
            lender_id=payload.lender_id,
            lender_name=payload.lender_name,
            policy_version=payload.policy_version,
            status=payload.status,
            effective_date=payload.effective_date,
            xml_content=payload.xml_content
        )
        
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)
        
        return LenderPolicyResponse.model_validate(policy)
    
    async def update_policy(self, lender_id: str, payload: LenderPolicyUpdate) -> LenderPolicyResponse:
        """Update an existing lender policy."""
        logger.info("updating_policy", lender_id=lender_id)
        
        result = await self.db.execute(
            select(LenderPolicy).where(LenderPolicy.lender_id == lender_id)
        )
        policy = result.scalar_one_or_none()
        
        if not policy:
            raise PolicyNotFoundError(f"Policy not found for lender {lender_id}")
        
        # Update fields
        policy.lender_name = payload.lender_name
        policy.policy_version = payload.policy_version
        policy.status = payload.status
        policy.effective_date = payload.effective_date
        
        if payload.xml_content:
            # Validate XML
            try:
                root = etree.fromstring(payload.xml_content)
                if root.tag != 'LenderPolicy':
                    raise InvalidPolicyXMLError("Root element must be 'LenderPolicy'")
            except Exception as e:
                raise InvalidPolicyXMLError(f"Invalid XML content: {str(e)}")
            policy.xml_content = payload.xml_content
        
        await self.db.commit()
        await self.db.refresh(policy)
        
        return LenderPolicyResponse.model_validate(policy)
    
    async def evaluate_policy(self, request: PolicyEvaluationRequest) -> PolicyEvaluationResponse:
        """Evaluate application data against lender policy."""
        logger.info("evaluating_policy", lender_id=request.lender_id)
        
        result = await self.db.execute(
            select(LenderPolicy).where(LenderPolicy.lender_id == request.lender_id)
        )
        policy = result.scalar_one_or_none()
        
        if not policy:
            raise PolicyNotFoundError(f"Policy not found for lender {request.lender_id}")
        
        # Parse XML
        try:
            root = etree.fromstring(policy.xml_content)
        except Exception as e:
            raise InvalidPolicyXMLError(f"Failed to parse policy XML: {str(e)}")
        
        # Extract policy rules
        ltv_max_insured = float(root.find('.//LTV').get('insured'))
        gds_max = float(root.find('.//GDS').get('max'))
        tds_max = float(root.find('.//TDS').get('max'))
        credit_score_min = int(root.find('.//CreditScore').get('min'))
        
        # Calculate metrics
        ltv = (Decimal(str(request.loan_amount)) / Decimal(str(request.property_value))) * 100
        
        # For now, we'll assume some mock values since we don't have full applicant data
        gds = Decimal('30')  # Mock GDS
        tds = Decimal('40')  # Mock TDS
        credit_score = 650  # Mock credit score
        
        # Check violations
        violations = []
        if ltv > Decimal(str(ltv_max_insured)):
            violations.append(f"LTV {ltv}% exceeds maximum allowed {ltv_max_insured}%")
        if gds > Decimal(str(gds_max)):
            violations.append(f"GDS {gds}% exceeds maximum allowed {gds_max}%")
        if tds > Decimal(str(tds_max)):
            violations.append(f"TDS {tds}% exceeds maximum allowed {tds_max}%")
        if credit_score < credit_score_min:
            violations.append(f"Credit score {credit_score} below minimum required {credit_score_min}")
        
        # Increment evaluation counter
        policy.evaluations_count += 1
        await self.db.commit()
        
        return PolicyEvaluationResponse(
            compliant=len(violations) == 0,
            violations=violations,
            qualifying_rate=5.25  # Mock qualifying rate
        )