# Design: Background Jobs (Celery + Redis)
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Background Jobs Module Design Plan

**Module Path:** `modules/background_jobs/`  
**Feature Slug:** `background-jobs-celery-redis`  
**Document:** `docs/design/background-jobs-celery-redis.md`

---

## 1. Endpoints

### Job Management & Monitoring

#### `POST /api/v1/jobs/{job_name}/trigger`
**Purpose:** Manually trigger a background job (admin-only)  
**Auth:** Admin API key + JWT (role: `system_admin`)

**Request Body (JobTriggerRequest):**
```python
{
  "force": bool = False,  # Skip schedule checks and run immediately
  "params": dict = {}     # Job-specific parameters
}
```

**Response (200 OK):**
```python
{
  "job_name": str,
  "task_id": str,
  "status": "queued" | "started",
  "queued_at": datetime
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 404 | `JOB_001` | "Job '{job_name}' not configured" |
| 409 | `JOB_002` | "Job '{job_name}' already running (task_id: ...)" |
| 403 | `JOB_003` | "Admin privileges required to trigger job" |
| 422 | `JOB_004` | "Invalid job parameters: {field}" |

---

#### `GET /api/v1/jobs/{job_name}/status`
**Purpose:** Retrieve last execution status and history  
**Auth:** Authenticated (role: `underwriter` or `system_admin`)

**Response (200 OK):**
```python
{
  "job_name": str,
  "is_enabled": bool,
  "schedule": str,  # cron expression
  "last_execution": {
    "task_id": str,
    "status": "success" | "failure" | "retrying" | "running",
    "started_at": datetime,
    "completed_at": datetime | None,
    "duration_seconds": float,
    "records_processed": int,
    "error_code": str | None,
    "error_message": str | None  # No PII included
  } | None,
  "next_scheduled_run": datetime | None
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 404 | `JOB_001` | "Job '{job_name}' not found" |

---

#### `GET /api/v1/jobs`
**Purpose:** List all configured jobs with aggregated metrics  
**Auth:** Authenticated (role: `underwriter` or `system_admin`)

**Query Parameters:**
- `status_filter`: "all" | "enabled" | "disabled" | "failing" (default: "all")
- `limit`: int (default: 50, max: 200)

**Response (200 OK):**
```python
{
  "jobs": List[JobStatusResponse],
  "summary": {
    "total_jobs": int,
    "enabled_jobs": int,
    "failing_jobs": int,  # >3 consecutive failures
    "avg_execution_time_seconds": float
  }
}
```

---

#### `PATCH /api/v1/jobs/{job_name}`
**Purpose:** Enable/disable scheduled job or update schedule  
**Auth:** Admin API key + JWT (role: `system_admin`)

**Request Body:**
```python
{
  "is_enabled": bool | None,
  "schedule": str | None  # Cron expression (validated)
}
```

**Response (200 OK):** Same as GET /status

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 | `JOB_005` | "Invalid cron expression: {detail}" |
| 404 | `JOB_001` | "Job '{job_name}' not found" |

---

## 2. Models & Database

### `job_execution_log` Table
**Purpose:** Immutable audit trail for all job executions (FINTRAC 5-year retention)

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | |
| `job_name` | VARCHAR(100) | NOT NULL | IDX (job_name, started_at DESC) |
| `task_id` | VARCHAR(255) | UNIQUE, NOT NULL | IDX (task_id) |
| `status` | VARCHAR(20) | NOT NULL | IDX (status) |
| `started_at` | TIMESTAMP | NOT NULL | |
| `completed_at` | TIMESTAMP | | |
| `duration_seconds` | DECIMAL(10,3) | | |
| `records_processed` | INTEGER | DEFAULT 0 | |
| `error_code` | VARCHAR(50) | | |
| `error_message` | TEXT | | **EXCLUDE PII** |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |
| `created_by` | VARCHAR(50) | NOT NULL, DEFAULT 'system' | |

**Relationships:** None (standalone audit table)

**Notes:**
- `error_message` must be sanitized: strip PII, SIN, DOB, income, banking data
- Insert-only table; no updates or deletes (FINTRAC compliance)
- Partition by `created_at` monthly for 5-year retention policy

---

### `scheduled_job_config` Table
**Purpose:** Dynamic job schedule management

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | |
| `job_name` | VARCHAR(100) | UNIQUE, NOT NULL | |
| `is_enabled` | BOOLEAN | NOT NULL, DEFAULT TRUE | IDX (is_enabled) |
| `schedule` | VARCHAR(100) | NOT NULL | |
| `last_run_at` | TIMESTAMP | | |
| `next_run_at` | TIMESTAMP | | IDX (next_run_at) |
| `max_retries` | INTEGER | DEFAULT 3 | |
| `retry_backoff_seconds` | INTEGER | DEFAULT 300 | |
| `rate_limit_per_minute` | INTEGER | DEFAULT 60 | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Relationships:** None

---

### `job_retry_log` Table
**Purpose:** Track retry attempts for debugging

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | |
| `execution_log_id` | UUID | FK → job_execution_log.id | IDX (execution_log_id) |
| `retry_number` | INTEGER | NOT NULL | |
| `attempted_at` | TIMESTAMP | NOT NULL | |
| `error_code` | VARCHAR(50) | | |
| `error_message` | TEXT | | **EXCLUDE PII** |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Relationships:** Many-to-one with `job_execution_log`

---

## 3. Business Logic

### Job Algorithms & Specifications

#### **send_document_reminder**
```python
Algorithm:
  1. Query: SELECT * FROM applications 
     WHERE status = 'documents_pending' 
     AND last_reminder_sent_at < NOW() - INTERVAL '48 hours'
  2. For each application:
     a. Check rate_limit_per_minute (Redis sliding window)
     b. Render email template (client name, application_id, missing_docs list)
     c. Send via SMTP/sendgrid with correlation_id in headers
     d. Update applications.last_reminder_sent_at = NOW()
     e. Log: records_processed++, NO PII in logs
  3. FINTRAC: Log audit entry for each email sent (communication record)
```

**Rate Limiting:** Redis key `email:reminder:{application_id}` with TTL 48h  
**Template Context:** `{client_name: str, application_id: str, missing_docs: list[str]}`  
**PIPEDA:** Email body must not include SIN, DOB, income; use application_id only

---

#### **check_rate_expiry**
```python
Algorithm:
  1. Query: SELECT * FROM lender_products 
     WHERE rate_expiry < NOW() AND status != 'expired'
  2. For each product:
     a. Update status = 'expired', updated_at = NOW()
     b. Log: "Product {product_id} rate expired" (no rates in logs)
     c. If product is 'qualifying_rate', trigger OSFI B-20 re-calculation alert
  3. Records processed count = updated rows
```

**OSFI B-20 Impact:** Expired qualifying rates must trigger re-underwriting for pending applications  
**Audit:** Log product_id only, never log actual rate values

---

#### **check_condition_due_dates**
```python
Algorithm:
  1. Query: SELECT * FROM lender_conditions 
     WHERE due_date < NOW() AND status IN ('pending', 'in_progress')
  2. For each condition:
     a. Update status = 'overdue', updated_at = NOW()
     b. Create notification: "Condition {condition_id} overdue for application {app_id}"
     c. Log: records_processed++
  3. Bulk update for performance
```

**State Machine:** `pending → overdue` (terminal state, manual resolution required)  
**Notification:** Publishes to `notifications.overdue_condition` queue

---

#### **generate_monthly_report**
```python
Algorithm:
  1. Determine reporting month (previous month)
  2. Query aggregates:
     - Total applications submitted
     - Average loan_amount (Decimal)
     - Average LTV ratio
     - CMHC insurance count by tier
     - GDS/TDS rejection reasons breakdown
  3. Generate PDF/JSON report (no PII, aggregated only)
  4. Store in `monthly_reports` table with retention_policy = '5_years'
  5. Log: records_processed = 1 (report generated)
```

**FINTRAC Retention:** Report must be stored for 5 years, immutable  
**CMHC Data:** Include insurance premium totals by LTV tier  
**PIPEDA:** Aggregate data only; no individual client identifiers

---

#### **cleanup_temp_uploads**
```python
Algorithm:
  1. Scan directory /uploads/temp recursively
  2. For each file:
     a. Stat file modified_time
     b. If age > 24 hours: delete file
     c. Log: "Deleted temp file {file_path}" (hash filename, no PII)
  3. Return count of deleted files
```

**Security:** Ensure path traversal protection; validate file_path is within /uploads/temp  
**PIPEDA:** Temp uploads may contain PII; must be securely deleted (shred)

---

#### **flag_fintrac_overdue**
```python
Algorithm:
  1. Query: SELECT * FROM applications 
     WHERE fintrac_verified = FALSE 
     AND created_at < NOW() - INTERVAL '24 hours'
     AND status NOT IN ('rejected', 'withdrawn')
  2. For each application:
     a. Update status = 'fintrac_overdue', updated_at = NOW()
     b. Create high-priority alert for compliance team
     c. Log: "Application {application_id} flagged FINTRAC overdue" (NO PII)
  3. If count > 0: send immediate Slack/Email alert to compliance@lender.com
```

**FINTRAC Compliance:** This job prevents regulatory violations; failures must page on-call  
**Audit:** Each flag creates immutable record in `application_status_history`  
**PIPEDA:** Do not log SIN, DOB, or identity verification details

---

### State Machine & Transitions
- **Jobs:** `pending → running → success|failure → (retry) → dead_letter`
- **Applications:** `submitted → fintrac_overdue → (verified) → underwriting`
- **Lender Products:** `active → expired` (no reversal)
- **Conditions:** `pending → overdue` (manual resolution only)

---

## 4. Migrations

### New Tables

```sql
-- migration: 2024_01_background_jobs_execution_log
CREATE TABLE job_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name VARCHAR(100) NOT NULL,
    task_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'success', 'failure', 'retrying')),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds DECIMAL(10,3),
    records_processed INTEGER DEFAULT 0,
    error_code VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) NOT NULL DEFAULT 'system'
);

CREATE INDEX idx_job_execution_log_name_started ON job_execution_log(job_name, started_at DESC);
CREATE INDEX idx_job_execution_log_task_id ON job_execution_log(task_id);
CREATE INDEX idx_job_execution_log_status ON job_execution_log(status);

-- Partitioning setup (run in separate migration)
CREATE TABLE job_execution_log_2024_01 PARTITION OF job_execution_log
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

```sql
-- migration: 2024_01_background_jobs_config
CREATE TABLE scheduled_job_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name VARCHAR(100) UNIQUE NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    schedule VARCHAR(100) NOT NULL,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    max_retries INTEGER DEFAULT 3,
    retry_backoff_seconds INTEGER DEFAULT 300,
    rate_limit_per_minute INTEGER DEFAULT 60,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scheduled_job_config_enabled ON scheduled_job_config(is_enabled);
CREATE INDEX idx_scheduled_job_config_next_run ON scheduled_job_config(next_run_at);
```

```sql
-- migration: 2024_01_background_jobs_retry_log
CREATE TABLE job_retry_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_log_id UUID NOT NULL REFERENCES job_execution_log(id),
    retry_number INTEGER NOT NULL,
    attempted_at TIMESTAMP NOT NULL,
    error_code VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_job_retry_log_execution_id ON job_retry_log(execution_log_id);
```

### Existing Table Modifications

```sql
-- migration: 2024_01_applications_add_reminder_timestamp
ALTER TABLE applications ADD COLUMN last_reminder_sent_at TIMESTAMP;
CREATE INDEX idx_applications_reminder_sent ON applications(last_reminder_sent_at) 
    WHERE status = 'documents_pending';
```

```sql
-- migration: 2024_01_lender_products_add_status_index
ALTER TABLE lender_products ADD COLUMN IF NOT EXISTS status VARCHAR(20);
CREATE INDEX idx_lender_products_rate_expiry ON lender_products(rate_expiry) 
    WHERE status != 'expired';
```

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Rate Expiry Impact:** When `check_rate_expiry` marks a qualifying_rate product as expired, the system must:
  1. Re-calculate all pending applications using that rate
  2. Re-apply stress test: `qualifying_rate = max(new_rate + 2%, 5.25%)`
  3. Re-validate GDS ≤ 39% and TDS ≤ 44%
  4. Log re-calculation audit trail with `job_execution_log` referencing `application_id`

### FINTRAC Requirements
- **5-Year Retention:** `job_execution_log` and `monthly_reports` tables must be partitioned monthly; archive to cold storage after 5 years
- **Immutable Records:** All job logs are INSERT-only; no UPDATE/DELETE permitted
- **FINTRAC Overdue Flagging:** The `flag_fintrac_overdue` job must:
  - Run before 9 AM to meet regulatory deadline
  - Create alerts in `compliance_alerts` table with `severity = 'critical'`
  - Log each flagging action with `created_by = 'system_job:flag_fintrac_overdue'`
- **Transaction Records:** `generate_monthly_report` must include aggregate FINTRAC reporting metrics (suspicious activity counts, verification rates)

### PIPEDA Requirements
- **No PII in Logs:** All `error_message` fields must be sanitized via `common/security.sanitize_log_message()` which removes patterns matching SIN, DOB, income, banking data
- **Email Rate Limiting:** `send_document_reminder` must enforce per-client email limits to prevent harassment; store `last_reminder_sent_at` to track
- **Secure Deletion:** `cleanup_temp_uploads` must use `shred`-like functionality to overwrite file contents before deletion; log only hashed filenames

### Authentication & Authorization
- **Manual Triggers:** Require `system_admin` role + valid JWT + admin API key (mTLS recommended)
- **Status Queries:** Accessible to `underwriter` role for operational visibility
- **Job Execution:** Runs as `system` user with `created_by = 'system_job:{job_name}'`

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy

```python
# modules/background_jobs/exceptions.py
class JobException(AppException):
    """Base exception for all job-related errors"""
    pass

class JobNotFoundError(JobException):
    """Raised when job configuration is missing"""
    pass

class JobAlreadyRunningError(JobException):
    """Raised when job is triggered while already executing"""
    pass

class JobConfigurationError(JobException):
    """Raised for invalid cron expressions or parameters"""
    pass

class JobExecutionError(JobException):
    """Raised when job fails after all retries"""
    pass

class JobRateLimitError(JobException):
    """Raised when job exceeds rate limits"""
    pass
```

### Error Code Mapping

| Exception Class | HTTP Status | Error Code | Message Pattern | Logs PII? |
|-----------------|-------------|------------|-----------------|-----------|
| `JobNotFoundError` | 404 | `JOB_001` | "Job '{job_name}' not configured" | No |
| `JobAlreadyRunningError` | 409 | `JOB_002` | "Job '{job_name}' already running (task_id: {tid})" | No |
| `JobConfigurationError` | 400 | `JOB_005` | "Invalid cron expression: {detail}" | No |
| `JobExecutionError` | 500 | `JOB_006` | "Job '{job_name}' failed after {retries} retries" | **Sanitized** |
| `JobRateLimitError` | 429 | `JOB_007` | "Rate limit exceeded for {resource}" | No |
| `JobValidationError` | 422 | `JOB_004` | "Invalid parameters: {field}" | No |

### Retry & Dead Letter Strategy

```python
# Celery task configuration
task_annotations = {
    'modules.background_jobs.tasks.*': {
        'max_retries': 3,
        'retry_backoff': 300,  # 5 minutes
        'retry_backoff_max': 3600,  # 1 hour
        'retry_jitter': True,
        'acks_late': True,  # Acknowledge after completion
        'reject_on_worker_lost': True,
    }
}

# Dead Letter Queue routing
task_routes = {
    'modules.background_jobs.tasks.send_document_reminder': {
        'queue': 'jobs.email',
        'dead_letter_queue': 'dlq.jobs.email'
    },
    'modules.background_jobs.tasks.flag_fintrac_overdue': {
        'queue': 'jobs.compliance',
        'dead_letter_queue': 'dlq.jobs.compliance'
    },
}
```

**DLQ Monitoring:** Prometheus alert when `celery_queue_depth{queue="dlq.*"}` > 0 for >5 minutes

---

## 7. Infrastructure & Observability

### Celery Configuration (common/config.py)
```python
class CelerySettings(BaseSettings):
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/0"
    timezone: str = "America/Toronto"
    enable_utc: bool = False
    beat_schedule: dict = {
        'send_document_reminder': {
            'task': 'modules.background_jobs.tasks.send_document_reminder',
            'schedule': crontab(hour=9, minute=0),  # 9 AM daily
        },
        'check_rate_expiry': {
            'task': 'modules.background_jobs.tasks.check_rate_expiry',
            'schedule': crontab(hour=7, minute=0),  # 7 AM daily
        },
        # ... other schedules
    }
```

### Prometheus Metrics
```python
# In services.py
job_execution_total = Counter(
    'job_execution_total',
    'Total job executions',
    ['job_name', 'status']
)

job_execution_duration_seconds = Histogram(
    'job_execution_duration_seconds',
    'Job execution duration',
    ['job_name']
)

job_execution_failures_total = Counter(
    'job_execution_failures_total',
    'Job execution failures after retries',
    ['job_name', 'error_code']
)
```

### Logging (structlog)
```python
# Every job must log with correlation_id
logger.info(
    "job_started",
    job_name="send_document_reminder",
    task_id=task_id,
    correlation_id=get_correlation_id()
)
```

---

## 8. Missing Details Resolution

### Email Templates
- Store in `modules/background_jobs/templates/{job_name}.html`
- Use Jinja2 with strict context validation (only whitelisted variables)
- PIPEDA review required before deployment

### Scaling Requirements
- **Worker Pool:** Start with 2 workers per queue (`jobs.email`, `jobs.compliance`, `jobs.maintenance`)
- **Auto-scaling:** Scale workers based on `celery_queue_depth` > 50
- **Resource Limits:** Memory limit 2GB per worker; CPU limit 1 core

### Monitoring & Alerting
- **PagerDuty:** `flag_fintrac_overdue` failures page on-call immediately
- **Slack:** Daily summary of job successes/failures at 10 AM
- **Dashboard:** Grafana dashboard showing job execution heatmap by hour

---

**Next Steps:** Implementation tickets should be created for each job task with priority: `flag_fintrac_overdue` (P0), `send_document_reminder` (P1), others (P2).