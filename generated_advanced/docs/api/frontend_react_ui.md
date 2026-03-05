# Frontend React UI API

This document describes the API endpoints consumed by the Frontend React UI module to facilitate application submission, status tracking, decision review, and exception handling.

## POST /api/v1/applications

Initializes a new mortgage application and accepts document metadata for upload.

**Request:**
```json
{
  "lender_id": "uuid-string",
  "product_type": "fixed_rate",
  "requested_amount": "450000.00",
  "property_value": "600000.00",
  "borrower_details": {
    "first_name": "Jane",
    "last_name": "Doe",
    "dob_hash": "sha256_hash_of_dob",
    "sin_hash": "sha256_hash_of_sin"
  },
  "document_ids": ["uuid-doc-1", "uuid-doc-2"]
}
```

**Response (201):**
```json
{
  "application_id": "uuid-app-123",
  "status": "submitted",
  "created_at": "2026-03-02T10:00:00Z",
  "message": "Application received successfully"
}
```

**Errors:**
- 400: Invalid financial amount or missing required fields
- 422: Validation error (e.g., LTV > 95%)
- 401: Not authenticated

---

## GET /api/v1/applications/{application_id}/status

Retrieves the current pipeline stage and progress percentage for the status dashboard.

**Request:**
- Headers: `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "application_id": "uuid-app-123",
  "current_stage": "policy_engine",
  "stages": [
    {"name": "extraction", "status": "complete", "updated_at": "2026-03-02T10:05:00Z"},
    {"name": "policy_engine", "status": "in_progress", "updated_at": "2026-03-02T10:10:00Z"},
    {"name": "decision", "status": "pending", "updated_at": null}
  ],
  "progress_percent": 66
}
```

**Errors:**
- 404: Application not found

---

## GET /api/v1/applications/{application_id}/decision

Fetches the detailed underwriting decision, including ratio breakdowns (GDS/TDS), compliance flags, and audit trail for the Decision Review page.

**Request:**
- Headers: `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "application_id": "uuid-app-123",
  "decision": "approved",
  "final_score": "850.00",
  "financials": {
    "gds_ratio": "28.50",
    "tds_ratio": "38.20",
    "ltv_ratio": "75.00",
    "stress_test_rate": "5.25"
  },
  "cmhc": {
    "insurance_required": false,
    "premium_amount": "0.00"
  },
  "flags": [],
  "audit_trail": [
    {"action": "calculation_gds", "performed_by": "system", "timestamp": "2026-03-02T10:15:00Z"}
  ]
}
```

**Errors:**
- 403: User does not have permission to view this decision (e.g., Borrower viewing Underwriter data)
- 404: Decision not yet generated

---

## GET /api/v1/underwriting/queue

Retrieves a list of applications flagged for human review (Exception Queue). Supports pagination.

**Request:**
- Query Params: `page=1`, `limit=20`, `severity=high`
- Headers: `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "total": 5,
  "items": [
    {
      "application_id": "uuid-app-456",
      "flagged_at": "2026-03-02T09:30:00Z",
      "severity": "high",
      "reason": "Income variance > 10% vs stated",
      "assigned_to": null
    }
  ]
}
```

**Errors:**
- 401: Not authenticated
- 403: Insufficient permissions (Underwriter role required)

---

## PATCH /api/v1/underwriting/queue/{application_id}/resolve

Allows an underwriter to resolve a flag and update the application status.

**Request:**
```json
{
  "resolution_notes": "Verified via additional paystub upload",
  "new_status": "approved",
  "underwriter_id": "uuid-user-789"
}
```

**Response (200):**
```json
{
  "application_id": "uuid-app-456",
  "status": "approved",
  "resolved_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 400: Invalid resolution status
- 403: Insufficient permissions
- 404: Application not in queue

---

# Frontend React UI Module - README

## Overview
The Frontend React UI module serves as the primary interface for Borrowers and Underwriters. It is a Single Page Application (SPA) built with React that consumes the FastAPI backend.

### Key Features
1.  **Application Submission**: Drag-and-drop document uploader integrating with the backend document parsing service.
2.  **Pipeline Visualization**: Real-time progress bars tracking application state through Extraction, Policy, and Decision stages.
3.  **Decision Review**: Detailed breakdown of GDS/TDS calculations, LTV charts, and CMHC insurance requirements.
4.  **Exception Queue**: A dedicated workspace for underwriters to review, annotate, and resolve flagged applications.

## Usage Examples

### Starting the Development Server
```bash
# Install dependencies
uv sync

# Start the Vite dev server
uv run npm run dev
```

### Viewing Application Status
The `ApplicationStatus` component polls `GET /api/v1/applications/{id}/status` every 5 seconds to update the UI without requiring a refresh.

### Handling Sensitive Data
Per PIPEDA requirements, the frontend never displays raw SIN or DOB. It only displays masked identifiers (e.g., `***-***-123`) or uses the hashed values for internal lookups.

---

# Configuration Notes

## Environment Variables

Update `.env.example` for the frontend configuration:

```env
# Frontend React UI Configuration

# Backend API URL (FastAPI)
VITE_API_BASE_URL=http://localhost:8000/api/v1

# OpenTelemetry Exporter Endpoint
VITE_OTEL_EXPORTER_URL=http://localhost:4318

# File Upload Constraints
VITE_MAX_FILE_SIZE_MB=10
VITE_ALLOWED_FILE_TYPES=.pdf,.png,.jpg

# Feature Flags
VITE_ENABLE_DECISION_CHARTS=true
```

---

## [2026-03-02]

### Added
- **Frontend React UI**: Initial module structure for borrower and underwriter interfaces.
- **API Endpoints**: Added endpoints for application submission (`POST /applications`), status tracking (`GET /applications/{id}/status`), and decision review (`GET /applications/{id}/decision`).
- **Exception Queue**: Implemented endpoints for retrieving (`GET /underwriting/queue`) and resolving (`PATCH /underwriting/queue/{id}/resolve`) flagged applications.
- **Document Uploader**: Configuration for drag-and-drop file upload constraints.

### Changed
- Updated API response schemas to include `audit_trail` for all decision endpoints to comply with FINTRAC requirements.

### Fixed
- N/A (Initial release)