# Background Jobs (Celery + Redis) API

## POST /api/v1/background-jobs/trigger

Manually trigger a specific background task. Useful for administrative overrides or immediate execution of scheduled tasks.

**Request:**
```json
{
  "task_name": "check_rate_expiry",
  "args": [],
  "kwargs": {}
}
```

**Response (202 Accepted):**
```json
{
  "task_id": "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv",
  "status": "PENDING",
  "message": "Task queued for execution"
}
```

**Errors:**
- 400: Invalid task name or arguments
- 401: Not authenticated
- 403: Permission denied (Admin role required)

---

## GET /api/v1/background-jobs/status/{task_id}

Retrieve the current status and result of a previously executed background task.

**Response (200 OK):**
```json
{
  "task_id": "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv",
  "status": "SUCCESS",
  "result": {
    "processed": 15,
    "flagged": 2
  },
  "date_done": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 404: Task ID not found
- 500: Error retrieving result from backend

---

## GET /api/v1/background-jobs/health

Health check endpoint for the Celery worker and Redis connection.

**Response (200 OK):**
```json
{
  "status": "ok",
  "redis_connected": true,
  "active_workers": 4
}
```

**Errors:**
- 503: Service unavailable (Redis connection failed or no active workers)

---

# Background Jobs Module Documentation

## Overview
The Background Jobs module handles asynchronous processing and scheduled tasks using **Celery** and **Redis**. This module ensures that long-running processes (such as monthly report generation) and periodic maintenance (such as data cleanup) do not block the main API threads.

## Key Scheduled Tasks

The following tasks are configured via Celery Beat:

| Task Name | Schedule | Description |
| :--- | :--- | :--- |
| `send_document_reminder` | Daily 9:00 AM | Scans for clients with outstanding documents and sends email reminders. Ensures PII is not logged. |
| `check_rate_expiry` | Daily 7:00 AM | Flags lender products where the qualifying rate has expired. Critical for OSFI B-20 compliance. |
| `check_condition_due_dates` | Daily 8:00 AM | Identifies overdue lender conditions on applications and updates status. |
| `generate_monthly_report` | 1st of Month, 6:00 AM | Aggregates underwriting data for the previous month and stores the record. |
| `cleanup_temp_uploads` | Daily 2:00 AM | Deletes files in `/uploads/temp` older than 24 hours to free up storage. |
| `flag_fintrac_overdue` | Daily 9:00 AM | Flags applications where FINTRAC identity verification is incomplete or overdue. |

## Regulatory Compliance Notes

- **FINTRAC:** The `flag_fintrac_overdue` task ensures that 5-year retention requirements are monitored. All status updates are logged with `correlation_id` for audit trails.
- **PIPEDA:** The `send_document_reminder` task uses encrypted email payloads. Document contents are never logged.
- **OSFI B-20:** The `check_rate_expiry` task validates that the `qualifying_rate` (max of contract rate + 2% or 5.25%) is still valid for active product lookups.

## Usage Example

To trigger a job programmatically via the Python client:

```python
from httpx import AsyncClient

async def trigger_report():
    async with AsyncClient() as client:
        response = await client.post(
            "http://api:8000/api/v1/background-jobs/trigger",
            json={"task_name": "generate_monthly_report"},
            headers={"Authorization": "Bearer <token>"}
        )
        return response.json()
```

## Configuration Notes

### Environment Variables

Add the following to your `.env` file:

```bash
# Background Jobs Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_TRACK_STARTED=True
CELERY_TASK_TIME_LIMIT=30*60  # 30 minutes hard limit
```

### Infrastructure Requirements
- **Redis:** Required as the message broker and result backend.
- **Worker Process:** Must run `uv run celery -A mortgage_underwriting.modules.background_jobs.worker worker --loglevel=info`.
- **Beat Scheduler:** Must run `uv run celery -A mortgage_underwriting.modules.background_jobs.worker beat --loglevel=info` to handle scheduled tasks.

---

## [2026-03-02]
### Added
- Background Jobs (Celery + Redis): New module for async task processing.
- Implemented scheduled tasks: document reminders, rate expiry checks, condition monitoring, monthly reporting, temp cleanup, and FINTRAC flagging.
- Added endpoints for manual job triggering and status checking.