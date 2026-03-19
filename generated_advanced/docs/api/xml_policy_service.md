Here is the documentation for the XML Policy Service module, structured according to the project conventions.

### 1. API Documentation
**File:** `docs/api/xml_policy_service.md`

```markdown
# XML Policy Service API

This module handles the ingestion of MISMO 3.0 aligned XML policy files from lenders and provides endpoints to evaluate mortgage applications against these specific lender guidelines.

## POST /api/v1/xml-policy/upload

Uploads and parses a new Lender XML policy file.

**Request (multipart/form-data):**
- `file`: The XML policy file (MISMO 3.0 format).
- `lender_id`: Unique identifier for the lender (string).

**Response (201):**
```json
{
  "id": "uuid-of-policy-record",
  "lender_id": "lender_001",
  "version": "1.0",
  "created_at": "2026-03-02T14:30:00Z",
  "status": "active"
}
```

**Errors:**
- 400: Invalid XML format or missing required fields.
- 422: Validation error (XML structure does not match LenderPolicy schema).
- 401: Not authenticated.

---

## GET /api/v1/xml-policy/{lender_id}

Retrieves the currently active policy configuration for a specific lender.

**Parameters:**
- `lender_id` (path): The unique identifier of the lender.

**Response (200):**
```json
{
  "lender_id": "lender_001",
  "version": "1.0",
  "ltv": {
    "max_insured": "95.00",
    "max_conventional": "80.00"
  },
  "gds": {
    "max": "39"
  },
  "tds": {
    "max": "44"
  },
  "credit_score": {
    "min": 620
  },
  "amortization_max": {
    "insured": "25",
    "conventional": "30"
  },
  "property_types": {
    "allowed": ["single-family", "condo", "townhouse"],
    "excluded": ["rooming-house"]
  }
}
```

**Errors:**
- 404: Policy not found for lender_id.

---

## POST /api/v1/xml-policy/{lender_id}/evaluate

Evaluates a mortgage application scenario against the specific lender's policy XML.

**Request:**
```json
{
  "application_data": {
    "ltv": "90.00",
    "gds": "35.00",
    "tds": "42.00",
    "credit_score": 700,
    "amortization_years": "25",
    "property_type": "condo",
    "is_insured": true
  }
}
```

**Response (200):**
```json
{
  "decision": "pass",
  "lender_id": "lender_001",
  "evaluated_at": "2026-03-02T14:35:00Z",
  "details": {
    "ltv_check": "pass",
    "gds_check": "pass",
    "tds_check": "pass",
    "credit_check": "pass",
    "amortization_check": "pass",
    "property_type_check": "pass"
  }
}
```

**Errors:**
- 400: Invalid input data (e.g., LTV > 100).
- 404: Policy not found for lender_id.
- 422: Validation error.

---
```

### 2. Module README
**File:** `docs/modules/xml_policy_service.md`

```markdown
# XML Policy Service Module

## Overview
The XML Policy Service is responsible for externalizing business logic regarding lender-specific underwriting criteria. Instead of hardcoding limits (e.g., Max LTV) into the application code, this service parses MISMO 3.0 aligned XML files uploaded by administrators.

It ensures that the Decision Engine can dynamically adapt to different lender appetites without requiring a code deployment.

## Key Functions
1.  **XML Parsing & Validation**: Uses `lxml` or `xmltodict` to parse incoming XML streams and validates them against a strict Pydantic schema (`LenderPolicy`).
2.  **Policy Storage**: Stores parsed policies in PostgreSQL. Historical versions are maintained for audit trails (FINTRAC compliance).
3.  **Evaluation Engine**: Takes application inputs (LTV, GDS, TDS, etc.) and compares them against the stored policy thresholds to return a Pass/Fail result.

## Usage Example

### Uploading a Policy
An administrator uploads a new XML file for "Lender A". The service validates that the XML contains required fields like `LTV Max` and `CreditScore min`. If valid, it is stored as the active version.

### Evaluating an Application
The core underwriting flow calls this service during the decision process:
```python
# Pseudo-code example
policy_check = await xml_policy_client.evaluate(
    lender_id="lender_A",
    data={"ltv": "85.00", "credit_score": 650, ...}
)

if policy_check.decision == "fail":
    # Reject application based on lender specific criteria
    return ApplicationDecision(reject_reason="Lender Policy: LTV too high")
```

## Important Notes
- **Decimal Precision**: All financial values in the XML are parsed as `Decimal` to prevent floating-point errors.
- **Audit Trail**: Every policy upload creates a new immutable record. Previous policies are never deleted, only superseded.
- **Security**: XML uploads are strictly validated to prevent XXE (XML External Entity) attacks.
```

### 3. Configuration Notes
**Update:** `.env.example`

```bash
# XML Policy Service Configuration
# Directory to temporarily store XML files during processing (cleared after parsing)
XML_TEMP_UPLOAD_DIR=/tmp/mortgage_uploads

# Maximum allowed size for XML policy uploads in bytes (e.g., 5MB)
XML_MAX_UPLOAD_SIZE=5242880

# Flag to enable strict MISMO 3.0 validation
XML_STRICT_VALIDATION=true
```

### 4. Changelog Update
**Update:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- XML Policy Service: New endpoints for uploading MISMO 3.0 lender policy files.
- XML Policy Service: New evaluation endpoint `/api/v1/xml-policy/{lender_id}/evaluate` to check application data against lender rules.
- XML Policy Service: Schema validation for LenderPolicy XML (LTV, GDS, TDS, CreditScore, Amortization, Property Types).

### Changed
- N/A

### Fixed
- N/A
```