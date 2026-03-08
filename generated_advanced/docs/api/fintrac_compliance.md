Here is the documentation for the **FINTRAC Compliance** module.

### 1. API Documentation
**File:** `docs/api/FINTRAC Compliance.md`

```markdown
# FINTRAC Compliance API

This module handles the recording and management of FINTRAC-related data, including client identity verifications and the logging of reportable transactions (Large Cash, Suspicious, Terrorist Property).

## POST /api/v1/fintrac/verifications

Create a new identity verification record for a client. This action logs the verification method and securely stores identification details.

**Request:**
```json
{
  "application_id": 45,
  "client_id": 102,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_number": "string_value_to_be_encrypted",
  "id_expiry_date": "2029-12-31",
  "id_issuing_province": "ON",
  "verified_by": 5,
  "is_pep": false,
  "is_hio": false
}
```

**Response (201):**
```json
{
  "id": 987,
  "application_id": 45,
  "client_id": 102,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_number_encrypted": null,
  "id_expiry_date": "2029-12-31",
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
- 400: Invalid verification method or ID type.
- 422: Validation error (e.g., missing required fields).
- 401: Not authenticated.
- 403: Insufficient permissions to perform verification.

---

## GET /api/v1/fintrac/verifications/{id}

Retrieve a specific identity verification record by ID.

**Response (200):**
```json
{
  "id": 987,
  "application_id": 45,
  "client_id": 102,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_expiry_date": "2029-12-31",
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
- 404: Verification record not found.

---

## POST /api/v1/fintrac/reports

Log a FINTRAC reportable event (e.g., Large Cash Transaction). This creates an immutable record within the system. Transactions > $10,000 CAD must be flagged explicitly.

**Request:**
```json
{
  "application_id": 45,
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02"
}
```

**Response (201):**
```json
{
  "id": 101,
  "application_id": 45,
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": null,
  "created_at": "2026-03-02T14:35:00Z",
  "created_by": 5
}
```

**Errors:**
- 400: Invalid report type or amount format.
- 422: Validation error.

---

## GET /api/v1/fintrac/reports/{id}

Retrieve details of a specific FINTRAC report.

**Response (200):**
```json
{
  "id": 101,
  "application_id": 45,
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": "2026-03-03T09:00:00Z",
  "created_at": "2026-03-02T14:35:00Z",
  "created_by": 5
}
```

**Errors:**
- 404: Report not found.
```

### 2. Module README
**File:** `docs/modules/FINTRAC Compliance.md`

```markdown
# FINTRAC Compliance Module

## Overview
The FINTRAC Compliance module is responsible for managing regulatory requirements related to the Financial Transactions and Reports Analysis Centre of Canada (FINTRAC). It ensures that the mortgage underwriting system maintains an immutable audit trail for identity verification and reportable financial transactions.

## Key Features
- **Identity Verification:** Records client verification methods (In-person, Credit File, Dual Process) and securely encrypts personally identifiable information (PII) such as ID numbers.
- **Risk Assessment:** Tracks Politically Exposed Persons (PEP) and Heads of International Organizations (HIO) status to determine client risk levels.
- **Transaction Reporting:** Logs Large Cash Transactions (LCTR), Suspicious Transactions (STR), and Terrorist Property Reports (TPR).
- **Data Retention:** Ensures all records are retained for a minimum of 5 years and are immutable (never deleted or modified).

## Usage Example

### Creating a Verification
To verify a client's identity as part of the underwriting process:

```python
from modules.fintrac.services import FintracService
from decimal import Decimal

async with get_async_session() as db:
    service = FintracService(db)
    
    verification = await service.create_verification(
        application_id=1,
        client_id=100,
        verification_method="dual_process",
        id_type="drivers_license",
        id_number="A123456789", # Will be encrypted via common/security.py
        id_expiry_date="2030-01-01",
        id_issuing_province="BC",
        verified_by=5, # User ID
        is_pep=False,
        is_hio=False
    )
    print(f"Verification ID: {verification.id}, Risk Level: {verification.risk_level}")
```

### Logging a Large Cash Transaction
If a client receives a cash deposit greater than $10,000 CAD:

```python
from modules.fintrac.services import FintracService

async with get_async_session() as db:
    service = FintracService(db)
    
    report = await service.log_report(
        application_id=1,
        report_type="large_cash_transaction",
        amount=Decimal("15000.00"),
        currency="CAD",
        report_date="2026-03-02",
        created_by=5
    )
    print(f"Report logged: {report.id}")
```

## Security Notes
- **Encryption:** All ID numbers are encrypted at rest using AES-256 before storage. The plain text value is never returned in API responses.
- **Logging:** Verification events and report creations are logged with correlation IDs for auditability.
```

### 3. Configuration Notes
**File:** `docs/configuration/FINTRAC Compliance.md`

```markdown
# FINTRAC Compliance Configuration

## Environment Variables

The following environment variables must be configured in `.env` to support the FINTRAC module's encryption and compliance features.

### Encryption
- `FINTRAC_ENCRYPTION_KEY` (Required): A 32-byte URL-safe base64-encoded key used for AES-256 encryption of ID numbers. 
  - *Note:* This key must be managed securely (e.g., AWS KMS, Vault). Do not commit to version control.

### Thresholds
- `FINTRAC_LARGE_CASH_THRESHOLD` (Optional): Default: `10000.00`. The threshold in CAD for triggering Large Cash Transaction reporting logic.
```

### 4. Changelog Update
**Append to:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- FINTRAC Compliance: New endpoints for identity verification and transaction reporting.
- Encryption support for client ID numbers (AES-256).
- Immutable audit trail support for FINTRAC records (5-year retention).
- PIPEDA compliance updates for ID data handling in the FINTRAC module.

### Changed
- Updated database models to include `fintrac_verifications` and `fintrac_reports`.
```

### 5. Environment Variables Update
**Append to:** `.env.example`

```bash
# FINTRAC Compliance Configuration
# Generate a secure key using: python -c "import secrets; print(secrets.token_urlsafe(32))"
FINTRAC_ENCRYPTION_KEY=change_me_to_a_secure_32_byte_key
FINTRAC_LARGE_CASH_THRESHOLD=10000.00
```