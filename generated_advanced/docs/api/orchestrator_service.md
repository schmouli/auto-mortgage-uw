```markdown
# Orchestrator Service API

## Overview

The Orchestrator Service acts as the single entry point for the frontend, coordinating the asynchronous mortgage underwriting pipeline. It manages document ingestion, triggers Celery tasks for data extraction and policy evaluation, and persists the final decision to the database.

---

## POST /api/v1/orchestrator/submit

Initiates a new mortgage application. This endpoint accepts the application metadata and the supporting PDF document. It uploads the document to object storage and dispatches a Celery task chain to process the application.

**Request:** `multipart/form-data`

| Form Field | Type | Description |
|------------|------|-------------|
| `lender_id` | string | UUID of the selected lending institution. |
| `applicant_email` | string | Contact email for the applicant (used for notifications). |
| `document` | file | The mortgage application document (PDF). Max size: 25MB. |

**Response (202 Accepted):**

```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "message": "Application received and queued for processing.",
  "created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `400 Bad Request`: Invalid file type or size exceeds limit.
- `401 Unauthorized`: Authentication token missing or invalid.
- `422 Unprocessable Entity`: Validation error on input fields (e.g., invalid UUID format).

---

## GET /api/v1/orchestrator/status/{application_id}

Retrieves the current processing status of a specific application.

**Parameters:**
- `application_id` (path): UUID of the application.

**Response (200 OK):**

```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "UNDER_REVIEW",
  "current_step": "evaluate_policy",
  "updated_at": "2026-03-02T14:35:00Z"
}
```

**Status Values:**
- `PROCESSING`: Initial ingestion and document upload.
- `EXTRACTING`: OCR and data extraction in progress.
- `EVALUATING`: Policy engine (GDS/TDS/LTV) calculation.
- `COMPLETED`: Decision finalized.
- `FAILED`: An error occurred during processing (check logs).

**Errors:**
- `404 Not Found`: Application ID does not exist.

---

## GET /api/v1/orchestrator/decision/{application_id}

Retrieves the final underwriting decision. This endpoint is only populated once the status is `COMPLETED`. Includes the calculated financial metrics required for auditability.

**Parameters:**
- `application_id` (path): UUID of the application.

**Response (200 OK):**

```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "APPROVED",
  "limit_amount": "450000.00",
  "interest_rate": "5.25",
  "metrics": {
    "gds_ratio": "28.50",
    "tds_ratio": "38.10",
    "ltv_ratio": "75.00",
    "stress_test_rate": "7.25"
  },
  "insurance_required": false,
  "created_at": "2026-03-02T14:45:00Z"
}
```

**Errors:**
- `404 Not Found`: Application ID does not exist.
- `400 Bad Request`: Decision is not yet ready (Status is not `COMPLETED`).

---
```

```markdown
# Orchestrator Service Module

## Overview

The Orchestrator Module is the central coordinator of the Canadian Mortgage Underwriting System. It does not contain business logic for calculating ratios or validating rules; instead, it manages the workflow state, delegates tasks to specialized services (Document Extractor, Policy Engine, Decision Engine), and ensures data integrity across the pipeline.

## Key Functions

### 1. Application Ingestion
Receives `multipart/form-data` requests containing lender selection and PDF documents. Validates file types and basic metadata before handing off to storage workers.

### 2. Pipeline Management
Utilizes **Celery** to manage the following task chain:
1.  **`extract_documents`**: Sends PDF to MinIO, triggers OCR service.
2.  **`evaluate_policy`**: Calls the Policy Engine with extracted data to perform OSFI B-20 stress tests and CMHC insurance checks.
3.  **`run_decision`**: Finalizes the approval/denial status and persists the result to PostgreSQL.

### 3. State Tracking
Maintains the status of every application in the database, allowing the frontend to poll for updates without blocking the main thread.

## Usage Example

### Submitting an Application

```python
import requests

url = "https://api.mortgage-system.com/api/v1/orchestrator/submit"
files = {'document': open('application.pdf', 'rb')}
data = {
    'lender_id': '123e4567-e89b-12d3-a456-426614174000',
    'applicant_email': 'applicant@example.com'
}

response = requests.post(url, files=files, data=data, headers={
    'Authorization': 'Bearer <token>'
})

print(response.json())
# Output: {'application_id': '...', 'status': 'PROCESSING', ...}
```

### Polling for Status

```python
app_id = response.json()['application_id']
status_url = f"https://api.mortgage-system.com/api/v1/orchestrator/status/{app_id}"

status_response = requests.get(status_url)
print(status_response.json()['status'])
```

## Compliance Notes

*   **Auditability:** All state transitions and task dispatches are logged with `correlation_id` to trace the lifecycle of a specific application.
*   **Data Minimization:** The orchestrator only persists the metadata required to track the process. Raw PII extracted from documents is stored securely by the specific document handling services, not in the orchestrator tables.
```

```ini
# .env.example
# Additions for Orchestrator Service Configuration

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Object Storage (MinIO/S3) for Document Uploads
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET_NAME=mortgage-documents

# Task Timeouts (in seconds)
CELERY_TASK_SOFT_TIME_LIMIT=300
CELERY_TASK_TIME_LIMIT=600
```