```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/dpt/services.py",
      "line": 70,
      "description": "Incorrect exception parameter type: DPTApplicationNotFoundError expects application_id (str) but receives job_id (UUID object). This will cause type errors and misleading error messages.",
      "suggested_fix": "Replace line 70 with:\n```python\nraise DPTApplicationNotFoundError(application_id=str(job_id))\n```\nAlso update lines 85 and 102 similarly."
    },
    {
      "severity": "critical",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/dpt/services.py",
      "line": 55,
      "description": "Docstring promises to raise DPTInvalidDocumentTypeError but the exception is never actually raised. Invalid document types silently default to 60 seconds instead of failing fast.",
      "suggested_fix": "Add validation after duration_map lookup:\n```python\nif estimated_duration is None:\n    raise DPTInvalidDocumentTypeError(document_type=payload.document_type)\n```"
    },
    {
      "severity": "critical",
      "category": "security",
      "file": "mortgage_underwriting/modules/dpt/models.py",
      "line": 36,
      "description": "extracted_json column stores PII (SIN, DOB, income) without encryption at rest, violating PIPEDA requirements for encryption of sensitive personal information.",
      "suggested_fix": "Add encryption using SQLAlchemy TypeDecorator:\n```python\nfrom sqlalchemy import TypeDecorator, LargeBinary\nfrom mortgage_underwriting.common.security import encrypt_pii, decrypt_pii\n\nclass EncryptedJSON(TypeDecorator):\n    impl = LargeBinary\n    \n    def process_bind_param(self, value, dialect):\n        return encrypt_pii(value) if value else None\n    \n    def process_result_value(self, value, dialect):\n        return decrypt_pii(value) if value else None\n\nextracted_json: Mapped[Optional[dict]] = mapped_column(EncryptedJSON, nullable=True)\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/dpt/services.py",
      "line": 28,
      "description": "Magic dictionary duration_map hardcoded inside method violates DRY principle and makes durations difficult to configure or test.",
      "suggested_fix": "Move to class constant:\n```python\nclass DPTService:\n    EXTRACTION_DURATIONS = {\n        DocumentType.T4: 30,\n        DocumentType.NOA: 45,\n        DocumentType.CREDIT_REPORT: 60,\n        DocumentType.BANK_STATEMENT: 120,\n        DocumentType.PURCHASE_AGREEMENT: 90\n    }\n    \n    async def submit_extraction_job(self, ...):\n        estimated_duration = self.EXTRACTION_DURATIONS.get(payload.document_type, 60)\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 1,
      "description": "Test fixtures import non-existent models (DocumentRecord, ExtractedData) that don't match actual implementation (ExtractionJob). Tests use SQLite instead of PostgreSQL, causing compatibility issues with UUID, JSONB, and PostgreSQL-specific features.",
      "suggested_fix": "Update imports and use PostgreSQL test container:\n```python\nfrom mortgage_underwriting.modules.dpt.models import ExtractionJob, DocumentType, JobStatus\nfrom mortgage_underwriting.modules.applications.models import Application\n\n# Use testcontainers for PostgreSQL\n@pytest.fixture(scope='session')\nasync def postgres_container():\n    from testcontainers.postgres import PostgresContainer\n    postgres = PostgresContainer('postgres:15')\n    postgres.start()\n    yield postgres\n    postgres.stop()\n```"
    },
    {
      "severity": "high",
      "category": "performance",
      "file": "mortgage_underwriting/modules/dpt/routes.py",
      "line": 13,
      "description": "No rate limiting on public endpoints, exposing the service to potential abuse and DoS attacks.",
      "suggested_fix": "Add rate limiting:\n```python\nfrom slowapi import Limiter, _rate_limit_exceeded_handler\nfrom slowapi.util import get_remote_address\n\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.post('/extract', ...)\n@limiter.limit('10/minute')\nasync def submit_extraction(request: Request, ...):\n    ...\n```"
    },
    {
      "severity": "high",
      "category": "database",
      "file": "mortgage_underwriting/modules/dpt/models.py",
      "line": 32,
      "description": "Missing composite index on (application_id, status) which is a common query pattern for checking job status by application.",
      "suggested_fix": "Add composite index:\n```python\n__table_args__ = (\n    Index('ix_extraction_jobs_application_id', 'application_id'),\n    Index('ix_extraction_jobs_status', 'status'),\n    Index('ix_extraction_jobs_app_status', 'application_id', 'status'),\n)\n```"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/dpt/services.py",
      "line": 92,
      "description": "progress_percent hardcoded to None instead of being calculated from job metadata, providing no real progress tracking for clients.",
      "suggested_fix": "Calculate progress based on status and timestamps:\n```python\nprogress_percent = {\n    JobStatus.QUEUED: 0,\n    JobStatus.PROCESSING: 50,\n    JobStatus.COMPLETED: 100,\n    JobStatus.FAILED: 100\n}.get(job.status, 0)\n```"
    },
    {
      "severity": "medium",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/dpt/services.py",
      "line": 73,
      "description": "Generic IntegrityError catch masks potential database issues. Should catch specific constraint violations and provide actionable error messages.",
      "suggested_fix": "Catch specific exceptions:\n```python\nfrom sqlalchemy.exc import IntegrityError, DBAPIError\n\nexcept IntegrityError as e:\n    await self.db.rollback()\n    if 'foreign_key' in str(e.orig).lower():\n        logger.error('foreign_key_violation', application_id=payload.application_id)\n        raise DPTApplicationNotFoundError(application_id=payload.application_id)\n    logger.error('db_integrity_error', error=str(e))\n    raise\n```"
    },
    {
      "severity": "medium",
      "category": "observability",
      "file": "mortgage_underwriting/modules/dpt/services.py",
      "line": 76,
      "description": "Logging statements missing correlation_id for distributed tracing across microservices.",
      "suggested_fix": "Include correlation_id in log context:\n```python\nlogger.info('extraction_job_submitted', job_id=job.id, document_type=job.document_type, correlation_id=get_correlation_id())\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/dpt/services.py",
      "line": 42,
      "description": "Callback URL is stored but never implemented. Missing webhook notification system for async job completion.",
      "suggested_fix": "Implement callback mechanism:\n```python\nasync def _notify_callback(self, job: ExtractionJob):\n    if job.callback_url:\n        try:\n            await httpx.post(job.callback_url, json={'job_id': job.id, 'status': job.status})\n        except Exception as e:\n            logger.error('callback_failed', job_id=job.id, error=str(e))\n```"
    },
    {
      "severity": "medium",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 15,
      "description": "No test fixtures for actual service methods or edge cases (invalid UUIDs, missing jobs, database errors, etc.).",
      "suggested_fix": "Add comprehensive fixtures:\n```python\n@pytest.fixture\nasync def mock_extraction_job(db_session: AsyncSession) -> ExtractionJob:\n    job = ExtractionJob(...)\n    db_session.add(job)\n    await db_session.commit()\n    return job\n\n@pytest.fixture\ndef invalid_uuid() -> UUID:\n    return UUID('00000000-0000-0000-0000-000000000000')\n```"
    },
    {
      "severity": "low",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/dpt/schemas.py",
      "line": 50,
      "description": "Extracted JSON schema lacks validation for PII fields that should be encrypted or excluded per PIPEDA.",
      "suggested_fix": "Add validator to check for forbidden fields:\n```python\n@validator('extracted_json')\ndef validate_no_pii(cls, v):\n    if v and any(key in v for key in ['sin', 'dob', 'ssn']):\n        raise ValueError('PII fields must be encrypted')\n    return v\n```"
    }
  ],
  "summary": "BLOCKED due to critical security and error handling violations. The service has PIPEDA compliance gaps (unencrypted PII in extracted_json), incorrect exception handling that will cause runtime errors, and missing functionality. High-priority issues include lack of rate limiting, hardcoded configuration, inadequate test coverage, and missing progress tracking. Architecture is generally sound but needs significant fixes before production deployment."
}
```