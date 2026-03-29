# Documentation for Client Intake & Application

## 1. API Documentation

**File:** `docs/api/Client Intake & Application.md`

```markdown
# Client Intake & Application API

## POST /api/v1/clients

Create a new client record. This initiates the borrower profile.

**Request:**
```json
{
  "user_id": 42,
  "sin": "123456789",
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
  "sin_encrypted": "aes256_encrypted_hash...",
  "date_of_birth": "1990-05-15",
  "employment_status": "full_time_employed",
  "employer_name": "Acme Corp",
  "years_employed": 5,
  "annual_income": "95000.00",
  "other_income": "5000.00",
  "credit_score": 720,
  "marital_status": "married",
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid SIN format or Date of Birth
- 422: Validation error (e.g., negative income)
- 401: Not authenticated

---

## GET /api/v1/clients/{id}

Retrieve client details by ID. 
*Note: SIN is never returned in clear text.*

**Response (200):**
```json
{
  "id": 101,
  "user_id": 42,
  "sin_hash": "sha256_hash...",
  "date_of_birth": "1990-05-15",
  "annual_income": "95000.00",
  "credit_score": 720,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 404: Client not found

---

## POST /api/v1/applications

Create a new mortgage application for a specific client.

**Request:**
```json
{
  "client_id": 101,
  "broker_id": 5,
  "application_type": "purchase",
  "property_address": "123 Maple Dr, Toronto, ON",
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
  "id": 202,
  "client_id": 101,
  "broker_id": 5,
  "status": "draft",
  "property_value": "800000.00",
  "requested_loan_amount": "600000.00",
  "created_at": "2026-03-02T10:05:00Z",
  "updated_at": "2026-03-02T10:05:00Z"
}
```

**Errors:**
- 400: Invalid financial data (e.g., down payment > purchase price)
- 422: Validation error

---

## POST /api/v1/applications/{id}/co-borrowers

Add a co-borrower to an existing application.

**Request:**
```json
{
  "application_id": 202,
  "sin": "987654321",
  "annual_income": "85000.00",
  "relationship_to_primary": "spouse"
}
```

**Response (201):**
```json
{
  "id": 305,
  "application_id": 202,
  "sin_encrypted": "aes256_encrypted_hash...",
  "annual_income": "85000.00",
  "created_at": "2026-03-02T10:10:00Z"
}
```

---

## POST /api/v1/applications/{id}/submit

Submit the application for underwriting review. Changes status from `draft` to `submitted`.

**Request:**
```json
{}
```

**Response (200):**
```json
{
  "id": 202,
  "status": "submitted",
  "submitted_at": "2026-03-02T10:15:00Z",
  "updated_at": "2026-03-02T10:15:00Z"
}
```

**Errors:**
- 400: Application cannot be submitted (missing required fields)
- 409: Application already submitted
```

## 2. Module README

**File:** `docs/modules/Client Intake & Application.md`

```markdown
# Client Intake & Application Module

## Overview
This module handles the initial collection of borrower and property data. It serves as the entry point for the mortgage underwriting system, ensuring all data required for OSFI B-20 and CMHC calculations is captured securely before the underwriting process begins.

## Key Functions

### Client Management
- **Profile Creation**: Captures personal identification, employment history, and financials.
- **PIPEDA Compliance**: Automatically encrypts SIN and DOB fields using AES-256 at rest. Logs only hashed values for audit trails.

### Application Processing
- **Mortgage Details**: Stores property information, loan amounts, and amortization terms.
- **Draft State**: Applications remain in `draft` status until explicitly submitted, allowing brokers to edit data.
- **Validation**: Enforces basic financial logic (e.g., Down Payment <= Purchase Price).

### Co-borrower Support
- Allows linking additional borrowers to a primary application to support joint income calculations for GDS/TDS.

## Usage Examples

### Creating a New Client
```python
from modules.client_intake.services import ClientService

service = ClientService(db_session)
client = await service.create_client(
    user_id=1,
    sin="123456789",
    annual_income=Decimal("95000.00")
    # ... other fields
)
# client.sin_encrypted is now populated; raw SIN is discarded from memory
```

### Submitting an Application
```python
from modules.client_intake.services import ApplicationService

service = ApplicationService(db_session)
app = await service.submit_application(application_id=202)
# app.status == "submitted"
# app.submitted_at is set to current UTC time
```

## Regulatory Notes
- **FINTRAC**: All client creations and application submissions are logged with `created_at` and `user_id` to maintain an immutable audit trail.
- **Data Minimization**: Only fields necessary for underwriting (income, credit, property value) are stored in the primary intake tables.
```

## 3. Configuration Notes

**File:** `.env.example` (Additions)

```ini
# Client Intake & Application Configuration
# Minimum acceptable credit score for intake validation
MIN_CREDIT_SCORE=600

# Maximum amortization period allowed for new applications (regulatory limit)
MAX_AMORTIZATION_YEARS=25

# Minimum down payment percentage threshold (simple validation)
# Note: Complex tiered calculation happens in underwriting, but basic guardrails here.
MIN_DOWN_PAYMENT_PERCENT=5.0
```

## 4. Changelog

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Client Intake & Application: New endpoints for creating clients and mortgage applications.
- Client Intake & Application: Co-borrower association endpoints.
- Client Intake & Application: Application submission workflow (`draft` -> `submitted`).
- Documentation: API usage guide and module overview for Client Intake.

### Changed
- Updated common/security.py to support SIN hashing for lookup indexes.
- Updated .env.example with intake-specific validation thresholds.
```