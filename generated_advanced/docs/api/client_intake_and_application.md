Here is the documentation for the **Client Intake & Application** module.

### 1. API Documentation
**File:** `docs/api/client_intake.md`

```markdown
# Client Intake & Application API

This module handles the onboarding of new clients and the submission of mortgage applications. It enforces PIPEDA compliance for sensitive data (SIN, DOB) and collects financial data required for OSFI B-20 and CMHC calculations.

## POST /api/v1/clients

Register a new client in the system.

**Request:**
```json
{
  "user_id": 42,
  "sin_encrypted": "aes256_encrypted_string_here",
  "date_of_birth": "1990-05-15",
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
  "id": 101,
  "user_id": 42,
  "date_of_birth": "1990-05-15",
  "employment_status": "full_time_employed",
  "employer_name": "Acme Corp",
  "annual_income": "95000.00",
  "credit_score": 720,
  "created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Invalid employment status or marital status value
- 422: Validation error (e.g., negative income, invalid date format)
- 401: Not authenticated

---

## GET /api/v1/clients/{client_id}

Retrieve client details by ID.

**Response (200):**
```json
{
  "id": 101,
  "user_id": 42,
  "date_of_birth": "1990-05-15",
  "employment_status": "full_time_employed",
  "annual_income": "95000.00",
  "created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 404: Client not found

---

## POST /api/v1/applications

Submit a new mortgage application for an existing client.

**Request:**
```json
{
  "client_id": 101,
  "broker_id": 5,
  "application_type": "purchase",
  "property_address": "123 Maple Dr, Toronto, ON",
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
  "id": 550,
  "client_id": 101,
  "status": "draft",
  "property_value": "750000.00",
  "requested_loan_amount": "600000.00",
  "created_at": "2026-03-02T14:35:00Z",
  "updated_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- 400: Invalid application type or mortgage type
- 404: Client or Broker not found
- 422: Down payment exceeds purchase price or invalid financial amount

---

## POST /api/v1/applications/{application_id}/co-borrowers

Add a co-borrower to an existing application.

**Request:**
```json
{
  "application_id": 550,
  "sin_encrypted": "aes256_encrypted_string_here",
  "date_of_birth": "1988-08-20",
  "annual_income": "85000.00",
  "relationship_to_primary": "spouse"
}
```

**Response (201):**
```json
{
  "id": 201,
  "application_id": 550,
  "date_of_birth": "1988-08-20",
  "annual_income": "85000.00",
  "created_at": "2026-03-02T14:40:00Z"
}
```

**Errors:**
- 404: Application not found
- 422: Validation error
```

### 2. Module README
**File:** `docs/modules/client_intake.md`

```markdown
# Client Intake & Application Module

## Overview
The Client Intake module is the entry point for the mortgage underwriting system. It manages the lifecycle of client data and initial application submissions. It captures necessary financial and personal identifiers required for downstream underwriting decisions.

## Key Functions

### Client Management
- **Registration:** Securely captures Personally Identifiable Information (PII).
- **Data Storage:** Enforces encryption for SIN and DOB at rest (AES-256).
- **Financial Profiling:** Records income sources, employment history, and credit scores.

### Application Processing
- **Application Creation:** Links clients to brokers and initiates the mortgage request.
- **Property Details:** Captures property specifics required for CMHC insurance eligibility (LTV calculations).
- **Co-borrower Support:** Allows the addition of secondary applicants to the application.

## Usage Examples

### Creating a Client
When creating a client, the `sin_encrypted` field must be pre-encrypted using the utility in `common/security.py`. Raw SIN numbers must never be sent to this endpoint.

```python
from common.security import encrypt_pii

sin_hash = encrypt_pii("123456789")
# sin_hash is then sent in the POST request
```

### Submitting an Application
An application must be linked to a valid `client_id` and `broker_id`. The system validates that the `requested_loan_amount` aligns logically with `property_value` and `down_payment` (LTV checks happen in the underwriting phase, but basic validation occurs here).

## Regulatory Compliance

### PIPEDA
- **Data Minimization:** Only fields relevant to creditworthiness are stored.
- **Encryption:** `sin_encrypted` and `date_of_birth` are stored using AES-256.
- **Logging:** SIN values are never logged. Audit logs reference clients by `client_id` only.

### CMHC
- **Data Collection:** Collects `property_value`, `down_payment`, and `purchase_price` to enable Loan-to-Value (LTV) ratio calculations.
- **Insurance Logic:** While the insurance requirement flag is calculated later, this module provides the necessary inputs (LTV > 80% triggers insurance logic).

### FINTRAC
- **Audit Trail:** All records include `created_at` timestamps. Records are immutable (soft deletes only).
```

### 3. Changelog Updates
**File:** `CHANGELOG.md` (Append to existing)

```markdown
## [2026-03-02]
### Added
- Client Intake & Application: New endpoints for client registration (`POST /api/v1/clients`).
- Client Intake & Application: New endpoints for mortgage application submission (`POST /api/v1/applications`).
- Client Intake & Application: New endpoints for co-borrower management (`POST /api/v1/applications/{id}/co-borrowers`).
- Database Models: Added `clients`, `applications`, and `co_borrowers` tables with audit fields (`created_at`, `updated_at`).

### Changed
- Updated security configuration to support AES-256 field encryption for intake module.
```

### 4. Environment Variables
**File:** `.env.example` (Add or update)

```ini
# Client Intake & Application Configuration
# Note: Standard database and encryption keys are required for this module.

# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:password@localhost/mortgage_db

# Security (PIPEDA Compliance)
# Secret key used for AES-256 encryption of SIN/DOB fields.
# Must be 32 bytes (url-safe base64 encoded recommended)
ENCRYPTION_KEY=your_32_byte_url_safe_base64_encoded_key_here
```