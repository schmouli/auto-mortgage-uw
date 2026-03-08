# Background Jobs (Celery + Redis)
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Background Jobs Module Design Plan

**Module Path:** `modules/background_jobs/`  
**Feature Slug:** `background-jobs-celery`  
**Document Path:** `docs/design/background-jobs-celery.md`

---

## 1. Endpoints

### Job Management Endpoints

**`POST /api/v1/jobs/trigger/{task_name}`**
- **Auth:** Admin-only (scope `jobs:manage`)
- **Request:** 
  ```json
  {
    "task_name": "send_document_reminder",
    "run_immediately": false,
    "params": {"application_id": "uuid-here"} // optional
  }
  ```
- **Response (202 Accepted):**
  ```json
  {
    "task_id": "celery-task-uuid",
    "status": "queued",
    "scheduled_at": "2024-01-15T09:00:00Z"
  }
  ```
- **Errors:**
  - `400` `JOBS_001` - Invalid task name
  - `401` - Missing/invalid JWT
  - `403` - Insufficient permissions
  - `422` - Validation error in params

**`GET /api/v1/jobs/status/{task_id}`**
- **Auth:** Admin-only
- **Response (200):**
  ```json
  {
    "task_id": "celery-task-uuid",
    "task_name": "send_document_reminder",
    "status": "success|failure|pending|retry",
    "started_at": "2024-01-15T09:00:05Z",
    "completed_at": "2024-01-15T09:00:45Z",
    "result": {"emails_sent": 12},
    "error": null
  }
  ```
- **Errors:**
  - `404` `JOBS_002` - Task not found

**`GET /api/v1/jobs/schedule`**
- **Auth:** Admin-only
- **Response (200):**
  ```json
  {
    "schedules": [
      {
        "task": "send_document_reminder",
        "cron": "0 9 * * *",
        "last_run": "2024-01-14T09:00:00Z",
        "next_run": "2024-01-15T09:00:00Z",
        "is_active": true
      }
    ]
  }
  ```

**`POST /api/v1/jobs/schedule/{task_name}/enable`**
- **Auth:** Admin-only
- **Response (200):** `{"task": "...", "is_active": true}`

---

## 2. Models & Database

### `job_execution_log` Table
```python
class JobExecutionLog(Base):
    __tablename__ = "job_execution_log"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # pending, running, success, failure, retry
    retry_count: Mapped[int] = mapped_column(default=0)
    
    # Timing
    scheduled_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(nullable=True)
    completed_at: Mapped[datetime] = mapped_column(nullable=True)
    
    # Result/data (encrypted if contains PII)
    result: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Audit & compliance
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="system")  # For manual triggers
    
    # FINTRAC audit requirement: immutable record
    __table_args__ = (
        Index('ix_job_execution_log_task_status', 'task_name', 'status'),
        Index('ix_job_execution_log_date_range', 'scheduled_at', 'completed_at'),
    )
```

### `email_template` Table
```python
class EmailTemplate(Base):
    __tablename__ = "email_template"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    template_key: Mapped[str] = mapped_column(String(100), unique=True)  # e.g., "document_reminder"
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Rate limiting config
    max_emails_per_hour: Mapped[int] = mapped_column(default=100)
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
```

### `monthly_report` Table (CMHC/FINTRAC retention)
```python
class MonthlyReport(Base):
    __tablename__ = "monthly_report"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_month: Mapped[str] = mapped_column(String(7), unique=True, index=True)  # YYYY-MM
    report_type: Mapped[str] = mapped_column(String(50))  # "underwriting_summary", "fintrac_audit"
    
    # Report file stored in secure vault (S3 with encryption)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 for integrity
    
    # Encrypted metadata (contains aggregate counts, NO PII)
    report_metadata: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # AES-256 encrypted JSON
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by: Mapped[str] = mapped_column(default="system")
    
    # 5-year retention marker (FINTRAC requirement)
    retention_until: Mapped[datetime] = mapped_column(nullable=False)
```

---

## 3. Business Logic

