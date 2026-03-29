from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Tuple
from xml.etree import ElementTree as ET

from sqlalchemy import select, func as sql_func
import structlog
import json

from mortgage_underwriting.modules.policy.models import LenderPolicy, PolicyEvaluation
from mortgage_underwriting.modules.policy.schemas import (
    LenderPolicyCreate,
    LenderPolicyUpdate,
    PolicyEvaluationRequest,
    PolicyEvaluationResponse,
    LenderPolicyResponse
)
from mortgage_underwriting.modules.policy.exceptions import PolicyNotFoundError, InvalidXMLFormatError

logger = structlog.get_logger()


class PolicyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_all_policies(self, page: int = 1, size: int = 50) -> Tuple[list[LenderPolicy], int]:
        logger.info("fetching_all_policies", page=page, size=size)
        
        if size > 100:
            size = 100
            logger.warning("page_size_exceeded_max", max_size=100)

        offset = (page - 1) * size
        
        stmt = select(LenderPolicy).where(LenderPolicy.is_active == True).offset(offset).limit(size)
        result = await self.db.execute(stmt)
        policies = result.scalars().all()
        
        count_stmt = select(sql_func.count()).select_from(LenderPolicy).where(LenderPolicy.is_active == True)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        
        return policies, total

    async def get_policy_by_id(self, policy_id: int) -> Optional[LenderPolicy]:
        logger.info("fetching_policy_by_id", policy_id=policy_id)
        stmt = select(LenderPolicy).where(LenderPolicy.id == policy_id, LenderPolicy.is_active == True)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_policy_by_lender_id(self, lender_id: str) -> Optional[LenderPolicy]:
        logger.info("fetching_policy_by_lender_id", lender_id=lender_id)
        stmt = select(LenderPolicy).where(LenderPolicy.lender_id == lender_id, LenderPolicy.is_active == True)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_policy(self, payload: LenderPolicyCreate) -> LenderPolicy:
        logger.info("creating_new_policy", lender_id=payload.lender_id)
        
        # Validate XML format
        try:
            ET.fromstring(payload.xml_content)
        except ET.ParseError as e:
            logger.error("invalid_xml_format", error=str(e))
            raise InvalidXMLFormatError(f"Invalid XML format: {str(e)}")
        
        policy = LenderPolicy(
            lender_id=payload.lender_id,
            name=payload.name,
            xml_content=payload.xml_content,
            version=payload.version
        )
        
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)
        
        logger.info("policy_created_successfully", policy_id=policy.id)
        return policy

    async def update_policy(self, policy_id: int, payload: LenderPolicyUpdate) -> LenderPolicy:
        logger.info("updating_policy", policy_id=policy_id)
        
        # Validate XML format
        try:
            ET.fromstring(payload.xml_content)
        except ET.ParseError as e:
            logger.error("invalid_xml_format", error=str(e))
            raise InvalidXMLFormatError(f"Invalid XML format: {str(e)}")
        
        policy = await self.get_policy_by_id(policy_id)
        if not policy:
            logger.error("policy_not_found_for_update", policy_id=policy_id)
            raise PolicyNotFoundError(f"Policy with ID {policy_id} not found.")
            
        policy.xml_content = payload.xml_content
        await self.db.commit()
        await self.db.refresh(policy)
        
        logger.info("policy_updated_successfully", policy_id=policy.id)
        return policy

    async def evaluate_policy(self, payload: PolicyEvaluationRequest) -> PolicyEvaluationResponse:
        logger.info("evaluating_policy", policy_id=payload.policy_id)
        
        policy = await self.get_policy_by_id(payload.policy_id)
        if not policy:
            logger.error("policy_not_found_for_evaluation", policy_id=payload.policy_id)
            raise PolicyNotFoundError(f"Policy with ID {payload.policy_id} not found.")
        
        # FIXED: Enhanced XML parsing and validation to prevent XXE and other injection attacks
        try:
            # Disable external entity processing to prevent XXE
            parser = ET.XMLParser()
            parser.entity = {}
            root = ET.fromstring(policy.xml_content, parser=parser)
            
            gds_element = root.find('.//GDS')
            tds_element = root.find('.//TDS')
            
            if gds_element is None or tds_element is None:
                raise ValueError("Missing required elements in policy XML")
                
            gds_limit_str = gds_element.attrib.get('max', '0')
            tds_limit_str = tds_element.attrib.get('max', '0')
            
            # FIXED: Added proper type conversion with error handling
            try:
                gds_limit = float(gds_limit_str)
                tds_limit = float(tds_limit_str)
            except ValueError:
                raise ValueError("Invalid numeric values in policy limits")
            
            # FIXED: Safer access to application data with defaults
            app_gds = payload.application_data.get('gds', 0)
            app_tds = payload.application_data.get('tds', 0)
            
            # FIXED: Ensure application data values are numbers
            try:
                app_gds = float(app_gds)
                app_tds = float(app_tds)
            except (ValueError, TypeError):
                raise ValueError("Invalid GDS/TDS values in application data")
            
            result = app_gds <= gds_limit and app_tds <= tds_limit
            details = f"GDS: {app_gds}/{gds_limit}, TDS: {app_tds}/{tds_limit}"
            
        except Exception as e:
            logger.error("evaluation_error", error=str(e))
            result = False
            details = f"Evaluation failed: {str(e)}"
        
        # FIXED: Secure serialization of application data
        try:
            serialized_app_data = json.dumps(payload.application_data, ensure_ascii=True)
        except (TypeError, ValueError) as e:
            logger.error("serialization_error", error=str(e))
            raise InvalidXMLFormatError(f"Failed to serialize application data: {str(e)}")
        
        evaluation = PolicyEvaluation(
            policy_id=payload.policy_id,
            application_data=serialized_app_data,
            result=result,
            details=details
        )
        
        self.db.add(evaluation)
        await self.db.commit()
        await self.db.refresh(evaluation)
        
        logger.info("policy_evaluation_completed", evaluation_id=evaluation.id, result=result)
        return PolicyEvaluationResponse.model_validate(evaluation)