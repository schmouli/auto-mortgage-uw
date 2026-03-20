```markdown
# XML Policy Service

## Overview

The XML Policy Service is responsible for managing underwriting guidelines defined by external lenders. It ingests policy files formatted in XML (aligned with the MISMO 3.0 Canadian standard), parses them, and exposes endpoints to evaluate mortgage applications against these dynamic rules.

### Key Functions

- **Ingestion:** Validates and loads XML policy definitions into the database.
- **Parsing:** Extracts specific underwriting criteria (LTV, GDS, TDS, Credit Score, Amortization, Property Types).
- **Evaluation:** Provides a decisioning interface that compares applicant data against the active lender policy.

### Usage Example

1.  **Upload Policy:** The administrative interface uploads a new `LenderPolicy.xml` file via the upload endpoint.
2.  **Validation:** The service validates the XML structure and stores the constraints.
3.  **Decisioning:** The core Underwriting module sends application data to the `evaluate` endpoint to receive a Pass/Fail determination based on the loaded policy.

---

## Configuration

To operate the XML Policy Service, ensure the following environment variables are configured in `.env`.

```bash
# XML Policy Service Configuration

# Directory where temporary XML files are stored during processing
POLICY_STORAGE_PATH=/tmp/mortgage_policies

# Filesystem path or URL to the MISMO 3.0 XSD schema for validation
MISMO_XSD_PATH=/schemas/mismo_3.0_canada.xsd

# Maximum size of an uploaded XML policy file (in bytes)
MAX_POLICY_UPLOAD_SIZE=5242880
```

---

## API Documentation

### POST /api/v1/policy/upload

Uploads and parses a new lender XML policy file. This endpoint validates the XML against the MISMO 3.0 schema and extracts underwriting rules.

**Request:**
- **Content-Type:** `multipart/form-data`
- **Body:** Form field named `file` containing the XML document.

```json
// N/A (Multipart form-data)
```

**Response (201 Created):**
```json
{
  "id": "uuid-v4",
  "lender_name": "Example Lender Corp",
  "version": "1.0",
  "created_at": "2026-03-02T14:30:00Z",
  "status": "active"
}
```

**Errors:**
- `400`: Invalid XML format or syntax error.
- `422`: Validation error against MISMO XSD schema or missing required fields (e.g., `LTV Max`).
- `401`: Not authenticated.
- `413`: Payload too large (exceeds `MAX_POLICY_UPLOAD_SIZE`).

---

### POST /api/v1/policy/evaluate

Evaluates a mortgage application scenario against the currently active policy. This endpoint calculates ratios and compares them against the thresholds defined in the loaded XML.

**Request:**
```json
{
  "application_id": "app_12345",
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "income_monthly": "12000.00",
  "piti_monthly": "3800.00",
  "debt_monthly": "500.00",
  "credit_score": 720,
  "property_type": "single-family",
  "amortization_years": 25,
  "is_insured": true
}
```

**Response (200 OK):**
```json
{
  "application_id": "app_12345",
  "is_eligible": true,
  "evaluation_timestamp": "2026-03-02T14:35:00Z",
  "policy_version": "1.0",
  "checks": {
    "ltv": {
      "passed": true,
      "calculated_value": "90.00",
      "limit": "95.00",
      "message": "LTV within limit"
    },
    "gds": {
      "passed": true,
      "calculated_value": "31.66",
      "limit": "39.00",
      "message": "GDS within OSFI B-20 limit"
    },
    "tds": {
      "passed": true,
      "calculated_value": "35.83",
      "limit": "44.00",
      "message": "TDS within OSFI B-20 limit"
    },
    "credit_score": {
      "passed": true,
      "input_value": 720,
      "min_required": 620,
      "message": "Credit score acceptable"
    },
    "amortization": {
      "passed": true,
      "input_years": 25,
      "max_years": 25,
      "message": "Amortization within insured limit"
    },
    "property_type": {
      "passed": true,
      "input_type": "single-family",
      "allowed_types": ["single-family", "condo", "townhouse"],
      "message": "Property type allowed"
    }
  }
}
```

**Response (200 OK - Failure Example):**
```json
{
  "application_id": "app_67890",
  "is_eligible": false,
  "evaluation_timestamp": "2026-03-02T14:36:00Z",
  "policy_version": "1.0",
  "rejection_reason": "Credit score below minimum",
  "checks": {
    "credit_score": {
      "passed": false,
      "input_value": 600,
      "min_required": 620,
      "message": "Credit score too low"
    }
    // ... other checks omitted for brevity
  }
}
```

**Errors:**
- `400`: Invalid input data (e.g., negative income, malformed Decimal).
- `404`: No active policy found for the requested lender/context.
- `422`: Validation error (missing required field in request).
- `500`: Internal error during XML parsing or evaluation logic.

---

### GET /api/v1/policy/active

Retrieves the configuration details of the currently active policy without evaluating a specific application. Useful for UI display or debugging.

**Request:**
None

**Response (200 OK):**
```json
{
  "id": "uuid-v4",
  "lender_name": "Example Lender Corp",
  "version": "1.0",
  "created_at": "2026-03-02T14:30:00Z",
  "constraints": {
    "ltv": {
      "max_insured": "95.00",
      "max_conventional": "80.00"
    },
    "gds": {
      "max": "39.00"
    },
    "tds": {
      "max": "44.00"
    },
    "credit_score": {
      "min": 620
    },
    "amortization": {
      "max_insured_years": 25,
      "max_conventional_years": 30
    },
    "property_types": {
      "allowed": ["single-family", "condo", "townhouse"],
      "excluded": ["manufactured", "land_only"]
    }
  }
}
```

**Errors:**
- `404`: No active policy currently loaded in the system.
- `401`: Not authenticated.
```