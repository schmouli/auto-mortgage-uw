```python
# Canadian Mortgage Underwriting System - XML Policy Service

# --- models.py ---
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, Integer, Numeric, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import uuid


class Base(DeclarativeBase):
    pass


class LenderPolicy(Base):
    __tablename__ = "lender_policies"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lender_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    version: Mapped[str] = mapped_column(String(20))
    xml_content: Mapped[str] = mapped_column(Text)
    
    # Policy attributes stored for quick access
    ltv_max_insured: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2))
    ltv_max_conventional: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2))
    gds_max: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2))
    tds_max: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2))
    credit_score_min: Mapped[int] = mapped_column(Integer)
    amortization_max_insured: Mapped[int] = mapped_column(Integer)
    amortization_max_conventional: Mapped[int] = mapped_column(Integer)
    property_types_allowed: Mapped[str] = mapped_column(Text)  # JSON string list
    property_types_excluded: Mapped[str] = mapped_column(Text)  # JSON string list
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    changed_by: Mapped[Optional[str]] = mapped_column(String(100))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "lender_id": self.lender_id,
            "version": self.version,
            "ltv_max_insured": self.ltv_max_insured,
            "ltv_max_conventional": self.ltv_max_conventional,
            "gds_max": self.gds_max,
            "tds_max": self.tds_max,
            "credit_score_min": self.credit_score_min,
            "amortization_max_insured": self.amortization_max_insured,
            "amortization_max_conventional": self.amortization_max_conventional,
            "property_types_allowed": self.property_types_allowed,
            "property_types_excluded": self.property_types_excluded,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "changed_by": self.changed_by
        }


# --- schemas.py ---
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from decimal import Decimal


class LenderPolicyCreate(BaseModel):
    lender_id: str = Field(..., description="Unique identifier for the lender")
    xml_content: str = Field(..., description="XML content of the policy")
    changed_by: Optional[str] = Field(None, description="User who made the change")


class LenderPolicyUpdate(BaseModel):
    xml_content: str = Field(..., description="Updated XML content of the policy")
    changed_by: Optional[str] = Field(None, description="User who made the change")


class LenderPolicyResponse(BaseModel):
    id: str
    lender_id: str
    version: str
    ltv_max_insured: Decimal
    ltv_max_conventional: Decimal
    gds_max: Decimal
    tds_max: Decimal
    credit_score_min: int
    amortization_max_insured: int
    amortization_max_conventional: int
    property_types_allowed: List[str]
    property_types_excluded: List[str]
    created_at: str
    updated_at: str
    changed_by: Optional[str]


class PolicyEvaluationRequest(BaseModel):
    lender_id: str = Field(..., description="Lender ID to evaluate against")
    application_data: Dict[str, Any] = Field(..., description="Application data for evaluation")
    
    @validator('application_data')
    def validate_application_data(cls, v):
        required_fields = ['ltv', 'gds', 'tds', 'credit_score', 'amortization_years', 'property_type']
        for field in required_fields:
            if field not in v:
                raise ValueError(f'Missing required field: {field}')
        return v


class PolicyEvaluationResult(BaseModel):
    compliant: bool = Field(..., description="Whether the application complies with policy")
    violations: List[str] = Field(..., description="List of policy violations if not compliant")
    details: Dict[str, Any] = Field(..., description="Detailed evaluation results")


class LenderListResponse(BaseModel):
    lenders: List[str] = Field(..., description="List of available lender IDs")


# --- exceptions.py ---
class PolicyServiceException(Exception):
    """Base exception for Policy Service"""
    pass


class PolicyNotFoundException(PolicyServiceException):
    """Raised when a policy is not found"""
    def __init__(self, lender_id: str):
        self.lender_id = lender_id
        super().__init__(f"Policy not found for lender: {lender_id}")


class InvalidPolicyXmlException(PolicyServiceException):
    """Raised when policy XML is invalid"""
    def __init__(self, message: str):
        super().__init__(f"Invalid policy XML: {message}")


class PolicyEvaluationException(PolicyServiceException):
    """Raised when policy evaluation fails"""
    def __init__(self, message: str):
        super().__init__(f"Policy evaluation failed: {message}")


# --- services.py ---
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from decimal import Decimal
import json

from .models import LenderPolicy
from .schemas import PolicyEvaluationRequest, PolicyEvaluationResult
from .exceptions import PolicyNotFoundException, InvalidPolicyXmlException, PolicyEvaluationException


class PolicyService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_all_lender_ids(self) -> List[str]:
        """Get list of all lender IDs"""
        result = await self.db.execute(select(LenderPolicy.lender_id))
        return [row[0] for row in result.fetchall()]

    async def get_policy(self, lender_id: str) -> LenderPolicy:
        """Get policy by lender ID"""
        result = await self.db.execute(
            select(LenderPolicy).where(LenderPolicy.lender_id == lender_id)
        )
        policy = result.scalar_one_or_none()
        if not policy:
            raise PolicyNotFoundException(lender_id)
        return policy

    async def create_or_update_policy(self, lender_id: str, xml_content: str, changed_by: Optional[str] = None) -> LenderPolicy:
        """Create or update a lender policy from XML content"""
        # Parse and validate XML
        try:
            root = ET.fromstring(xml_content)
            if root.tag != "LenderPolicy":
                raise InvalidPolicyXmlException("Root element must be 'LenderPolicy'")
            
            # Extract policy data
            policy_data = {
                "lender_id": lender_id,
                "version": root.attrib.get("version", "1.0"),
                "xml_content": xml_content,
                "changed_by": changed_by
            }
            
            # Extract LTV limits
            ltv_elem = root.find("LTV")
            if ltv_elem is not None:
                policy_data["ltv_max_insured"] = Decimal(ltv_elem.attrib.get("insured", "0"))
                policy_data["ltv_max_conventional"] = Decimal(ltv_elem.attrib.get("conventional", "0"))
            else:
                raise InvalidPolicyXmlException("Missing LTV element")
            
            # Extract GDS limit
            gds_elem = root.find("GDS")
            if gds_elem is not None:
                policy_data["gds_max"] = Decimal(gds_elem.attrib.get("max", "0"))
            else:
                raise InvalidPolicyXmlException("Missing GDS element")
            
            # Extract TDS limit
            tds_elem = root.find("TDS")
            if tds_elem is not None:
                policy_data["tds_max"] = Decimal(tds_elem.attrib.get("max", "0"))
            else:
                raise InvalidPolicyXmlException("Missing TDS element")
            
            # Extract Credit Score minimum
            credit_elem = root.find("CreditScore")
            if credit_elem is not None:
                policy_data["credit_score_min"] = int(credit_elem.attrib.get("min", "0"))
            else:
                raise InvalidPolicyXmlException("Missing CreditScore element")
            
            # Extract Amortization limits
            amortization_elem = root.find("AmortizationMax")
            if amortization_elem is not None:
                policy_data["amortization_max_insured"] = int(amortization_elem.attrib.get("insured", "0"))
                policy_data["amortization_max_conventional"] = int(amortization_elem.attrib.get("conventional", "0"))
            else:
                raise InvalidPolicyXmlException("Missing AmortizationMax element")
            
            # Extract Property Types
            property_elem = root.find("PropertyTypes")
            if property_elem is not None:
                allowed = property_elem.attrib.get("Allowed", "")
                excluded = property_elem.attrib.get("Excluded", "")
                policy_data["property_types_allowed"] = json.dumps([t.strip() for t in allowed.split(",") if t.strip()])
                policy_data["property_types_excluded"] = json.dumps([t.strip() for t in excluded.split(",") if t.strip()])
            else:
                raise InvalidPolicyXmlException("Missing PropertyTypes element")
                
        except ET.ParseError as e:
            raise InvalidPolicyXmlException(f"XML parsing error: {str(e)}")
        
        # Check if policy exists
        existing = await self.db.execute(
            select(LenderPolicy).where(LenderPolicy.lender_id == lender_id)
        )
        existing_policy = existing.scalar_one_or_none()
        
        if existing_policy:
            # Update existing policy
            for key, value in policy_data.items():
                setattr(existing_policy, key, value)
            await self.db.commit()
            await self.db.refresh(existing_policy)
            return existing_policy
        else:
            # Create new policy
            new_policy = LenderPolicy(**policy_data)
            self.db.add(new_policy)
            await self.db.commit()
            await self.db.refresh(new_policy)
            return new_policy

    async def evaluate_policy(self, evaluation_request: PolicyEvaluationRequest) -> PolicyEvaluationResult:
        """Evaluate an application against a lender's policy"""
        try:
            policy = await self.get_policy(evaluation_request.lender_id)
        except PolicyNotFoundException:
            raise PolicyEvaluationException(f"Policy not found for lender {evaluation_request.lender_id}")
        
        app_data = evaluation_request.application_data
        violations = []
        
        # LTV Check
        if app_data.get("mortgage_type") == "insured":
            if Decimal(str(app_data["ltv"])) > policy.ltv_max_insured:
                violations.append(f"LTV {app_data['ltv']} exceeds insured maximum of {policy.ltv_max_insured}")
        else:  # conventional
            if Decimal(str(app_data["ltv"])) > policy.ltv_max_conventional:
                violations.append(f"LTV {app_data['ltv']} exceeds conventional maximum of {policy.ltv_max_conventional}")
        
        # GDS Check
        if Decimal(str(app_data["gds"])) > policy.gds_max:
            violations.append(f"GDS {app_data['gds']} exceeds maximum of {policy.gds_max}")
        
        # TDS Check
        if Decimal(str(app_data["tds"])) > policy.tds_max:
            violations.append(f"TDS {app_data['tds']} exceeds maximum of {policy.tds_max}")
        
        # Credit Score Check
        if int(app_data["credit_score"]) < policy.credit_score_min:
            violations.append(f"Credit score {app_data['credit_score']} below minimum of {policy.credit_score_min}")
        
        # Amortization Check
        if app_data.get("mortgage_type") == "insured":
            if int(app_data["amortization_years"]) > policy.amortization_max_insured:
                violations.append(f"Amortization {app_data['amortization_years']} years exceeds insured maximum of {policy.amortization_max_insured}")
        else:  # conventional
            if int(app_data["amortization_years"]) > policy.amortization_max_conventional:
                violations.append(f"Amortization {app_data['amortization_years']} years exceeds conventional maximum of {policy.amortization_max_conventional}")
        
        # Property Type Check
        allowed_types = json.loads(policy.property_types_allowed)
        excluded_types = json.loads(policy.property_types_excluded)
        
        if app_data["property_type"] in excluded_types:
            violations.append(f"Property type '{app_data['property_type']}' is excluded")
        elif allowed_types and app_data["property_type"] not in allowed_types:
            violations.append(f"Property type '{app_data['property_type']}' is not allowed. Allowed types: {allowed_types}")
        
        return PolicyEvaluationResult(
            compliant=len(violations) == 0,
            violations=violations,
            details={
                "evaluated_policy": policy.lender_id,
                "application_values": app_data,
                "policy_limits": policy.to_dict()
            }
        )


# --- routes.py ---
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from . import schemas, services
from .database import get_db
from .exceptions import PolicyNotFoundException, InvalidPolicyXmlException, PolicyEvaluationException

router = APIRouter(prefix="/policy", tags=["policy"])

@router.get("/lenders", response_model=schemas.LenderListResponse)
async def list_lenders(db: AsyncSession = Depends(get_db)):
    """List all loaded lender policies"""
    policy_service = services.PolicyService(db)
    lender_ids = await policy_service.get_all_lender_ids()
    return schemas.LenderListResponse(lenders=lender_ids)

@router.get("/{lender_id}", response_model=schemas.LenderPolicyResponse)
async def get_lender_policy(lender_id: str, db: AsyncSession = Depends(get_db)):
    """Get specific lender policy"""
    try:
        policy_service = services.PolicyService(db)
        policy = await policy_service.get_policy(lender_id)
        # Convert stored JSON strings back to lists
        import json
        response_data = policy.to_dict()
        response_data["property_types_allowed"] = json.loads(response_data["property_types_allowed"])
        response_data["property_types_excluded"] = json.loads(response_data["property_types_excluded"])
        return schemas.LenderPolicyResponse(**response_data)
    except PolicyNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/evaluate", response_model=schemas.PolicyEvaluationResult)
async def evaluate_policy(
    evaluation_request: schemas.PolicyEvaluationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Evaluate application data against policy"""
    try:
        policy_service = services.PolicyService(db)
        result = await policy_service.evaluate_policy(
            schemas.PolicyEvaluationRequest(**evaluation_request.dict())
        )
        return result
    except PolicyEvaluationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PolicyNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.put("/{lender_id}", response_model=schemas.LenderPolicyResponse)
async def update_lender_policy(
    lender_id: str,
    policy_update: schemas.LenderPolicyUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update lender policy XML"""
    try:
        policy_service = services.PolicyService(db)
        policy = await policy_service.create_or_update_policy(
            lender_id, 
            policy_update.xml_content, 
            policy_update.changed_by
        )
        # Convert stored JSON strings back to lists
        import json
        response_data = policy.to_dict()
        response_data["property_types_allowed"] = json.loads(response_data["property_types_allowed"])
        response_data["property_types_excluded"] = json.loads(response_data["property_types_excluded"])
        return schemas.LenderPolicyResponse(**response_data)
    except InvalidPolicyXmlException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```