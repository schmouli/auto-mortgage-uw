Here is the documentation for the **FINTRAC Compliance** module.

---

# File: `docs/api/fintrac_compliance.md`

# FINTRAC Compliance API

This module handles the regulatory requirements for the Financial Transactions and Reports Analysis Centre of Canada (FINTRAC), including identity verification logging and the reporting of specific transaction types.

## POST /api/v1/fintrac/verifications

Log a client identity verification. This creates an immutable record of the due diligence performed.

**Request:**
```json
{
  "application_id": 550,
  "client_id": 102,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_number": "string", 
  "id_expiry_date": "2029-05-20",
  "id_issuing_province": "ON",
  "verified_by": 5,
  "is_pep": false,
  "is_hio": false,
  "risk_level": "low"
}
```
*\*Note: The `id_number` is encrypted at rest by the service layer before storage per PIPEDA requirements.*

**Response (201):**
```json
{
  "id": 987,
  "application_id": 550,
  "client_id": 102,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_expiry_date": "2029-05-20",
  "id_issuing_province": "ON",
  "verified_by": 5,
  "verified_at": "2026-03-02T14:30:00Z",
  "is_pep": false,
  "is_hio": false,
  "risk_level": "low",
  "record_created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `400`: Invalid verification method or risk level.
- `401`: Not authenticated.
- `403`: User lacks permission to perform verification.
- `422`: Validation error (e.g., invalid date format, missing required fields).

---

## POST /api/v1/fintrac/reports

Create a FINTRAC report for specific transaction types (Large Cash, Suspicious, or Terrorist Property).

**Request:**
```json
{
  "application_id": 550,
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02"
}
```

**Response (201):**
```json
{
  "id": 45,
  "application_id": 550,
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": null,
  "record_created_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- `400`: Invalid report type or currency.
- `401`: Not authenticated.
- `422`: Validation error (e.g., amount must be positive Decimal).

---

## GET /api/v1/fintrac/verifications/{verification_id}

Retrieve a specific verification record by ID.

**Response (200):**
```json
{
  "id": 987,
  "application_id": 550,
  "client_id": 102,
  "verification_method": "credit_file",
  "risk_level": "medium",
  "verified_at": "2026-03-01T10:00:00Z",
  "record_created_at": "2026-03-01T10:00:00Z"
}
```

**Errors:**
- `401`: Not authenticated.
- `404`: Verification record not found.

---

## GET /api/v1/fintrac/reports/{report_id}

Retrieve a specific FINTRAC report by ID.

**Response (200):**
```json
{
  "id": 45,
  "application_id": 550,
  "report_type": "suspicious_transaction",
  "amount": "50000.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": "2026-03-02T15:00:00Z",
  "record_created_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- `401`: Not authenticated.
- `404`: Report not found.

---

# File: `docs/modules/fintrac_compliance.md`

# FINTRAC Compliance Module

## Overview
The FINTRAC Compliance module manages the Canadian anti-money laundering (AML) and counter-terrorist financing (CTF) regulatory obligations within the mortgage underwriting system. It ensures that all client identifications are verified, logged, and retained, and that specific financial transactions are reported as required by law.

## Key Functions

### 1. Identity Verification Logging
Records the method used to verify a client's identity (In-Person, Credit File, or Dual Process). It captures the risk assessment of the client, including Politically Exposed Persons (PEP) and Head of International Organization (HIO) status.

*   **Retention:** All records are retained for a minimum of 5 years from the date of creation.
*   **Security:** Identification numbers are encrypted at rest using AES-256.

### 2. Transaction Reporting
Automates the creation of reports for:
*   **Large Cash Transactions (LCT):** Receipt of cash equal to or greater than $10,000 CAD.
*   **Suspicious Transactions (STR):** Transactions where there are reasonable grounds to suspect they are related to a money laundering or terrorist activity financing offence.
*   **Terrorist Property Reports (TPR):** Property owned/controlled by a listed terrorist entity.

## Usage Examples

### Creating a Verification
When a client onboards, the system must record the verification attempt.

```python
# Pseudo-code example
await fintrac_service.create_verification(
    application_id=101,
    client_id=55,
    verification_method="dual_process",
    id_type="drivers_license",
    id_number="A123-456-789", # Service layer encrypts this
    is_pep=False,
    is_hio=False,
    risk_level="low"
)
```

### Reporting a Large Cash Transaction
If a mortgage payout or down payment involves cash > $10k, a report must be generated.

```python
# Pseudo-code example
await fintrac_service.create_report(
    application_id=101,
    report_type="large_cash_transaction",
    amount=Decimal("15000.00"),
    currency="CAD"
)
```

---

# File: `.env.example`

```bash
# FINTRAC Compliance Configuration

# URL endpoint for external FINTRAC reporting submission (if applicable)
FINTRAC_SUBMISSION_URL=https://api.fintrac-canafe.gc.ca/v1/submit

# Number of years to retain FINTRAC records before archival/deletion (Regulatory minimum is 5)
FINTRAC_RETENTION_YEARS=5
```

---

# File: `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- FINTRAC Compliance: New endpoints for logging identity verifications and generating regulatory reports.
- FINTRAC Compliance: Added immutable audit trail support (`record_created_at`) for all compliance records.
- FINTRAC Compliance: Implemented encryption at rest for client identification numbers.
```