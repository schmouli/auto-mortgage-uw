Here is the documentation for the **Orchestrator Service** module.

### 1. API Documentation
**File:** `docs/api/orchestrator.md`

```markdown
# Orchestrator Service API

The Orchestrator Service acts as the single entry point for the mortgage underwriting system. It manages the asynchronous pipeline flow, coordinating document ingestion, policy evaluation, and final decisioning via Celery tasks.

## POST /api/v1/orchestrator/submit-application

Initiates a new mortgage application. Accepts applicant data and supporting documents, uploads files to object storage, and triggers the asynchronous underwriting pipeline.

**Request:** `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `application_data` | string (JSON) | Stringified JSON containing applicant financial details (income, property value, loan amount, etc.). |
| `documents` | List[File] | Upload files (PDF/PNG/JPG) corresponding to identity proof, income statements, etc. |

**`application_data` JSON Schema Example:**
```json
{
  "lender_id": "lender_123",
  "applicant_name": "John Doe",
  "date_of_birth": "1990-01-01", 
  "sin_hash": "a1b2c3d4...", 
  "income_monthly": "5000.00",
  "loan_amount": "350000.00",
  "property_value": "450000.00",
  "contract_rate": "5.00"
}
```

**Response (202 Accepted):**
```json
{
  "application_id": "uuid-v4-string",
  "task_id": "celery-task-id",
  "status": "PROCESSING",
  "message": "Application received and documents queued for extraction."
}
```

**Errors:**
- `400 Bad Request`: Invalid file format or malformed JSON.
- `422 Unprocessable Entity`: Validation error on financial fields (e.g., negative amounts).
- `503 Service Unavailable`: Celery broker or MinIO connection failed.

---

## GET /api/v1/orchestrator/status/{application_id}

Retrieves the current processing status of a specific application.

**Parameters:**
- `application_id` (path): UUID of the application.

**Response (200 OK):**
```json
{
  "application_id": "uuid-v4-string",
  "status": "UNDER_REVIEW",
  "current_step": "evaluate_policy",
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:05:00Z"
}
```

**Status Values:**
- `RECEIVED`: Initial upload complete.
- `EXTRACTING`: OCR/Document parsing in progress.
- `EVALUATING`: Policy engine running (OSFI/CMHC checks).
- `DECIDING`: Final decision generation.
- `COMPLETED`: Process finished successfully.
- `FAILED`: Error encountered in pipeline.

**Errors:**
- `404 Not Found`: Application ID does not exist.

---

## GET /api/v1/orchestrator/result/{application_id}

Retrieves the final underwriting decision and audit trail for a completed application.

**Parameters:**
- `application_id` (path): UUID of the application.

**Response (200 OK):**
```json
{
  "application_id": "uuid-v4-string",
  "decision": "APPROVED",
  "gds_ratio": "25.00",
  "tds_ratio": "32.00",
  "ltv_ratio": "77.77",
  "insurance_required": false,
  "qualifying_rate": "5.25",
  "audit_trail": [
    {
      "step": "extract_documents",
      "status": "SUCCESS",
      "timestamp": "2026-03-02T10:01:00Z"
    },
    {
      "step": "evaluate_policy",
      "status": "SUCCESS",
      "timestamp": "2026-03-02T10:02:00Z"
    }
  ],
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `404 Not Found`: Application ID does not exist.
- `425 Too Early`: The application has not finished processing yet.
```

### 2. Module README
**File:** `docs/modules/orchestrator_service.md`

```markdown
# Orchestrator Service Module

## Overview
The Orchestrator Service is the central coordination hub for the Canadian Mortgage Underwriting System. It exposes FastAPI endpoints that serve as the single entry point for frontend clients. It manages the lifecycle of a mortgage application by delegating heavy processing tasks to Celery workers.

## Key Responsibilities
1.  **Inake & Validation**: Receives application data and documents, validating inputs using Pydantic schemas.
2.  **Storage Management**: Handles secure upload of documents to MinIO/S3 with immutable versioning (FINTRAC compliance).
3.  **Pipeline Orchestration**: Dispatches tasks to the Celery queue in sequence:
    *   `extract_documents`: Parses PDFs/images to extract financial data.
    *   `evaluate_policy`: Runs OSFI B-20 stress tests and CMHC logic.
    *   `run_decision`: Aggregates results to generate Approve/Decline/Refer.
4.  **State Management**: Updates PostgreSQL with the status of the application pipeline.

## Architecture
```
Client (Frontend)
       |
       v
