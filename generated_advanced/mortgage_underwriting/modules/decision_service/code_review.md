```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/decision/models.py",
      "line": 26,
      "description": "Missing foreign key constraint on application_id. DecisionRecord should reference applications table but has no ForeignKey definition, breaking referential integrity.",
      "suggested_fix": "Add ForeignKey constraint:\n```python\napplication_id: Mapped[UUID] = mapped_column(\n    PG_UUID(as_uuid=True), \n    ForeignKey(\"applications.id\", ondelete=\"CASCADE\"), \n    nullable=False, \n    index=True\n)\n```"
    },
    {
      "severity": "critical",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/decision/services.py",
      "line": 27,
      "description": "Complex function evaluate() exceeds 50 lines (approx. 80 lines) with high cyclomatic complexity. Contains duplicate payment calculation logic and multiple responsibilities.",
      "suggested_fix": "Refactor into smaller methods:\n```python\nasync def evaluate(self, payload: DecisionEvaluateRequest) -> DecisionEvaluateResponse:\n    stress_rate = self._calculate_stress_rate(payload.loan_data.contract_rate)\n    monthly_payment = self._calculate_mortgage_payment(...)\n    stress_payment = self._calculate_mortgage_payment(...)\n    ratios = self._calculate_ratios(payload, stress_payment)\n    decision, confidence = self._determine_decision(ratios)\n    return await self._save_and_return(payload, decision, confidence, ratios, stress_rate)\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/decision/services.py",
      "line": 34,
      "description": "DRY violation: Mortgage payment calculation logic duplicated for standard and stress-tested payments. Same formula repeated with different interest rates.",
      "suggested_fix": "Extract to helper method:\n```python\ndef _calculate_mortgage_payment(self, principal: Decimal, annual_rate: Decimal, years: int) -> Decimal:\n    monthly_rate = annual_rate / Decimal('12') / Decimal('100')\n    n_payments = years * 12\n    if monthly_rate == 0:\n        return principal / Decimal(n_payments)\n    return principal * (monthly_rate * (1 + monthly_rate) ** n_payments) / ((1 + monthly_rate) ** n_payments - 1)\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/decision/services.py",
      "line": 61,
      "description": "Magic numbers for regulatory limits (39, 44, 95) and thresholds hardcoded throughout. Violates maintainability and makes updates difficult.",
      "suggested_fix": "Add module-level constants:\n```python\nOSFI_GDS_LIMIT = Decimal('39')\nOSFI_TDS_LIMIT = Decimal('44')\nOSFI_LTV_MAX = Decimal('95')\nCONDITIONAL_GDS_LIMIT = Decimal('42')\nCONDITIONAL_TDS_LIMIT = Decimal('47')\nCMHC_INSURANCE_THRESHOLD = Decimal('80')\n```"
    },
    {
      "severity": "high",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/decision/routes.py",
      "line": 28,
      "description": "Bare except clause in spirit - catches all exceptions indiscriminately and exposes internal error details via str(e). Risk of leaking sensitive data.",
      "suggested_fix": "Catch specific exceptions and use structured errors:\n```python\nfrom mortgage_underwriting.modules.decision.exceptions import DecisionEngineError\n\nexcept DecisionEngineError as e:\n    raise HTTPException(status_code=400, detail={\"error_code\": \"DECISION_ERROR\", \"message\": str(e)})\nexcept Exception as e:\n    logger.error(\"unexpected_error\", error=str(e))\n    raise HTTPException(status_code=500, detail={\"error_code\": \"INTERNAL_ERROR\", \"message\": \"Decision evaluation failed\"})\n```"
    },
    {
      "severity": "high",
      "category": "performance",
      "file": "mortgage_underwriting/modules/decision/routes.py",
      "line": 17,
      "description": "Missing rate limiting on critical underwriting endpoint. Exposes system to abuse and violates security requirements.",
      "suggested_fix": "Add rate limiting:\n```python\nfrom slowapi import Limiter\nfrom slowapi.util import get_remote_address\n\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.post(\"/evaluate\", ...)\n@limiter.limit(\"5/minute\")\nasync def evaluate_decision(request: Request, ...):\n    ...\n```"
    },
    {
      "severity": "high",
      "category": "database",
      "file": "mortgage_underwriting/modules/decision/models.py",
      "line": 18,
      "description": "Missing SQLAlchemy relationship definition. No relationship to Application model prevents proper ORM usage and can cause N+1 queries.",
      "suggested_fix": "Add relationship:\n```python\nfrom sqlalchemy.orm import relationship\n\nclass DecisionRecord(Base):\n    ...\n    application: Mapped[\"Application\"] = relationship(\"Application\", back_populates=\"decisions\")\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 15,
      "description": "Test fixtures use SQLite instead of PostgreSQL, causing dialect differences (UUID handling, Numeric precision, JSON operations) that won't catch production bugs.",
      "suggested_fix": "Use PostgreSQL test container:\n```python\n@pytest.fixture(scope=\"session\")\nasync def db_engine():\n    from testcontainers.postgres import PostgresContainer\n    postgres = PostgresContainer(\"postgres:15\")\n    postgres.start()\n    engine = create_async_engine(postgres.get_connection_url())\n    yield engine\n    postgres.stop()\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/decision/services.py",
      "line": 88,
      "description": "Uses deprecated datetime.utcnow() which is removed in Python 3.12+. Should use timezone-aware datetime.",
      "suggested_fix": "Replace with:\n```python\nfrom datetime import datetime, timezone\n\"timestamp\": datetime.now(timezone.utc).isoformat()\n```"
    },
    {
      "severity": "medium",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/decision/services.py",
      "line": 99,
      "description": "Database commit without try/except block. If database operation fails, leaves system in inconsistent state without proper rollback.",
      "suggested_fix": "Wrap in try/except with rollback:\n```python\ntry:\n    self.db.add(record)\n    await self.db.commit()\n    await self.db.refresh(record)\nexcept Exception as e:\n    await self.db.rollback()\n    logger.error(\"database_error\", error=str(e))\n    raise CalculationError(\"Failed to save decision record\")\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/decision/exceptions.py",
      "line": 1,
      "description": "Custom exceptions inherit from base Exception instead of AppException from common.exceptions, breaking consistent error handling across modules.",
      "suggested_fix": "Change base class:\n```python\nfrom mortgage_underwriting.common.exceptions import AppException\n\nclass DecisionEngineError(AppException):\n    pass\n```"
    },
    {
      "severity": "medium",
      "category": "performance",
      "file": "mortgage_underwriting/modules/decision/services.py",
      "line": 102,
      "description": "Converts Decimal ratios to float in logs, causing precision loss and potential regulatory audit issues. Financial values should remain Decimal.",
      "suggested_fix": "Remove float conversion or log as Decimal:\n```python\nlogger.info(\"decision_evaluate_complete\", \n           application_id=payload.application_id,\n           decision=decision,\n           gds=str(gds),  # Convert to string to avoid precision loss\n           tds=str(tds))\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/decision/services.py",
      "line": 69,
      "description": "Hardcoded model version '1.0.0' should be configurable via common.config.py to allow version updates without code changes.",
      "suggested_fix": "Move to config:\n```python\nfrom mortgage_underwriting.common.config import settings\n\naudit_trail = {\n    \"model_version\": settings.DECISION_MODEL_VERSION\n}\n```"
    },
    {
      "severity": "low",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/decision/schemas.py",
      "line": 40,
      "description": "ExceptionItem.severity uses string type instead of Enum, allowing invalid values at runtime.",
      "suggested_fix": "Use Enum:\n```python\nfrom enum import Enum\n\nclass ExceptionSeverity(str, Enum):\n    ERROR = \"error\"\n    WARNING = \"warning\"\n    INFO = \"info\"\n\nclass ExceptionItem(BaseModel):\n    severity: ExceptionSeverity\n```"
    },
    {
      "severity": "low",
      "category": "database",
      "file": "mortgage_underwriting/modules/decision/models.py",
      "line": 33,
      "description": "Indexes are not composite. Frequently queried together columns (application_id, created_at) could benefit from composite index.",
      "suggested_fix": "Add composite index:\n```python\n__table_args__ = (\n    Index(\"ix_decision_records_app_created\", \"application_id\", \"created_at\"),\n)\n```"
    }
  ],
  "summary": "CRITICAL and HIGH severity issues block approval. Missing foreign key constraint breaks data integrity. Complex evaluate() function violates DRY principle with duplicated payment calculations and hardcoded magic numbers for regulatory limits. No rate limiting on critical endpoint poses security risk. Test fixtures use wrong database dialect. Exception handling is too broad and inconsistent with project conventions. Database operations lack proper transaction management. Several medium-severity issues including deprecated datetime usage and precision loss in logs require attention before production deployment."
}
```