```markdown
# Client Intake & Application API

## Overview

The **Client Intake & Application** module handles the initial collection of borrower data and mortgage application details. It serves as the entry point for the underwriting system, ensuring all regulatory data (PII, financials) is captured securely before processing begins.

### Key Features
- **Client Management:** Secure storage of personal and financial identity.
- **Application Creation:** Linking clients to specific mortgage requests and property details.
- **Co-Borrower Support:** Handling secondary applicants (partial implementation based on available context).
- **Regulatory Compliance:**
  - **PIPEDA:** SIN and DOB are encrypted at rest (AES-256). Raw SIN values are never returned in API responses.
  - **FINTRAC:** All records are immutable with strict audit trails (`created_at`).

---

## POST /api/v1/clients

Register a new client in the system.

**Request:**
```json
{
  "user_id": 42,
  "sin_encrypted": "aes256_encrypted_string_here",
  "date_of_birth": "1985-04-12",
  "employment_status": "employed",
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
  "date_of_birth": "1985-04-12",
  "employment_status": "employed",
  "annual_income": "95000.00",
  "credit_score": 720,
  "created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `400`: Invalid financial format (use Decimal strings).
- `422`: Validation error (e.g., `sin_encrypted` format invalid, missing required fields).
- `401`: Not authenticated.

**Security Note:** The `sin_encrypted` field is stored but never exposed in the response payload.

---

## GET /api/v1/clients/{id}

Retrieve client details by ID.

**Response (200):**
```json
{
  "id": 101,
  "user_id": 42,
  "date_of_birth": "1985-04-12",
  "employment_status": "employed",
  "employer_name": "Acme Corp",
  "annual_income": "95000.00",
  "other_income": "5000.00",
  "credit_score": 720,
  "marital_status": "married",
  "created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `404`: Client not found.

---

## POST /api/v1/applications

Create a new mortgage application associated with a client.

**Request:**
```json
{
  "client_id": 101,
  "broker_id": 5,
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
  "id": 550,
  "client_id": 101,
  "broker_id": 5,
  "application_type": "purchase",
  "status": "draft",
  "property_address": "123 Maple St, Toronto, ON",
  "property_value": "750000.00",
  "requested_loan_amount": "600000.00",
  "created_at": "2026-03-02T15:00:00Z",
  "updated_at": "2026-03-02T15:00:00Z",
  "submitted_at": null
}
```

**Errors:**
- `400`: Invalid financial data (e.g., down payment > purchase price).
- `422`: Validation error.
- `404`: Referenced `client_id` or `broker_id` does not exist.

---

## GET /api/v1/applications/{id}

Retrieve a specific mortgage application.

**Response (200):**
```json
{
  "id": 550,
  "client_id": 101,
  "broker_id": 5,
  "application_type": "purchase",
  "status": "submitted",
  "property_value": "750000.00",
  "requested_loan_amount": "600000.00",
  "created_at": "2026-03-02T15:00:00Z",
  "submitted_at": "2026-03-02T15:05:00Z"
}
```

**Errors:**
- `404`: Application not found.

---

## POST /api/v1/applications/{id}/co-borrowers

**WARNING:** Input context for `co_borrowers` model was truncated. The endpoint below is inferred based on standard naming conventions and the `clients` schema structure.

Add a co-borrower to an existing application.

**Request:**
```json
{
  "application_id": 550,
  "sin_encrypted": "aes256_encrypted_string_here",
  "date_of_birth": "1988-08-20",
  "annual_income": "65000.00",
  "relationship_to_primary": "spouse"
}
```

**Response (201):**
```json
{
  "id": 22,
  "application_id": 550,
  "date_of_birth": "1988-08-20",
  "annual_income": "65000.00",
  "created_at": "2026-03-02T15:10:00Z"
}
```

**Errors:**
- `404`: Application not found.
- `400`: Application already submitted (updates restricted).

---

## Configuration Notes

### Environment Variables

Update `.env.example` with the following variables for this module:

```bash
# Client Intake & Application Configuration

# Encryption key for PII (SIN/DOB) - 32 bytes for AES-256
# Generate using: openssl rand -hex 32
PII_ENCRYPTION_KEY=change_me_to_a_32_byte_hex_string

# Minimum acceptable credit score for auto-approval logic (if implemented)
MIN_CREDIT_SCORE=600

# Maximum amortization period allowed (years)
MAX_AMORTIZATION_YEARS=30
```

### Setup Instructions

1.  **Dependencies:** Ensure `cryptography` and `pydantic` are installed via `uv`.
2.  **Migrations:** Run Alembic to create the `clients`, `applications`, and `co_borrowers` tables.
    ```bash
    uv run alembic revision --autogenerate -m "Create client intake tables"
    uv run alembic upgrade head
    ```
3.  **Encryption:** The `common/security.py` module must be configured with the `PII_ENCRYPTION_KEY` before the application starts to handle client data.
```