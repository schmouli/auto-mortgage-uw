# XML Policy Service Documentation

Here is the documentation for the XML Policy Service module.

## 1. API Documentation

**File:** `docs/api/xml_policy_service.md`

```markdown
# XML Policy Service API

## Overview
The XML Policy Service handles the ingestion, parsing, and evaluation of lender-specific underwriting guidelines provided in MISMO 3.0 aligned XML format.

---

## POST /api/v1/xml-policy

Uploads and parses a new Lender XML policy file.

**Request:**
```json
{
  "lender_id": "lender_abc",
  "policy_name": "Standard Residential Q1 2026",
  "version": "1.0",
  "xml_content": "<LenderPolicy version=\"1.0\"><LTV Max insured=\"95\" conventional=\"80\"/><GDS max=\"39\"/><TDS max=\"44\"/><CreditScore min=\"620\"/><AmortizationMax insured=\"25\" conventional=\"30\"/><PropertyTypes Allowed=\"single-family, condo, townhouse\" Excluded=\"\"/></LenderPolicy>"
}
```

**Response (201):**
```json
{
  "id": "pol_uuid_12345",
  "lender_id": "lender_abc",
  "policy_name": "Standard Residential Q1 2026",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid XML structure or missing required fields (LTV, GDS, TDS, CreditScore).
- 409: Policy version already exists for this lender.
- 422: Validation error (see error_code).

---

## GET /api/v1/xml-policy/{lender_id}

Retrieves the currently active policy for a specific lender.

**Parameters:**
- `lender_id` (path): The unique identifier of the lender.

**Response (200):**
```json
{
  "id": "pol_uuid_12345",
  "lender_id": "lender_abc",
  "policy_name": "Standard Residential Q1 2026",
  "parsed_rules": {
    "ltv": {
      "max_insured": 95,
      "max_conventional": 80
    },
    "gds_max": 39,
    "tds_max": 44,
    "credit_score_min": 620,
    "amortization_max": {
      "insured_years": 25,
      "conventional_years": 30
    },
    "property_types": {
      "allowed": ["single-family", "condo", "townhouse"],
      "excluded": []
    }
  },
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 404: No active policy found for lender.

---

## POST /api/v1/xml-policy/evaluate

Evaluates a mortgage application scenario against the active lender policy. This endpoint is intended for consumption by the Decision Service.

**Request:**
```json
{
  "lender_id": "lender_abc",
  "application_data": {
    "ltv_ratio": 82.5,
    "gds_ratio": 35.0,
    "tds_ratio": 42.0,
    "credit_score": 680,
    "amortization_years": 25,
    "property_type": "condo",
    "is_insured": true
  }
}
```

**Response (200):**
```json
{
  "is_approved": true,
  "rejections": [],
  "evaluation_details": {
    "ltv_check": "PASS (82.5 <= 95)",
    "gds_check": "PASS (35.0 <= 39)",
    "tds_check": "PASS (42.0 <= 44)",
    "credit_check": "PASS (680 >= 620)",
    "amortization_check": "PASS (25 <= 25)",
    "property_check": "PASS (condo is allowed)"
  }
}
```

**Response (200 - Rejection Example):**
```json
{
  "is_approved": false,
  "rejections": [
    {
      "rule": "LTV Max Insured",
      "reason": "LTV ratio 96.0 exceeds maximum 95.0"
    }
  ],
  "evaluation_details": {
    "ltv_check": "FAIL (96.0 > 95)",
    "gds_check": "PASS (30.0 <= 39)",
    "tds_check": "PASS (40.0 <= 44)",
    "credit_check": "PASS (700 >= 620)",
    "amortization_check": "PASS (25 <= 25)",
    "property_check": "PASS (single-family is allowed)"
  }
}
```

**Errors:**
- 404: No active policy found for lender.
- 422: Invalid application data format.
```

## 2. Module README

**File:** `docs/modules/xml_policy_service.md`

```markdown
# XML Policy Service Module

## Overview
The XML Policy Service is responsible for managing underwriting rules defined by external lenders. Instead of hardcoding logic into the decision engine, this service loads MISMO 3.0 aligned XML files, parses them into structured rules, and provides an evaluation endpoint to check application data against these rules.

## Key Functions

### Policy Ingestion
- Accepts XML payloads via API.
- Validates XML structure against the `LenderPolicy` schema.
- Enforces mandatory fields: LTV (Insured/Conventional), GDS, TDS, CreditScore, Amortization, and Property Types.
- Stores policies in the database with full audit trails (FINTRAC compliance).

### Policy Evaluation
- The `evaluate_applicant` method in `services.py` takes applicant financial data and compares it against the parsed lender rules.
- Returns a boolean approval status alongside a detailed breakdown of which checks passed or failed.
- Ensures strict decimal comparison for financial ratios to prevent precision loss.

## Regulatory Compliance

- **OSFI B-20:** The service enforces that the XML definitions cannot exceed regulatory hard limits (e.g., even if a lender XML specifies GDS max 50%, the service validates a warning or hard error depending on configuration, though typically the Decision Service applies the stress test, this service ensures the base rules are sound).
- **Auditability:** Every policy load and evaluation is logged with `correlation_id` for traceability.

## Usage Example

1.  **Upload a Policy:**
    Send a `POST` request to `/api/v1/xml-policy` with the XML content.

2.  **Evaluate an Application:**
    From the Decision Service, send a request to `/api/v1/xml-policy/evaluate` with the calculated ratios (LTV, GDS, TDS) and applicant details.

## Data Schema

The service expects XML compliant with this structure:

```xml
<LenderPolicy version="1.0">
  <LTV Max insured="95" conventional="80"/>
  <GDS max="39"/>
  <TDS max="44"/>
  <CreditScore min="620"/>
  <AmortizationMax insured="25" conventional="30"/>
  <PropertyTypes Allowed="single-family, condo, townhouse" Excluded="..."/>
</LenderPolicy>
```
```

## 3. Configuration Notes

**File:** `.env.example`

```bash
# XML Policy Service Configuration

# Directory where uploaded XML files are temporarily stored before parsing
# Note: In production, consider using S3 or Azure Blob Storage references instead of local disk
XML_POLICY_STORAGE_PATH=/tmp/mortgage_policies

# The strictest allowable limits (OSFI B-20 baseline) to validate incoming XML against
# If a lender sends a policy with GDS > 39, the system will reject the upload
POLICY_GDS_HARD_LIMIT=39
POLICY_TDS_HARD_LIMIT=44
POLICY_LTV_INSURED_HARD_LIMIT=95
```

## 4. Changelog Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- XML Policy Service: New endpoints for uploading (`POST /api/v1/xml-policy`) and evaluating (`POST /api/v1/xml-policy/evaluate`) lender policies.
- XML Policy Service: Logic to parse MISMO 3.0 aligned XML definitions for LTV, GDS, TDS, and Credit Score.
- XML Policy Service: Configuration for hard limits to ensure uploaded policies comply with OSFI B-20 standards.

### Changed
- Updated common/config.py to include XML Policy specific environment variables.
```

## 5. Service Docstrings

*To be added to `modules/xml_policy_service/services.py`*

```python
async def parse_xml_policy(self, xml_content: str) -> dict:
    """
    Parse MISMO 3.0 aligned XML string into a structured dictionary.
    
    Validates presence of required nodes (LTV, GDS, TDS, CreditScore, AmortizationMax).
    Converts string attributes to Decimal for financial fields.
    
    Args:
        xml_content: Raw XML string from the request payload.
        
    Returns:
        A dictionary representing the parsed policy rules.
        
    Raises:
        InvalidPolicyStructureError: If required tags are missing or malformed.
    """

async def evaluate_applicant(self, policy_id: str, application_data: dict) -> dict:
    """
    Evaluate applicant financial data against a specific lender policy.
    
    Performs point-in-time comparison of ratios (LTV, GDS, TDS) and
    qualitative data (Property Type) against the parsed XML rules.
    
    Args:
        policy_id: UUID of the stored policy to evaluate against.
        application_data: Dictionary containing calculated ratios and 
                          applicant details (ltv_ratio, gds_ratio, etc.).
                          
    Returns:
        Evaluation result containing 'is_approved' (bool), 'rejections' (list),
        and 'evaluation_details' (dict) for audit trails.
    """
```