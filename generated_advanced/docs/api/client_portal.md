Here is the documentation for the Client Portal module, structured according to the project conventions and requirements.

---

# 1. API Documentation

**File:** `docs/api/client_portal.md`

```markdown
# Client Portal API

## POST /api/v1/auth/login
Authenticate a user (Client or Broker) and issue a JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password_123"
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
- 422: Validation error (see error_code)

---

## GET /api/v1/portal/dashboard
Retrieve summary data for the authenticated user's dashboard.

**Response (200):**
```json
{
  "active_applications": 3,
  "pending_documents": 2,
  "recent_notifications": [
    {
      "id": 101,
      "message": "Application #12345 approved",
      "created_at": "2026-03-01T14:30:00Z"
    }
  ]
}
```

**Errors:**
- 401: Not authenticated

---

## GET /api/v1/applications
List all mortgage applications accessible to the user.

**Query Parameters:** `page` (int), `limit` (int), `status` (str)

**Response (200):**
```json
{
  "items": [
    {
      "id": 1,
      "applicant_name": "John Doe",
      "status": "submitted",
      "loan_amount": "450000.00",
      "created_at": "2026-02-20T10:00:00Z"
    }
  ],
  "total": 25,
  "page": 1
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (accessing restricted records)

---

## GET /api/v1/applications/{id}
Retrieve detailed information for a specific application.

**Response (200):**
```json
{
  "id": 1,
  "applicant_name": "John Doe",
  "property_address": "123 Maple St, Toronto, ON",
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "ltv_ratio": "90.00",
  "status": "under_review",
  "created_at": "2026-02-20T10:00:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 404: Application not found

---

## POST /api/v1/applications/{id}/documents
Upload a supporting document for an application. 
*Note: Files are scanned for viruses and metadata is stripped. PII is encrypted at rest.*

**Request:** `multipart/form-data`
- `file`: The file binary
- `document_type`: string (e.g., "pay_stub", "bank_statement", "id_verification")

**Response (201):**
```json
{
  "id": 501,
  "application_id": 1,
  "document_type": "pay_stub",
  "filename": "stub_jan.pdf",
  "status": "uploaded",
  "created_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 400: Invalid file type or size exceeded
- 401: Not authenticated
- 413: Payload too large

---

## GET /api/v1/applications/{id}/checklist
Retrieve the document checklist status for the application.

**Response (200):**
```json
{
  "application_id": 1,
  "items": [
    {
      "category": "Income Verification",
      "description": "Most recent pay stub",
      "is_received": true,
      "received_at": "2026-02-25T09:15:00Z"
    },
    {
      "category": "Identity",
      "description": "Government Issued ID",
      "is_received": false,
      "received_at": null
    }
  ]
}
```

**Errors:**
- 401: Not authenticated
- 404: Application not found

---

## GET /api/v1/applications/{id}/results
Retrieve underwriting results (GDS/TDS calculations and decision). 
*Permission: Broker Only.*

**Response (200):**
```json
{
  "application_id": 1,
  "decision": "approved",
  "gds_ratio": "28.50",
  "tds_ratio": "38.20",
  "qualifying_rate": "6.25",
  "stress_test_passed": true,
  "insurance_required": true,
  "calculated_at": "2026-03-01T16:45:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: User does not have Broker role
- 404: Application not found

---

## POST /api/v1/applications/{id}/fintrac
Submit or update FINTRAC verification data. 
*Requirement: Creates an immutable audit trail for regulatory compliance.*

**Request:**
```json
{
  "risk_level": "low",
  "pep_declaration": false,
  "funds_source_verified": true,
  "notes": "Source of funds matches declared savings."
}
```

**Response (201):**
```json
{
  "id": 999,
  "application_id": 1,
  "verified_by": "broker_01",
  "verified_at": "2026-03-02T12:00:00Z"
}
```

**Errors:**
- 400: Invalid risk level data
- 401: Not authenticated
- 403: User does not have Broker role

---

## GET /api/v1/applications/{id}/lenders
Retrieve lender comparison quotes for the application. 
*Permission: Broker Only.*

**Response (200):**
```json
{
  "application_id": 1,
  "quotes": [
    {
      "lender_name": "Bank A",
      "rate": "5.29",
      "term_months": 60,
      "amortization": "300",
      "estimated_payment": "2610.45"
    },
    {
      "lender_name": "Credit Union B",
      "rate": "5.15",
      "term_months": 60,
      "amortization": "300",
      "estimated_payment": "2580.12"
    }
  ]
}
```

**Errors:**
- 401: Not authenticated
- 403: User does not have Broker role

---

## GET /api/v1/notifications
List notifications for the authenticated user.

**Response (200):**
```json
{
  "items": [
    {
      "id": 1,
      "title": "Document Required",
      "body": "Please upload your T4 slip.",
      "read": false,
      "created_at": "2026-03-01T09:00:00Z"
    }
  ]
}
```

**Errors:**
- 401: Not authenticated
```

---

# 2. Module README

**File:** `docs/modules/client_portal.md`

```markdown
# Client Portal Module

## Overview
The Client Portal module serves as the primary interface for borrowers and brokers to interact with the mortgage underwriting system. It provides functionality for application management, document collection, and viewing underwriting decisions.

## Key Functions

### Authentication & Authorization
- Secure login handling via JWT.
- Role-based access control (RBAC) distinguishing between `client` and `broker` roles.
- Brokers have elevated privileges to view underwriting results, FINTRAC data, and lender comparisons.

### Application Management
- **Listing:** Retrieve paginated lists of mortgage applications.
- **Details:** View specific application data, including property and financial summaries.
- **Checklist:** Dynamic document checklist generation based on application type and state.

### Document Handling
- **Upload:** Secure file upload endpoint supporting MIME type validation and size limits.
- **PIPEDA Compliance:** Automatic encryption of PII at rest. Metadata stripping on upload.
- **Audit:** Immutable logging of all document uploads for audit trails.

### Underwriting & Compliance
- **Results:** Displays OSFI B-20 compliant calculations (GDS/TDS) and stress test results.
- **FINTRAC:** Interface for brokers to input verification data, ensuring 5-year retention compliance.
- **Lender Comparison:** Aggregates quotes from different lenders for broker review.

## Usage Examples

### Client Uploading a Document
1. Client authenticates via `/api/v1/auth/login`.
2. Client retrieves checklist via `GET /api/v1/applications/{id}/checklist`.
3. Client uploads PDF via `POST /api/v1/applications/{id}/documents` with `document_type` set to `pay_stub`.

### Broker Reviewing Results
1. Broker authenticates.
2. Broker accesses `GET /api/v1/applications/{id}/results`.
3. System returns calculated ratios (ensuring GDS ≤ 39% and TDS ≤ 44%) and the final decision.

## Regulatory Notes
- **PIPEDA:** SIN and DOB are never returned in list views. Sensitive fields are encrypted.
- **FINTRAC:** All verification entries create immutable records; updates create new records rather than modifying existing ones.
- **OSFI B-20:** All ratio calculations displayed in the portal are derived from the `Underwriting` module using the qualifying rate logic.
```

---

# 3. Configuration Notes

**Update to:** `.env.example`

```bash
# ... existing config ...

# Client Portal Configuration
# Maximum file upload size in Megabytes
PORTAL_MAX_UPLOAD_MB=10

# Allowed document extensions (comma separated)
PORTAL_ALLOWED_EXTENSIONS=pdf,jpg,png

# Session timeout in minutes
PORTAL_SESSION_TIMEOUT_MINUTES=60

# Frontend URL for CORS configuration
FRONTEND_URL=https://mortgage-portal.example.com
```

---

# 4. Changelog Update

**Update to:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Client Portal: New endpoints for application management, document uploads, and dashboard views.
- Client Portal: Broker-specific endpoints for viewing underwriting results, FINTRAC verification, and lender comparisons.
- Client Portal: Role-based access control implementation for secure data segregation.
- Documentation: API reference and Module README for the Client Portal.

### Changed
- Updated common/security.py to support document metadata stripping for PIPEDA compliance.

### Fixed
- N/A
```