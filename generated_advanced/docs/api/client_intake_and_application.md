Here is the documentation for the **Client Intake & Application** module.

### 1. API Documentation

**File:** `docs/api/client_intake.md`

```markdown
# Client Intake & Application API

This module handles the onboarding of new clients and the creation of mortgage applications. It ensures compliance with PIPEDA for sensitive data (SIN/DOB) and validates initial financial data for CMHC insurance requirements.

## Clients

### POST /api/v1/clients

Register a new client.

**Request:**
```json
{
  "sin_encrypted": "encrypted_string_or_placeholder",
  "date_of_birth": "1990-01-01",
  "employment_status": "full_time",
  "employer_name": "Acme Corp",
  "years_employed": 5,
  "annual_income": "95000.00",
  "other_income": "5000.00",
  "credit_score": 750,
  "marital_status": "single"
}
```

**Response (201):**
```json
{
  "id": 1,
  "user_id": 42,
  "date_of_birth": "1990-01-01",
  "employment_status": "full_time",
  "annual_income": "95000.00",
  "credit_score": 750,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid data format (e.g., negative income).
- 422: Validation error (missing required fields).
- 401: Not authenticated.

---

### GET /api/v1/clients/{id}

Retrieve client details by ID.

**Response (200):**
```json
{
  "id": 1,
  "employment_status": "full_time",
  "annual_income": "95000.00",
  "credit_score": 750,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Note:** `sin_encrypted` is never returned in full via API for security (PIPEDA).

**Errors:**
- 404: Client not found.

---

## Applications

### POST /api/v1/applications

Create a new mortgage application linked to a client.

**Request:**
```json
{
  "client_id": 1,
  "broker_id": 10,
  "application_type": "purchase",
  "property_address": "123 Maple St, Toronto, ON",
  "property_type": "detached",
  "property_value": "800000.00",
  "purchase_price": "750000.00",
  "down_payment": "150000.00",
  "requested_loan_amount": "600000.00",
  "amortization_years": 25,
  "term_years": 5,
  "mortgage_type": "fixed"
}
```

**Response (201):**
```json
{
  "id": 101,
  "client_id": 1,
  "status": "draft",
  "requested_loan_amount": "600000.00",
  "property_value": "800000.00",
  "created_at": "2026-03-02T11:00:00Z",
  "updated_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 400: Logic error (e.g., Down payment > Purchase Price).
- 404: Client not found.

---

### GET /api/v1/applications/{id}

Retrieve application details.

**Response (200):**
```json
{
  "id": 101,
  "client_id": 1,
  "status": "draft",
  "requested_loan_amount": "600000.00",
  "ltv_ratio": "0.80",
  "insurance_required": false,
  "created_at": "2026-03-02T11:00:00Z"
}
```

---

### POST /api/v1/applications/{id}/submit

Submit the application for underwriting review. Changes status from `draft` to `submitted`.

**Response (200):**
```json
{
  "id": 101,
  "status": "submitted",
  "submitted_at": "2026-03-02T12:00:00Z"
}
```

**Errors:**
- 400: Cannot submit application in current status.
- 422: Validation failed (missing required fields for submission).

---

## Co-Borrowers

### POST /api/v1/applications/{id}/co-borrowers

Add a co-borrower to an existing application.

**Request:**
```json
{
  "application_id": 101,
  "sin_encrypted": "encrypted_string_2",
  "date_of_birth": "1988-05-15",
  "annual_income": "85000.00",
  "credit_score": 720
}
```

**Response (201):**
```json
{
  "id": 5,
  "application_id": 101,
  "annual_income": "85000.00",
  "created_at": "2026-03-02T12:30:00Z"
}
```

**Errors:**
- 404: Application not found.
- 400: Application already submitted (cannot modify).
```

### 2. Module README

**File:** `docs/modules/client_intake.md`

```markdown
# Client Intake & Application Module

## Overview
The Client Intake & Application module is the entry point for the mortgage underwriting system. It manages the collection of borrower data, property details, and initial application structuring.

## Key Features

### 1. PIPEDA Compliance
- **Data Encryption:** Sensitive Personal Information (SIN, DOB) is encrypted at rest using AES-256 via `common/security.py`.
- **Data Minimization:** Only fields strictly necessary for underwriting are collected.
- **Logging:** Sensitive fields are strictly excluded from structlog output and error messages.

### 2. Application Lifecycle
- Applications are created in a `draft` state.
- Supports updates to financials and property details while in `draft`.
- Transition to `submitted` state locks the application from further modification by the client/broker, triggering the underwriting workflow.

### 3. CMHC Insurance Logic
- Upon application creation or update, the system calculates the Loan-to-Value (LTV) ratio:
  `LTV = requested_loan_amount / property_value`
- If `LTV > 80%`, the `insurance_required` flag is set automatically.
- The system logs the LTV calculation breakdown for auditing purposes.

### 4. Audit Trail (FINTRAC)
- All entities (`Client`, `Application`, `CoBorrower`) include immutable `created_at` timestamps.
- Records are never soft-deleted to ensure transaction history integrity.

## Usage Example

```python
import httpx

async def create_mortgage_application():
    async with httpx.AsyncClient() as client:
        # 1. Create Client
        client_resp = await client.post(
            "http://api/v1/clients",
            json={
                "sin_encrypted": "...",
                "annual_income": "120000.00",
                "employment_status": "full_time",
                # ... other fields
            }
        )
        client_id = client_resp.json()["id"]

        # 2. Create Application
        app_resp = await client.post(
            "http://api/v1/applications",
            json={
                "client_id": client_id,
                "property_value": "500000.00",
                "requested_loan_amount": "400000.00",
                # ... other fields
            }
        )
        application_id = app_resp.json()["id"]

        # 3. Submit
        await client.post(f"http://api/v1/applications/{application_id}/submit")
```

## Data Models
- **Client:** Stores personal, financial, and employment data.
- **Application:** Stores property details, loan structure, and status.
- **CoBorrower:** Links additional borrowers to an application (structure mirrors Client).
```

### 3. Changelog Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Client Intake & Application: New endpoints for creating clients, mortgage applications, and co-borrowers.
- Client Intake & Application: Implemented PIPEDA-compliant encryption for SIN and DOB fields.
- Client Intake & Application: Added LTV calculation logic to determine CMHC insurance requirements automatically.

### Changed
- N/A

### Fixed
- N/A
```

### 4. Environment Variables

**File:** `.env.example`

```bash
# ... existing vars

# Client Intake & Application Configuration
# Key used for AES-256 encryption of PII (SIN, DOB). Must be 32 bytes url-safe base64 encoded.
PII_ENCRYPTION_KEY=change_this_to_a_secure_32_byte_key

# CMHC Configuration
# Base URL for CMHC insurance premium lookup (if external service is used)
# CMHC_API_URL=https://api.cmhc-schl.gc.ca
```