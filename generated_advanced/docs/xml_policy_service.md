# XML Policy Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# XML Policy Service Design Plan

**File:** `docs/design/xml_policy_service.md`  
**Module:** `xml_policy_service`  
**Purpose:** Load, parse, version, and evaluate Canadian lender mortgage policies encoded in MISMO 3.0‑aligned XML. Expose REST endpoints for underwriting decision service integration.

---

## 1. Endpoints

| Method | Path | Auth | Request Body | Response Body | Status Codes (non‑2xx) | Notes |
|--------|------|------|--------------|---------------|------------------------|-------|
| **GET** | `/api/v1/policy/lenders` | authenticated (JWT) | Query: `page` (int, optional), `page_size` (int, optional, ≤100) | `{ "items": [ { "lender_id": "str", "name": "str", "version": "str", "is_active": "bool", "loaded_at": "datetime" } ], "total": "int" }` | 401 (invalid token), 403 (missing `policy:read` scope), 422 (invalid pagination) | List all loaded policies with pagination. |
| **GET** | `/api/v1/policy/{lender_id}` | authenticated (JWT) | Path: `lender_id` (str) | `{ "lender_id": "str", "version": "str", "ltv_max_insured": "Decimal", "ltv_max_conventional": "Decimal", "gds_max": "Decimal", "tds_max": "Decimal", "credit_score_min": "int", "amortization_max_insured": "int", "amortization_max_conventional": "int", "property_types_allowed": "list[str]", "property_types_excluded": "list[str]", "created_at": "datetime", "updated_at": "datetime" }` | 401, 403, 404 (policy not found), 422 (invalid lender_id format) | Retrieve the active version of a lender’s policy. |
| **POST** | `/api/v1/policy/evaluate` | authenticated (JWT) | `{ "lender_id": "str", "ltv": "Decimal", "gds": "Decimal", "tds": "Decimal", "credit_score": "int", "amortization_years": "int", "property_type": "str", "loan_amount": "Decimal", "property_value": "Decimal" }` | `{ "pass": "bool", "reasons": "list[str]" }` | 401, 403, 404 (lender policy not found), 422 (validation error), 400 (malformed request) | Evaluate an application against the lender’s active policy. All financial values must be `Decimal`. |
| **PUT** | `/api/v1/policy/{lender_id}` | admin‑only (JWT + `policy:write` scope) | Multipart: `policy_xml` (file, `.xml`), `version` (str, optional) | `{ "lender_id": "str", "version": "str", "loaded_at": "datetime" }` | 401, 403, 400 (invalid XML or XSD violation), 409 (version conflict), 422 (file too large >5 MiB) | Upload a new policy XML; creates a new version, marks previous as inactive. |
| **POST** | `/api/v1/policy/{lender_id}/rollback/{version}` | admin‑only (JWT + `policy:write` scope) | Path: `lender_id`, `version` | `{ "lender_id": "str", "activated_version": "str", "activated_at": "datetime" }` | 401, 403, 404 (policy version not found), 409 (version already active) | Rollback to a previously uploaded version. |

### Additional Endpoints (Optional but Recommended)

- **GET** `/api/v1/policy/{lender_id}/versions` – list all versions of a lender’s policy (admin‑only).  
- **GET** `/api/v1/policy/health` – service health check (public).  

---

## 2. Models & Database

### 2.1 `lender_policies` Table

| Column | Type | Constraints | Index | Encrypted | Description |
|--------|------|-------------|-------|-----------|-------------|
| `id` | `UUID` | `PRIMARY KEY`, default `gen_random_uuid()` | – | – | Internal surrogate key. |
| `lender_id` | `VARCHAR(50)` | `NOT NULL`, `UNIQUE` | `idx_lender_id_unique` | – | External lender identifier (e.g., `RBC`). |
| `policy_xml` | `TEXT` | `NOT NULL` | – | **Yes** (AES‑256) | Full MISMO 3.0 XML document. |
| `version` | `VARCHAR(20)` | `NOT NULL` | – | – | Semantic version (`1.0.2`). |
| `is_active` | `BOOLEAN` | `DEFAULT true` | `idx_is_active` | – | Only one version per lender may be active. |
| `parsed_config` | `JSONB` | `NOT NULL` | `GIN` | – | Cached parse of LTV, GDS, TDS, etc. for fast evaluation. |
| `created_at` | `TIMESTAMP` | `NOT NULL`, default `now()` | – | – | Audit field. |
| `updated_at` | `TIMESTAMP` | `NOT NULL`, default `now()`, on update `now()` | – | – | Audit field. |

