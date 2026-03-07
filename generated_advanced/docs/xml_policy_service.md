# XML Policy Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# XML Policy Service Design Plan

**Module ID:** `policy_xml`  
**File:** `docs/design/xml-policy-service.md`  
**Last Updated:** 2024-01-15

---

## 1. Endpoints

### 1.1 GET /api/v1/policy/lenders
List all loaded lender policies with metadata (no XML content).

**Authentication:** Authenticated (internal services + admin users)  
**Rate Limit:** 100 req/min per client

**Request Query Parameters:**
- `status` (optional, enum: `active`, `draft`, `deprecated`) - filter by policy status
- `limit` (optional, int, default=50, max=200) - pagination limit
- `offset` (optional, int, default=0) - pagination offset

**Response Schema (200 OK):**
```json
{
  "policies": [
    {
      "lender_id": "bmo-001",
      "lender_name": "Bank of Montreal",
      "policy_version": "2.1.3",
      "status": "active",
      "effective_date": "2024-01-01T00:00:00Z",
      "created_at": "2023-12-15T10:30:00Z",
      "evaluations_count": 1247
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `403 Forbidden` - Insufficient permissions (`policy:read` scope required)
- `422 ValidationError` - Invalid query parameter format

---

### 1.2 GET /api/v1/policy/{lender_id}
Get specific lender policy including parsed XML content.

**Authentication:** Authenticated (internal services + admin users)  
**Rate Limit:** 200 req/min per client

**Path Parameters:**
- `lender_id` (string, required) - Lender identifier (e.g., `bmo-001`)

**Request Query Parameters:**
- `version` (optional, string) - Specific policy version. If omitted, returns active version.

**Response Schema (200 OK):**
```json
{
  "lender_id": "bmo-001",
  "lender_name": "Bank of Montreal",
  "policy_version": "2.1.3",
  "status": "active",
  "effective_date": "2024-01-01T00:00:00Z",
  "xml_content": "<LenderPolicy>...</LenderPolicy>",
  "parsed_config": {
    "ltv": {
      "max_insured": "95.00",
      "max_conventional": "80.00"
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
      "excluded": ["co-op", "commercial-mix"]
    }
  },
  "created_at": "2023-12-15T10:30:00Z",
  "created_by": "admin@underwriting.ca",
  "checksum": "sha256:abc123..."
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `403 Forbidden` - Insufficient permissions (`policy:read` scope required)
- `404 PolicyNotFoundError` - Policy does not exist (`POLICY_XML_001`)
- `422 ValidationError` - Invalid lender_id format

---

### 1.3 POST /api/v1/policy/evaluate
Evaluate application data against lender policy. Core endpoint for decision service integration.

**Authentication:** Authenticated (internal services only, mTLS recommended)  
**Rate Limit:** 1000 req/min per service principal  
**Timeout:** 5 seconds max (must meet decision service SLA)

**Request Body Schema:**
```json
{
  "lender_id": "bmo-001",
  "application_id": "app-2024-001",
  "applicant_data": {
    "gross_annual_income": "85000.00",
    "monthly_debt_payments": "1200.00",
    "credit_score": 720,
    "down_payment_amount": "75000.00"
  },
  "property_data": {
    "property_value": "500000.00",
    "property_type": "condo",
    "address": {
      "street": "123 Main St",
      "city": "Toronto",
      "province": "ON",
      "postal_code": "M5V 1A1"
    }
  },
  "mortgage_data": {
    "loan_amount": "425000.00",
    "contract_rate": "5.24",
    "amortization_years": 25,
    "payment_frequency": "monthly"
  }
}
```

**Response Schema (200 OK):**
```json
{
  "application_id": "app-2024-001",
  "lender_id": "bmo-001",
  "policy_version": "2.1.3",
  "decision": "approved",  // enum: approved, rejected, referred
  "decision_reasons": [
    {
      "rule": "gds_ratio",
      "status": "pass",
      "value": "32.50",
      "limit": "39.00",
      "details": "GDS calculation includes PITH at stress test rate 7.24%"
    },
    {
      "rule": "tds_ratio",
      "status": "pass",
      "value": "42.10",
      "limit": "44.00"
    },
    {
      "rule": "credit_score",
      "status": "pass",
      "value": 720,
      "limit": 620
    },
    {
      "rule": "ltv_ratio",
      "status": "pass",
      "value": "85.00",
      "limit": "95.00",
      "insurance_required": true,
      "insurance_premium_rate": "3.10"
    }
  ],
  "evaluated_at": "2024-01-15T14:30:00Z",
  "correlation_id": "corr-123-xyz"
}
```

**Error Responses:**
- `400 Bad Request` - Invalid XML policy configuration on server side
- `401 Unauthorized` - Invalid or missing JWT/mTLS certificate
- `403 Forbidden` - Service principal lacks `policy:evaluate` scope
- `404 PolicyNotFoundError` - Lender policy not found (`POLICY_XML_001`)
- `422 ValidationError` - Application data validation failed (`POLICY_XML_002`)
- `500 EvaluationEngineError` - Policy evaluation engine failure (`POLICY_XML_004`)
- `503 ServiceUnavailable` - Cache/redis connectivity issue

**FINTRAC Compliance Note:** All evaluation requests are logged to `policy_evaluation_log` table with `created_by` = service principal ID. No PII logged.

---

### 1.4 PUT /api/v1/policy/{lender_id}
Update lender policy XML (creates new version, enables rollback).

**Authentication:** Authenticated (admin users only)  
**Rate Limit:** 10 req/min per user  
**Audit Trail:** Full change tracking, previous version archived automatically

**Path Parameters:**
- `lender_id` (string, required)

**Request Body Schema:**
```json
{
  "xml_content": "<LenderPolicy version=\"1.0\">...</LenderPolicy>",
  "effective_date": "2024-02-01T00:00:00Z",
  "change_reason": "Updated LTV limits for 2024 Q1",
  "changed_by": "admin@underwriting.ca"
}
```

**Response Schema (200 OK):**
```json
{
  "lender_id": "bmo-001",
  "new_version": "2.1.4",
  "previous_version": "2.1.3",
  "status": "draft",
  "effective_date": "2024-02-01T00:00:00Z",
  "validation_status": "passed",
  "xsd_validation": true,
  "checksum": "sha256:def456...",
  "created_at": "2024-01-15T15:00:00Z",
  "activation_url": "/api/v1/policy/bmo-001/activate?version=2.1.4"
}
```

**Error Responses:**
- `400 XMLValidationError` - XSD schema validation failed (`POLICY_XML_005`)
- `401 Unauthorized` - Invalid or missing JWT token
- `403 Forbidden` - Insufficient permissions (`policy:write` scope required)
- `404 PolicyNotFoundError` - Lender not found (`POLICY_XML_001`)
- `409 VersionConflictError` - Concurrent update detected (`POLICY_XML_006`)
- `422 ValidationError` - Invalid XML structure or content

---

## 2. Models & Database

### 2.1 ORM Models

#### `policy_xml.models.LenderPolicy`
**Table:** `lender_policies`

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY, default=gen_random_uuid() | - |
| `lender_id` | VARCHAR(50) | UNIQUE, NOT NULL | ✅ |
| `lender_name` | VARCHAR(255) | NOT NULL | ✅ |
| `policy_version` | VARCHAR(20) | NOT NULL | ✅ composite |
| `status` | VARCHAR(20) | NOT NULL, CHECK (status IN ('draft','active','deprecated')) | ✅ composite |
| `effective_date` | TIMESTAMP | NOT NULL | ✅ composite |
| `xml_content` | TEXT | NOT NULL (encrypted at rest) | - |
| `parsed_config` | JSONB | NOT NULL (cached parsed rules) | - |
| `checksum` | VARCHAR(71) | NOT NULL, UNIQUE (sha256:...) | ✅ |
| `created_at` | TIMESTAMP | NOT NULL, default=now() | ✅ |
| `created_by` | VARCHAR(255) | NOT NULL | ✅ |
| `updated_at` | TIMESTAMP | NOT NULL, default=now(), onupdate=now() | - |

**Indexes:**
- `idx_lender_policies_lender_id_status` (lender_id, status) - for active policy lookups
- `idx_lender_policies_effective_date` (effective_date DESC) - for version timeline queries
- `idx_lender_policies_version` (policy_version) - for version-specific queries

**Relationships:**
- One-to-many with `PolicyVersionHistory` (cascade delete prohibited for audit)
- One-to-many with `PolicyEvaluationLog` (cascade delete prohibited)

---

#### `policy_xml.models.PolicyVersionHistory`
**Table:** `policy_version_history`

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | - |
| `lender_policy_id` | UUID | FOREIGN KEY (lender_policies.id), NOT NULL | ✅ |
| `version` | VARCHAR(20) | NOT NULL | ✅ composite |
| `xml_content` | TEXT | NOT NULL (encrypted) | - |
| `change_reason` | TEXT | NOT NULL | - |
| `changed_by` | VARCHAR(255) | NOT NULL | ✅ |
| `created_at` | TIMESTAMP | NOT NULL, default=now() | ✅ |

**Indexes:**
- `idx_version_history_policy_version` (lender_policy_id, version) - for rollback queries
- `idx_version_history_created_by` (changed_by) - for audit trails

**Note:** 5-year retention enforced via PostgreSQL partition on `created_at` (monthly partitions).

---

#### `policy_xml.models.PolicyEvaluationLog`
**Table:** `policy_evaluation_log`

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | - |
| `application_id` | VARCHAR(100) | NOT NULL | ✅ |
| `lender_id` | VARCHAR(50) | NOT NULL | ✅ composite |
| `policy_version` | VARCHAR(20) | NOT NULL | ✅ composite |
| `decision` | VARCHAR(20) | NOT NULL, CHECK (decision IN ('approved','rejected','referred')) | ✅ |
| `decision_reasons` | JSONB | NOT NULL (full calculation breakdown) | - |
| `correlation_id` | VARCHAR(100) | NOT NULL | ✅ |
| `evaluated_at` | TIMESTAMP | NOT NULL, default=now() | ✅ |
| `created_by` | VARCHAR(255) | NOT NULL (service principal ID) | ✅ |

**Indexes:**
- `idx_eval_log_app_id` (application_id) - for FINTRAC lookups
- `idx_eval_log_lender_decision` (lender_id, decision, evaluated_at) - for reporting
- `idx_eval_log_correlation` (correlation_id) - for tracing

**FINTRAC Compliance:** Table is INSERT-only. No UPDATE/DELETE permissions granted to application role. Partitioned by `evaluated_at` for 5-year retention.

---

### 2.2 Encrypted Fields
- `LenderPolicy.xml_content` - AES-256-GCM encryption (via `common.security.encrypt_pii()`)
- `PolicyVersionHistory.xml_content` - AES-256-GCM encryption

**Key Management:** Use separate KMS key `policy_xml_content_key` with rotation every 90 days.

---

## 3. Business Logic

### 3.1 Policy Evaluation Engine (`policy_xml.services.EvaluationEngine`)

**Algorithm Specification:**

```python
async def evaluate_policy(
    lender_id: str,
    application: PolicyEvaluationRequest
) -> PolicyEvaluationResult:
    """
    OSFI B-20 Compliant Evaluation
    """
    # 1. Retrieve active policy from cache or DB
    policy = await get_active_policy(lender_id)
    
    # 2. Calculate LTV
    ltv = (application.mortgage_data.loan_amount / 
           application.property_data.property_value) * 100
    
    # 3. Determine if insured required (CMHC)
    insurance_required = ltv > Decimal('80.00')
    if insurance_required:
        premium_rate = lookup_cmhc_premium(ltv)  # 2.80%, 3.10%, or 4.00%
    
    # 4. Stress Test Rate (OSFI B-20)
    qualifying_rate = max(
        application.mortgage_data.contract_rate + Decimal('2.00'),
        Decimal('5.25')
    )
    
    # 5. Calculate GDS/TDS
    pith = calculate_pith(
        loan_amount=application.mortgage_data.loan_amount,
        rate=qualifying_rate,
        amortization=application.mortgage_data.amortization_years,
        property_value=application.property_data.property_value
    )
    
    gross_monthly = application.applicant_data.gross_annual_income / 12
    
    gds = (pith / gross_monthly) * 100
    tds = ((pith + application.applicant_data.monthly_debt_payments) / 
           gross_monthly) * 100
    
    # 6. Evaluate all rules
    rules = [
        RuleResult("gds_ratio", gds <= policy.gds_max, gds, policy.gds_max),
        RuleResult("tds_ratio", tds <= policy.tds_max, tds, policy.tds_max),
        RuleResult("credit_score", 
                   application.applicant_data.credit_score >= policy.credit_score_min,
                   application.applicant_data.credit_score,
                   policy.credit_score_min),
        RuleResult("ltv_ratio", ltv <= get_ltv_limit(policy, insurance_required), ltv),
        RuleResult("property_type", 
                   application.property_data.property_type in policy.allowed_property_types),
        RuleResult("amortization", 
                   application.mortgage_data.amortization_years <= 
                   get_amortization_limit(policy, insurance_required))
    ]
    
    # 7. Determine decision
    failed_rules = [r for r in rules if not r.passed]
    if not failed_rules:
        decision = "approved"
    elif any(r.rule in ["gds_ratio", "tds_ratio", "ltv_ratio"] for r in failed_rules):
        decision = "rejected"
    else:
        decision = "referred"
    
    # 8. Log evaluation (FINTRAC audit)
    await log_evaluation(
        application_id=application.application_id,
        lender_id=lender_id,
        policy_version=policy.version,
        decision=decision,
        decision_reasons=[r.to_dict() for r in rules],
        correlation_id=structlog.contextvars.get("correlation_id")
    )
    
    return PolicyEvaluationResult(
        decision=decision,
        decision_reasons=rules,
        policy_version=policy.version
    )
```

**Key Formulas:**
- **LTV** = (Loan Amount / Property Value) × 100
- **GDS** = (PITH / Gross Monthly Income) × 100 (OSFI B-20: PITH uses qualifying rate)
- **TDS** = (PITH + Debt Payments) / Gross Monthly Income × 100
- **Qualifying Rate** = max(Contract Rate + 2%, 5.25%)
- **PITH** = Principal + Interest + Property Tax + Heating (calculated using stress test rate)

---

### 3.2 XML Processing Pipeline

**Validation Flow:**
1. **XSD Validation:** Validate against `mismo_policy_3.0.xsd` (stored in `common/static/schemas/`)
2. **Business Rule Validation:** Ensure numeric values within OSFI/CMHC bounds
3. **Checksum Generation:** SHA256 of canonical XML form
4. **Semantic Versioning:** Auto-increment patch version for minor changes, minor for rule changes, major for structural changes

**Caching Strategy:**
- **Redis Cache:** Key `policy:active:{lender_id}` → parsed `LenderPolicy` object (TTL: 24h)
- **Cache Invalidation:** On `PUT` or `activation`, delete cache key and publish `policy:updated` event to Redis Pub/Sub
- **Cache Warming:** Background worker loads active policies on startup

---

### 3.3 Versioning & Rollback State Machine

```
draft → active → deprecated
   ↓________________↑
      (rollback)
```

- **draft:** Policy uploaded but not yet active. Can be modified/deleted.
- **active:** Current production policy. Only one active per lender. Cannot be modified.
- **deprecated:** Previously active policy. Immutable. Kept for 5-year audit.

**Rollback Process:**
1. Select previous version from `policy_version_history`
2. Create new draft with restored XML content
3. Set `change_reason = "Rollback from vX to vY"`
4. Activate new draft (creates vZ, preserving history)

---

## 4. Migrations

### 4.1 New Tables

```sql
-- Table: lender_policies
CREATE TABLE lender_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_id VARCHAR(50) NOT NULL,
    lender_name VARCHAR(255) NOT NULL,
    policy_version VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('draft','active','deprecated')),
    effective_date TIMESTAMP NOT NULL,
    xml_content TEXT NOT NULL,
    parsed_config JSONB NOT NULL,
    checksum VARCHAR(71) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    created_by VARCHAR(255) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT uq_lender_active UNIQUE (lender_id, status) WHERE status = 'active'
);

CREATE INDEX idx_lender_policies_lender_id_status ON lender_policies(lender_id, status);
CREATE INDEX idx_lender_policies_effective_date ON lender_policies(effective_date DESC);
CREATE INDEX idx_lender_policies_version ON lender_policies(policy_version);

-- Table: policy_version_history
CREATE TABLE policy_version_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_policy_id UUID NOT NULL REFERENCES lender_policies(id),
    version VARCHAR(20) NOT NULL,
    xml_content TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    changed_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_version_history_policy_version ON policy_version_history(lender_policy_id, version);
CREATE INDEX idx_version_history_created_by ON policy_version_history(changed_by);

-- Table: policy_evaluation_log
CREATE TABLE policy_evaluation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id VARCHAR(100) NOT NULL,
    lender_id VARCHAR(50) NOT NULL,
    policy_version VARCHAR(20) NOT NULL,
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('approved','rejected','referred')),
    decision_reasons JSONB NOT NULL,
    correlation_id VARCHAR(100) NOT NULL,
    evaluated_at TIMESTAMP NOT NULL DEFAULT now(),
    created_by VARCHAR(255) NOT NULL
) PARTITION BY RANGE (evaluated_at);

-- Create partitions for 5-year retention (monthly)
CREATE INDEX idx_eval_log_app_id ON policy_evaluation_log(application_id);
CREATE INDEX idx_eval_log_lender_decision ON policy_evaluation_log(lender_id, decision, evaluated_at);
CREATE INDEX idx_eval_log_correlation ON policy_evaluation_log(correlation_id);
```

### 4.2 Data Migration

**Initial Seed Migration:**
```sql
-- Insert default OSFI B-20 compliant policy template
INSERT INTO lender_policies (
    lender_id, lender_name, policy_version, status, effective_date,
    xml_content, parsed_config, checksum, created_by
) VALUES (
    'default-template',
    'OSFI B-20 Template',
    '1.0.0',
    'deprecated',
    '2020-01-01',
    '<LenderPolicy>...</LenderPolicy>',
    '{"gds_max": "39.00", "tds_max": "44.00", ...}',
    'sha256:abc123...',
    'system@migration'
);
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test Enforcement:** Hardcoded logic in `EvaluationEngine` always uses `qualifying_rate = max(contract_rate + 2%, 5.25%)`
- **Ratio Limits:** Policy file cannot exceed GDS 39% / TDS 44%. Validation rejects uploads with higher values.
- **Auditability:** Every evaluation logs full calculation breakdown including stress test rate used, PITH components, and ratio formulas.
- **Immutability:** Active policies cannot be modified; new versions must be created.

### 5.2 FINTRAC Compliance
- **Audit Trail:** `policy_evaluation_log` is INSERT-only. Application role has no UPDATE/DELETE privileges.
- **5-Year Retention:** PostgreSQL partitions automatically drop partitions older than 5 years + 1 day.
- **Transaction Flagging:** `decision_reasons` JSON includes `insurance_required` flag. If loan amount > $10,000 (always true for mortgages), log includes `"transaction_type": "mortgage"` for FINTRAC reporting.
- **Access Logging:** All policy uploads/activations logged with `created_by` user ID for FINTRAC traceability.

### 5.3 CMHC Insurance Logic
```python
def lookup_cmhc_premium(ltv: Decimal) -> Decimal:
    if Decimal('80.01') <= ltv <= Decimal('85.00'):
        return Decimal('2.80')
    elif Decimal('85.01') <= ltv <= Decimal('90.00'):
        return Decimal('3.10')
    elif Decimal('90.01') <= ltv <= Decimal('95.00'):
        return Decimal('4.00')
    else:
        raise PolicyXMLBusinessRuleError("LTV outside insurable range")
```
- **LTV Precision:** Uses Decimal with 2 decimal places to avoid precision loss.
- **Mandatory Insurance:** Evaluation automatically sets `insurance_required=True` when LTV > 80%.

### 5.4 PIPEDA Data Handling
- **No PII in Logs:** XML content is encrypted; only `lender_id` and `policy_version` appear in logs.
- **Data Minimization:** Evaluation endpoint only accepts required underwriting fields. Extra fields are rejected with 422.
- **Encryption at Rest:** AES-256-GCM for `xml_content`. Keys rotated every 90 days via KMS.
- **Response Filtering:** Policy endpoints never return applicant data; only policy metadata.

### 5.5 Authentication & Authorization
| Endpoint | Auth Method | Required Scopes |
|----------|-------------|-----------------|
| `GET /policy/lenders` | JWT Bearer | `policy:read` |
| `GET /policy/{id}` | JWT Bearer | `policy:read` |
| `POST /policy/evaluate` | mTLS + JWT | `policy:evaluate` |
| `PUT /policy/{id}` | JWT Bearer + MFA | `policy:write` |

**Inter-Service Communication:** mTLS required for `/evaluate`. Certificate CN must match allowed service principal list.

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
# policy_xml/exceptions.py
class PolicyXMLException(AppException):
    """Base exception for policy XML module"""
    pass

class PolicyNotFoundError(PolicyXMLException):
    """Policy XML not found for lender"""
    pass

class PolicyXMLValidationError(PolicyXMLException):
    """XSD or business rule validation failed"""
    pass

class PolicyVersionConflictError(PolicyXMLException):
    """Concurrent policy update detected"""
    pass

class PolicyEvaluationError(PolicyXMLException):
    """Evaluation engine internal error"""
    pass

class PolicyCacheError(PolicyXMLException):
    """Redis cache operation failed"""
    pass
```

### 6.2 Error Mapping Table

| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `PolicyNotFoundError` | 404 | `POLICY_XML_001` | "Policy for lender '{lender_id}' not found" | WARNING |
| `PolicyXMLValidationError` | 400 | `POLICY_XML_005` | "XML validation failed: {detail}" | ERROR |
| `PolicyVersionConflictError` | 409 | `POLICY_XML_006` | "Concurrent update on policy {lender_id}" | WARNING |
| `PolicyEvaluationError` | 500 | `POLICY_XML_004` | "Evaluation engine error: {detail}" | ERROR |
| `PolicyCacheError` | 503 | `POLICY_XML_007` | "Cache unavailable: {detail}" | WARNING |
| `ValidationError` (Pydantic) | 422 | `POLICY_XML_002` | "{field}: {reason}" | INFO |

### 6.3 Structured Error Response Example
```json
{
  "detail": "XML validation failed: LTV max_insured exceeds OSFI limit of 95%",
  "error_code": "POLICY_XML_005",
  "correlation_id": "corr-789-xyz",
  "timestamp": "2024-01-15T15:00:00Z",
  "metadata": {
    "lender_id": "bmo-001",
    "version": "2.1.4",
    "failing_rule": "ltv_max_insured"
  }
}
```

**Security Note:** Error messages never include XML content, stack traces, or internal paths.

---

## 7. Infrastructure & Operations

### 7.1 Caching
- **Redis Cluster:** 3-node cluster for high availability
- **Key TTL:** 24 hours with background refresh
- **Cache Warming:** Cron job reloads all active policies at 02:00 UTC daily
- **Metrics:** `policy_cache_hit_rate`, `policy_cache_miss_total`

### 7.2 Background Workers
- **Worker Queue:** Celery with Redis broker
- **Tasks:**
  - `validate_and_parse_policy(lender_id, version)` - Async XSD validation
  - `activate_policy_version(lender_id, version)` - Atomic activation with cache purge
  - `archive_old_policies()` - Mark policies >5 years as deprecated

### 7.3 Monitoring
- **Prometheus Metrics:**
  - `policy_evaluation_duration_seconds` (histogram)
  - `policy_evaluation_total` (counter, labeled by decision)
  - `policy_version_total` (gauge)
  - `policy_xml_validation_failures_total` (counter)

- **Alerts:**
  - Evaluation p95 latency > 3s
  - Cache hit rate < 80%
  - Policy activation failure rate > 5%

---

## 8. Testing Strategy

### 8.1 Unit Tests (`tests/unit/test_policy_xml.py`)
- XML parsing and XSD validation
- Evaluation engine calculations (Decimal precision)
- Cache hit/miss logic
- Versioning logic

### 8.2 Integration Tests (`tests/integration/test_policy_xml_integration.py`)
- End-to-end policy upload → activate → evaluate flow
- Concurrent policy updates (locking)
- Cache invalidation on activation
- FINTRAC audit log verification (INSERT-only)

### 8.3 Compliance Tests
- OSFI B-20 stress test scenarios (rate floor, rate + 2%)
- CMHC premium tier boundaries (80.01%, 85.01%, 90.01%)
- PIPEDA: Verify no PII in logs (structlog capture test)

---

**Design Approval Required By:** Chief Underwriting Officer, Compliance Officer, Infrastructure Architect