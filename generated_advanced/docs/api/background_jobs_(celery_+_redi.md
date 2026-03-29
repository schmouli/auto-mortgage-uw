Here is the documentation for the **Background Jobs (Celery + Redis)** module, structured according to the project conventions.

---

# Background Jobs (Celery + Redis) API

## Overview
This module manages asynchronous task processing and scheduled jobs using Celery and Redis. While most tasks are triggered automatically by Celery Beat based on a cron schedule, administrative endpoints are provided for health checks and manual triggering.

## GET /api/v1/jobs/health

Check the status of the Celery worker and Redis connection.

**Response (200):**
```json
{
  "status": "healthy",
  "celery_reachable": true,
  "redis_reachable": true,
  "active_workers": 4
}
```

**Errors:**
- 503: Service Unavailable (Redis or Worker down)

---

## POST /api/v1/jobs/trigger/{job_name}

Manually trigger a specific scheduled job. Requires administrative privileges.

**Parameters:**
- `job_name` (path): The name of the job to trigger (e.g., `send_document_reminder`).

**Request:**
```json
{
  "run_immediately": true
}
```

**Response (202):**
```json
{
  "message": "Job 'send_document_reminder' queued successfully",
  "task_id": "a1b2-c3d4-e5f6"
}
```

**Errors:**
- 401: Not authenticated
- 403: Permission denied (Admin required)
- 404: Job name not found

---

# Background Jobs Module README

## Overview
The Background Jobs module handles asynchronous processing and scheduled maintenance tasks for the Canadian Mortgage Underwriting System. It utilizes **Celery** as the task queue and **Redis** as the message broker and result backend.

This module ensures time-sensitive operations—such as compliance checks (FINTRAC), document reminders, and data cleanup—are executed reliably without blocking the main API threads.

## Scheduled Jobs

The following tasks are automated via Celery Beat:

| Job Name | Schedule | Description | Compliance Notes |
| :--- | :--- | :--- | :--- |
| **send_document_reminder** | Daily 9:00 AM | Identifies clients with outstanding documents and sends email reminders. | **PIPEDA:** Ensure PII is minimized in email content; never log SIN/DOB. |
| **check_rate_expiry** | Daily 7:00 AM | Flags lender products in the database where the posted rate has expired. | **OSFI B-20:** Ensures qualifying rates are always calculated against valid data. |
| **check_condition_due_dates** | Daily 8:00 AM | Flags overdue lender conditions on active mortgage applications. | Updates `condition_status` to `OVERDUE`. |
| **generate_monthly_report** | 1st of Month, 6:00 AM | Aggregates underwriting data for the previous month and stores the report. | **FINTRAC:** Reports must be immutable and retained for 5 years. |
| **cleanup_temp_uploads** | Daily 2:00 AM | Scans `/uploads/temp` and deletes files older than 24 hours. | **PIPEDA:** Ensures unnecessary PII is purged promptly. |
| **flag_fintrac_overdue** | Daily 9:00 AM | Scans for applications pending FINTRAC verification beyond the allowed window. | **FINTRAC:** Critical audit trail trigger; updates `compliance_status`. |

## Key Implementation Details

### Task Logic & Compliance
- **FINTRAC Compliance:** The `flag_fintrac_overdue` task interacts strictly with immutable audit fields. It sets flags but never modifies historical financial transaction records.
- **Data Security:** The `send_document_reminder` task retrieves email addresses from the encrypted database fields. Document links are generated with short-lived, signed tokens to prevent unauthorized access.
- **Error Handling:** All tasks utilize the `AppException` base class. Failed tasks are logged via `structlog` with a `correlation_id` for tracing in OpenTelemetry.

### Decimal Precision
All financial calculations within these tasks (e.g., rate checks) utilize Python's `Decimal` type to prevent floating-point rounding errors, adhering to the project's "No float for money" rule.

## Usage Examples

### Triggering a Job Manually
While jobs run on a schedule, administrators can trigger them via the API:

```bash
curl -X POST "https://api.mortgage-system.com/api/v1/jobs/trigger/cleanup_temp_uploads" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"run_immediately": true}'
```

### Monitoring
Check worker status to ensure jobs are being consumed:
```bash
curl -X GET "https://api.mortgage-system.com/api/v1/jobs/health"
```

---

# Configuration Notes

To operate the Background Jobs module, the following environment variables must be configured in `.env` or your deployment environment.

### Environment Variables

```bash
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_TRACK_STARTED=True
CELERY_TASK_TIMEZONE=America/Toronto

# Job Schedules (Cron expressions can be adjusted here if needed)
# Note: Default schedules are hardcoded in celeryconfig.py based on requirements.
# These variables allow overrides without code changes.

# File Cleanup
TEMP_UPLOAD_DIR=/var/www/mortgage_system/uploads/temp
TEMP_UPLOAD_MAX_AGE_HOURS=24

# External Services
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@mortgage-system.com
```

### Setup Instructions

1.  **Redis Instance:** Ensure a Redis instance is running and accessible at `CELERY_BROKER_URL`.
2.  **Worker Process:** Start the Celery worker to process tasks:
    ```bash
    uv run celery -A mortgage_underwriting.common.celery_app worker --loglevel=info
    ```
3.  **Beat Scheduler:** Start the Celery Beat scheduler to trigger cron jobs:
    ```bash
    uv run celery -A mortgage_underwriting.common.celery_app beat --loglevel=info
    ```
4.  **Monitoring:** It is recommended to use **Flower** (Celery monitoring tool) for production visibility into task throughput and failures.

---

# CHANGELOG.md Updates

```markdown
## [2026-03-02]
### Added
- Background Jobs (Celery + Redis): Implemented asynchronous task processing infrastructure.
- Scheduled Jobs: Added 6 automated tasks including document reminders, rate expiry checks, and FINTRAC compliance flagging.
- API Endpoints: Added `/api/v1/jobs/health` and `/api/v1/jobs/trigger/{job_name}` for job management.

### Changed
- Infrastructure: Integrated Redis as the message broker for the application layer.

### Fixed
- N/A
```