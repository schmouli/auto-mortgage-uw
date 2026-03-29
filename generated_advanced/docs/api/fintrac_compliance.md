# FINTRAC Compliance API

## Overview
The FINTRAC Compliance module manages the verification of client identities and the reporting of financial transactions as required by the Proceeds of Crime (Money Laundering) and Terrorist Financing Act (PCMLTFA). It ensures immutable audit trails, PEP (Politically Exposed Person) and HIO (Head of International Organization) screening, and handles the creation of reports for large cash transactions or suspicious activities.

**Key Features:**
- Immutable audit trails for all records (5-year retention).
- Risk-based assessment (Low, Medium, High).
- Automated flagging for transactions > CAD $10,000.
- Encryption of sensitive identity data at rest (AES-256).

---

## POST /api/v1/fintrac/verifications

Create a new identity verification record linked to a mortgage application. This endpoint logs the method of verification and checks PEP/HIO status.

**Request:**
```json
{
  "application_id": 123,
  "client_id": 456,
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_number": "string_encrypted_on_ingest",
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
  "id": 101,
  "application_id": 123,
  "client_id": 456,
  "verification_method": "dual_process",
  "risk_level": "low",
  "verified_by": 1,
  "verified_at": "2026-03-02T14:30:00Z",
  "record_created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `400`: Invalid verification method or ID type.
- `422`: Validation error (e.g., missing required fields, invalid risk_level).
- `401`: Not authenticated.

---

## GET /api/v1/fintrac/verifications/{verification_id}

Retrieve a specific verification record by ID.

**Response (200):**
```json
{
  "id": 101,
  "application_id": 123,
  "client_id": 456,
  "verification_method": "in_person",
  "risk_level": "medium",
  "verified_at": "2026-03-01T09:15:00Z",
  "record_created_at": "2026-03-01T09:15:00Z"
}
```

**Errors:**
- `404`: Verification record not found.

---

## POST /api/v1/fintrac/reports

Create and log a FINTRAC report (Large Cash Transaction, Suspicious Transaction, or Terrorist Property). If the amount exceeds CAD $10,000, the system enforces the `large_cash_transaction` type explicitly.

**Request:**
```json
{
  "application_id": 123,
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
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
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": null,
  "created_at": "2026-03-02T16:45:00Z"
}
```

**Errors:**
- `400`: Invalid report type or currency.
- `422`: Validation error (e.g., amount is not a valid Decimal).
- `401`: Not authenticated.

---

## GET /api/v1/fintrac/reports/{report_id}

Retrieve the status and details of a specific FINTRAC report.

**Response (200):**
```json
{
  "id": 202,
  "application_id": 123,
  "report_type": "suspicious_transaction",
  "amount": "50000.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": "2026-03-03T08:00:00Z",
  "created_at": "2026-03-02T16:45:00Z"
}
```

**Errors:**
- `404`: Report not found.

---

# Module README: FINTRAC Compliance

## Overview
This module implements the core logic for compliance with Canadian FINTRAC regulations within the mortgage underwriting system. It handles two primary data streams: **Identity Verification** and **Transaction Reporting**.

### Regulatory Compliance
*   **Immutable Audit Trail:** All records in `fintrac_verifications` and `fintrac_reports` are immutable. Updates are prohibited; corrections must be made via new entries with a reference to the original record ID.
*   **Data Retention:** Records are retained for a minimum of 5 years from the date of creation (`record_created_at`).
*   **Privacy:** Sensitive data (e.g., `id_number`) is encrypted using AES-256 before storage. Raw values are never returned in API responses or logs.

## Key Functions

### 1. Identity Verification Service
The `FINTRACVerificationService` manages the lifecycle of client identity checks.

*   **Methods:**
    *   `create_verification(...)`: Logs the verification details, performs PEP/HIO checks, and assigns a risk level.
    *   `assess_risk(pep: bool, hio: bool, method: str) -> str`: Algorithmically determines the risk level based on input factors.

### 2. Reporting Service
The `FINTRACReportService` handles the generation of mandatory reports.

*   **Methods:**
    *   `create_report(...)`: Validates the transaction amount. If `amount > 10000` and `currency == 'CAD'`, it ensures the report type is compliant.
    *   `submit_to_fintrac(...)`: Marks the report as submitted to the regulatory body (timestamping `submitted_to_fintrac_at`).

## Usage Examples

### Creating a Verification
```python
from decimal import Decimal
from modules.fintrac.services import FINTRACVerificationService

service = FINTRACVerificationService(db_session)

# Log a dual-process verification
verification = await service.create_verification(
    application_id=1,
    client_id=5,
    verification_method="dual_process",
    id_type="drivers_license",
    id_number="encrypted_payload_here",
    is_pep=False,
    is_hio=False
)
# Returns verification object with risk_level="low"
```

### Logging a Large Cash Transaction
```python
from modules.fintrac.services import FINTRACReportService

service = FINTRACReportService(db_session)

# Automatically flagged as Large Cash Transaction
report = await service.create_report(
    application_id=1,
    report_type="large_cash_transaction",
    amount=Decimal("15000.00"),
    currency="CAD"
)
```

---

# Configuration Notes

## Environment Variables

Create/update `.env.example` for all new config variables:

```bash
# FINTRAC Compliance Configuration
# Encryption key for ID numbers at rest (AES-256)
FINTRAC_ENCRYPTION_KEY=change_me_in_production

# Threshold for Large Cash Transaction Reports (in CAD)
FINTRAC_LARGE_CASH_THRESHOLD=10000.00

# Data retention period in years (FINTRAC requirement: 5 years)
FINTRAC_RETENTION_YEARS=5
```

---

# Changelog Updates

Append to `CHANGELOG.md`:

```markdown
## [2026-03-02]
### Added
- FINTRAC Compliance: New endpoints for identity verification and transaction reporting.
- Immutable audit trail support for `fintrac_verifications` and `fintrac_reports` models.
- PEP/HIO risk assessment logic in `FINTRACVerificationService`.

### Changed
- Updated common/security.py to support AES-256 encryption for FINTRAC ID numbers.

### Fixed
- N/A
```