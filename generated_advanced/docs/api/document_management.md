Here is the documentation for the Document Management module.

### 1. API Documentation
**File:** `docs/api/Document Management.md`

```markdown
# Document Management API

## POST /api/v1/documents

Upload a new document and associate it with a mortgage application.

**Request:**
```json
{
  "application_id": 123,
  "document_type": "government_id",
  "file_name": "passport_scan.pdf",
  "file_path": "/uploads/secure/uuid/passport_scan.pdf",
  "file_size": 1024000,
  "mime_type": "application/pdf"
}
```

**Response (201):**
```json
{
  "id": 456,
  "application_id": 123,
  "uploaded_by": 101,
  "document_type": "government_id",
  "file_name": "passport_scan.pdf",
  "status": "pending",
  "uploaded_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Invalid file type or size exceeds limit.
- 404: Application not found.
- 422: Validation error (e.g., missing required fields).

---

## GET /api/v1/documents/{document_id}

Retrieve details of a specific document.

**Response (200):**
```json
{
  "id": 456,
  "application_id": 123,
  "document_type": "t4_slip",
  "file_name": "2024_t4.pdf",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 401: Not authenticated.
- 403: Access denied (User not associated with the application).
- 404: Document not found.

---

## PATCH /api/v1/documents/{document_id}/verify

Verify or reject a document. This action is auditable per FINTRAC requirements.

**Request (Verify):**
```json
{
  "action": "verify"
}
```

**Request (Reject):**
```json
{
  "action": "reject",
  "rejection_reason": "Document is expired or blurry"
}
```

**Response (200):**
```json
{
  "id": 456,
  "status": "accepted",
  "is_verified": true,
  "verified_by": 202,
  "verified_at": "2026-03-02T15:00:00Z"
}
```

**Errors:**
- 400: Invalid action or missing rejection reason for rejection.
- 403: User does not have underwriting permissions.

---

## GET /api/v1/applications/{application_id}/requirements

Check the document fulfillment status for an application.

**Response (200):**
```json
{
  "application_id": 123,
  "requirements": [
    {
      "document_type": "government_id",
      "is_required": true,
      "is_received": true,
      "due_date": "2026-03-15"
    },
    {
      "document_type": "proof_of_sin",
      "is_required": true,
      "is_received": false,
      "due_date": "2026-03-15"
    }
  ]
}
```

**Errors:**
- 404: Application not found.
```

### 2. Module README
**File:** `docs/modules/Document Management.md`

```markdown
# Document Management Module

## Overview
The Document Management module handles the secure ingestion, storage, and verification of applicant documents required for mortgage underwriting. It ensures that all necessary documentation is collected according to specific application requirements and maintains an immutable audit trail for regulatory compliance.

## Key Features

### 1. Document Ingestion
- Supports uploading various document types defined by OSFI and internal policies (e.g., Identity, Income, Property).
- Validates file metadata (size, MIME type) before storage.
- Tracks the uploader (`uploaded_by`) and timestamp (`uploaded_at`) for FINTRAC auditability.

### 2. Verification Workflow
- Underwriters can review documents and mark them as `accepted` or `rejected`.
- Rejections require a reason to be stored in `rejection_reason`.
- Verification actions are tracked with `verified_by` and `verified_at` timestamps.

### 3. Requirement Tracking
- The `document_requirements` table dynamically tracks what documents are needed for a specific application.
- Automatically updates `is_received` status when matching documents are uploaded.

## Data Models

### `documents`
Stores metadata for every uploaded file.
- **Status Enum:** `pending`, `accepted`, `rejected`.
- **PIPEDA Compliance:** Sensitive documents (e.g., `proof_of_sin`) must be stored encrypted at rest. The database stores the reference path, while the actual file content is secured on the filesystem.

### `document_requirements`
Defines the checklist for an application.
- **Logic:** When a document of type `X` is uploaded for application `Y`, the corresponding entry in this table is updated (`is_received = True`).

## Usage Example: Checking Application Readiness

Before moving an application to "Underwriting", the system checks if all required documents are received.

```python
from modules.document_management.services import DocumentService

async def check_docs(app_id: int):
    service = DocumentService()
    requirements = await service.get_requirements(app_id)
    
    missing = [r.document_type for r in requirements if r.is_required and not r.is_received]
    
    if missing:
        return False, f"Missing documents: {', '.join(missing)}"
    return True, "All documents received"
```

## Security Notes
- **Access Control:** Endpoints enforce that users can only view/upload documents for applications they are associated with or own.
- **PIPEDA:** Document contents are never logged. Only metadata (filenames, types) is recorded in logs.
- **Retention:** Per FINTRAC, document records and files are retained for 5 years.
```

### 3. Configuration Notes
**File:** `.env.example` (Append these entries)

```bash
# Document Management Configuration
# Local or S3 base path for storing encrypted files
DOCUMENT_STORAGE_PATH=./secure_storage
# Maximum file size allowed for upload (in MB)
MAX_UPLOAD_SIZE_MB=25
# Allowed MIME types (comma separated)
ALLOWED_MIME_TYPES=application/pdf,image/jpeg,image/png
# Encryption key for PIPEDA compliance (AES-256 key derivation base)
DOCUMENT_ENCRYPTION_KEY_BASE=
```