### Task: `send_document_reminder`
- **Schedule:** Daily 9:00 AM UTC
- **Logic:**
  1. Query applications with `status='submitted'` AND `documents_completed=False`
  2. Filter where `last_reminder_sent < NOW() - INTERVAL '48 hours'` OR `last_reminder_sent IS NULL`
  3. For each application:
     - Render email template with `application_id`, `client_name` (hashed), `missing_docs_list`
     - **PIPEDA Compliance:** Do NOT include SIN, DOB, or full address in email body
     - Send via email service with rate limiting (100/hour max)
     - Log `job_execution_log.result` as `{"application_id": "...", "email_sent": true}` (NO PII)
     - Update `application.last_reminder_sent = NOW()`
  4. **Retry:** 3 attempts with exponential backoff (5min, 15min, 45min)
  5. **Error Handling:** On failure, log error and continue to next application

### Task: `check_rate_expiry`
- **Schedule:** Daily 7:00 AM UTC
- **Logic:**
  1. Query `lender_product` where `rate_expiry_date < NOW()` AND `is_active=True`
  2. For each expired product:
     - Set `is_active=False`, `expiry_flagged_at=NOW()`
     - Create `lender_product_audit_log` entry (immutable)
     - **OSFI B-20 Impact:** If product was used in stress test calculations, mark affected applications for recalculation
  3. Log summary: `{"expired_products_count": 5, "affected_applications": [...]}`

### Task: `check_condition_due_dates`
- **Schedule:** Daily 8:00 AM UTC
- **Logic:**
  1. Query `lender_condition` where `due_date < NOW()` AND `status='pending'`
  2. For each overdue condition:
     - Update status to `overdue`
     - Create `condition_overdue_event` log (FINTRAC audit trail)
     - **FINTRAC Trigger:** If condition related to identity verification, flag for manual review
  3. Send notification to underwriting team (internal only, no client PII in message)

### Task: `generate_monthly_report`
- **Schedule:** 1st of month 6:00 AM UTC
- **Logic:**
  1. **CMHC Report:** Aggregate LTV ratios, insurance premiums by tier
     - Use Decimal for ALL calculations (no float)
     - Query: `SELECT COUNT(*), SUM(loan_amount), AVG(ltv_ratio) FROM applications WHERE created_at BETWEEN ...`
  2. **FINTRAC Report:** Count applications with transactions > $10,000
     - Filter `transaction_amount > 10000`
     - Include `transaction_type_flag` counts
  3. Encrypt report metadata with AES-256 (key from `common/security.py`)
  4. Store file in S3 with versioning and 5-year retention policy
  5. **Audit:** Create `monthly_report` record with checksum for integrity verification

### Task: `cleanup_temp_uploads`
- **Schedule:** Daily 2:00 AM UTC
- **Logic:**
  1. Scan `/uploads/temp` directory for files older than 24h
  2. For each file:
     - **PIPEDA Compliance:** Before deletion, check if filename contains SIN or DOB patterns
     - If sensitive data found, move to secure quarantine instead of deletion
     - Log: `{"file_path_hash": "sha256_of_path", "action": "deleted|quarantined", "size_bytes": 1024}` (NEVER log actual filename)
  3. Use `shred` or secure delete to prevent forensic recovery

### Task: `flag_fintrac_overdue`
- **Schedule:** Daily 9:00 AM UTC
- **Logic:**
  1. Query `applications` where `fintrac_verified=False` AND `created_at < NOW() - INTERVAL '30 days'`
  2. For each application:
     - Set `fintrac_overdue_flag=True`
     - Create `fintrac_audit_log` entry with `event_type='verification_overdue'`
     - **FINTRAC Requirement:** Log immutable record with `application_id_hash` (SHA256), `flagged_at`
  3. Generate internal alert to compliance team (no PII in alert message)

---

## 4. Migrations

