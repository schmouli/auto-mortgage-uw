```markdown
# XML Policy Service API

## Module Overview

The **XML Policy Service** is responsible for ingesting, parsing, and managing lender-specific underwriting policies provided in XML format (aligned with MISMO 3.0 standards). It acts as the central source of truth for lending criteria, exposing these rules to the Decision Service for evaluation.

### Key Functions
- **Ingestion:** Parses uploaded XML files to extract underwriting constraints (LTV, GDS, TDS, Credit Scores, Amortization).
- **Validation:** Ensures uploaded policies conform to the required schema and regulatory baselines (e.g., OSFI B-20 limits).
- **Retrieval:** Provides structured access to policy rules for the Decision Engine.
- **Audit:** Maintains an immutable record of policy versions and activation timestamps (FINTRAC compliance).

### Usage Example
The Decision Service queries the XML Policy Service to determine the specific GDS limit for a given lender:

```python
# Pseudo-code example of interaction
policy = await policy_client.get_policy(lender_id="lender_123")
max_gds = policy.gds_max # e.g., 39
```

---

## Configuration Notes

### Environment Variables

To configure the XML Policy Service, add the following variables to your `.env` file:

```bash
# XML Policy Service Configuration
# Directory or S3 path where uploaded XML files are stored
XML_POLICY_STORAGE_PATH=./data/policies

# Path to the XSD schema used for validating incoming XML files
XML_POLICY_SCHEMA_PATH=./schemas/mismo_3.0_policy.xsd

# Maximum allowed file size for XML uploads in bytes (default: 5MB)
XML_MAX_UPLOAD_SIZE=5242880
```

---

## API Endpoints

### POST /api/v1/policies

Uploads and parses a new lender policy XML file.

**Request:**
- Content-Type: `multipart/form-data`
- Body: Form data with key `file` containing the XML document.

```json
// Form Data
{
  "file": "<LenderPolicy version=\"1.0\">...</LenderPolicy>"
}
```

**Response (201 Created):**
```json
{
  "id": "pol_550e8400-e29b",
  "lender_id": "lender_001",
  "version": "1.0",
  "status": "active",
  "created_at": "2026-03-02T14:30:00Z",
  "details": {
    "ltv_max_insured": "95.00",
    "ltv_max_conventional": "80.00",
    "gds_max": "39",
    "tds_max": "44",
    "credit_score_min": "620",
    "amortization_max_insured": "25",
    "amortization_max_conventional": "30",
    "property_types_allowed": ["single-family", "condo", "townhouse"]
  }
}
```

**Errors:**
- `400 Bad Request`: Invalid XML structure or file size exceeded.
- `422 Unprocessable Entity`: XML validation failed against schema (e.g., missing required fields).
- `409 Conflict`: A policy for this lender/version already exists.

---

### GET /api/v1/policies/{lender_id}

Retrieves the currently active underwriting policy for a specific lender.

**Parameters:**
- `lender_id` (path): The unique identifier of the lender.

**Response (200 OK):**
```json
{
  "id": "pol_550e8400-e29b",
  "lender_id": "lender_001",
  "version": "1.0",
  "rules": {
    "ltv": {
      "max_insured": 95,
      "max_conventional": 80
    },
    "ratios": {
      "gds_max": 39,
      "tds_max": 44
    },
    "credit": {
      "min_score": 620
    },
    "amortization": {
      "max_insured_years": 25,
      "max_conventional_years": 30
    },
    "property": {
      "allowed_types": ["single-family", "condo", "townhouse"],
      "excluded_types": ["rooming-house"]
    }
  },
  "updated_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `404 Not Found`: No active policy found for the specified lender.

---

### POST /api/v1/policies/{lender_id}/evaluate

Evaluates a set of applicant data against the lender's active policy without creating a full application. Used for pre-qualification checks.

**Request:**
```json
{
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "is_insured": true,
  "gross_monthly_income": "12000.00",
  "housing_costs": "3500.00",
  "total_debts": "4500.00",
  "credit_score": 680,
  "property_type": "condo",
  "amortization_years": 25
}
```

**Response (200 OK):**
```json
{
  "decision": "pass",
  "is_insurable": true,
  "checks": {
    "ltv": {
      "value": "90.00",
      "limit": "95.00",
      "status": "pass"
    },
    "gds": {
      "value": "29.16",
      "limit": "39.00",
      "status": "pass"
    },
    "tds": {
      "value": "37.50",
      "limit": "44.00",
      "status": "pass"
    },
    "credit_score": {
      "value": 680,
      "limit": 620,
      "status": "pass"
    },
    "property_type": {
      "value": "condo",
      "allowed": true,
      "status": "pass"
    },
    "amortization": {
      "value": 25,
      "limit": 25,
      "status": "pass"
    }
  }
}
```

**Errors:**
- `404 Not Found`: Policy not found.
- `422 Unprocessable Entity`: Missing required fields in evaluation request.
```

***

### CHANGELOG.md Entry

```markdown
## [2026-03-02]
### Added
- XML Policy Service: New module for loading and parsing lender XML policy files (MISMO 3.0).
- `POST /api/v1/policies`: Endpoint for uploading and validating new policy XML files.
- `GET /api/v1/policies/{lender_id}`: Endpoint to retrieve active policy rules.
- `POST /api/v1/policies/{lender_id}/evaluate`: Endpoint to evaluate applicant data against specific lender policy rules.
- Implemented XML schema validation to ensure compliance with MISMO 3.0 standards.

### Changed
- Updated common/config.py to support XML storage paths and schema validation locations.

### Fixed
- N/A
```

### .env.example Entry

```bash
# XML Policy Service Configuration
# Directory or S3 path where uploaded XML files are stored
XML_POLICY_STORAGE_PATH=./data/policies

# Path to the XSD schema used for validating incoming XML files
XML_POLICY_SCHEMA_PATH=./schemas/mismo_3.0_policy.xsd

# Maximum allowed file size for XML uploads in bytes (default: 5MB)
XML_MAX_UPLOAD_SIZE=5242880
```