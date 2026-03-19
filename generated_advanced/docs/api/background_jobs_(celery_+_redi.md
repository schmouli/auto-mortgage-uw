```markdown
# Background Jobs (Celery + Redis)

## Module Overview

The Background Jobs module handles asynchronous and scheduled tasks using Celery with Redis as the message broker. This module ensures that long-running processes, periodic maintenance, and regulatory compliance checks do not block the main application thread.

### Key Functions

The module implements the following scheduled tasks to support the mortgage underwriting lifecycle:

1.  **`send_document_reminder`** (Daily 9:00 AM)
    *   Scans for active applications with outstanding document requirements.
    *   Sends automated email notifications to clients.
    *   *Compliance:* Ensures PII is minimized in logs; only status is recorded.

2.  **`check_rate_expiry`** (Daily 7:00 AM)
    *   Queries lender products to identify rates that have expired since the last check.
    *   Flags expired products in the database to prevent new submissions using invalid data.
    *   *Logic:* Compares current UTC timestamp against `expiry_date` (Decimal/Date precision).

3.  **`check_condition_due_dates`** (Daily 8:00 AM)
    *   Identifies lender conditions on approved mortgages that have passed their due date without fulfillment.
    *   Updates application status to "Attention Required" or similar.

4.  **`generate_monthly_report`** (1st of Month, 6:00 AM)
    *   Aggregates data from the previous month (applications approved, rejected, volume).
    *   Generates a financial report and stores it in the database or secure file storage.
    *   *Compliance:* Audit trail created for report generation.

5.  **`cleanup_temp_uploads`** (Daily 2:00 AM)
    *   Scans the `/uploads/temp` directory.
    *   Deletes files older than 24 hours.
    *   *Compliance (PIPEDA):* Critical for ensuring temporary PII (SIN, income docs) is not retained indefinitely.

6.  **`flag_fintrac_overdue`** (Daily 9:00 AM)
    *   Checks applications where identity verification or source of funds is pending.
    *   Flags applications that are approaching or have exceeded regulatory time limits.
    *   *Compliance (FINTRAC):* Ensures audit trails are maintained for compliance officers.

---

## API Documentation

While most tasks are scheduled via Celery Beat, administrative endpoints are provided to trigger tasks manually or check status.

### POST /api/v1/background-jobs/trigger

Manually triggers a specific background job. Useful for immediate maintenance or missed schedules.

**Permissions:** `admin`

**Request:**
```json
{
  "task_name": "send_document_reminder",
  "args": {}
}
```
*Note: `task_name` must match one of the defined Celery tasks.*

**Response (202 Accepted):**
```json
{
  "detail": "Task 'send_document_reminder' queued for execution",
  "task_id": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8"
}
```

**Errors:**
- `400 Bad Request`: Invalid task name or arguments.
- `401 Unauthorized`: Authentication missing or invalid.
- `403 Forbidden`: User lacks admin privileges.

---

### GET /api/v1/background-jobs/status/{task_id}

Retrieves the status of a previously triggered background job.

**Permissions:** `admin`

**Parameters:**
- `task_id` (path): The UUID of the Celery task.

**Response (200 OK):**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8",
  "status": "SUCCESS",
  "result": {
    "emails_sent": 5,
    "processed_at": "2026-03-02T09:05:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Task ID does not exist.
- `401 Unauthorized`: Authentication missing or invalid.

---

### GET /api/v1/background-jobs/schedules

Lists all configured scheduled jobs and their next run times (read-only from Celery Beat configuration).

**Permissions:** `admin`

**Response (200 OK):**
```json
{
  "schedules": [
    {
      "name": "send_document_reminder",
      "schedule": "cron(hour=9, minute=0)",
      "next_run": "2026-03-03T09:00:00Z"
    },
    {
      "name": "cleanup_temp_uploads",
      "schedule": "cron(hour=2, minute=0)",
      "next_run": "2026-03-03T02:00:00Z"
    }
  ]
}
```

---

## Configuration Notes

This module relies on Redis for the message broker and backend. Ensure the following environment variables are set in `.env`.

### Environment Variables (.env.example)

```bash
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Task Settings
CELERY_TASK_TRACK_STARTED=true
CELERY_TASK_TIME_LIMIT=3600  # Hard limit for task execution (1 hour)

# Schedules (Optional overrides if using DB-backed schedules)
# Defaults are coded in celeryapp.py
```

### Setup Requirements

1.  **Redis Instance:** A running Redis instance is required for the broker and backend.
2.  **Worker Process:** The Celery worker must be started separately from the FastAPI API server.
    ```bash
    uv run celery -A mortgage_underwriting.common.celeryapp worker --loglevel=info
    ```
3.  **Beat Process:** The Celery Beat scheduler must be running to trigger periodic tasks.
    ```bash
    uv run celery -A mortgage_underwriting.common.celeryapp beat --loglevel=info
    ```

### Compliance & Logging

*   **FINTRAC/PIPEDA:** Tasks involving PII (like `cleanup_temp_uploads` or `flag_fintrac_overdue`) must strictly use the structured logger. Do not log raw SIN or DOB.
*   **Audit:** All task executions are logged with `correlation_id` where applicable to trace actions back to specific administrative triggers.
```