```markdown
# Client Intake & Application Module

## Overview
The Client Intake & Application module handles the initial collection of borrower data, property details, and the creation of mortgage applications. It serves as the entry point for the underwriting workflow, ensuring all necessary data is captured securely and validated against regulatory standards before processing.

### Key Functions
- **Client Management**: Secure storage of personal and financial identity information.
- **Application Creation**: Linking clients to properties and defining loan terms.
- **Co-borrower Support**: Adding additional borrowers to an application.
- **Compliance Validation**: Enforcing data encryption (PIPEDA) and audit trails (FINTRAC).

### Regulatory Compliance
- **PIPEDA**: SIN and DOB are encrypted at rest (AES-256) and never exposed in API responses or logs. SINs are hashed (SHA256) for indexing/lookup.
- **FINTRAC**: All records include immutable audit trails (`created_at`). Identity verification events are logged.
- **CMHC**: LTV (Loan-to-Value) is calculated upon application creation to determine insurance eligibility (LTV > 80%).

## Configuration Notes

### Environment Variables
Ensure the following variables are set in your `.env` file to support the encryption and audit features of this module.

```bash
# Security & Encryption (PIPEDA Compliance)
# Key used for AES-256 encryption of PII (SIN, DOB). Must be 32 bytes (URL-safe base64 encoded).
PII_ENCRYPTION_KEY=your_base64_encoded_32_byte_key_here

# Security & Hashing
# Salt used for SIN hashing (SHA256) for lookups.
SIN_HASH_SALT=your_random_salt_string

# Application Configuration
# Default number of years for amortization if not specified
DEFAULT_AMORTIZATION_YEARS=25
```

---

## API Documentation

### Clients

#### POST /api/v1/clients
Registers a new client in the system. This endpoint captures sensitive Personally Identifiable Information (PII).

**Request:**
```json
{
  "user_id": "auth_12345",
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
  "user_id": "auth_12345",
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
> **Note:** `sin` and `date_of_birth` are never returned in the response.

**Errors:**
- `400`: Invalid SIN format or DOB.
- `422`: Validation error (e.g., negative income).
- `401`: Not authenticated.

---

#### GET /api/v1/clients/{id}
Retrieves a client's profile by ID.

**Response (200):**
```json
{
  "id": 101,
  "user_id": "auth_12345",
  "employment_status": "full_time_employed",
  "annual_income": "95000.00",
  "credit_score": 720,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `404`: Client not found.

---

### Applications

#### POST /api/v1/applications
Creates a new mortgage application associated with a specific client and broker. Automatically calculates LTV.

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
  "application_type": "purchase",
  "status": "draft",
  "property_address": "123 Maple Dr, Toronto, ON",
  "property_value": "800000.00",
  "requested_loan_amount": "600000.00",
  "ltv_ratio": "75.00",
  "insurance_required": false,
  "created_at": "2026-03-02T10:05:00Z",
  "updated_at": "2026-03-02T10:05:00Z"
}
```

**Errors:**
- `400`: Invalid LTV calculation or down payment < 5%.
- `404`: Client or Broker not found.
- `422`: Validation error.

---

#### GET /api/v1/applications/{id}
Retrieves details of a specific mortgage application.

**Response (200):**
```json
{
  "id": 202,
  "client_id": 101,
  "status": "submitted",
  "property_address": "123 Maple Dr, Toronto, ON",
  "requested_loan_amount": "600000.00",
  "ltv_ratio": "75.00",
  "insurance_required": false,
  "submitted_at": "2026-03-02T11:00:00Z",
  "updated_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- `404`: Application not found.

---

### Co-borrowers

#### POST /api/v1/applications/{id}/co-borrowers
Adds a co-borrower to an existing application.

**Request:**
```json
{
  "sin": "987654321",
  "date_of_birth": "1988-08-20",
  "annual_income": "85000.00",
  "credit_score": 700,
  "relationship_to_primary": "spouse"
}
```

**Response (201):**
```json
{
  "id": 305,
  "application_id": 202,
  "annual_income": "85000.00",
  "credit_score": 700,
  "relationship_to_primary": "spouse",
  "created_at": "2026-03-02T10:10:00Z"
}
```

**Errors:**
- `404`: Application not found.
- `400`: Application already submitted (cannot modify).
```