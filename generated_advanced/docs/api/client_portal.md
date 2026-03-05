```markdown
# Client Portal API

## Module Overview

The Client Portal module serves as the primary interface for both clients and brokers to interact with the mortgage underwriting system. It aggregates data from various backend services (Applications, Documents, Compliance) to serve the frontend views.

### Key Functions
- **Dashboard Aggregation:** Provides a summary of active applications, pending tasks, and recent notifications.
- **Document Management:** Handles the upload, retrieval, and validation of supporting documents (e.g., Income verification, Property appraisal).
- **Compliance Views:** Exposes FINTRAC verification status and Underwriting results (Broker only).
- **Lender Comparison:** Allows brokers to view and compare lender offers for a specific application.

### Regulatory Compliance Notes
- **PIPEDA:** All document uploads are scanned for PII in filenames. SIN and DOB are never returned in API responses.
- **FINTRAC:** Access to `/fintrac` endpoints requires broker-level permissions and logs every access attempt for the immutable audit trail.

---

## API Endpoints

### Authentication

#### POST /api/v1/auth/login
Authenticates a user and returns a JWT token.

**Request:**
```json
{
  "username": "user@example.com",
  "password": "secure_password_123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-string",
    "role": "broker"
  }
}
```

**Errors:**
- 401: Invalid credentials
- 422: Validation error

---

### Dashboard

#### GET /api/v1/portal/dashboard
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
      "message": "Document approved: T4 Slip",
      "created_at": "2026-03-01T14:30:00Z"
    }
  ]
}
```

---

### Applications

#### GET /api/v1/applications
Lists all mortgage applications accessible to the current user.

**Permissions:** `client` or `broker`

**Query Parameters:**
- `status` (optional): Filter by status (e.g., `submitted`, `approved`)

**Response (200):**
```json
{
  "items": [
    {
      "id": "app-123-uuid",
      "applicant_name": "John Doe",
      "status": "under_review",
      "loan_amount": "450000.00",
      "created_at": "2026-02-15T09:00:00Z"
    }
  ],
  "total": 1,
  "page": 1
}
```

#### GET /api/v1/applications/{id}
Retrieves detailed information for a specific application.

**Permissions:** `client` (own apps) or `broker`

**Response (200):**
```json
{
  "id": "app-123-uuid",
  "status": "under_review",
  "property_address": "123 Maple St, Toronto, ON",
  "loan_amount": "450000.00",
  "property_value": "550000.00",
  "ltv": "81.81",
  "insurance_required": true,
  "created_at": "2026-02-15T09:00:00Z"
}
```

**Errors:**
- 404: Application not found

---

### Documents

#### POST /api/v1/applications/{id}/documents
Uploads a supporting document for an application.

**Permissions:** `client` (own apps) or `broker`

**Request:** `multipart/form-data`
- `file`: The file binary (PDF, PNG, JPG).
- `document_type`: String (e.g., `employment_letter`, `notice_of_assessment`).
- `description`: String (optional).

