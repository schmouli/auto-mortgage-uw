# Document Management API

## POST /api/v1/documents

Upload a new document for a specific mortgage application.

**Request:**
```json
{
  "application_id": 123,
  "document_type": "government_id",
  "file_name": "passport_scan.jpg",
  "file_size": 2048576,
  "mime_type": "image/jpeg",
  "file_path": "/uploads/secure/uuid-hash.jpg"
}
```
*(Note: In a real implementation, `file` might be sent as multipart/form-data, and the backend handles the path generation)*

**Response (201):**
```json
{
  "id": 501,
  "application_id": 123,
  "uploaded_by": 42,
  "document_type": "government_id",
  "file_name": "passport_scan.jpg",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Invalid file type or size exceeds limit
- 404: Application not found
- 413: Payload too large (File size limit exceeded)

---

## GET /api/v1/applications/{application_id}/documents

Retrieve all documents associated with a specific application.

**Response (200):**
```json
[
  {
    "id": 501,
    "document_type": "government_id",
    "file_name": "passport_scan.jpg",
    "status": "accepted",
    "is_verified": true,
    "verified_at": "2026-03-02T15:00:00Z"
  },
  {
    "id": 502,
    "document_type": "t4_slip",
    "file_name": "2023_t4.pdf",
    "status": "pending",
    "is_verified": false
  }
]
```

**Errors:**
- 401: Not authenticated
- 403: Access denied (User not associated with the application)
- 404: Application not found

---

## PATCH /api/v1/documents/{document_id}/verify

Verify or reject a document. This action is auditable per FINTRAC requirements.

**Request:**
```json
{
  "status": "accepted",
  "rejection_reason": null
}
```
*OR*
```json
{
  "status": "rejected",
  "rejection_reason": "Document is blurry and ID number is not visible."
}
```

**Response (200):**
```json
{
  "id": 501,
  "status": "rejected",
  "rejection_reason": "Document is blurry and ID number is not visible.",
  "is_verified": false,
  "verified_by": 99,
  "verified_at": "2026-03-02T16:15:00Z"
}
```

**Errors:**
- 400: Invalid status value
- 403: User lacks underwriting permissions
- 404: Document not found

---

## GET /api/v1/applications/{application_id}/requirements

Check the document requirements status for an application (e.g., which documents are required vs. received).

**Response (200):**
```json
[
  {
    "document_type": "government_id",
    "is_required": true,
    "is_received": true,
    "due_date": "2026-03-10T00:00:00Z"
  },
  {
    "document_type": "t1_general",
    "is_required": true,
    "is_received": false,
    "due_date": "2026-03-15T00:00:00Z"
  }
]
```

**Errors:**
- 404: Application not found

---

# Document Management Module

## Overview
The Document Management module handles the lifecycle of financial and identity documents required for the Canadian mortgage underwriting process. It manages file uploads, tracks verification status (Underwriter review), and ensures compliance with FINTRAC audit trails and PIPEDA data privacy requirements.

## Key Functions
1.  **Secure Upload:** Handles file ingestion, associating files with specific `application_id`s and `user_id`s. 
2.  **Verification Workflow:** Allows underwriters to mark documents as `accepted` or `rejected`. All status changes are immutable audit logs (`verified_by`, `verified_at`).
3.  **Requirement Tracking:** Automatically generates checklists based on the applicant profile (e.g., Self-employed requires T1 General; Employed requires Pay Stubs) and tracks receipt status.

## Compliance Notes
- **FINTRAC:** All document records are immutable. Deletion is not supported; only soft status changes are permitted. `created_at` and `uploaded_by` are always captured.
- **PIPEDA:** Files stored at `file_path` must be encrypted at rest (AES-256). Sensitive document types (e.g., `proof_of_sin`) trigger additional encryption headers.
- **Data Minimization:** Only metadata (filename, size, type) is returned via API; the binary file content is served via a separate, secure endpoint (not documented here) to prevent accidental logging of PII.

## Usage Example
1.  **Applicant** uploads a PDF of their T4 Slip via the frontend.
2.  System creates a `documents` record with `status: pending`.
3.  **Underwriter** views the pending documents list.
4.  Underwriter calls `PATCH /documents/{id}/verify` with `status: accepted`.
5.  System updates `document_requirements` to mark `t4_slip` as `is_received: true`.

---

# Configuration Updates

## .env.example

```bash
# Document Management Configuration
# Storage path for encrypted documents (Local or S3 prefix)
DOCUMENT_STORAGE_PATH=./secure_uploads

# Maximum upload size in bytes (e.g., 25MB)
MAX_UPLOAD_SIZE=26214400

# Allowed MIME types for upload (comma separated)
ALLOWED_MIME_TYPES=image/jpeg,application/pdf,image/png

# Encryption key for PII documents at rest (Must be 32 bytes for AES-256)
DOCUMENT_ENCRYPTION_KEY=change_this_to_a_secure_random_32_char_string
```