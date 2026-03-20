```markdown
# FINTRAC Compliance API

## POST /api/v1/fintrac/verifications

Create a new identity verification record. This endpoint logs the verification method and checks PEP (Politically Exposed Person) and HIO (Head of International Organization) status. Per PIPEDA, the ID number is encrypted at rest and never returned in the response.

**Request:**
```json
{
  "application_id": "uuid-string",
  "client_id": "uuid-string",
  "verification_method": "dual_process",
  "id_type": "passport",
  "id_number": "string",
  "id_expiry_date": "2028-12-31",
  "id_issuing_province": "ON",
  "verified_by": "user-id-uuid",
  "is_pep": false,
  "is_hio": false,
  "risk_level": "low"
}
```

**Response (201):**
```json
{
  "id": "uuid-string",
  "application_id": "uuid-string",
  "client_id": "uuid-string",
  "verification_method": "dual_process",
  "risk_level": "low",
  "is_pep": false,
  "is_hio": false,
  "verified_at": "2026-03-02T14:30:00Z",
  "record_created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Invalid verification method or risk level
- 422: Validation error (e.g., invalid ID format, missing fields)
- 401: Not authenticated

---

## POST /api/v1/fintrac/reports

Create and submit a FINTRAC report (Large Cash Transaction, Suspicious Transaction, or Terrorist Property). Records are immutable and retained for 5 years per regulatory requirements.

**Request:**
```json
{
  "application_id": "uuid-string",
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02"
}
```

**Response (201):**
```json
{
  "id": "uuid-string",
  "application_id": "uuid-string",
  "report_type": "large_cash_transaction",
  "amount": "12500.00",
  "currency": "CAD",
  "report_date": "2026-03-02",
  "submitted_to_fintrac_at": "2026-03-02T14:35:00Z",
  "record_created_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- 400: Invalid report type or amount (must be > 10,000.00 for Large Cash Transaction)
- 422: Validation error
- 401: Not authenticated

---

## GET /api/v1/fintrac/reports/{report_id}

Retrieve details of a specific FINTRAC report.

**Response (200):**
```json
{
  "id": "uuid-string",
  "application_id": "uuid-string",
  "report_type": "suspicious_transaction",
  "amount": "50000.00",
  "currency": "CAD",
  "report_date": "2026-03-01",
  "submitted_to_fintrac_at": "2026-03-01T09:00:00Z",
  "record_created_at": "2026-03-01T09:00:00Z"
}
```

**Errors:**
- 404: Report not found
- 401: Not authenticated
```

```markdown
# FINTRAC Compliance Module

## Overview
The FINTRAC Compliance module handles the mandatory logging and reporting requirements for the Canadian mortgage underwriting system. It ensures that all identity verifications and financial transactions meet the standards set by the Financial Transactions and Reports Analysis Centre of Canada (FINTRAC).

## Key Functions

### 1. Identity Verification (`fintrac_verifications`)
- **Purpose:** Record the method used to verify client identity (In-person, Credit File, or Dual Process).
- **Features:**
  - Encrypts sensitive identification numbers (AES-256) at rest.
  - Flags Politically Exposed Persons (PEP) and Heads of International Organizations (HIO).
  - Assigns a risk level (Low, Medium, High) based on verification results.
  - Immutable audit trail (`record_created_at`, `verified_by`).

### 2. Reporting (`fintrac_reports`)
- **Purpose:** Generate reports for specific transaction types.
- **Report Types:**
  - `large_cash_transaction`: For cash amounts > CAD $10,000.
  - `suspicious_transaction`: For activities suspected of being related to money laundering or terrorist financing.
  - `terrorist_property`: For property owned/controlled by listed terrorists.
- **Features:**
  - Automatic timestamping of submission to FINTRAC.
  - Enforces 5-year retention policy on all records.

## Regulatory Compliance
- **FINTRAC:** All records are immutable. `record_created_at` is set once and never modified. PII (SIN, ID Numbers) is encrypted and excluded from logs.
- **PIPEDA:** Data minimization is enforced; only fields required for underwriting are stored.

## Usage Examples

### Creating a Verification
```python
import httpx

async def log_verification(app_id: str, client_id: str):
    async with httpx.AsyncClient() as client:
        payload = {
            "application_id": app_id,
            "client_id": client_id,
            "verification_method": "dual_process",
            "id_type": "drivers_license",
            "id_number": "A123-456-789", # Will be encrypted
            "id_expiry_date": "2029-01-01",
            "id_issuing_province": "BC",
            "verified_by": "admin-uuid",
            "is_pep": False,
            "is_hio": False,
            "risk_level": "low"
        }
        response = await client.post("http://api/v1/fintrac/verifications", json=payload)
        return response.json()
```

### Submitting a Large Cash Transaction Report
```python
async def submit_cash_report(app_id: str, amount: Decimal):
    if amount <= 10000:
        raise ValueError("Amount must exceed $10,000 for this report type")
        
    async with httpx.AsyncClient() as client:
        payload = {
            "application_id": app_id,
            "report_type": "large_cash_transaction",
            "amount": str(amount),
            "currency": "CAD",
            "report_date": datetime.utcnow().date().isoformat()
        }
        response = await client.post("http://api/v1/fintrac/reports", json=payload)
        return response.json()
```
```

```markdown
## [2026-03-02]
### Added
- FINTRAC Compliance: New endpoints for identity verification logging and regulatory reporting.
- `POST /api/v1/fintrac/verifications`: Logs client identity checks with PEP/HIO screening.
- `POST /api/v1/fintrac/reports`: Submits Large Cash, Suspicious, or Terrorist Property reports.
- `GET /api/v1/fintrac/reports/{id}`: Retrieves specific report details.
- Implemented AES-256 encryption for ID numbers in `fintrac_verifications` model.
- Enforced 5-year retention logic for all FINTRAC related records.

### Changed
- Updated security configuration to support FINTRAC PII encryption fields.

### Fixed
- N/A
```

```ini
# FINTRAC Compliance Configuration
# Retention period for FINTRAC records in years (Mandatory: 5)
FINTRAC_RETENTION_YEARS=5

# Threshold for Large Cash Transaction Reports in CAD
FINTRAC_LARGE_CASH_THRESHOLD=10000.00

# Encryption key reference for ID number fields (Managed by common/security.py)
# FINTRAC_ENCRYPTION_KEY_ID=fintrac_prod_key
```