**Response (201):**
```json
{
  "id": "doc-uuid",
  "document_type": "employment_letter",
  "filename": "employment_letter_2025.pdf",
  "status": "pending_review",
  "uploaded_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid file type or size exceeds limit
- 413: Payload too large

#### GET /api/v1/applications/{id}/documents
Lists all documents associated with an application.

**Permissions:** `client` (own apps) or `broker`

**Response (200):**
```json
{
  "items": [
    {
      "id": "doc-uuid",
      "document_type": "government_id",
      "status": "verified",
      "uploaded_at": "2026-02-20T11:00:00Z"
    }
  ]
}
```

---

### Checklist

#### GET /api/v1/applications/{id}/checklist
Retrieves the document checklist status for an application.

**Permissions:** `client` (own apps) or `broker`

**Response (200):**
```json
{
  "application_id": "app-123-uuid",
  "is_complete": false,
  "categories": [
    {
      "name": "Income Verification",
      "required_count": 2,
      "uploaded_count": 1,
      "items": [
        {
          "name": "Pay Stubs (Last 2 months)",
          "status": "pending"
        },
        {
          "name": "T4 Slip",
          "status": "received"
        }
      ]
    }
  ]
}
```

---

### Underwriting & Results (Broker Only)

#### GET /api/v1/applications/{id}/results
Retrieves the underwriting decision and details.

**Permissions:** `broker` only

**Response (200):**
```json
{
  "application_id": "app-123-uuid",
  "decision": "approved",
  "gds_ratio": "28.50",
  "tds_ratio": "35.20",
  "stress_test_rate": "6.75",
  "qualifying_income": "95000.00",
  "calculated_at": "2026-03-01T16:45:00Z"
}
```

**Errors:**
- 403: Forbidden (Client access)

---

### FINTRAC (Broker Only)

#### GET /api/v1/applications/{id}/fintrac
Retrieves the FINTRAC compliance status and verification log.

**Permissions:** `broker` only

**Response (200):**
```json
{
  "application_id": "app-123-uuid",
  "risk_level": "low",
  "identity_verified": true,
  "large_cash_transactions": false,
  "audit_trail": [
    {
      "action": "identity_verified",
      "performed_by": "broker_1",
      "timestamp": "2026-02-18T10:00:00Z"
    }
  ]
}
```

---

### Lender Comparison (Broker Only)

#### GET /api/v1/applications/{id}/lenders
Retrieves a list of potential lenders and their offers for the application.

**Permissions:** `broker` only

**Response (200):**
```json
{
  "application_id": "app-123-uuid",
  "offers": [
    {
      "lender_name": "Bank A",
      "rate": "5.24",
      "term_years": 5,
      "amortization_years": 25,
      "monthly_payment": "2650.50",
      "cashback": "0.00"
    },
    {
      "lender_name": "Credit Union B",
      "rate": "5.15",
      "term_years": 5,
      "amortization_years": 25,
      "monthly_payment": "2620.10",
      "cashback": "500.00"
    }
  ]
}
```

---

### Notifications

#### GET /api/v1/notifications
Lists notifications for the logged-in user.

**Permissions:** `client` or `broker`

**Response (200):**
```json
{
  "items": [
    {
      "id": "notif-1",
      "title": "Application Update",
      "body": "Your application status has changed to 'Approved'.",
      "read": false,
      "created_at": "2026-03-02T09:00:00Z"
    }
  ]
}
```

---

### Settings

#### GET /api/v1/users/me
Retrieves the current user's profile settings.

**Permissions:** `client` or `broker`

**Response (200):**
```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "phone": "+14165551234",
  "preferred_language": "en",
  "broker_id": null
}
```

#### PATCH /api/v1/users/me
Updates the current user's profile.

**Permissions:** `client` or `broker`

**Request:**
```json
{
  "phone": "+14165559999",
  "preferred_language": "fr"
}
```

**Response (200):**
```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "phone": "+14165559999",
  "preferred_language": "fr",
  "updated_at": "2026-03-02T11:00:00Z"
}
```

---

## Configuration Notes

### Environment Variables

Add the following to your `.env` file to configure the Client Portal module:

```bash
# Client Portal Configuration
# Maximum file size for document uploads (in bytes)
PORTAL_MAX_UPLOAD_SIZE=10485760

# Allowed MIME types for document uploads
PORTAL_ALLOWED_DOCUMENT_TYPES=application/pdf,image/jpeg,image/png

# Frontend URL for CORS configuration (if applicable)
FRONTEND_URL=https://portal.example.com

# JWT Token expiration time (in minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Setup Instructions

1.  **Dependencies:** Ensure `fastapi`, `python-multipart` (for file uploads), and `python-jose` (for auth) are installed via `uv`.
2.  **Database:** Run Alembic migrations to ensure the `users` and `applications` tables are up to date.
3.  **Storage:** Configure an S3-compatible bucket or local storage path for uploaded documents. Ensure PII encryption at rest is enabled for the storage backend.
```