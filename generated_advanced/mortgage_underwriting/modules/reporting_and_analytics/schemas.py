from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import Optional


class ReportBase(BaseModel):
    report_type: str = Field(..., max_length=50)
    title: str = Field(..., max_length=255)
    content: str


class ReportCreate(ReportBase):
    generated_by: int = Field(..., description="User ID who generated the report")


class ReportUpdate(ReportBase):
    pass


class ReportResponse(ReportBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    generated_by: int
    created_at: datetime
    updated_at: datetime


class PortfolioSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    total_value: Decimal
    average_ltv: Decimal
    created_at: datetime
    updated_at: datetime
```

```