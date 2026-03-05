# Client Intake & Application API

## Overview

This module handles the initial collection of borrower data, property details, and application structuring. It ensures compliance with PIPEDA for data encryption and FINTRAC for audit trails.

## POST /api/v1/clients

Registers a new primary borrower.

**Request:**
```json
{
  "sin": "123456789",
  "date_of_birth": "1990-01-01",
  "employment_status": "full_time_employed",
  "employer_name": "Acme Corp",
  "years_employed": 5,
  "annual_income": "95000.00",
  "other_income": "5000.00",
  "credit_score": 720,
  "marital_status": "married"
}
```

**Response (201):**
```json
{
  "id": "uuid-v4",
  "user_id": "uuid-v4",
  "sin_encrypted": "aes256_encrypted_hash",
  "date_of_birth": "1990-01-01",
  "employment_status": "full_time_employed",
  "annual_income": "95000.00",
  "credit_score": 720,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid SIN format or DOB
- 422: Validation error (e.g., negative income)
- 401: Not authenticated

---

## GET /api/v1/clients/{client_id}

Retrieves client details. PII (SIN) is returned in encrypted format only.

**Response (200):**
```json
{
  "id": "uuid-v4",
  "sin_encrypted": "aes256_encrypted_hash",
  "annual_income": "95000.00",
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 404: Client not found

---

## POST /api/v1/applications

Initiates a new mortgage application linked to a client.

**Request:**
```json
{
  "client_id": "uuid-v4",
  "broker_id": "uuid-v4",
  "application_type": "purchase",
  "property_address": "123 Maple St, Toronto, ON",
  "property_type": "detached",
  "property_value": "750000.00",
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
  "id": "uuid-v4",
  "client_id": "uuid-v4",
  "status": "draft",
  "requested_loan_amount": "600000.00",
  "ltv_ratio": "0.80",
  "created_at": "2026-03-02T10:05:00Z",
  "updated_at": "2026-03-02T10:05:00Z"
}
```

**Errors:**
- 400: LTV > 95% (System constraint)
- 404: Client or Broker not found
- 422: Invalid financial calculation (Down payment > Purchase Price)

---

## POST /api/v1/applications/{application_id}/co-borrowers

Adds a co-borrower to an existing application.

**Request:**
```json
{
  "application_id": "uuid-v4",
  "sin": "987654321",
  "date_of_birth": "1992-05-15",
  "annual_income": "85000.00",
  "credit_score": 700
}
```

**Response (201):**
```json
{
  "id": "uuid-v4",
  "application_id": "uuid-v4",
  "sin_encrypted": "aes256_encrypted_hash",
  "annual_income": "85000.00",
  "created_at": "2026-03-02T10:10:00Z"
}
```

**Errors:**
- 400: Application already submitted
- 404: Application not found

---

## PUT /api/v1/applications/{application_id}/submit

Submits the application for underwriting review. Validates all required fields and locks the application from further edits.

**Request Body:** Empty

**Response (200):**
```json
{
  "id": "uuid-v4",
  "status": "submitted",
  "submitted_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 400: Validation failed (missing documents, invalid GDS/TDS)
- 409: Application already submitted

---

# Module README: Client Intake & Application

## Overview
The Client Intake & Application module is the entry point for the mortgage underwriting system. It manages the lifecycle of borrower data (Clients) and mortgage requests (Applications) from creation to submission.

## Key Functions
1.  **Client Management**: Secure storage of borrower PII (SIN/DOB encrypted via AES-256) and financial history.
2.  **Application Structuring**: Captures property details and loan parameters. Automatically calculates LTV (Loan-to-Value) ratios to determine CMHC insurance eligibility.
3.  **Co-borrower Support**: Allows linking additional borrowers to a single application.
4.  **State Management**: Transitions applications from `draft` to `submitted`, ensuring data integrity before underwriting begins.

## Usage Examples
### Creating a Client
Use the `POST /api/v1/clients` endpoint. Ensure the SIN is valid. The system will automatically hash the SIN for lookups and encrypt it for storage.
*Note: Annual income must be provided as a string or Decimal to maintain precision.*

### Submitting an Application
Before calling `PUT /api/v1/applications/{id}/submit`, ensure:
1.  Property value and down payment are accurate.
2.  LTV is calculated correctly (if LTV > 80%, insurance logic is triggered).
3.  All co-borrowers are added.

## Compliance Notes
*   **PIPEDA**: SIN and DOB are never logged. They are encrypted at rest.
*   **FINTRAC**: `created_at` timestamps are immutable. All records are retained for 5 years minimum.
*   **CMHC**: LTV is calculated using strict Decimal arithmetic: `loan_amount / property_value`.

---

# Configuration Notes

## Environment Variables

Update `.env.example` with the following:

```bash
# Client Intake & Application Configuration
# Encryption key for PII (SIN, DOB) - Must be 32 bytes for AES-256
PII_ENCRYPTION_KEY=change_this_to_a_secure_32_byte_string

# Max LTV allowed for automated intake (Manual review required if exceeded)
INTAKE_MAX_LTV=0.95

# Minimum credit score required for intake
INTAKE_MIN_CREDIT_SCORE=600
```