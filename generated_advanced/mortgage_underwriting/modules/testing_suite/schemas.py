from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator

# --- Constants ---
MAX_MODULE_NAME_LENGTH = 100
MAX_TEST_SUITE_TYPE_LENGTH = 50
MAX_STATUS_LENGTH = 20
MAX_TEST_NAME_LENGTH = 255
MAX_FILE_PATH_LENGTH = 500
MAX_LOG_OUTPUT_LENGTH = 10000
MAX_MISSED_LINES_LENGTH = 5000

# --- Test Run Schemas ---

class TestRunBase(BaseModel):
    module_name: str = Field(..., max_length=MAX_MODULE_NAME_LENGTH)
    test_suite_type: str = Field(..., pattern="^(unit|integration|e2e)$")
    status: str = Field(..., pattern="^(passed|failed|running)$")
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = Field(None, ge=0, le=3600000)  # Max 1 hour
    total_tests: int = Field(0, ge=0, le=10000)
    passed_tests: int = Field(0, ge=0, le=10000)
    failed_tests: int = Field(0, ge=0, le=10000)
    skipped_tests: int = Field(0, ge=0, le=10000)
    coverage_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    log_output: Optional[str] = Field(None, max_length=MAX_LOG_OUTPUT_LENGTH)
    triggered_by: Optional[int] = Field(None, gt=0)
    metadata_json: Optional[Dict[str, Any]] = None

    @field_validator('finished_at')
    @classmethod
    def finish_not_before_start(cls, v, info):
        start = info.data.get('started_at')
        if v and start and v < start:
            raise ValueError('finish time cannot be before start time')
        return v

    @field_validator('total_tests')
    @classmethod
    def validate_test_counts(cls, v, info):
        passed = info.data.get('passed_tests', 0)
        failed = info.data.get('failed_tests', 0)
        skipped = info.data.get('skipped_tests', 0)
        if passed + failed + skipped > v:
            raise ValueError('sum of passed/failed/skipped tests cannot exceed total')
        return v


class TestRunCreate(TestRunBase):
    pass


class TestRunUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(passed|failed|running)$")
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = Field(None, ge=0, le=3600000)
    total_tests: Optional[int] = Field(None, ge=0, le=10000)
    passed_tests: Optional[int] = Field(None, ge=0, le=10000)
    failed_tests: Optional[int] = Field(None, ge=0, le=10000)
    skipped_tests: Optional[int] = Field(None, ge=0, le=10000)
    coverage_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    log_output: Optional[str] = Field(None, max_length=MAX_LOG_OUTPUT_LENGTH)



class TestRunResponse(TestRunBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# --- Test Case Schemas ---


class TestCaseBase(BaseModel):
    run_id: int = Field(..., gt=0)
    test_name: str = Field(..., max_length=MAX_TEST_NAME_LENGTH)
    test_class: Optional[str] = Field(None, max_length=MAX_TEST_NAME_LENGTH)
    file_path: Optional[str] = Field(None, max_length=MAX_FILE_PATH_LENGTH)
    status: str = Field(..., pattern="^(passed|failed|skipped|error)$")
    duration_ms: int = Field(0, ge=0, le=300000)  # Max 5 minutes
    error_message: Optional[str] = Field(None, max_length=5000)
    stack_trace: Optional[str] = Field(None, max_length=10000)
    assertion_details: Optional[Dict[str, Any]] = None
    compliance_tags: Optional[Dict[str, str]] = None


class TestCaseCreate(TestCaseBase):
    pass


class TestCaseUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(passed|failed|skipped|error)$")
    duration_ms: Optional[int] = Field(None, ge=0, le=300000)
    error_message: Optional[str] = Field(None, max_length=5000)
    stack_trace: Optional[str] = Field(None, max_length=10000)
    assertion_details: Optional[Dict[str, Any]] = None


class TestCaseResponse(TestCaseBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# --- Coverage Report Schemas ---


class TestCoverageReportBase(BaseModel):
    module_name: str = Field(..., max_length=MAX_MODULE_NAME_LENGTH)
    reported_at: datetime
    line_coverage_percent: Decimal = Field(..., ge=0, le=100)
    branch_coverage_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    function_coverage_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    missed_lines: Optional[str] = Field(None, max_length=MAX_MISSED_LINES_LENGTH)
    complexity_score: Optional[int] = Field(None, ge=0, le=1000)
    issues_found: Optional[int] = Field(None, ge=0, le=1000)
    security_findings: Optional[int] = Field(None, ge=0, le=100)


class TestCoverageReportCreate(TestCoverageReportBase):
    pass


class TestCoverageReportUpdate(BaseModel):
    line_coverage_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    branch_coverage_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    function_coverage_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    missed_lines: Optional[str] = Field(None, max_length=MAX_MISSED_LINES_LENGTH)
    complexity_score: Optional[int] = Field(None, ge=0, le=1000)
    issues_found: Optional[int] = Field(None, ge=0, le=1000)
    security_findings: Optional[int] = Field(None, ge=0, le=100)


class TestCoverageReportResponse(TestCoverageReportBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime