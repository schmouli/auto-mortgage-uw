```markdown
# Frontend React UI API Documentation

## Module Overview

The **Frontend React UI** module serves as the backend interface for the React Single Page Application (SPA). It handles the orchestration of document submissions, pipeline status tracking, decision retrieval, and exception management for human underwriters.

### Key Features
- **Application Submission:** Ingests borrower PDFs and associates them with specific lenders.
- **Pipeline Tracking:** Provides real-time status updates (Extraction → Policy → Decision).
- **Decision Review:** Serves detailed decision payloads, including GDS/TDS breakdowns and audit trails.
- **Exception Queue:** Manages applications flagged for manual review.

### Regulatory Compliance Notes
- **FINTRAC:** All document uploads trigger an immutable audit log (created_at, created_by).
- **PIPEDA:** PII is never returned in list views; sensitive data requires explicit authorization checks on detail endpoints.
- **OSFI B-20:** Decision endpoints return the qualifying rate used and the specific GDS/TDS percentages for auditing.

---

## API Endpoints

### POST /api/v1/frontend/submission

Initialize a new mortgage application and upload supporting documents.

**Request:** `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| lender_id | string | UUID of the selected lender |
| files | file[] | Array of PDF files (Borrower identity, income, property) |

**Response (201 Created):**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "received",
  "message": "Documents uploaded successfully",
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `400 Bad Request`: Invalid file type or file size exceeded.
- `401 Unauthorized`: Invalid or missing authentication token.
- `422 Unprocessable Entity`: Lender ID not found.

---

### GET /api/v1/frontend/applications/{application_id}/status

Retrieve the current pipeline stage for a specific application.

**Parameters:**
- `application_id` (path): UUID string

**Response (200 OK):**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "current_stage": "policy_check",
  "stages": [
    { "name": "extraction", "status": "completed", "updated_at": "2026-03-02T10:05:00Z" },
    { "name": "policy_check", "status": "in_progress", "updated_at": "2026-03-02T10:10:00Z" },
    { "name": "decision", "status": "pending", "updated_at": null }
  ]
}
```

**Errors:**
- `404 Not Found`: Application ID does not exist.

---

### GET /api/v1/frontend/applications/{application_id}/decision

Retrieve the full underwriting decision, including ratio breakdowns and risk flags.

**Parameters:**
- `application_id` (path): UUID string

**Response (200 OK):**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "approved",
  "qualifying_rate": "5.25",
  "ratios": {
    "gds": "32.50",
    "tds": "38.10",
    "ltv": "75.00"
  },
  "flags": [],
  "audit_trail": [
    {
      "action": "gds_calculation",
      "performed_by": "system",
      "timestamp": "2026-03-02T10:15:00Z",
      "details": "GDS calculated using qualifying rate 5.25%"
    }
  ]
}
```

**Errors:**
- `403 Forbidden`: User does not have permission to view detailed financial data.
- `404 Not Found`: Decision not yet generated.

---

### GET /api/v1/frontend/exceptions

List all applications currently in the exception queue for human review.

**Query Parameters:**
- `status` (optional): Filter by exception status (e.g., `pending`, `reviewed`)

**Response (200 OK):**
```json
{
  "count": 2,
  "results": [
    {
      "exception_id": "ex-123",
      "application_id": "550e8400-e29b-41d4-a716-446655440000",
      "reason": "income_discrepancy",
      "severity": "high",
      "flagged_at": "2026-03-02T11:00:00Z"
    },
    {
      "exception_id": "ex-124",
      "application_id": "660e8400-e29b-41d4-a716-446655440001",
      "reason": "policy_violation",
      "severity": "medium",
      "flagged_at": "2026-03-02T11:30:00Z"
    }
  ]
}
```

**Errors:**
- `401 Unauthorized`: Invalid or missing authentication token.

---

### POST /api/v1/frontend/exceptions/{exception_id}/resolve

Submit a resolution for a flagged exception (Human Underwriter action).

**Parameters:**
- `exception_id` (path): UUID string

**Request Body:**
```json
{
  "resolution": "approved",
  "notes": "Borrower provided additional proof of income via secure upload."
}
```

**Response (200 OK):**
```json
{
  "exception_id": "ex-123",
  "status": "resolved",
  "resolved_at": "2026-03-02T12:00:00Z",
  "resolved_by": "user_123"
}
```

**Errors:**
- `400 Bad Request`: Invalid resolution status.
- `404 Not Found`: Exception ID does not exist.
- `409 Conflict`: Exception already resolved.

---

## Configuration Notes

The Frontend React UI module relies on the following environment variables to configure file handling and CORS policies.

### .env.example

```bash
# Frontend React UI Configuration

# Maximum file upload size in bytes (e.g., 25MB)
MAX_UPLOAD_SIZE=26214400

# Allowed file extensions for document upload
ALLOWED_UPLOAD_EXTENSIONS=.pdf,.jpg,.png

# CORS Origins (Comma separated list of frontend URLs)
CORS_ORIGINS=http://localhost:3000,https://mortgage-portal.example.com

# Time in seconds before a status poll should refresh
STATUS_POLL_INTERVAL=15
```