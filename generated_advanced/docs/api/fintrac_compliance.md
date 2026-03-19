Here is the documentation for the **FINTRAC Compliance** module, generated according to the project conventions and regulatory requirements.

---

# 1. API Documentation

**File:** `docs/api/fintrac_compliance.md`

```markdown
# FINTRAC Compliance API

## POST /api/v1/fintrac/verifications

Creates a new identity verification record. This endpoint logs the method used to verify the client identity and assesses risk factors (PEP/HIO). Per FINTRAC requirements, all records are immutable and retained for 5 years.

**Request:**
```json
{
  "application_id": 123,
  "client_id": 456,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_number": "string",
  "id_expiry_date": "2029-03-02",
  "id_issuing_province": "ON",
  "verified_by": 789,
  "is_pep": false,
  "is_hio": false
}
```

**Response (201):**
```json
{
  "id": 101,
  "application_id": 123,
  "client_id": 456,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_expiry_date": "2029-03-02",
  "id_issuing_province": "ON",
  "risk_level": "low",
  "verified_at": "2026-03-02T14:30:00Z",
  "record_created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Invalid verification method or ID type.
- 422: Validation error (e.g., expired ID provided).
- 401: Not authenticated.

---

## POST /api/v1/fintrac/reports

Creates a FINTRAC report record (Large Cash Transaction, Suspicious Transaction, or Terrorist Property). Transactions > $10,000 CAD automatically trigger specific logging requirements.

**Request:**
```json
{
  "application_id": 123,
  "report_type": "large_cash_transaction",
  "amount": "15000.00",
  "currency": "CAD",
  "report_date": "2026-03-02"
}
```

**Response (201):**
```json
{
  "id": 202,
  "application_id": 123,
  "report_type": "large_cash_transaction",
  "amount": "15000.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": null,
  "created_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- 400: Invalid report type or amount.
- 422: Validation error.
- 401: Not authenticated.

---

## GET /api/v1/fintrac/reports/{id}

Retrieves details of a specific FINTRAC report by ID.

**Response (200):**
```json
{
  "id": 202,
  "application_id": 123,
  "report_type": "large_cash_transaction",
  "amount": "15000.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": "2026-03-02T15:00:00Z",
  "created_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- 404: Report not found.
- 401: Not authenticated.
```

---

# 2. Module README

**File:** `docs/modules/fintrac_compliance.md`

```markdown
# FINTRAC Compliance Module

## Overview
The FINTRAC Compliance module manages the tracking and reporting requirements mandated by the Financial Transactions and Reports Analysis Centre of Canada (FINTRAC). It ensures that the mortgage underwriting system maintains an immutable audit trail for identity verification and financial transactions.

## Key Functions

### 1. Identity Verification (`fintrac_verifications`)
Handles the logging of client identity verification processes.
- **Verification Methods:** Supports `in_person`, `credit_file`, and `dual_process` methods.
- **Risk Assessment:** Automatically assigns a `risk_level` (low, medium, high) based on PEP (Politically Exposed Person) or HIO (Head of International Organization) status.
- **Data Security:** ID numbers are encrypted at rest using AES-256 (via `common/security.py`) and never exposed in logs or API responses.

### 2. Transaction Reporting (`fintrac_reports`)
Manages the lifecycle of mandatory reports.
- **Report Types:**
  - `large_cash_transaction`: For cash amounts > $10,000 CAD.
  - `suspicious_transaction`: For activities suspected of being related to money laundering or terrorist financing.
  - `terrorist_property`: For property owned/controlled by listed terrorists.
- **Audit Trail:** Tracks `created_at` timestamps and ensures records are never modified or deleted (5-year retention).

## Usage Example

### Creating a Verification
When a client provides identification, the underwriting service calls the verification endpoint to log the event.

```python
from modules.fintrac_compliance.schemas import FintracVerificationCreate

verification_data = FintracVerificationCreate(
    application_id=101,
    client_id=202,
    verification_method="dual_process",
    id_type="drivers_license",
    id_number="A123-456-789", # Will be encrypted by service layer
    id_expiry_date="2030-01-01",
    id_issuing_province="BC",
    verified_by=1, # User ID of underwriter
    is_pep=False,
    is_hio=False
)

# Call service to persist
await fintrac_service.create_verification(verification_data)
```

### Reporting a Large Cash Transaction
If a client brings > $10k CAD to closing, a report must be generated.

```python
from modules.fintrac_compliance.schemas import FintracReportCreate

report_data = FintracReportCreate(
    application_id=101,
    report_type="large_cash_transaction",
    amount=Decimal("12000.00"),
    currency="CAD",
    report_date=date.today()
)

await fintrac_service.create_report(report_data)
```

## Regulatory Notes
- **Retention:** All records in this module are subject to a mandatory 5-year retention policy.
- **Immutability:** Updates to `fintrac_verifications` and `fintrac_reports` are strictly prohibited. Corrections must be made via new supplementary records.
- **PIPEDA Compliance:** `id_number_encrypted` is stored using AES-256. Hashes (SHA-256) are used for lookups where necessary.
```

---

# 3. Configuration Notes

**File:** `.env.example`

```bash
# FINTRAC Compliance Configuration
# Encryption key for ID numbers at rest (AES-256)
# Must be 32 bytes (64 hex chars) for Fernet-compatible encryption
FINTRAC_ENCRYPTION_KEY=generate_new_key_using_openssl_or_python_secrets

# API endpoint for external FINTRAC submission (if applicable)
# Leave empty if submission is handled manually via batch export
FINTRAC_SUBMISSION_URL=https://api.fintrac-ca.example.com/submit

# Threshold for Large Cash Transaction Reports (CAD)
FINTRAC_LCT_THRESHOLD=10000.00

# Mandatory retention period in years (Regulatory requirement)
FINTRAC_RETENTION_YEARS=5
```