**Indexes:**  
- `idx_lender_id_unique` – unique constraint on `lender_id`.  
- `idx_is_active` – filter active policies.  
- `GIN` index on `parsed_config` for JSON queries (if needed).

### 2.2 `policy_versions` Table (Immutable Audit Trail)

| Column | Type | Constraints | Index | Encrypted | Description |
|--------|------|-------------|-------|-----------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | – | – | Surrogate key. |
| `lender_policy_id` | `UUID` | `FOREIGN KEY (lender_policies.id)` | `idx_lender_policy_id` | – | Links to the lender policy. |
| `version` | `VARCHAR(20)` | `NOT NULL` | `idx_lender_version` | – | Version string. |
| `policy_xml` | `TEXT` | `NOT NULL` | – | **Yes** (AES‑256) | Snapshot of the XML at upload. |
| `created_at` | `TIMESTAMP` | `NOT NULL`, default `now()` | – | – | FINTRAC 5‑year retention. |
| `created_by` | `VARCHAR(100)` | `NOT NULL` | – | – | User ID from JWT (`sub` claim). |

**Indexes:**  
- Composite `idx_lender_version (lender_policy_id, version)` for fast lookups.  
- `idx_created_at` for retention queries.

### 2.3 `policy_evaluation_logs` Table (Audit)

| Column | Type | Constraints | Index | Description |
|--------|------|-------------|-------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | – | Surrogate key. |
| `lender_id` | `VARCHAR(50)` | `NOT NULL` | `idx_lender_id_created_at` | Lender evaluated. |
| `application_id` | `VARCHAR(100)` | `NOT NULL` | `idx_application_id` | Underwriting application UUID. |
| `evaluation_result` | `VARCHAR(20)` | `NOT NULL` | – | `pass` or `fail`. |
| `reasons` | `JSONB` | `NOT NULL` | `GIN` | Array of failure reasons (no PII). |
| `created_at` | `TIMESTAMP` | `NOT NULL`, default `now()` | – | Audit field. |

**Indexes:**  
- `idx_lender_id_created_at` – for lender‑time queries.  
- `idx_application_id` – link to application.  
- `GIN` on `reasons` for analytics.

### 2.4 `lenders` Reference Table (Optional)

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `lender_id` | `VARCHAR(50)` | `PRIMARY KEY` | – |
| `name` | `VARCHAR(255)` | `NOT NULL` | – |
| `created_at`, `updated_at` | `TIMESTAMP` | `NOT NULL` | – |

---

## 3. Business Logic

### 3.1 XML Parsing & Validation

1. **XSD Validation** – On `PUT /policy/{lender_id}`, the uploaded XML is validated against the MISMO 3.0 XSD schema stored in `common/data/mismo_30.xsd`. If validation fails, raise `PolicyValidationError` (HTTP 400).  
2. **Field Extraction** – Using `lxml.etree`, extract:  
   - `LTV/@insured`, `LTV/@conventional` → `Decimal`  
   - `GDS/@max` → `Decimal`  
   - `TDS/@max` → `Decimal`  
   - `CreditScore/@min` → `int`  
   - `AmortizationMax/@insured`, `AmortizationMax/@conventional` → `int`  
   - `PropertyTypes/@Allowed`, `PropertyTypes/@Excluded` → `list[str]` (comma‑delimited)  
3. **Store Parsed Config** – Serialize extracted fields into `parsed_config` JSONB (e.g., `{"ltv_max_insured": 95.0, "gds_max": 39.0, …}`).  
4. **Encryption** – Encrypt the raw `policy_xml` using `common.security.encrypt_pii()` before persisting.  

### 3.2 Policy Evaluation Algorithm

```text
evaluate(lender_id, ltv, gds, tds, credit_score, amortization_years, property_type, loan_amount, property_value):
    1. Retrieve active policy for lender_id (cache → DB).
    2. Compute LTV if not provided: loan_amount / property_value (Decimal, 2‑place precision).
    3. Determine if loan is insured: ltv > 80% → insured, else conventional.
    4. Validate each rule:
       a. LTV ≤ policy.ltv_max_insured (or ltv_max_conventional) → else fail "LTV exceeds policy maximum".
       b. GDS ≤ policy.gds_max → else fail "GDS exceeds policy maximum".
       c. TDS ≤ policy.tds_max → else fail "TDS exceeds policy maximum".
       d. credit_score ≥ policy.credit_score_min → else fail "Credit score below minimum".
       e. amortization_years ≤ policy.amortization_max_insured (or amortization_max_conventional) → else fail "Amortization exceeds policy maximum".
       f. property_type in policy.property_types_allowed AND not in policy.property_types_excluded → else fail "Property type not permitted".
    5. If all checks pass → return {"pass": true, "reasons": []}.
    6. Else → return {"pass": false, "reasons": ["…", "…"]}.
    7. Log evaluation result to policy_evaluation_logs (no PII).
```

