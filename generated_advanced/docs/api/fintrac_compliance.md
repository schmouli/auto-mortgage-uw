# FINTRAC Compliance API

## Overview

The FINTRAC Compliance module manages regulatory requirements for the Financial Transactions and Reports Analysis Centre of Canada (FINTRAC). It ensures that all financial transaction records maintain an immutable audit trail, identity verification is logged, and specific transaction types (e.g., Large Cash Transactions > $10,000) are flagged and reported.

**Regulatory Compliance:**
*   **FINTRAC:** 5-year retention on all records. Immutable audit trail (`created_at`, `created_by`).
*   **PIPEDA:** Sensitive data (SIN, ID numbers) is encrypted at rest (AES-256) and never returned in API responses.

---

## Endpoints

### POST /api/v1/fintrac/verifications

Logs a new identity verification event for a client. This record is immutable and creates the audit trail required for compliance.

**Request:**
```json
{
  "application_id": 101,
  "client_id": 45,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_number": "A12345678",
  "id_expiry_date": "2029-05-20",
  "id_issuing_province": "ON",
  "is_pep": false,
  "is_hio": false,
  "risk_level": "low"
}
```

**Response (201):**
```json
{
  "id": 5501,
  "application_id": 101,
  "client_id": 45,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_expiry_date": "2029-05-20",
  "id_issuing_province": "ON",
  "verified_by": "user_123",
  "verified_at": "2026-03-02T14:30:00Z",
  "is_pep": false,
  "is_hio": false,
  "risk_level": "low",
  "record_created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
*   `400`: Invalid verification method or risk level.
*   `422`: Validation error (e.g., invalid date format).
*   `401`: Not authenticated.

---

### POST /api/v1/fintrac/reports

Creates a FINTRAC report record. This is used to track Large Cash Transactions, Suspicious Transactions, or Terrorist Property Reports. Transactions > CAD $10,000 must be explicitly flagged.

**Request:**
```json
{
  "application_id": 101,
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02"
}
```

**Response (201):**
```json
{
  "id": 9901,
  "application_id": 101,
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": null,
  "record_created_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
*   `400`: Invalid report type or currency.
*   `422`: Validation error (e.g., amount is not a valid Decimal).
*   `401`: Not authenticated.

---

### GET /api/v1/fintrac/verifications/{id}

Retrieves a specific verification record by ID. Note that PII (ID number) is never returned.

**Response (200):**
```json
{
  "id": 5501,
  "application_id": 101,
  "client_id": 45,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_expiry_date": "2029-05-20",
  "id_issuing_province": "ON",
  "verified_by": "user_123",
  "verified_at": "2026-03-02T14:30:00Z",
  "is_pep": false,
  "is_hio": false,
  "risk_level": "low",
  "record_created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
*   `404`: Verification record not found.
*   `401`: Not authenticated.

---

## Module README

### Purpose
The `fintrac` module provides the data models and business logic necessary to maintain compliance with Canadian anti-money laundering (AML) and counter-terrorist financing (CTF) regulations.

### Key Features
1.  **Identity Verification Logging**: Records the method (In-person, Credit File, Dual Process) and results of client identity checks.
2.  **PEP/HIO Screening**: Flags Politically Exposed Persons (PEP) or Heads of International Organizations (HIO).
3.  **Reporting**: Tracks the lifecycle of mandatory reports (LCTR, STR, TPR).
4.  **Immutable Audit**: All records are timestamped at creation and never modified, ensuring data integrity for the 5-year retention period.

### Data Models
*   **fintrac_verifications**: Stores the encrypted ID number and verification metadata.
*   **fintrac_reports**: Stores transaction details exceeding reporting thresholds or flagged as suspicious.

### Usage Example (Service Layer)
```python
from modules.fintrac.services import FintracService
from decimal import Decimal

async def log_large_cash(app_id: int):
    service = FintracService(db_session)
    # Automatically flags > 10k CAD
    report = await service.create_report(
        application_id=app_id,
        report_type="large_cash_transaction",
        amount=Decimal("12000.00"),
        currency="CAD"
    )
    return report
```

---

## Configuration Notes

### Environment Variables

Ensure the following variables are set in your `.env` file to support encryption and audit logging:

```bash
# FINTRAC Module Configuration
# Algorithm used for PII encryption (ID numbers)
FINTRAC_ENCRYPTION_ALGORITHM=AES-256-GCM

# Key management URI or reference (KMS/Secrets Manager)
# NEVER store the raw key in .env
FINTRAC_ENCRYPTION_KEY_URI=aws:kms:ca-central-1:key/12345678-1234-1234-1234-123456789012

# Threshold for Large Cash Transaction Reporting (CAD)
FINTRAC_LCTR_THRESHOLD=10000.00
```

### Security Notes
*   **Encryption**: `id_number` is encrypted using `common.security.encrypt_pii()` before storage.
*   **Logging**: The `id_number` and `sin` fields are strictly excluded from structlog output. Only the `client_id` and `application_id` are logged for traceability.