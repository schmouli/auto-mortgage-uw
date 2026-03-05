```python
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime
from typing import Optional

class DecisionAuditCreate(BaseModel):
    application_id: int = Field(..., gt=0)
    user_id: int = Field(..., gt=0)
    interest_rate: Decimal = Field(..., gt=0)
    loan_amount: Decimal = Field(..., gt=0)
    decision_status: str = Field(..., max_length=50)
    notes: Optional[str] = Field(None, max_length=1000)

class DecisionAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    user_id: int
    interest_rate: Decimal
    loan_amount: Decimal
    decision_status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

class DecisionHistoryQueryParams(BaseModel):
    """
    Query parameters for decision history endpoint
    """
    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(50, ge=1, le=100, description="Maximum number of items to return (max 100)")
```