**Regulatory Hooks:**  
- **OSFI B‑20** – The evaluation **must** enforce the GDS/TDS limits defined in the policy; the decision service will later apply the stress‑test (contract_rate + 2% or 5.25%). The evaluation endpoint logs the raw GDS/TDS values for audit.  
- **CMHC** – The LTV thresholds (`insured` vs `conventional`) align with CMHC insurance tiers; the policy’s `ltv_max_insured` is typically 95% and `ltv_max_conventional` 80%.  
- **FINTRAC** – `policy_evaluation_logs` serves as an immutable audit trail; entries are never updated or deleted.  
- **PIPEDA** – No SIN, DOB, income, or banking data appear in the evaluation request/response or logs.

### 3.3 Caching Strategy

- **Redis** key: `policy:{lender_id}:active` → serialized `parsed_config` (JSON).  
- TTL: 5 minutes; invalidated on successful `PUT` or rollback.  
- On cache miss, load from `lender_policies` and populate cache.

### 3.4 Versioning & Rollback

- Each `PUT` creates a new row in `policy_versions` and sets `lender_policies.is_active = false` for the old version, then `true` for the new version.  
- Rollback: `POST /policy/{lender_id}/rollback/{version}` flips the `is_active` flag to the requested version after verifying it exists in `policy_versions`.  
- Historical versions remain immutable for FINTRAC retention.

---

## 4. Migrations (Alembic)

```yaml
# Example migration snippet (conceptual)
revision: "2025_06_10_create_policy_tables"
down_revision: "…"

create_tables:
  - lender_policies:
      columns:
        - id: UUID, primary_key
        - lender_id: VARCHAR(50), unique, not_null
        - policy_xml: TEXT, not_null
        - version: VARCHAR(20), not_null
        - is_active: BOOLEAN, default_true
        - parsed_config: JSONB, not_null
        - created_at: TIMESTAMP, not_null
        - updated_at: TIMESTAMP, not_null
      indexes:
        - idx_lender_id_unique (lender_id)
        - idx_is_active (is_active)
        - GIN (parsed_config)

  - policy_versions:
      columns:
        - id: UUID, primary_key
        - lender_policy_id: UUID, foreign_key (lender_policies.id)
        - version: VARCHAR(20), not_null
        - policy_xml: TEXT, not_null
        - created_at: TIMESTAMP, not_null
        - created_by: VARCHAR(100), not_null
      indexes:
        - idx_lender_version (lender_policy_id, version)
        - idx_created_at (created_at)

  - policy_evaluation_logs:
      columns:
        - id: UUID, primary_key
        - lender_id: VARCHAR(50), not_null
        - application_id: VARCHAR(100), not_null
        - evaluation_result: VARCHAR(20), not_null
        - reasons: JSONB, not_null
        - created_at: TIMESTAMP, not_null
      indexes:
        - idx_lender_id_created_at (lender_id, created_at)
        - idx_application_id (application_id)
        - GIN (reasons)

# Data migration: none (new module)
```

**Important:** Never modify existing Alembic migrations; always generate new revisions.

---

## 5. Security & Compliance

