Here is the documentation for the **XML Policy Service** module.

### File: `docs/api/xml_policy_service.md`

```markdown
# XML Policy Service API

## Overview
The XML Policy Service is responsible for loading, parsing, and validating lender-specific underwriting policies provided in MISMO 3.0 aligned XML format. It acts as the central source of truth for lending criteria (LTV, GDS, TDS, Credit Scores) and exposes evaluation endpoints to be consumed by the Decision Engine.

### Key Functions
- **XML Parsing & Validation**: Loads XML files and validates them against the MISMO 3.0 schema.
- **Policy Storage**: Persists parsed policy rules to the database.
- **Rule Evaluation**: Provides an endpoint to check applicant data against active lender policies.
- **Security**: Ensures XML parsing is secure (XXE prevention) and data integrity is maintained.

### Usage Example
1. **Upload Policy**: The administrator uploads a new `policy.xml` for "Lender A".
2. **Parse**: The service validates the XML structure and extracts limits (e.g., GDS=39%).
3. **Evaluate**: The Underwriting module sends a payload with applicant metrics to the `/evaluate` endpoint to determine if the application meets "Lender A" criteria.

---

## Endpoints

### POST /api/v1/xml-policy/upload

Uploads and parses a new Lender Policy XML file.

**Request:** `multipart/form-data`
- `file`: The XML file (e.g., `lender_a_policy.xml`).
- `lender_id`: The unique identifier for the lender (string).

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "lender_id": "lender_a",
  "version": "1.0",
  "created_at": "2026-03-02T10:00:00Z",
  "status": "active"
}
```

**Errors:**
- `400`: Invalid XML format or syntax error.
- `422`: Validation error (e.g., missing required fields like `LTV Max`).
- `401`: Not authenticated.
- `409`: Policy version conflict or duplicate upload.

---

### GET /api/v1/xml-policy/{lender_id}

Retrieves the currently active policy details for a specific lender.

**Parameters:**
- `lender_id` (path): The unique identifier for the lender.

**Response (200 OK):**
```json
{
  "lender_id": "lender_a",
  "version": "1.0",
  "ltv_limits": {
    "insured": "95.00",
    "conventional": "80.00"
  },
  "gds_max": "39.00",
  "tds_max": "44.00",
  "credit_score_min": 620,
  "amortization_max": {
    "insured": 25,
    "conventional": 30
  },
  "property_types": {
    "allowed": ["single-family", "condo", "townhouse"],
    "excluded": ["rooming-house"]
  }
}
```

**Errors:**
- `404`: Policy not found for the specified lender.

---

### POST /api/v1/xml-policy/evaluate

Evaluates a set of application data against the specific lender's active policy to determine eligibility.

**Request:**
```json
{
  "lender_id": "lender_a",
  "application_data": {
    "ltv": "85.50",
    "is_insured": true,
    "gds": "35.00",
    "tds": "42.00",
    "credit_score": 680,
    "amortization_years": 25,
    "property_type": "condo"
  }
}
```

**Response (200 OK):**
```json
{
  "is_eligible": true,
  "lender_id": "lender_a",
  "policy_version": "1.0",
  "evaluated_at": "2026-03-02T10:05:00Z",
  "violations": []
}
```

**Response (200 OK) - Failure Example:**
```json
{
  "is_eligible": false,
  "lender_id": "lender_a",
  "policy_version": "1.0",
  "evaluated_at": "2026-03-02T10:05:00Z",
  "violations": [
    {
      "rule": "GDS_MAX",
      "expected": "39.00",
      "actual": "42.50",
      "message": "GDS ratio exceeds maximum limit"
    },
    {
      "rule": "PROPERTY_TYPE",
      "expected": "single-family, condo, townhouse",
      "actual": "rooming-house",
      "message": "Property type is excluded by policy"
    }
  ]
}
```

**Errors:**
- `404`: Policy not found for the specified `lender_id`.
- `422`: Invalid input data format (e.g., strings instead of numbers for financial fields).
```

---

### File: `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- XML Policy Service: New module for parsing and managing lender underwriting policies.
  - `POST /api/v1/xml-policy/upload`: Endpoint to upload MISMO 3.0 aligned XML policies.
  - `GET /api/v1/xml-policy/{lender_id}`: Endpoint to retrieve active policy constraints.
  - `POST /api/v1/xml-policy/evaluate`: Endpoint to validate application data against policy rules.
- Added XML Schema validation logic to ensure compliance with MISMO 3.0 standards.
- Added support for dynamic LTV, GDS, TDS, Credit Score, and Amortization limits per lender.

### Changed
- Updated common exceptions to include `PolicyValidationError`.

### Security
- Enforced XXE (XML External Entity) prevention on all XML parsers.
- Ensured all policy uploads are logged with `created_by` for FINTRAC audit trails.
```

---

### File: `.env.example`

```bash
# XML Policy Service Configuration

# Directory or S3 path where uploaded XML policy files are temporarily stored before parsing
POLICY_UPLOAD_PATH=./temp_policies

# Filesystem path or URL to the MISMO 3.0 XSD schema for validation
XML_SCHEMA_XSD_PATH=./schemas/mismo_3.0_policy.xsd

# Maximum allowed size for XML policy uploads (e.g., 5MB)
MAX_POLICY_UPLOAD_SIZE=5242880
```