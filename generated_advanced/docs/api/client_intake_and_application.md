Here is the documentation for the **Client Intake & Application** module.

### 1. API Documentation

**File:** `docs/api/client_intake_application.md`

```markdown
# Client Intake & Application API

This module handles the onboarding of new clients and the creation of mortgage applications. All endpoints enforce strict data validation and regulatory compliance (PIPEDA for PII, OSFI for financial data).

## POST /api/v1/clients

Register a new client.

**Regulatory Notes:**
- **PIPEDA:** `sin` and `date_of_birth` are encrypted at rest using AES-256.
- **Audit:** `created_at` is immutable.

**Request:**
```json
{
  "user_id": 42,
  "sin": "123456789",
  "date_of_birth": "1990-01-01",
  "employment_status": "employed",
  "employer_name": "Acme Corp",
  "years_employed": 5,
  "annual_income": "85000.00",
  "other_income": "5000.00",
  "credit_score": 750,
  "marital_status": "single"
}
```

**Response (201):**
```json
{
  "id": 101,
  "user_id": 42,
  "sin_hash": "a1b2c3d4...",
  "date_of_birth": "1990-01-01",
  "employment_status": "employed",
  "employer_name": "Acme Corp",
  "years_employed": 5,
  "annual_income": "85000.00",
  "other_income": "5000.00",
  "credit_score": 750,
  "marital_status": "single",
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid SIN format or DOB.
- 422: Validation error (e.g., negative income).

---

## GET /api/v1/clients/{id}

Retrieve client details by ID.

**Security:** Returns `sin_hash` instead of raw SIN. Raw SIN is never exposed via API.

**Response (200):**
```json
{
  "id": 101,
  "user_id": 42,
  "sin_hash": "a1b2c3d4...",
  "annual_income": "85000.00",
  "credit_score": 750,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 404: Client not found.

---

## POST /api/v1/applications

Create a new mortgage application for a specific client.

**Regulatory Notes:**
- **CMHC:** `property_value`, `purchase_price`, `down_payment`, and `requested_loan_amount` must be Decimals to ensure precise LTV calculation.
- **FINTRAC:** Creates an immutable audit trail.

**Request:**
```json
{
  "client_id": 101,
  "broker_id": 5,
  "application_type": "purchase",
  "status": "draft",
  "property_address": "123 Maple St, Toronto, ON",
  "property_type": "detached",
  "property_value": "1000000.00",
  "purchase_price": "950000.00",
  "down_payment": "190000.00",
  "requested_loan_amount": "760000.00",
  "amortization_years": 25,
  "term_years": 5,
  "mortgage_type": "fixed"
}
```

**Response (201):**
```json
{
  "id": 201,
  "client_id": 101,
  "broker_id": 5,
  "status": "draft",
  "property_address": "123 Maple St, Toronto, ON",
  "requested_loan_amount": "760000.00",
  "created_at": "2026-03-02T11:00:00Z",
  "updated_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 400: LTV > 95% (System hard limit).
- 404: Client not found.

---

## POST /api/v1/applications/{id}/co-borrowers

Add a co-borrower to an existing application.

**Regulatory Notes:**
- **PIPEDA:** Co-borrower PII is encrypted identically to primary clients.

**Request:**
```json
{
  "application_id": 201,
  "sin": "987654321",
  "date_of_birth": "1988-05-15",
  "annual_income": "65000.00",
  "credit_score": 720
}
```

**Response (201):**
```json
{
  "id": 301,
  "application_id": 201,
  "sin_hash": "e5f6g7h8...",
  "annual_income": "65000.00",
  "created_at": "2026-03-02T11:30:00Z"
}
```

**Errors:**
- 404: Application not found.
- 422: Validation error.

---

## POST /api/v1/applications/{id}/submit

Submit an application for underwriting review.

**Behavior:**
- Validates that all required fields are present.
- Changes status to `submitted`.
- Sets `submitted_at` timestamp.

**Request:** (Empty body)

```json
{}
```

**Response (200):**
```json
{
  "id": 201,
  "status": "submitted",
  "submitted_at": "2026-03-02T12:00:00Z",
  "updated_at": "2026-03-02T12:00:00Z"
}
```

**Errors:**
- 400: Application cannot be submitted (missing data).
- 409: Application already submitted.
```

---

### 2. Module README

**File:** `docs/modules/client_intake_application.md`

```markdown
# Client Intake & Application Module

## Overview
The Client Intake & Application module is the entry point for the mortgage underwriting system. It manages the lifecycle of client data, initial application creation, and the association of co-borrowers. It is responsible for ensuring that all data entering the system meets regulatory standards for encryption (PIPEDA) and financial precision (OSFI/CMHC).

## Key Functions

### 1. Client Management
- **Registration:** Captures sensitive Personally Identifiable Information (PII).
- **Security:** Automatically encrypts SIN and Date of Birth using `common.security.encrypt_pii()` before persistence.
- **Data Integrity:** Enforces `Decimal` types for all income fields to prevent floating-point errors.

### 2. Application Creation
- **Property Details:** Stores property address, type, and value.
- **Financials:** Records purchase price, down payment, and requested loan amounts.
- **Validation:** Performs preliminary checks on LTV (Loan-to-Value) ratios to ensure they fall within insurable limits (< 95%).

### 3. Co-borrower Handling
- Supports multiple co-borrowers per application.
- Applies identical encryption and validation rules as primary clients.

## Usage Example

```python
from modules.client_intake_application.services import ClientService, ApplicationService
from decimal import Decimal

# 1. Create a Client
client_service = ClientService(db_session)
client = await client_service.create_client(
    user_id=1,
    sin="123456789",
    annual_income=Decimal("90000.00"),
    # ... other fields
)

# 2. Create Application
app_service = ApplicationService(db_session)
application = await app_service.create_application(
    client_id=client.id,
    broker_id=5,
    property_value=Decimal("500000.00"),
    requested_loan_amount=Decimal("400000.00"),
    # ... other fields
)

# 3. Submit
await app_service.submit_application(application.id)
```

## Regulatory Compliance

- **PIPEDA:** SIN and DOB are encrypted via AES-256. Logs never contain raw PII.
- **FINTRAC:** All records include immutable `created_at` timestamps. Data is retained for 5 years minimum.
- **CMHC:** Financial figures use `Decimal` to allow exact LTV calculation for insurance premium tiers.
```

---

### 3. Configuration Updates

**File:** `.env.example`

```bash
# ... existing config ...

# Client Intake & Application Configuration
# Encryption key for PII (SIN, DOB) - Must be 32 bytes (url-safe base64 encoded)
PII_ENCRYPTION_KEY=change_this_to_a_secure_random_key

# Application Limits
MAX_LTV_RATIO=0.95
```