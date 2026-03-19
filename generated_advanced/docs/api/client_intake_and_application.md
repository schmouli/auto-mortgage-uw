Here is the documentation for the **Client Intake & Application** module.

### 1. API Documentation
**File:** `docs/api/client_intake_application.md`

```markdown
# Client Intake & Application API

This module handles the initial collection of borrower data and mortgage application details. It enforces PIPEDA compliance for PII (SIN/DOB) and ensures financial data is captured using high-precision Decimals.

## POST /api/v1/clients

Register a new client. 
**Security Note:** SIN and DOB are encrypted at rest (AES-256) and are never returned in full in API responses.

**Request:**
```json
{
  "user_id": "auth_12345",
  "sin": "123456789",
  "date_of_birth": "1990-01-01",
  "employment_status": "full_time_employed",
  "employer_name": "Acme Corp",
  "years_employed": 5,
  "annual_income": "95000.00",
  "other_income": "5000.00",
  "credit_score": 750,
  "marital_status": "married"
}
```

**Response (201):**
```json
{
  "id": 1,
  "user_id": "auth_12345",
  "sin_masked": "*****789",
  "employment_status": "full_time_employed",
  "employer_name": "Acme Corp",
  "annual_income": "95000.00",
  "credit_score": 750,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `400`: Invalid input format (e.g., bad date format).
- `422`: Validation error (e.g., credit score out of range, negative income).
- `401`: Not authenticated.

---

## GET /api/v1/clients/{id}

Retrieve client details by ID. PII (SIN, DOB) is excluded from the response.

**Response (200):**
```json
{
  "id": 1,
  "user_id": "auth_12345",
  "employment_status": "full_time_employed",
  "annual_income": "95000.00",
  "credit_score": 750,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `404`: Client not found.

---

## POST /api/v1/applications

Create a new mortgage application linked to a specific client.

**Request:**
```json
{
  "client_id": 1,
  "broker_id": 101,
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
  "id": 501,
  "client_id": 1,
  "broker_id": 101,
  "status": "draft",
  "property_value": "800000.00",
  "requested_loan_amount": "600000.00",
  "created_at": "2026-03-02T11:00:00Z",
  "updated_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- `422`: Validation error (e.g., Down payment > Purchase Price, LTV logic checks).
- `404`: Client or Broker not found.

---

## POST /api/v1/applications/{id}/co-borrowers

Add a co-borrower to an existing application.
**Note:** This endpoint expects a subset of client fields (SIN, DOB, Income) as per the co_borrowers model definition.

**Request:**
```json
{
  "application_id": 501,
  "sin": "987654321",
  "date_of_birth": "1992-05-15",
  "annual_income": "85000.00",
  "relationship_to_primary": "spouse"
}
```

**Response (201):**
```json
{
  "id": 2,
  "application_id": 501,
  "sin_masked": "*****321",
  "annual_income": "85000.00",
  "created_at": "2026-03-02T11:15:00Z"
}
```

---

## PATCH /api/v1/applications/{id}

Update application details or submit the application. Submitting changes the status to `submitted`.

**Request (Submit):**
```json
{
  "status": "submitted"
}
```

**Response (200):**
```json
{
  "id": 501,
  "status": "submitted",
  "submitted_at": "2026-03-02T12:00:00Z",
  "updated_at": "2026-03-02T12:00:00Z"
}
```

**Errors:**
- `400`: Cannot update a submitted application (immutable after submission).
```

### 2. Module README
**File:** `docs/modules/client_intake_module.md`

```markdown
# Client Intake & Application Module

## Overview
The Client Intake module is the entry point for the mortgage underwriting system. It manages the lifecycle of borrower (`clients`) and their specific mortgage requests (`applications`). It strictly enforces data privacy standards (PIPEDA) and financial precision requirements (OSFI B-20).

## Key Entities

### 1. Clients
Stores personally identifiable information (PII) and financial capacity data.
- **PII Handling:** `sin_encrypted` and `date_of_birth` are encrypted using AES-256 via `common/security.py` before storage. They are never logged or returned in API responses.
- **Financials:** All income fields use `Decimal` type to prevent floating-point rounding errors.

### 2. Applications
Represents the mortgage deal linked to a client and a broker.
- **Statuses:** `draft`, `submitted`, `under_review`, `approved`, `rejected`.
- **Audit:** Tracks `created_at`, `updated_at`, and `submitted_at` timestamps to satisfy FINTRAC audit trail requirements.

### 3. Co-Borrowers
Associates additional borrowers to an application. Inherits similar PII and financial validation rules as the primary client.

## Usage Example

### 1. Creating a Client
First, register the primary borrower. The system will automatically hash the SIN for lookups and encrypt the raw value.

```python
from modules.client_intake.services import ClientService
from decimal import Decimal

client_data = {
    "sin": "123456789",
    "annual_income": Decimal("120000.00"),
    # ... other fields
}

client = await ClientService.create_client(client_data)
# client.sin_encrypted is now a binary blob; client.sin_hash is stored for indexing
```

### 2. Initiating an Application
Once the client is created, attach a property and loan request.

```python
app_data = {
    "client_id": client.id,
    "property_value": Decimal("500000.00"),
    "down_payment": Decimal("100000.00"),
    # ... other fields
}

application = await ApplicationService.create_application(app_data)
```

## Compliance Notes
- **PIPEDA:** SIN/DOB fields are strictly access-controlled. Ensure logs never contain raw PII.
- **FINTRAC:** The `created_at` timestamp on `clients` and `applications` establishes the immutable record start time.
- **CMHC:** While insurance calculation happens in the underwriting module, this module provides the `property_value` and `down_payment` required for LTV calculation.
```

### 3. Configuration Notes
**File:** `.env.example` (Append or update)

```bash
# Client Intake Configuration

# Encryption key for PII (SIN, DOB) - Must be 32 bytes (AES-256)
# Generated via: openssl rand -hex 32
PII_ENCRYPTION_KEY=changeme_to_32_byte_hex_key

# Default application status if not provided
DEFAULT_APP_STATUS=draft
```

### 4. Changelog Update
**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Client Intake & Application: New endpoints for creating clients and mortgage applications.
- PII Encryption: Automatic AES-256 encryption for SIN and DOB fields.
- Audit Fields: Added `created_at`, `updated_at`, and `submitted_at` to all intake models.
- Co-borrower Support: Endpoint to add secondary applicants to mortgage applications.

### Changed
- Updated API response structure to mask SIN in all client/co-borrower views.

### Fixed
- N/A
```