### New Tables
```sql
-- job_execution_log
CREATE TABLE job_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name VARCHAR(100) NOT NULL,
    task_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL,
    retry_count INTEGER DEFAULT 0,
    scheduled_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSONB,
    error_message TEXT,
    error_traceback TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system'
);
CREATE INDEX ix_job_execution_log_task_status ON job_execution_log(task_name, status);
CREATE INDEX ix_job_execution_log_date_range ON job_execution_log(scheduled_at, completed_at);
CREATE INDEX ix_job_execution_log_task_id ON job_execution_log(task_id);

-- email_template
CREATE TABLE email_template (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key VARCHAR(100) UNIQUE NOT NULL,
    subject VARCHAR(500) NOT NULL,
    body_html TEXT NOT NULL,
    body_text TEXT NOT NULL,
    max_emails_per_hour INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- monthly_report
CREATE TABLE monthly_report (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_month VARCHAR(7) UNIQUE NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_checksum VARCHAR(64) NOT NULL,
    report_metadata BYTEA NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',
    retention_until TIMESTAMP NOT NULL
);
CREATE INDEX ix_monthly_report_month ON monthly_report(report_month);

-- fintrac_audit_log (extension for overdue flags)
CREATE TABLE fintrac_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id_hash VARCHAR(64) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB,  -- NO PII, only metadata
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ix_fintrac_audit_log_app_hash ON fintrac_audit_log(application_id_hash);
```

### Existing Table Modifications
```sql
-- applications table
ALTER TABLE applications ADD COLUMN last_reminder_sent TIMESTAMP;
ALTER TABLE applications ADD COLUMN fintrac_overdue_flag BOOLEAN DEFAULT FALSE;

-- lender_product table
ALTER TABLE lender_product ADD COLUMN expiry_flagged_at TIMESTAMP;

-- lender_condition table
ALTER TABLE lender_condition ADD COLUMN overdue_notified_at TIMESTAMP;
```

---

## 5. Security & Compliance

### OSFI B-20
- **Stress Test Recalculation:** When `check_rate_expiry` flags a product, trigger async recalculation of affected applications' GDS/TDS using `qualifying_rate = max(contract_rate + 2%, 5.25%)`. Log calculation breakdown in `job_execution_log.result`.
- **Hard Limits:** If recalculated GDS > 39% or TDS > 44%, auto-reject application and log rejection reason.

### FINTRAC
- **5-Year Retention:** All `job_execution_log`, `fintrac_audit_log`, and `monthly_report` records have `retention_until` timestamp set to `created_at + INTERVAL '5 years'`.
- **Transaction Flagging:** `generate_monthly_report` must include count of applications where `transaction_amount > 10000` and `transaction_type_flag IS NOT NULL`.
- **Immutability:** Use PostgreSQL `EVENT TRIGGER` to prevent UPDATE/DELETE on audit tables.

### PIPEDA
- **Encryption at Rest:** `monthly_report.report_metadata` encrypted with AES-256 via `common/security.encrypt_pii()`.
- **Data Minimization:** Job logs NEVER contain SIN, DOB, income, or banking details. Use hashed identifiers only.
- **Secure Deletion:** `cleanup_temp_uploads` uses `shred -u -z` pattern for files containing potential PII.

### Authentication & Authorization
- All management endpoints require JWT with `admin` role and scope `jobs:manage`.
- Celery workers authenticate to PostgreSQL using mTLS certificates (not passwords).
- Redis broker uses password + TLS encryption in transit.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Scenario |
|-----------------|-------------|------------|-----------------|------------------|
| `JobNotFoundError` | 404 | `JOBS_001` | "Job {task_id} not found" | Invalid task_id in status check |
| `JobValidationError` | 422 | `JOBS_002` | "Invalid task parameter: {detail}" | Missing required param in trigger |
| `JobScheduleError` | 409 | `JOBS_003` | "Job {task_name} is already running" | Attempt to run duplicate daily job |
| `JobExecutionError` | 500 | `JOBS_004` | "Job failed after {retry_count} retries" | All retries exhausted |
| `JobPermissionError` | 403 | `JOBS_005` | "Insufficient permissions to manage jobs" | Non-admin access attempt |
| `JobRateLimitError` | 429 | `JOBS_006` | "Email rate limit exceeded: {count}/hour" | `send_document_reminder` hits template limit |

