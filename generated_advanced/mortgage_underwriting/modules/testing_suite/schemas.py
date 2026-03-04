```python
from pydantic import BaseModel, Field, validator
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import re


class TestRunCreateRequest(BaseModel):
    suite_name: str = Field(..., max_length=255, description="Name of the test suite")
    started_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class TestRunResponse(BaseModel):
    id: int
    run_id: str
    suite_name: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    passed_count: int
    failed_count: int
    skipped_count: int
    total_count: int
    coverage_percentage: Decimal
    is_success: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class TestCaseCreateRequest(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    module: str = Field(..., regex=r'^(underwriting|fintrac|auth|documents)$')
    category: str = Field(..., regex=r'^(unit|integration|e2e)$')
    expected_result: Optional[str] = Field(None, max_length=500)

    @validator('module')
    def validate_module(cls, v):
        allowed_modules = ['underwriting', 'fintrac', 'auth', 'documents']
        if v not in allowed_modules:
            raise ValueError(f'Module must be one of {allowed_modules}')
        return v

    @validator('category')
    def validate_category(cls, v):
        allowed_categories = ['unit', 'integration', 'e2e']
        if v not in allowed_categories:
            raise ValueError(f'Category must be one of {allowed_categories}')
        return v


class TestCaseUpdateRequest(BaseModel):
    actual_result: Optional[str] = Field(None, max_length=500)
    status: str = Field(..., regex=r'^(pass|fail|skip)$')
    execution_time_ms: Optional[int] = Field(None, ge=0)


class TestCaseResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    module: str
    category: str
    expected_result: Optional[str]
    actual_result: Optional[str]
    status: str
    execution_time_ms: Optional[int]
    test_run_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class TestSuiteSummaryResponse(BaseModel):
    suite_name: str
    run_count: int
    average_coverage: Decimal
    success_rate: Decimal

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }
```

---