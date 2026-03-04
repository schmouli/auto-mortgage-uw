```markdown
# FINTRAC Compliance API

## Overview
This module handles the recording and management of FINTRAC (Financial Transactions and Reports Analysis Centre of Canada) compliance data, specifically focusing on client identity verification and the reporting of specific transaction types (Large Cash, Suspicious, Terrorist Property) in adherence with the *Proceeds of Crime (Money Laundering) and Terrorist Financing Act* (PCMLTFA).

### Regulatory Compliance Notes
*   **Immutability:** All records created in this module are immutable. Updates are not permitted to ensure audit trail integrity.
*   **Retention:** All records are retained for a minimum of 5 years from the date of creation.
*   **PIPEDA:** Sensitive Personal Information (PII) such as ID numbers are encrypted at rest (AES-256) and are never returned in API responses or logs.
*   **Thresholds:** Transactions exceeding CAD $10,000.00 must be flagged as Large Cash Transactions.

---

## POST /api/v1/fintrac/verifications

Create a new identity verification record. This endpoint logs the method used to verify a client's identity (in-person, credit file, or dual-process) and assesses risk factors (PEP/HIO).

**Request:**
```json
{
  "application_id": 550,
  "client_id": 101,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_number": "AB1234567", 
  "id_expiry_date": "2029-12-31",
  "id_issuing_province": "ON",
  "is_pep": false,
  "is_hio": false,
  "risk_level": "low"
}
```

**Response (201):**
```json
{
  "id": 987,
  "application_id": 550,
  "client_id": 101,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_expiry_date": "2029-12-31",
  "id_issuing_province": "ON",
  "verified_by": 42,
  "verified_at": "2026-03-02T14:30:00Z",
  "is_pep": false,
  "is_hio": false,
  "risk_level": "low",
  "record_created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Invalid verification method or risk level.
- 404: Application or Client not found.
- 422: Validation error (e.g., invalid date format).

---

## GET /api/v1/fintrac/verifications/{id}

Retrieve a specific verification record by ID.

**Response (200):**
```json
{
  "id": 987,
  "application_id": 550,
  "client_id": 101,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_expiry_date": "2029-12-31",
  "id_issuing_province": "ON",
  "verified_by": 42,
  "verified_at": "2026-03-02T14:30:00Z",
  "is_pep": false,
  "is_hio": false,
  "risk_level": "low",
  "record_created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 401: Not authenticated.
- 404: Verification record not found.

---

## POST /api/v1/fintrac/reports

Create a FINTRAC report. Used for Large Cash Transactions ($10k+), Suspicious Transactions, or Terrorist Property Reports.

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
  "record_created_at": "2026-03-02T15:00:00Z"
}
```

**Errors:**
- 400: Invalid report type or amount below threshold (if applicable).
- 422: Validation error.

---

## GET /api/v1/fintrac/reports/{id}

Retrieve a specific FINTRAC report by ID.

**Response (200):**
```json
{
  "id": 45,
  "application_id": 550,
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": "2026-03-03T09:00:00Z",
  "record_created_at": "2026-03-02T15:00:00Z"
}
```

**Errors:**
- 401: Not authenticated.
- 404: Report not found.
```

```markdown
# FINTRAC Compliance Module Guide

## Overview
The FINTRAC Compliance module is responsible for managing the lifecycle of regulatory data required by the Financial Transactions and Reports Analysis Centre of Canada (FINTRAC). It ensures that the mortgage underwriting system adheres to the *Proceeds of Crime (Money Laundering) and Terrorist Financing Act* (PCMLTFA).

## Key Functions

### 1. Identity Verification
Records the details of client identity verification. The system supports three primary methods defined by FINTRAC regulations:
*   **In-person:** Verification using original, valid documents.
*   **Credit File:** Verification via a Canadian credit bureau.
*   **Dual-process:** Verification using two independent, reliable sources.

**Risk Assessment:**
The module captures Politically Exposed Person (PEP) and Head of an International Organization (HIO) status to determine the client's risk level (Low, Medium, High).

### 2. Transaction Reporting
Automates the creation of mandatory reports:
*   **Large Cash Transaction Reports (LCTR):** Triggered for cash transactions equal to or exceeding $10,000 CAD.
*   **Suspicious Transaction Reports (STR):** Created when there are reasonable grounds to suspect a transaction is related to a money laundering or terrorist financing offence.
*   **Terrorist Property Reports (TPR):** Created when property is owned/controlled by a terrorist or terrorist group.

### 3. Audit & Retention
*   **Immutable Records:** Once a verification or report is created, it cannot be modified or deleted via the API.
*   **Encryption:** All government-issued ID numbers are encrypted using AES-256 before storage.
*   **5-Year Retention:** Data is retained for a minimum of 5 years from the creation date to meet regulatory obligations.

## Usage Examples

### Logging a Client Verification
When an applicant is verified, call the verification endpoint to store the immutable record.

```python
import httpx

async def log_verification(app_id: int, client_id: int):
    payload = {
        "application_id": app_id,
        "client_id": client_id,
        "verification_method": "in_person",
        "id_type": "drivers_license",
        "id_number": "A123-456-789-012", # Will be encrypted immediately
        "id_expiry_date": "2030-01-01",
        "id_issuing_province": "BC",
        "is_pep": False,
        "is_hio": False,
        "risk_level": "low"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post("http://api/v1/fintrac/verifications", json=payload)
        return response.json()
```

### Reporting a Large Cash Transaction
If a client deposits $10,000 or more in cash towards a down payment, an LCTR must be generated.

```python
import httpx
from decimal import Decimal

async def report_large_cash(app_id: int, amount: Decimal):
    if amount >= 10000:
        payload = {
            "application_id": app_id,
            "report_type": "large_cash_transaction",
            "amount": str(amount),
            "currency": "CAD",
            "report_date": "2026-03-02"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post("http://api/v1/fintrac/reports", json=payload)
            return response.json()
```

## Data Privacy
*   **PIPEDA Compliance:** The module strictly follows the Personal Information Protection and Electronic Documents Act.
*   **Data Minimization:** Only data strictly necessary for compliance is collected.
*   **Logging:** ID numbers, SINs, and DOBs are **never** written to application logs (STDOUT/FILE) or included in error messages.
```

```bash
# .env.example Updates

# FINTRAC Compliance Configuration
# Encryption key for ID numbers at rest (AES-256). Must be 32 bytes (url-safe base64 encoded).
FINTRAC_ENCRYPTION_KEY="change_me_to_a_secure_32_byte_key"

# Threshold for Large Cash Transaction Reports in CAD (Default: 10000.00)
FINTRAC_LCTR_THRESHOLD="10000.00"

# Retention period for FINTRAC records in years (Mandatory: 5)
FINTRAC_RETENTION_YEARS="5"
```