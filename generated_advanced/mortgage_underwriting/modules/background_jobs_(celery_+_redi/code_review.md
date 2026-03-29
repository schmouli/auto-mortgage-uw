```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/background_jobs/routes.py",
      "line": 33,
      "description": "Undefined logger variable used in exception handler. Will raise NameError at runtime.",
      "suggested_fix": "Add logger import at top of file:\n```python\nimport structlog\nlogger = structlog.get_logger(__name__)\n```"
    },
    {
      "severity": "critical",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/background_jobs/services.py",
      "line": 25,
      "description": "Inconsistent datetime handling: models use timezone-aware DateTime but service uses naive datetime.now(). This causes timezone mismatch errors.",
      "suggested_fix": "Replace datetime.now() with timezone-aware UTC timestamp:\n```python\nfrom datetime import datetime, timezone\njob_record = BackgroundJob(\n    job_name=job_name,\n    task_id=task_id,\n    status=\"queued\",\n    params=str(payload.params) if payload.params else None,\n    created_at=datetime.now(timezone.utc)\n)\n```"
    },
    {
      "severity": "critical",
      "category": "security",
      "file": "mortgage_underwriting/modules/background_jobs/routes.py",
      "line": 18,
      "description": "Admin endpoint lacks authentication and rate limiting. Exposes job trigger functionality to unauthenticated users.",
      "suggested_fix": "Add authentication and rate limiting:\n```python\nfrom fastapi import Security\nfrom mortgage_underwriting.common.security import verify_token\nfrom slowapi import Limiter\n\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.post(\"/{job_name}/trigger\", response_model=JobTriggerResponse)\n@limiter.limit(\"5/minute\")\nasync def trigger_background_job(\n    job_name: str,\n    payload: JobTriggerRequest,\n    db: Annotated[AsyncSession, Depends(get_async_session)],\n    user: Annotated[dict, Security(verify_token, scopes=[\"admin:jobs\"])]\n) -> JobTriggerResponse:\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/background_jobs/exceptions.py",
      "line": 1,
      "description": "Dead code: JobNotFoundException is defined but never used. Services use AppException instead, creating inconsistent error handling.",
      "suggested_fix": "Remove unused exception class and standardize on AppException:\n```python\n# Delete this entire file\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "mortgage_underwriting/modules/background_jobs/tests.py",
      "line": 1,
      "description": "Missing unit and integration tests for BackgroundJobService methods and route handlers. Only test fixtures are provided.",
      "suggested_fix": "Create comprehensive test file tests/unit/test_background_jobs.py:\n```python\nimport pytest\nfrom unittest.mock import AsyncMock, patch\nfrom mortgage_underwriting.modules.background_jobs.services import BackgroundJobService\n\n@pytest.mark.unit\nasync def test_trigger_job_success(db_session, mock_celery_task):\n    service = BackgroundJobService(db_session)\n    payload = JobTriggerRequest(force=False, params={\"test\": \"data\"})\n    \n    # Mock schedule existence\n    schedule = JobSchedule(job_name=\"test_job\", schedule_expression=\"0 * * * *\")\n    db_session.add(schedule)\n    await db_session.commit()\n    \n    result = await service.trigger_job(\"test_job\", payload)\n    assert result.job_name == \"test_job\"\n    assert result.status == \"queued\"\n    assert result.task_id.startswith(\"task_\")\n\n@pytest.mark.unit\nasync def test_trigger_job_not_found(db_session):\n    service = BackgroundJobService(db_session)\n    payload = JobTriggerRequest()\n    \n    with pytest.raises(AppException) as exc:\n        await service.trigger_job(\"nonexistent\", payload)\n    assert exc.value.error_code == \"JOB_001\"\n```"
    },
    {
      "severity": "high",
      "category": "database",
      "file": "mortgage_underwriting/modules/background_jobs/models.py",
      "line": 19,
      "description": "Missing index on status column. The status column is frequently queried for job monitoring but lacks an index, causing full table scans.",
      "suggested_fix": "Add index to status column and create composite indexes:\n```python\nstatus: Mapped[str] = mapped_column(String(20), nullable=False, index=True)\n\n__table_args__ = (\n    Index('ix_background_jobs_job_name_status', 'job_name', 'status'),\n    Index('ix_background_jobs_status_created_at', 'status', 'created_at'),\n)\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/background_jobs/services.py",
      "line": 27,
      "description": "Magic number/string: Hardcoded status value 'queued' without using a constant enum. Scattered status strings across codebase create maintenance risk.",
      "suggested_fix": "Create enum for job statuses:\n```python\nfrom enum import Enum\n\nclass JobStatus(str, Enum):\n    QUEUED = \"queued\"\n    STARTED = \"started\"\n    SUCCESS = \"success\"\n    FAILURE = \"failure\"\n    RETRYING = \"retrying\"\n    RUNNING = \"running\"\n\n# Use in model\ndefault=JobStatus.QUEUED.value\n```"
    },
    {
      "severity": "high",
      "category": "performance",
      "file": "mortgage_underwriting/modules/background_jobs/services.py",
      "line": 24,
      "description": "Poor task_id generation using timestamp creates collision risk under high concurrency. Celery integration would fail with duplicate IDs.",
      "suggested_fix": "Use UUID for unique task identification:\n```python\nimport uuid\ntask_id = f\"task_{uuid.uuid4().hex}\"\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/background_jobs/schemas.py",
      "line": 28,
      "description": "No validation for cron expression format in schedule_expression field. Invalid cron strings cause runtime scheduler errors.",
      "suggested_fix": "Add Pydantic validator for cron expressions:\n```python\nfrom pydantic import field_validator\nfrom croniter import croniter\n\n@field_validator('schedule_expression')\n@classmethod\ndef validate_cron(cls, v: str) -> str:\n    if not croniter.is_valid(v):\n        raise ValueError('Invalid cron expression')\n    return v\n```"
    },
    {
      "severity": "medium",
      "category": "database",
      "file": "mortgage_underwriting/modules/background_jobs/services.py",
      "line": 56,
      "description": "N+1 query risk in get_job_status when fetching latest execution. While limited to 1 record, pattern could be misused for batch operations.",
      "suggested_fix": "Use eager loading pattern for future scalability:\n```python\nfrom sqlalchemy.orm import joinedload\n\njob_result = await self.db.execute(\n    select(BackgroundJob)\n    .where(BackgroundJob.job_name == job_name)\n    .options(joinedload(BackgroundJob.schedule))\n    .order_by(BackgroundJob.created_at.desc())\n    .limit(1)\n)\n```"
    },
    {
      "severity": "medium",
      "category": "performance",
      "file": "mortgage_underwriting/modules/background_jobs/services.py",
      "line": 62,
      "description": "Redundant Decimal conversion: duration_seconds is already Decimal type from model, converting to string then Decimal is inefficient.",
      "suggested_fix": "Remove redundant conversion:\n```python\nduration_seconds=job.duration_seconds,  # Already Decimal type\n```"
    },
    {
      "severity": "medium",
      "category": "observability",
      "file": "mortgage_underwriting/modules/background_jobs/routes.py",
      "line": 18,
      "description": "Missing OpenTelemetry tracing and Prometheus metrics decorators on endpoints. Required by project observability standards.",
      "suggested_fix": "Add observability decorators:\n```python\nfrom mortgage_underwriting.common.observability import trace_endpoint, metrics_timer\n\n@router.post(\"/{job_name}/trigger\")\n@trace_endpoint\n@metrics_timer(\"job_trigger_duration_seconds\")\nasync def trigger_background_job(...):\n```"
    },
    {
      "severity": "low",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/background_jobs/routes.py",
      "line": 21,
      "description": "Service class instantiated directly in route handler instead of using dependency injection pattern.",
      "suggested_fix": "Use FastAPI Depends for service injection:\n```python\nasync def get_job_service(db: AsyncSession = Depends(get_async_session)) -> BackgroundJobService:\n    return BackgroundJobService(db)\n\n@router.post(\"/{job_name}/trigger\")\nasync def trigger_background_job(\n    job_name: str,\n    payload: JobTriggerRequest,\n    service: BackgroundJobService = Depends(get_job_service)\n) -> JobTriggerResponse:\n```"
    }
  ],
  "summary": "BLOCKED: Critical runtime error (undefined logger) and security issues (no auth/rate limiting) must be fixed. High-severity issues include dead code, missing tests, and database performance concerns. Medium issues involve validation gaps and observability missing required decorators."
}
```