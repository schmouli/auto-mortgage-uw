Here is the documentation for the **Client Portal** module.

# Client Portal API

## Overview
The Client Portal module provides the primary interface for both Clients and Brokers to manage mortgage applications, upload documents, view underwriting results, and handle compliance verifications.

---

## GET /api/v1/client-portal/dashboard
Retrieve summary statistics and recent activity for the logged-in user.

**Permissions:** `client` or `broker`

**Response (200):**
```json
{
  "active_applications": 2,
  "pending_documents": 3,
  "recent_notifications": [
    {
      "id": "notif_123",
      "message": "Document approved",
      "created_at": "2026-03-01T14:30:00Z"
    }
  ]
}
```

**Errors:**
- 401: Not authenticated

---

## GET /api/v1/client-portal/applications
List all mortgage applications accessible to the user.

**Permissions:** `client` or `broker`

**Query Parameters:**
- `status` (optional): Filter by status (e.g., `submitted`, `under_review`)
- `limit` (optional): Default 50
- `offset` (optional): Default 0

**Response (200):**
```json
{
  "total": 10,
  "items": [
    {
      "id": "app_567",
      "property_address": "123 Maple St, Toronto, ON",
      "application_status": "under_review",
      "loan_amount": "450000.00",
      "created_at": "2026-02-15T09:00:00Z"
    }
  ]
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden

---

## GET /api/v1/client-portal/applications/{id}
Retrieve detailed information for a specific application.

**Permissions:** `client` (own apps) or `broker`

**Response (200):**
```json
{
  "id": "app_567",
  "applicant_name": "John Doe",
  "property_address": "123 Maple St, Toronto, ON",
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "ltv_ratio": "90.00",
  "application_status": "under_review",
  "created_at": "2026-02-15T09:00:00Z",
  "updated_at": "2026-03-01T10:00:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Access denied to this application
- 404: Application not found

---

## GET /api/v1/client-portal/applications/{id}/checklist
Retrieve the list of required documents for the application and their upload status.

**Permissions:** `client` or `broker`

**Response (200):**
```json
{
  "application_id": "app_567",
  "checklist_items": [
    {
      "document_type": "government_id",
      "description": "Valid Government Issued ID (Passport/Driver's License)",
      "status": "received",
      "received_at": "2026-02-20T14:00:00Z"
    },
    {
      "document_type": "proof_of_income",
      "description": "Recent Pay Stubs (2 most recent)",
      "status": "pending",
      "received_at": null
    }
  ]
}
```

**Errors:**
- 404: Application not found

---

## POST /api/v1/client-portal/applications/{id}/documents
Upload a document for a specific application.

**Permissions:** `client` or `broker`

**Request:** `multipart/form-data`
- `file`: The file binary (PDF, JPG, PNG)
- `document_type`: String (e.g., `government_id`, `proof_of_income`)
- `description`: String (optional)

**Response (201):**
```json
{
  "id": "doc_889",
  "application_id": "app_567",
  "document_type": "proof_of_income",
  "filename": "pay_stub_jan.pdf",
  "status": "uploaded",
  "created_at": "2026-03-02T11:15:00Z"
}
```

**Errors:**
- 400: Invalid file type or size exceeded
- 422: Validation error
- **Note:** PII data within files is encrypted at rest (AES-256) per PIPEDA.

---

## GET /api/v1/client-portal/applications/{id}/results
Retrieve underwriting decision details (GDS/TDS, LTV, insurance req).

**Permissions:** `broker` only

**Response (200):**
```json
{
  "application_id": "app_567",
  "decision": "approved",
  "gds_ratio": "28.50",
  "tds_ratio": "35.20",
  "ltv_ratio": "90.00",
  "stress_test_rate": "7.25",
  "insurance_required": true,
  "insurance_premium": "4.00",
  "calculated_at": "2026-03-01T16:45:00Z"
}
```

**Errors:**
- 403: User is not a broker
- 404: Results not available yet

---

## POST /api/v1/client-portal/applications/{id}/fintrac
Submit or update FINTRAC verification details for the application.

**Permissions:** `broker` only

**Request:**
```json
{
  "verification_method": "document_review",
  "identity_verified": true,
  "risk_assessment": "low",
  "notes": "ID matches credit bureau records."
}
```

**Response (200):**
```json
{
  "application_id": "app_567",
  "verified_by": "broker_123",
  "verified_at": "2026-03-02T12:00:00Z",
  "audit_id": "audit_999"
}
```

**Errors:**
- 403: User is not a broker
- 400: Invalid risk assessment value

---

## GET /api/v1/client-portal/applications/{id}/lenders
Retrieve lender comparisons and offers for the application.

**Permissions:** `broker` only

**Response (200):**
```json
{
  "application_id": "app_567",
  "offers": [
    {
      "lender_name": "Bank A",
      "rate": "5.19",
      "term_years": 5,
      "amortization_years": 25,
      "monthly_payment": "2678.50",
      "cashback": "0.00"
    },
    {
      "lender_name": "Credit Union B",
      "rate": "5.15",
      "term_years": 5,
      "amortization_years": 25,
      "monthly_payment": "2665.20",
      "cashback": "500.00"
    }
  ]
}
```

**Errors:**
- 403: User is not a broker

---

## GET /api/v1/client-portal/notifications
List notifications for the logged-in user.

**Permissions:** `client` or `broker`

**Response (200):**
```json
{
  "unread_count": 2,
  "items": [
    {
      "id": "notif_001",
      "title": "Application Status Update",
      "body": "Your application has moved to Underwriting.",
      "read": false,
      "created_at": "2026-03-02T09:00:00Z"
    }
  ]
}
```

---

## PATCH /api/v1/client-portal/settings
Update user preferences (e.g., email notifications, language).

**Permissions:** `client` or `broker`

**Request:**
```json
{
  "email_notifications_enabled": true,
  "preferred_language": "en"
}
```

**Response (200):**
```json
{
  "user_id": "user_123",
  "email_notifications_enabled": true,
  "preferred_language": "en",
  "updated_at": "2026-03-02T12:30:00Z"
}
```

**Errors:**
- 422: Validation error

---

# Client Portal Module

## Overview
The `client_portal` module serves as the user-facing gateway for the Canadian Mortgage Underwriting System. It handles the presentation logic for data aggregation, ensuring that Clients and Brokers have appropriate access levels to sensitive financial and personal information.

This module relies heavily on the `common/security` module to enforce PII encryption (PIPEDA) and role-based access control (RBAC).

## Key Functions

### `ApplicationService`
*   `get_dashboard_summary(user_id)`: Aggregates active application counts and pending tasks.
*   `list_applications(user_id, filters)`: Returns a paginated list of applications based on user role.
*   `get_application_detail(app_id, user)`: Fetches full application details, enforcing that clients can only see their own data.

### `DocumentService`
*   `upload_document(file, app_id, meta)`: Handles file validation, virus scanning hooks, and secure storage. Ensures audit trails (FINTRAC) are created for every upload.
*   `get_checklist(app_id)`: Dynamically generates required document lists based on the application state (e.g., Self-employed vs. Employed).

### `UnderwritingViewService`
*   `get_results(app_id)`: Retrieves calculated ratios (GDS/TDS) and decisions. Restricted to brokers.
*   `compare_lenders(app_id)`: Fetches pre-qualified offers from connected lender APIs.

## Usage Examples

### Broker viewing an application
```python
from modules.client_portal.services import ApplicationService

async def view_application(app_id: str, current_broker: Broker):
    # Service ensures broker has access to this specific application
    app_details = await ApplicationService.get_application_detail(app_id, current_broker)
    return app_details
```

### Client uploading a document
```python
from modules.client_portal.services import DocumentService

async def handle_upload(file: UploadFile, app_id: str, doc_type: str):
    # Validates file type, encrypts content, logs to audit trail
    doc_record = await DocumentService.upload_document(
        file=file,
        application_id=app_id,
        document_type=doc_type
    )
    return doc_record
```

---

# Configuration Notes

## Environment Variables

Add the following to your `.env.example` file to configure the Client Portal module:

```bash
# Client Portal Configuration
# Maximum file size for document uploads (in MB)
CLIENT_PORTAL_MAX_UPLOAD_SIZE=25

# Allowed file extensions for uploads (comma separated)
CLIENT_PORTAL_ALLOWED_EXTENSIONS=.pdf,.jpg,.jpeg,.png

# Frontend URL for CORS configuration (if served separately)
CLIENT_PORTAL_FRONTEND_URL=https://portal.example.com

# Session timeout duration in minutes
CLIENT_PORTAL_SESSION_TIMEOUT_MINUTES=60
```