### Celery-Specific Error Handling
- **Dead Letter Queue:** Failed tasks after max retries routed to `dlq_{task_name}` queue.
- **Monitoring:** Prometheus metrics exposed at `/metrics`:
  - `celery_task_total{task_name, status}` counter
  - `celery_task_duration_seconds{task_name}` histogram
  - `celery_task_retries{task_name}` counter
- **Alerts:** PagerDuty alert on `JOBS_004` errors > 5/hour or any FINTRAC-related job failure.

---

## Infrastructure Configuration

### Celery Configuration (`modules/background_jobs/celery_app.py`)
```python
# Broker settings
broker_url = "redis://localhost:6379/0"
broker_transport_options = {
    'visibility_timeout': 3600,  # 1 hour
    'fanout_prefix': True,
    'fanout_patterns': True,
}

# Worker settings
worker_pool = "prefork"
worker_concurrency = 4  # Scales with CPU cores
worker_max_tasks_per_child = 1000  # Prevent memory leaks
worker_prefetch_multiplier = 1  # Fair distribution

# Retry & DLQ
task_acks_late = True  # Ack after task completes
task_reject_on_worker_lost = True
task_default_retry_delay = 300  # 5 minutes
task_max_retries = 3

# Beat schedule (imported from beat_schedule.py)
beat_schedule = {
    "send_document_reminder": {
        "task": "modules.background_jobs.tasks.send_document_reminder",
        "schedule": crontab(hour=9, minute=0),
    },
    # ... other schedules
}
```

### Rate Limiting (`services.py`)
```python
async def check_email_rate_limit(template_key: str) -> bool:
    """Redis-backed sliding window rate limiter"""
    key = f"email_limit:{template_key}:{datetime.utcnow().hour}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 3600)
    template = await get_email_template(template_key)
    return count <= template.max_emails_per_hour
```

---

## Monitoring & Observability

### Logging (structlog)
```python
logger.bind(
    correlation_id=get_correlation_id(),
    task_name=task_name,
    task_id=task_id
).info(
    "job_started",
    scheduled_at=scheduled_at.isoformat()
)
# NEVER log: SIN, DOB, income, banking data, full file paths
```

### OpenTelemetry
- **Trace Propagation:** Use `opentelemetry.instrumentation.celery` to trace across task boundaries.
- **Baggage:** Pass `correlation_id` via Celery task headers for cross-process log correlation.

### Health Check Endpoint
**`GET /api/v1/jobs/health`**
- Returns worker status, queue depth, last successful run per task
- Used for Kubernetes liveness/readiness probes

---

## Scaling Requirements

- **Workers:** Start with 2 workers (4 concurrency each) on 2 vCPU nodes.
- **Redis:** Use Redis Cluster with 3 masters + 3 replicas for HA.
- **PostgreSQL Connections:** Pool size = `worker_concurrency * workers + 5` (e.g., 13 connections).
- **Auto-scaling:** Scale workers based on queue depth metric (`celery_queue_length > 50`).

---

## Missing Details Resolution

1. **Email Templates:** Seed default templates via Alembic migration in `email_template` table.
2. **Retry Strategy:** Exponential backoff implemented in Celery `autoretry_for` decorator.
3. **Rate Limiting:** Redis sliding window implemented in `services.check_email_rate_limit()`.
4. **Monitoring:** Prometheus metrics + Grafana dashboards configured in `common/observability.py`.
5. **Dead Letter Queue:** Celery `task_routes` config routes failures to `dlq_{task_name}`.
6. **Scaling:** HPA configured for Celery workers based on queue depth and CPU usage.

---

## Security Scanning
```bash
# Pre-deployment audit
uv add celery[redis] sqlalchemy alembic
uv run pip-audit --desc
# Must pass with zero high-severity vulnerabilities before deploy
```

---

**WARNING:** This module handles FINTRAC-regulated data. Any code change requires compliance team review before merge.