FastAPI (Orchestrator Routes)
       |
       +---> MinIO (Document Storage)
       |
       +---> Celery Broker (Redis/RabbitMQ)
                     |
                     v
              Celery Workers
        (Extract -> Evaluate -> Decide)
                     |
                     v
              PostgreSQL (Results)
```

## Usage Example

### Submitting an Application
To start a workflow, send a `multipart/form-data` request to `/api/v1/orchestrator/submit-application`.

```python
import httpx

files = {"documents": open("income_proof.pdf", "rb")}
data = {
    "application_data": json.dumps({
        "lender_id": "lender_001",
        "income_monthly": "6000.00",
        "loan_amount": "400000.00",
        "property_value": "500000.00"
    })
}

response = httpx.post("http://api:8000/api/v1/orchestrator/submit-application", files=files, data=data)
task_id = response.json()["task_id"]
```

### Monitoring Progress
Poll the status endpoint using the `application_id`.

```python
status = httpx.get(f"http://api:8000/api/v1/orchestrator/status/{app_id}").json()
if status["status"] == "COMPLETED":
    result = httpx.get(f"http://api:8000/api/v1/orchestrator/result/{app_id}").json()
    print(f"Decision: {result['decision']}")
```

## Compliance Notes
*   **PIPEDA**: All `application_data` containing PII (SIN, DOB) is encrypted before storage. Logs do not contain raw PII.
*   **FINTRAC**: Documents uploaded to MinIO are stored with WORM (Write Once, Read Many) policies to ensure the audit trail is immutable.
*   **OSFI B-20**: The `evaluate_policy` task enforces the minimum qualifying rate (max(contract_rate + 2%, 5.25%)).
```

### 3. Configuration Notes
**File:** `.env.example` (Additions)

```bash
# Orchestrator Service Configuration

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Object Storage (MinIO/S3) for Document Archival
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=mortgage-docs
MINIO_USE_SSL=false

# Internal Service URLs (for worker callbacks if necessary)
DOCUMENT_SERVICE_URL=http://document-service:8000
POLICY_SERVICE_URL=http://policy-service:8000
```

### 4. CHANGELOG Entry
**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Orchestrator Service: New module for coordinating mortgage application pipelines.
- Endpoints: `POST /api/v1/orchestrator/submit-application`, `GET /status/{id}`, `GET /result/{id}`.
- Integration: Celery task dispatch for asynchronous document extraction and policy evaluation.
- Storage: Automated MinIO/S3 upload for supporting documents with immutable versioning.

### Changed
- Updated project dependencies to include `celery`, `redis`, and `boto3`/`minio`.
```

### 5. Docstrings for Complex Logic
**File:** `mortgage_underwriting/modules/orchestrator/services.py`

```python
async def submit_application(
    self, 
    application_data: ApplicationCreateSchema, 
    files: List[UploadFile]
) -> dict:
    """
    Orchestrates the submission of a new mortgage application.
    
    1. Validates input data.
    2. Encrypts PII (PIPEDA compliance).
    3. Uploads documents to MinIO with immutable tags (FINTRAC compliance).
    4. Persists initial record to PostgreSQL.
    5. Dispatches the 'extract_documents' Celery task.
    
    Returns the application_id and celery task_id for tracking.
    """

async def get_pipeline_status(self, application_id: UUID) -> dict:
    """
    Retrieves the current status of the underwriting pipeline.
    Checks the Celery result backend and database state.
    """

async def get_final_decision(self, application_id: UUID) -> DecisionSchema:
    """
    Retrieves the final underwriting decision.
    Ensures the pipeline is complete before returning data.
    Includes audit trail for regulatory review.
    """
```