```markdown
# Client Portal API Documentation

## Overview
The Client Portal module provides the REST API endpoints used by the frontend application to manage mortgage applications, upload documents, view underwriting results, and handle user settings. It enforces Role-Based Access Control (RBAC) to distinguish between Client and Broker actions.

**Base Path:** `/api/v1/portal`

---

## Authentication

### POST /api/v1/auth/login
Authenticates a user and returns a JWT token.

**Request:**
```json
{
  "username": "user@example.com",
  "password": "secure_password"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_role": "broker"
}
```

**Errors:**
- 401: Invalid credentials
- 422: Validation error

---

## Dashboard

### GET /api/v1/portal/dashboard
Retrieves summary data for the logged-in user's dashboard.

**Permissions:** `client` or `broker`

**Response (200):**
```json
{
  "active_applications": 3,
  "pending_documents": 2,
  "recent_notifications": [
    {
      "id": 1,
      "message": "Application #1024 approved.",
      "created_at": "2026-03-01T14:30:00Z"
    }
  ]
}
```

**Errors:**
- 401: Not authenticated

---

## Applications

### GET /api/v1/portal/applications
Lists all mortgage applications accessible to the current user.

**Permissions:** `client` or `broker`

**Query Parameters:**
- `status` (optional): Filter by status (e.g., `submitted`, `approved`)

**Response (200):**
```json
{
  "applications": [
    {
      "id": 1024,
      "applicant_name": "John Doe",
      "property_address": "123 Maple St, Toronto, ON",
      "loan_amount": "450000.00",
      "status": "under_review",
      "created_at": "2026-02-20T10:00:00Z"
    }
  ],
  "total": 1
}
```

**Errors:**
- 401: Not authenticated

### GET /api/v1/portal/applications/{id}
Retrieves detailed information for a specific application.

**Permissions:** `client` (own apps) or `broker`

**Response (200):**
```json
{
  "id": 1024,
  "applicant_name": "John Doe",
  "status": "under_review",
  "financial_summary": {
    "income": "120000.00",
    "gds": "28.5",
    "tds": "32.1"
  },
  "created_at": "2026-02-20T10:00:00Z",
  "updated_at": "2026-03-01T09:15:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Access denied
- 404: Application not found

---

## Documents & Checklist

### POST /api/v1/portal/applications/{id}/documents
Uploads a document for a specific application.

**Permissions:** `client` (own apps) or `broker`

**Request:** `multipart/form-data`
- `file`: The file binary (PDF, JPG, PNG)
- `document_type`: Type of document (e.g., `pay_stub`, `id_verification`, `property_appraisal`)

**Response (201):**
```json
{
  "id": 55,
  "filename": "pay_stub_jan.pdf",
  "document_type": "pay_stub",
  "uploaded_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 400: Invalid file type or size
- 401: Not authenticated
- 413: Payload too large

### GET /api/v1/portal/applications/{id}/checklist
Retrieves the document checklist status for an application.

**Permissions:** `client` (own apps) or `broker`

**Response (200):**
```json
{
  "application_id": 1024,
  "items": [
    {
      "category": "Income Verification",
      "required": true,
      "status": "complete",
      "description": "Last 3 months of pay stubs"
    },
    {
      "category": "ID Verification",
      "required": true,
      "status": "pending",
      "description": "Government issued ID (PIPEDA compliant)"
    }
  ]
}
```

**Errors:**
- 404: Application not found

---

## Broker Only Features

### GET /api/v1/portal/applications/{id}/results
Retrieves the underwriting decision and details.

**Permissions:** `broker` only

**Response (200):**
```json
{
  "application_id": 1024,
  "decision": "approved",
  "qualifying_rate": "5.25",
  "gds": "28.5",
  "tds": "32.1",
  "notes": "All ratios within OSFI B-20 limits."
}
```

**Errors:**
- 403: User is not a broker

### GET /api/v1/portal/applications/{id}/fintrac
Retrieves FINTRAC verification status and audit trail.

**Permissions:** `broker` only

**Response (200):**
```json
{
  "application_id": 1024,
  "risk_level": "low",
  "identity_verified": true,
  "audit_trail": [
    {
      "action": "identity_check",
      "timestamp": "2026-02-21T10:00:00Z",
      "performed_by": "system"
    }
  ]
}
```

**Errors:**
- 403: User is not a broker

### GET /api/v1/portal/applications/{id}/lenders
Retrieves a comparison of lender offers for the application.

**Permissions:** `broker` only

**Response (200):**
```json
{
  "application_id": 1024,
  "offers": [
    {
      "lender_name": "Bank A",
      "rate": "4.85",
      "insurance_premium": "12500.00",
      "monthly_payment": "2450.50"
    },
    {
      "lender_name": "Trust B",
      "rate": "4.79",
      "insurance_premium": "12500.00",
      "monthly_payment": "2420.10"
    }
  ]
}
```

**Errors:**
- 403: User is not a broker

---

## User Management

### GET /api/v1/portal/notifications
Retrieves a list of notifications for the current user.

**Permissions:** `client` or `broker`

**Response (200):**
```json
{
  "notifications": [
    {
      "id": 101,
      "title": "Document Required",
      "body": "Please upload your T4 slip.",
      "read": false,
      "created_at": "2026-03-01T08:00:00Z"
    }
  ]
}
```

### GET /api/v1/portal/settings
Retrieves user settings and profile preferences.

**Permissions:** `client` or `broker`

**Response (200):**
```json
{
  "email": "user@example.com",
  "language": "en",
  "notifications_enabled": true
}
```

### PUT /api/v1/portal/settings
Updates user settings.

**Permissions:** `client` or `broker`

**Request:**
```json
{
  "language": "fr",
  "notifications_enabled": false
}
```

**Response (200):**
```json
{
  "email": "user@example.com",
  "language": "fr",
  "notifications_enabled": false
}
```

---

## Module README: Client Portal

### Overview
The Client Portal module acts as the gateway between the end-users (Clients and Brokers) and the core mortgage underwriting engine. It handles session management, data presentation, and file ingestion.

### Key Functions
1.  **Authentication & Authorization**: Integrates with `common/security.py` to handle JWT tokens and enforce role-based access (RBAC) for broker-specific endpoints.
2.  **File Management**: Handles secure uploads of sensitive documents, ensuring they are stored and indexed correctly for the underwriting team.
3.  **Data Aggregation**: Gathers data from various modules (Underwriting, Lenders, Compliance) to present a unified view in the dashboard and application details.
4.  **PIPEDA Compliance**: Ensures that sensitive data (SIN, DOB) is masked or omitted in API responses unless strictly necessary and encrypted.

### Usage Examples

**Broker accessing Underwriting Results:**
```python
import httpx

async def get_uw_results(token: str, app_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.mortgage-system.com/api/v1/portal/applications/{app_id}/results",
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json() # Contains GDS/TDS and decision
```

**Client uploading a document:**
```python
import httpx

async def upload_document(token: str, app_id: int, file_path: str):
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"document_type": "pay_stub"}
            response = await client.post(
                f"https://api.mortgage-system.com/api/v1/portal/applications/{app_id}/documents",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
                data=data
            )
            return response.json()
```

---

## Configuration Notes

### Environment Variables

Add the following to `.env.example` for the Client Portal module:

```bash
# Client Portal Configuration
PORTAL_MAX_UPLOAD_SIZE_MB=10
PORTAL_ALLOWED_DOCUMENT_TYPES=pdf,png,jpeg,jpg
PORTAL_SESSION_TIMEOUT_MINUTES=60
FRONTEND_URL=https://portal.mortgage-system.com
```

### Setup Requirements
1.  **Storage**: Ensure the configured storage backend (local or S3) is accessible and permissions are set for document uploads.
2.  **CORS**: The `FRONTEND_URL` must be added to the CORS allowed origins in the main application configuration.
3.  **Security**: Ensure all document endpoints require a valid JWT with the correct role claim.
```