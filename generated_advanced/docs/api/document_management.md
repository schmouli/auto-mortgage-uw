# Document Management API

## Overview
The Document Management module handles the secure upload, storage, verification, and lifecycle tracking of borrower documents required for mortgage underwriting. It ensures compliance with PIPEDA regarding sensitive data storage and FINTRAC audit trails.

---

## Endpoints

### POST /api/v1/documents

Uploads a new document and associates it with a mortgage application.

**Request:**
Content-Type: `multipart/form-data`

| Form Field | Type | Description |
|------------|------|-------------|
| file | File | The document file (PDF, JPEG, PNG). |
| application_id | integer | The ID of the mortgage application. |
| document_type | string | Type of document (e.g., `government_id`, `t4_slip`). |
| uploaded_by | integer | The ID of the user performing the upload. |

**Response (201):**
```json
{
  "id": 123,
  "application_id": 45,
  "document_type": "government_id",
  "file_name": "passport_scan.pdf",
  "file_path": "/secure/storage/45/passport_scan.pdf",
  "file_size": 1024000,
  "mime_type": "application/pdf",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Invalid file type or size exceeds limit.
- 404: Application not found.
- 413: Payload too large (File size limit exceeded).

---

### GET /api/v1/applications/{application_id}/documents

Retrieves a list of all documents associated with a specific application.

**Parameters:**
- `application_id` (path): Integer ID of the application.

**Response (200):**
```json
[
  {
    "id": 123,
    "document_type": "government_id",
    "file_name": "passport_scan.pdf",
    "status": "accepted",
    "is_verified": true,
    "verified_at": "2026-03-02T15:00:00Z"
  },
  {
    "id": 124,
    "document_type": "pay_stub",
    "file_name": "jan_payroll.pdf",
    "status": "pending",
    "is_verified": false,
    "uploaded_at": "2026-03-02T14:35:00Z"
  }
]
```

**Errors:**
- 401: Not authenticated.
- 404: Application not found.

---

### PATCH /api/v1/documents/{document_id}/verification

Updates the verification status of a document (Underwriter action). This action creates an immutable audit trail.

**Request:**
```json
{
  "status": "accepted",
  "verified_by": 5,
  "rejection_reason": null
}
```
*Allowed statuses:* `pending`, `accepted`, `rejected`

**Response (200):**
```json
{
  "id": 123,
  "status": "accepted",
  "is_verified": true,
  "verified_by": 5,
  "verified_at": "2026-03-02T16:00:00Z",
  "rejection_reason": null
}
```

**Errors:**
- 400: Invalid status transition.
- 403: User lacks underwriter permissions.
- 404: Document not found.

---

### GET /api/v1/applications/{application_id}/requirements

Checks the application's document requirements against uploaded documents to determine fulfillment status.

**Parameters:**
- `application_id` (path): Integer ID of the application.

**Response (200):**
```json
[
  {
    "id": 1,
    "document_type": "government_id",
    "is_required": true,
    "is_received": true,
    "due_date": "2026-03-15T00:00:00Z"
  },
  {
    "id": 2,
    "document_type": "t1_general",
    "is_required": true,
    "is_received": false,
    "due_date": "2026-03-15T00:00:00Z"
  }
]
```

**Errors:**
- 401: Not authenticated.
- 404: Application not found.

---

# Module README: Document Management

## Overview
The Document Management module is responsible for the secure handling of borrower documentation throughout the underwriting process. It manages file storage, metadata tracking, and the verification workflow required to approve a mortgage application.

## Key Functions

1.  **Secure Upload & Storage**
    *   Accepts file uploads via multipart/form-data.
    *   Validates file types (MIME type check) and enforces size limits.
    *   Stores files in a secure, non-publicly accessible directory structure defined by `DOCUMENT_STORAGE_PATH`.
    *   **PIPEDA Compliance:** Sensitive documents (e.g., `proof_of_sin`) are flagged for encryption at rest. Access logs are generated for every upload/download action.

2.  **Requirement Tracking**
    *   Automatically checks `document_requirements` when a file is uploaded.
    *   Updates the `is_received` flag for the corresponding `document_type` if a valid file exists.
    *   Returns a checklist of outstanding documents for the underwriter.

3.  **Verification Workflow**
    *   Allows authorized underwriters to mark documents as `accepted` or `rejected`.
    *   Requires `verified_by` (User ID) and timestamps the action (`verified_at`) to satisfy **FINTRAC** audit trail requirements.

## Usage Example

1.  **Borrower uploads ID:**
    `POST /api/v1/documents` with `document_type="government_id"`.
2.  **System updates status:**
    The `document_requirements` entry for `government_id` automatically updates `is_received` to `true`.
3.  **Underwriter reviews:**
    `GET /api/v1/applications/{id}/documents` to view the file.
4.  **Underwriter approves:**
    `PATCH /api/v1/documents/{id}/verification` with `status="accepted"`.

---

# Configuration Notes

## Environment Variables

Add the following to your `.env` file to configure the Document Management module:

```bash
# Document Management Configuration
# Absolute path to the directory where uploaded files are stored.
# Ensure this directory has restricted permissions (read/write only by the application user).
DOCUMENT_STORAGE_PATH=/var/lib/mortgage_app/uploads

# Maximum file size allowed for upload in Megabytes.
MAX_FILE_SIZE_MB=10

# Comma-separated list of allowed MIME types for security validation.
ALLOWED_MIME_TYPES=application/pdf,image/jpeg,image/png

# Encryption key for PIPEDA compliance (AES-256).
# Must be 32 bytes (url-safe base64 encoded).
DOCUMENT_ENCRYPTION_KEY=<your_32_byte_url_safe_base64_key>
```

## Setup Notes

1.  **Directory Permissions:** Ensure the user running the FastAPI application has write access to `DOCUMENT_STORAGE_PATH`.
2.  **Encryption:** For production, `DOCUMENT_ENCRYPTION_KEY` must be set in a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault) rather than `.env`. If the key is missing, the application should refuse to start or log a critical error.
3.  **Retention:** Per FINTRAC, document records in the database (`documents` table) must not be hard-deleted. Implement soft-deletes if removal is necessary, but retain the audit trail for 5 years.