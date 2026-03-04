Here is the documentation for the Client Intake & Application module.

### 1. API Documentation
**File:** `docs/api/Client Intake & Application.md`

```markdown
# Client Intake & Application API

This module handles the onboarding of new clients, the creation of mortgage applications, and the management of co-borrowers. It enforces PIPEDA compliance for sensitive data (SIN, DOB) and ensures all financial data is handled using Decimal precision.

## POST /api/v1/clients

Registers a new client in the system.

**Request:**
```json
{
  "user_id": "auth0|1234567890",
  "sin": "123456789",
  "date_of_birth": "1990-01-01",
  "employment_status": "full_time",
  "employer_name": "Acme Corp",
  "years_employed": 5,
  "annual_income": "85000.00",
  "other_income": "5000.00",
  "credit_score": 750,
  "marital_status": "married"
}
```

**Response (201):**
```json
{
  "id": 1,
  "user_id": "auth0|1234567890",
  "employment_status": "full_time",
  "employer_name": "Acme Corp",
  "annual_income": "85000.00",
  "credit_score": 750,
  "marital_status": "married",
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid input data (e.g., malformed SIN).
- 422: Validation error (e.g., negative income).
- 401: Not authenticated.

**Note:** 
- `sin` and `date_of_birth` are encrypted at rest (AES-256) and are never returned in the response body.
- `sin` is stored using SHA-256 hashing for lookup/verification purposes where applicable.

---

## GET /api/v1/clients/{id}

Retrieves a specific client's profile.

**Response (200):**
```json
{
  "id": 1,
  "user_id": "auth0|1234567890",
  "employment_status": "full_time",
  "employer_name": "Acme Corp",
  "annual_income": "85000.00",
  "credit_score": 750,
  "marital_status": "married",
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 404: Client not found.

---

## POST /api/v1/applications

Creates a new mortgage application linked to a specific client.

**Request:**
```json
{
  "client_id": 1,
  "broker_id": 10,
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
  "id": 100,
  "client_id": 1,
  "broker_id": 10,
  "application_type": "purchase",
  "status": "draft",
  "property_address": "123 Maple St, Toronto, ON",
  "property_value": "750000.00",
  "requested_loan_amount": "600000.00",
  "created_at": "2026-03-02T10:05:00Z",
  "updated_at": "2026-03-02T10:05:00Z"
}
```

**Errors:**
- 404: Client or Broker not found.
- 422: Validation error (e.g., LTV exceeds 95%).

---

## GET /api/v1/applications/{id}

Retrieves details of a specific mortgage application.

**Response (200):**
```json
{
  "id": 100,
  "client_id": 1,
  "status": "submitted",
  "property_address": "123 Maple St, Toronto, ON",
  "requested_loan_amount": "600000.00",
  "created_at": "2026-03-02T10:05:00Z",
  "submitted_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 404: Application not found.

---

## POST /api/v1/applications/{id}/co-borrowers

Adds a co-borrower to an existing application.

**Request:**
```json
{
  "application_id": 100,
  "sin": "987654321",
  "date_of_birth": "1988-05-15",
  "annual_income": "95000.00",
  "credit_score": 780
}
```

**Response (201):**
```json
{
  "id": 5,
  "application_id": 100,
  "annual_income": "95000.00",
  "credit_score": 780,
  "created_at": "2026-03-02T10:10:00Z"
}
```

**Errors:**
- 404: Application not found.
- 400: Application already submitted (cannot modify co-borrowers).
- 422: Validation error.

---

## POST /api/v1/applications/{id}/submit

Marks the application as submitted. This action validates that all required fields are present and locks the application from further edits (except by underwriters).

**Request:**
```json
{}
```

**Response (200):**
```json
{
  "id": 100,
  "status": "submitted",
  "submitted_at": "2026-03-02T11:00:00Z",
  "updated_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 400: Application is already submitted or cancelled.
- 422: Missing mandatory data for submission.
```

### 2. Module README
**File:** `docs/modules/Client Intake & Application.md`

```markdown
# Client Intake & Application Module

## Overview
The Client Intake & Application module is responsible for the initial data capture phase of the mortgage underwriting process. It manages the lifecycle of client profiles, mortgage applications, and co-borrower associations.

## Key Functions

### 1. Client Management (`services.py`)
- **Client Creation**: Handles the ingestion of Personally Identifiable Information (PII).
- **PII Encryption**: Automatically encrypts SIN and Date of Birth using AES-256 before storage. Hashes SIN for indexing/lookup to satisfy PIPEDA requirements.
- **Financial Data Validation**: Ensures income and credit scores are valid inputs.

### 2. Application Management (`services.py`)
- **Application Lifecycle**: Manages state transitions (e.g., `draft` -> `submitted`).
- **LTV Calculation**: Validates the Loan-to-Value ratio during intake to ensure it falls within insurable limits (LTV ≤ 95%).
- **Audit Trail**: Maintains immutable timestamps (`created_at`, `updated_at`, `submitted_at`) for FINTRAC compliance.

### 3. Co-Borrower Handling
- Links additional borrowers to an application to support joint mortgage applications.
- Enforces the same encryption standards for co-borrower PII as primary clients.

## Usage Examples

### Creating a Client and Application
```python
from mortgage_underwriting.modules.client_intake.services import ClientService, ApplicationService

# 1. Register Client
client_data = {
    "sin": "123456789",
    "annual_income": Decimal("85000.00"),
    "date_of_birth": "1990-01-01"
    # ... other fields
}
client = await ClientService.create_client(db_session, client_data)

# 2. Create Application
app_data = {
    "client_id": client.id,
    "requested_loan_amount": Decimal("600000.00"),
    "property_value": Decimal("750000.00")
    # ... other fields
}
application = await ApplicationService.create_application(db_session, app_data)

# 3. Submit
await ApplicationService.submit_application(db_session, application.id)
```

## Compliance Notes
- **PIPEDA**: SIN and DOB are never logged or returned in API responses. Access to raw encrypted data requires specific decryption privileges.
- **FINTRAC**: All records are immutable regarding creation timestamps. No physical deletes are performed; soft deletes are used if necessary, retaining the record for 5 years.
```

### 3. Configuration Notes
**File:** `.env.example`

```bash
# ... existing config ...

# Client Intake & Application Configuration
# Minimum acceptable credit score for automatic intake validation
MIN_CREDIT_SCORE=600

# Maximum Loan-to-Value (LTV) ratio allowed for application creation (percentage)
MAX_LTV_RATIO=95.0

# Encryption Key Rotation ID (for audit trails of PII encryption)
PII_ENCRYPTION_KEY_ID=prod_key_v1
```