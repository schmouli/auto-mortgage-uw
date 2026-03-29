```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/fintrac/routes.py",
      "line": 7,
      "description": "Invalid Python import syntax - import statement is split across lines with services import inserted in the middle, causing syntax error",
      "suggested_fix": "Fix import structure:\n```python\nfrom mortgage_underwriting.modules.fintrac.schemas import (\n    FintracVerificationRequest,\n    FintracTransactionReportRequest,\n    FintracVerificationResponse,\n    FintracVerificationStatusResponse,\n    FintracReportListResponse,\n    FintracRiskAssessmentResponse\n)\nfrom mortgage_underwriting.modules.fintrac.services import FintracComplianceService\n```"
    },
    {
      "severity": "critical",
      "category": "database",
      "file": "mortgage_underwriting/modules/fintrac/models.py",
      "line": 46,
      "description": "FINTRAC regulatory violation: `is_deleted` flag allows soft deletion of financial transaction records, violating FINTRAC immutability requirement ('never deleted or modified') and 5-year retention mandate",
      "suggested_fix": "Remove `is_deleted` column entirely. FINTRAC records must be immutable. Add comment: '# FINTRAC records immutable per regulation - no deletion allowed'"
    },
    {
      "severity": "critical",
      "category": "database",
      "file": "mortgage_underwriting/modules/fintrac/models.py",
      "line": 48,
      "description": "FINTRAC regulatory violation: `updated_at` field implies mutable records, violating immutable audit trail requirement",
      "suggested_fix": "Remove `updated_at` column. FINTRAC verification and report records must be immutable once created. Only `created_at`/`record_created_at` should exist."
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/fintrac/services.py",
      "line": 57,
      "description": "Magic number: 5 minute duplicate check window is hardcoded, not configurable, and lacks business logic justification",
      "suggested_fix": "Define constant at module level:\n```python\nDUPLICATE_VERIFICATION_WINDOW_MINUTES = 5  # Configurable duplicate check window\n```\nThen use: `datetime.now(timezone.utc) - timedelta(minutes=DUPLICATE_VERIFICATION_WINDOW_MINUTES)`"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/fintrac/services.py",
      "line": 117,
      "description": "Magic number: $10,000 threshold for large cash transactions is hardcoded, should be configurable constant per FINTRAC regulations",
      "suggested_fix": "Define constant:\n```python\nFINTRAC_LARGE_TRANSACTION_THRESHOLD = Decimal('10000.00')  # CAD\n```\nThen use: `if payload.report_type == 'large_cash_transaction' and payload.amount > FINTRAC_LARGE_TRANSACTION_THRESHOLD:`"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/fintrac/routes.py",
      "line": 26,
      "description": "Repetitive error handling pattern across all endpoints violates DRY principle and centralizes error handling logic in each route",
      "suggested_fix": "Create custom exception handler dependency:\n```python\nfrom fastapi import Request\nfrom mortgage_underwriting.common.exceptions import AppException\n\nasync def fintrac_exception_handler(request: Request, call_next):\n    try:\n        return await call_next(request)\n    except AppException as e:\n        raise HTTPException(status_code=400, detail={'detail': e.detail, 'error_code': e.error_code})\n    except Exception:\n        logger.error('unexpected_error', path=request.url.path)\n        raise HTTPException(status_code=500, detail={'detail': 'An unexpected error occurred', 'error_code': 'INTERNAL_ERROR'})\n```"
    },
    {
      "severity": "high",
      "category": "performance",
      "file": "mortgage_underwriting/modules/fintrac/services.py",
      "line": 129,
      "description": "N+1 query pattern: Each endpoint independently queries MortgageApplication existence, causing redundant database hits",
      "suggested_fix": "Create reusable dependency for application validation:\n```python\nasync def get_application_or_404(db: AsyncSession, application_id: int) -> MortgageApplication:\n    result = await db.execute(select(MortgageApplication).where(MortgageApplication.id == application_id))\n    application = result.scalar_one_or_none()\n    if not application:\n        raise NotFoundError(detail='Application not found', error_code='FINTRAC_001')\n    return application\n```"
    },
    {
      "severity": "high",
      "category": "performance",
      "file": "mortgage_underwriting/modules/fintrac/services.py",
      "line": 135,
      "description": "Missing pagination on list endpoints (`get_verification_status`, `list_reports`) could return unlimited results, causing memory issues",
      "suggested_fix": "Add pagination parameters:\n```python\nasync def get_verification_status(self, application_id: int, skip: int = 0, limit: int = 100) -> List[FintracVerificationStatusResponse]:\n    query = select(FintracVerification).where(...).offset(skip).limit(limit)\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 25,
      "description": "Test fixtures define fields (`applicant_id`, `transaction_type`) that don't match actual FINTRAC schemas, indicating tests don't align with implementation",
      "suggested_fix": "Update fixtures to match actual schemas:\n```python\ndef valid_transaction_payload() -> dict:\n    return {\n        'report_type': 'large_cash_transaction',\n        'amount': '5000.00',\n        'currency': 'CAD',\n        'created_by': 1\n    }\n```"
    },
    {
      "severity": "medium",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/fintrac/services.py",
      "line": 46,
      "description": "Uses deprecated `datetime.utcnow()` which returns naive datetime. Should use timezone-aware UTC datetime per Python 3.12+ best practices",
      "suggested_fix": "Replace with: `from datetime import datetime, timezone` and use `datetime.now(timezone.utc)`"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/fintrac/models.py",
      "line": 33,
      "description": "Redundant timestamp fields: `record_created_at` and `created_at` serve identical purpose, causing confusion and data inconsistency risk",
      "suggested_fix": "Remove `record_created_at` and keep only `created_at` with comment: '# FINTRAC audit timestamp - immutable'"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/fintrac/schemas.py",
      "line": 58,
      "description": "Schema field mismatch: `FintracRiskAssessmentResponse` references `last_verified_at` but model has `verified_at` and `record_created_at`, causing potential validation errors",
      "suggested_fix": "Align schema with model: rename to `verified_at: datetime` or add computed property in service"
    },
    {
      "severity": "medium",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/fintrac/exceptions.py",
      "line": 4,
      "description": "Custom exception doesn't inherit from `AppException` base class defined in common.exceptions, breaking centralized error handling",
      "suggested_fix": "Update inheritance:\n```python\nfrom mortgage_underwriting.common.exceptions import AppException\n\nclass FintracComplianceError(AppException):\n    def __init__(self, detail: str, error_code: str):\n        super().__init__(detail, error_code)\n```"
    },
    {
      "severity": "medium",
      "category": "security",
      "file": "mortgage_underwriting/modules/fintrac/schemas.py",
      "line": 34,
      "description": "PIPEDA data minimization: `FintracVerificationStatusResponse` includes `id_type` and `id_expiry_date` which may be more than necessary for status checks, increasing PII exposure surface",
      "suggested_fix": "Create minimal status schema without ID details:\n```python\nclass FintracVerificationMinimalResponse(BaseModel):\n    verification_id: int\n    risk_level: str\n    verified_at: datetime\n    requires_enhanced_due_diligence: bool\n```"
    },
    {
      "severity": "low",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/fintrac/services.py",
      "line": 102,
      "description": "Duplicate logic for `requires_enhanced_due_diligence` calculation in multiple places violates DRY principle",
      "suggested_fix": "Add helper method:\n```python\ndef _requires_enhanced_diligence(self, verification: FintracVerification) -> bool:\n    return verification.risk_level == 'high' or verification.is_pep or verification.is_hio\n```"
    }
  ],
  "summary": "BLOCKED: Critical regulatory compliance violations (mutable FINTRAC records with is_deleted flag) and fatal syntax errors in routes.py imports prevent deployment. High-severity issues include missing rate limiting, pagination, and misaligned test fixtures. Medium-severity concerns around deprecated datetime usage and exception hierarchy require attention."
}
```