| Requirement | Implementation |
|-------------|----------------|
| **Authentication** | JWT via OAuth2 (`Authorization: Bearer <token>`). Token must contain `sub` (user ID) and `scope` (`policy:read`, `policy:write`). |
| **Authorization** | `GET` endpoints require `policy:read` scope; `PUT` and rollback require `policy:write` (admin‑only). |
| **Encryption at Rest** | `policy_xml` encrypted with AES‑256 using `common.security.encrypt_pii()`; key from `common.config.settings.ENCRYPTION_KEY`. |
| **Audit Logging** | `structlog` JSON logs with `correlation_id` for each request; log policy uploads, evaluations, rollbacks. Logs never contain SIN/DOB/income. |
| **OSFI B‑20** | Evaluation endpoint enforces GDS/TDS limits defined in policy; logs breakdown (`gds`, `tds`, `ltv`) for audit. |
| **FINTRAC** | `policy_evaluation_logs` and `policy_versions` are append‑only; retained for 5 years; `created_by` tracks user identity. |
| **CMHC** | LTV thresholds (`insured`/`conventional`) sourced from policy; evaluation rejects loans exceeding insurer limits. |
| **PIPEDA** | No PII (SIN, DOB, income, banking) in request/response or logs; `policy_xml` encrypted; use `lender_id` (non‑PII) for lookups. |
| **mTLS** | Enable mutual TLS for inter‑service calls (decision service → policy service) via FastAPI `HTTPSRedirect` and client cert validation. |
| **Rate Limiting** | `PUT` endpoint: 10 requests/minute per lender (prevent abuse). |
| **Input Validation** | Pydantic v2 models enforce `Decimal` for financial fields, integer ranges, string enums; XML size limit 5 MiB. |

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | When Raised |
|-----------------|-------------|------------|-----------------|-------------|
| `PolicyNotFoundError` | 404 | `POLICY_001` | `"Lender policy '{lender_id}' not found"` | `GET`/`POST`/`PUT` when lender does not exist. |
| `PolicyValidationError` | 422 | `POLICY_002` | `"Policy XML validation failed: {detail}"` | XSD validation failure on upload. |
| `PolicyBusinessRuleError` | 409 | `POLICY_003` | `"Policy rule violated: {rule}"` | Evaluation fails a business rule (e.g., LTV too high). |
| `PolicyAccessDeniedError` | 403 | `POLICY_004` | `"Access denied: insufficient scope"` | User lacks required scope. |
| `PolicyInvalidInputError` | 400 | `POLICY_005` | `"Invalid input: {field} {reason}"` | Malformed request payload. |
| `PolicyConflictError` | 409 | `POLICY_006` | `"Version '{version}' already exists"` | Duplicate version on upload. |
| `PolicyRollbackError` | 404 | `POLICY_007` | `"Version '{version}' not found for lender '{lender_id}'"` | Rollback target does not exist. |

**Error Response Format (consistent across all errors):**

```json
{
  "detail": "Lender policy 'XYZ' not found",
  "error_code": "POLICY_001",
  "correlation_id": "c8a7b3e2-..."
}
```

---

## 7. Additional Design Considerations

### 7.1 XSD Schema Management

- Store the canonical MISMO 3.0 XSD at `mortgage_underwriting/common/data/mismo_30.xsd`.  
- Load it once at service startup into memory (`lxml.etree.XMLSchema`) for fast validation.  
- Version the XSD file; if the standard evolves, create a new file (e.g., `mismo_31.xsd`) and a corresponding migration to add a `schema_version` column to `lender_policies`.

### 7.2 Caching & Performance

- **Redis** cluster recommended for high‑throughput evaluation.  
- Cache key TTL: 5 minutes; refreshed on policy update.  
- Use `FastAPI.Depends` to inject a `PolicyCache` dependency that abstracts cache lookup.

### 7.3 Monitoring & Observability

- **Prometheus** metrics: `policy_evaluations_total`, `policy_uploads_total`, `policy_cache_hits`, `policy_cache_misses`.  
- **OpenTelemetry** tracing spans for XML parsing, validation, and evaluation.  
- **Structured logging** (structlog) includes `lender_id`, `version`, `evaluation_result`, `correlation_id`.

### 7.4 Testing Strategy

- **Unit tests** (`tests/unit/test_xml_policy_service.py`): Mock XML parsing, validation, and evaluation logic; test edge cases (e.g., LTV at boundary).  
- **Integration tests** (`tests/integration/test_xml_policy_service_integration.py`): Use a test PostgreSQL container, upload real MISMO XML, validate evaluation against known outcomes.  
- **Security tests**: Verify encryption, absence of PII in logs, and scope enforcement.

---

## 8. References

- **OSFI B‑20** – *Guideline B‑20: Residential Mortgage Underwriting Practices and Procedures* (stress‑test & GDS/TDS limits).  
- **FINTRAC** – *Proceeds of Crime (Money Laundering) and Terrorist Financing Act* (5‑year retention, immutable records).  
- **CMHC** – *Mortgage Loan Insurance* (LTV thresholds and premium tiers).  
- **PIPEDA** – *Personal Information Protection and Electronic Documents Act* (encryption, data minimization).  
- **MISMO 3.0** – *Mortgage Industry Standards Maintenance Organization* XML specification.  

--- 

**Note:** This design follows the project’s absolute rules (no `float`, no hardcoded secrets, audit fields, etc.) and complies with all listed regulatory requirements. Implementation must keep `policy_xml` encrypted and never log PII.