# XML Policy Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

docs/design/xml-policy-service.md

# XML Policy Service Design Plan

## 1. Endpoints

### 1.1 GET /api/v1/policy/lenders
**Purpose**: List all loaded lender policy metadata (paginated)

**Authentication**: Required (JWT, underwriter/admin role)

**Query Parameters**:
- `page` (int, optional): Page number, default 1
- `size` (int, optional): Items per page, default 50, max 100
- `is_active` (bool, optional): Filter by active status

**Response Schema** (200 OK):
```json
{
  "items": [
    {
      "lender_id": "rbc",
      "lender_name": "Royal Bank of Canada",
      "policy_version": "1.0.3",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-20T14:22:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "size": 50
}
```

**Error Responses**:
- `401 Unauthorized`: `{"detail": "Authentication required", "error_code": "AUTH_001"}`
- `403 Forbidden`: `{"detail": "Insufficient permissions", "error_code": "AUTH_002"}`

---

### 1.2 GET /api/v1/policy/{lender_id}
**Purpose**: Retrieve full policy configuration for a specific lender

**Authentication**: Required (JWT, underwriter/admin role)

**Path Parameters**:
- `lender_id` (string, required): Lender identifier (e.g., "rbc")

**Response Schema** (200 OK):
```json
{
  "lender_id": "rbc",
  "lender_name": "Royal Bank of Canada",
  "version": "1.0.3",
  "is_active": true,
  "policy_config": {
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
    "amortization_max": {
      "insured": 25,
      "conventional": 30
    },
    "property_types": {
      "allowed": ["single-family", "condo", "townhouse"],
      "excluded": ["co-op", "commercial-mix"]
    }
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-20T14:22:00Z"
}
```

**Error Responses**:
- `401 Unauthorized`: `{"detail": "Authentication required", "error_code": "AUTH_001"}`
- `403 Forbidden`: `{"detail": "Insufficient permissions", "error_code": "AUTH_002"}`
- `404 Not Found`: `{"detail": "Lender policy rbc not found", "error_code": "POLICY_001"}`

---

### 1.3 POST /api/v1/policy/evaluate
**Purpose**: Evaluate mortgage application data against lender policy rules

**Authentication**: Required (JWT, decision-service role or underwriter)

**Request Schema**:
```json
{
  "lender_id": "rbc",
  "application_id": "app_12345",
  "applicant": {
    "gross_annual_income": "85000.00",
    "monthly_debts": "1200.00",
    "credit_score": 720
  },
  "property": {
    "type": "single-family",
    "value": "750000.00",
    "taxes_annual": "4200.00",
    "heating_monthly": "150.00"
  },
  "loan": {
    "amount": "600000.00",
    "interest_rate": "5.24",
    "amortization_years": 25,
    "contract_rate": "5.24"
  }
}
```

**Response Schema** (200 OK):
```json
{
  "application_id": "app_12345",
  "lender_id": "rbc",
  "passed": false,
  "calculated_ratios": {
    "ltv": "80.00",
    "gds": "39.50",
    "tds": "44.80",
    "stress_test_rate": "7.24"
  },
  "policy_limits": {
    "ltv_max": "80.00",
    "gds_max": "39.00",
    "tds_max": "44.00",
    "credit_score_min": 620,
    "amortization_max": 30
  },
  "violations": [
    {
      "rule": "gds_max",
      "actual": "39.50",
      "limit": "39.00",
      "severity": "error"
    },
    {
      "rule": "tds_max",
      "actual": "44.80",
      "limit": "44.00",
      "severity": "error"
    }
  ],
  "timestamp": "2024-01-20T15:45:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: `{"detail": "Evaluation failed: Missing required field 'loan.amount'", "error_code": "POLICY_004"}`
- `422 Unprocessable Entity`: `{"detail": "credit_score: must be greater than or equal to 300", "error_code": "POLICY_002"}`
- `404 Not Found`: `{"detail": "Lender policy rbc not found", "error_code": "POLICY_001"}`
- `401 Unauthorized`: `{"detail": "Authentication required", "error_code": "AUTH_001"}`
- `403 Forbidden`: `{"detail": "Insufficient permissions", "error_code": "AUTH_002"}`

---

### 1.4 PUT /api/v1/policy/{lender_id}
**Purpose**: Upload and activate new lender policy XML file

**Authentication**: Required (JWT, admin role only)

**Path Parameters**:
- `lender_id` (string, required)

**Request**: Multipart form data
- `policy_xml` (file, required): XML file content
- `activate_immediately` (bool, optional): Default true

**Response Schema** (200 OK):
```json
{
  "lender_id": "rbc",
  "version": "1.0.4",
  "is_active": true,
  "xml_hash": "a3f5c8e9b2d1f4a6c8e9b2d1f4a6c8e9b2d1f4a6c8e9b2d1f4a6c8e9b2d1f4a6",
  "created_at": "2024-01-20T16:00:00Z",
  "created_by": "admin.user@example.com"
}
```

**Error Responses**:
- `400 Bad Request`: `{"detail": "XML validation failed: Malformed XML", "error_code": "POLICY_002"}`
- `422 Unprocessable Entity`: `{"detail": "XSD validation error: Element 'LTV' missing required attribute 'max_insured'", "error_code": "POLICY_003"}`
- `409 Conflict`: `{"detail": "Policy version conflict: Hash matches existing version", "error_code": "POLICY_005"}`
- `401 Unauthorized`: `{"detail": "Authentication required", "error_code": "AUTH_001"}`
- `403 Forbidden`: `{"detail": "Admin role required", "error_code": "AUTH_002"}`
- `413 Payload Too Large`: `{"detail": "XML file exceeds maximum size of 5MB", "error_code": "POLICY_006"}`

---

## 2. Models & Database

### 2.1 ORM Models

**Table: `xml_policy_service_lender_policies`**
```python
class LenderPolicy(Base):
    __tablename__ = "xml_policy_service_lender_policies"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lender_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    lender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    current_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("xml_policy_service_policy_versions.id"), nullable=True)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    versions: Mapped[list["PolicyVersion"]] = relationship(back_populates="lender_policy", cascade="all, delete-orphan")
    current_version: Mapped["PolicyVersion"] = relationship(foreign_keys=[current_version_id])
```

**Table: `xml_policy_service_policy_versions`**
```python
class PolicyVersion(Base):
    __tablename__ = "xml_policy_service_policy_versions"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lender_policy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("xml_policy_service_lender_policies.id"), nullable=False, index=True)
    version_number: Mapped[str] = mapped_column(String(20), nullable=False)
    xml_content: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted at rest (AES-256)
    xml_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)  # SHA256
    parsed_config: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Cached policy rules
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)  # From JWT sub claim
    
    # Relationships
    lender_policy: Mapped["LenderPolicy"] = relationship(back_populates="versions", foreign_keys=[lender_policy_id])
```

**Table: `xml_policy_service_evaluation_logs`**
```python
class PolicyEvaluationLog(Base):
    __tablename__ = "xml_policy_service_evaluation_logs"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lender_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    evaluation_result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    calculated_gds: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=True)
    calculated_tds: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    
    # FINTRAC compliance: immutable audit trail
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Indexes for 5-year retention queries
    __table_args__ = (
        Index('idx_eval_log_lender_created', 'lender_id', 'created_at'),
        Index('idx_eval_log_application', 'application_id', unique=True),
    )
```

### 2.2 Indexes

**Composite Indexes**:
- `idx_lender_policies_active_lender` on `lender_policies(is_active, lender_id)`
- `idx_policy_versions_lender_version` on `policy_versions(lender_policy_id, version_number)`
- `idx_evaluation_logs_retention` on `evaluation_logs(created_at)` for 5-year retention policy

---

## 3. Business Logic

### 3.1 XML Parsing & Validation Service

**Algorithm: `parse_and_validate_policy_xml(xml_content: str) -> PolicyVersion`**

1. **Integrity Check**: Calculate SHA256 hash of raw XML content
   - Query DB for existing `xml_hash` to prevent duplicate storage
   - If exists, raise `PolicyVersionConflictError`

2. **XSD Validation**: Validate against MISMO 3.0 Canadian extension XSD
   - Use `lxml.etree.XMLSchema` for validation
   - If validation fails, raise `PolicyXSDError` with detailed schema violations

3. **XML Parsing**: Parse to Pydantic model `LenderPolicyXML`
   - Extract attributes: `LTV@max_insured`, `LTV@max_conventional`, `GDS@max`, `TDS@max`
   - Extract nested elements: `CreditScore@min`, `AmortizationMax@insured`, `AmortizationMax@conventional`
   - Parse comma-delimited `PropertyTypes@Allowed` and `PropertyTypes@Excluded`

4. **Config Serialization**: Convert to JSON-serializable dict
   ```python
   {
     "ltv": {"max_insured": "95.00", "max_conventional": "80.00"},
     "gds": {"max": "39.00"},
     "tds": {"max": "44.00"},
     "credit_score": {"min": 620},
     "amortization_max": {"insured": 25, "conventional": 30},
     "property_types": {
       "allowed": ["single-family", "condo", "townhouse"],
       "excluded": ["co-op", "commercial-mix"]
     }
   }
   ```

5. **Encryption**: Encrypt `xml_content` using AES-256-GCM with key from `common/security.py`
   - Key rotation: Use `common/config.py` `POLICY_ENCRYPTION_KEY_ID`

### 3.2 Policy Evaluation Engine

**Algorithm: `evaluate_policy(application: PolicyEvaluationRequest) -> PolicyEvaluationResult`**

**Input Validation**:
- All financial values must be positive Decimal
- `credit_score` must be between 300-900
- `property.type` must be in allowed list from policy

**Calculation Steps**:

1. **LTV Calculation** (CMHC compliance):
   ```
   ltv = (loan.amount / property.value) * 100
   ltv = ltv.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
   is_insured = ltv > Decimal('80.00')
   ```

2. **Stress Test Rate** (OSFI B-20):
   ```
   qualifying_rate = max(contract_rate + 2.0, 5.25)
   ```

3. **Monthly Payment (PITH)**:
   ```
   monthly_rate = qualifying_rate / 100 / 12
   num_payments = loan.amortization_years * 12
   pith = loan.amount * (monthly_rate * (1 + monthly_rate) ** num_payments) / ((1 + monthly_rate) ** num_payments - 1)
   ```

4. **GDS/TDS Ratios** (OSFI B-20):
   ```
   gross_monthly_income = applicant.gross_annual_income / 12
   gds = (pith + property.heating_monthly + (property.taxes_annual / 12)) / gross_monthly_income * 100
   tds = (pith + property.heating_monthly + (property.taxes_annual / 12) + applicant.monthly_debts) / gross_monthly_income * 100
   ```

5. **Policy Rule Validation**:
   - `ltv ≤ policy.ltv.max_insured` if is_insured else `policy.ltv.max_conventional`
   - `gds ≤ policy.gds.max` (hard limit 39%)
   - `tds ≤ policy.tds.max` (hard limit 44%)
   - `applicant.credit_score ≥ policy.credit_score.min`
   - `loan.amortization_years ≤ policy.amortization_max.insured` if is_insured else `policy.amortization_max.conventional`
   - `property.type in policy.property_types.allowed`
   - `property.type not in policy.property_types.excluded`

6. **Audit Logging**:
   - Log calculation breakdown with correlation_id
   - Store in `PolicyEvaluationLog` with `created_by` from JWT
   - Never log income, debts, or PII

**Caching Strategy**:
- Use Redis key `policy:v1:{lender_id}` storing parsed_config
- TTL: 86400 seconds (24 hours)
- Invalidate on successful PUT update via Redis pub/sub

### 3.3 Versioning & Rollback

**Version Numbering**: Semantic versioning `X.Y.Z`
- `X`: Major policy changes (new rules)
- `Y`: Minor adjustments (threshold changes)
- `Z`: Patch (XML formatting, comments)

**Rollback Algorithm**:
1. Fetch previous `PolicyVersion` by `lender_policy_id` and `version_number`
2. Validate version exists and is not the current version
3. Update `LenderPolicy.current_version_id` to previous version ID
4. Set `is_active=False` on current version, `is_active=True` on target version
5. Invalidate Redis cache
6. Log rollback event in audit table

---

## 4. Migrations

### 4.1 New Tables

```sql
-- Table: xml_policy_service_lender_policies
CREATE TABLE xml_policy_service_lender_policies (
    id BIGSERIAL PRIMARY KEY,
    lender_id VARCHAR(50) NOT NULL UNIQUE,
    lender_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    current_version_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT fk_current_version FOREIGN KEY (current_version_id) 
        REFERENCES xml_policy_service_policy_versions(id)
);

-- Table: xml_policy_service_policy_versions
CREATE TABLE xml_policy_service_policy_versions (
    id BIGSERIAL PRIMARY KEY,
    lender_policy_id BIGINT NOT NULL,
    version_number VARCHAR(20) NOT NULL,
    xml_content TEXT NOT NULL,  -- Encrypted at rest
    xml_hash VARCHAR(64) NOT NULL UNIQUE,
    parsed_config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL,
    CONSTRAINT fk_lender_policy FOREIGN KEY (lender_policy_id) 
        REFERENCES xml_policy_service_lender_policies(id) ON DELETE CASCADE
);

-- Table: xml_policy_service_evaluation_logs
CREATE TABLE xml_policy_service_evaluation_logs (
    id BIGSERIAL PRIMARY KEY,
    lender_id VARCHAR(50) NOT NULL,
    application_id VARCHAR(100) NOT NULL,
    evaluation_result JSONB NOT NULL,
    calculated_gds NUMERIC(5, 2),
    calculated_tds NUMERIC(5, 2),
    passed BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL
);
```

### 4.2 Indexes

```sql
-- Performance indexes
CREATE INDEX idx_lender_policies_active_lender 
    ON xml_policy_service_lender_policies(is_active, lender_id);

CREATE INDEX idx_policy_versions_lender_version 
    ON xml_policy_service_policy_versions(lender_policy_id, version_number);

CREATE INDEX idx_policy_versions_xml_hash 
    ON xml_policy_service_policy_versions(xml_hash);

CREATE INDEX idx_evaluation_logs_lender_created 
    ON xml_policy_service_evaluation_logs(lender_id, created_at);

CREATE INDEX idx_evaluation_logs_application 
    ON xml_policy_service_evaluation_logs(application_id);

-- Retention policy index (for 5-year FINTRAC retention)
CREATE INDEX idx_evaluation_logs_retention 
    ON xml_policy_service_evaluation_logs(created_at);
```

### 4.3 Data Migration

**Initial Seed Migration**:
- Create default policy for "cmhc" lender with standard B-20 limits
- Insert initial version with XML template

```python
# Alembic migration script
def upgrade():
    op.bulk_insert('xml_policy_service_lender_policies', [
        {
            'lender_id': 'cmhc',
            'lender_name': 'CMHC Standard Policy',
            'is_active': True,
            'current_version_id': None
        }
    ])
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements

**Implementation**:
- Evaluation engine enforces hard GDS ≤ 39% and TDS ≤ 44% limits
- Stress test rate calculation: `qualifying_rate = max(contract_rate + 2%, 5.25%)`
- All ratio calculations use Decimal with 2 decimal precision
- Calculation breakdown logged for audit:
  ```json
  {
    "calculation": "gds",
    "pith": "2847.32",
    "heating": "150.00",
    "taxes": "350.00",
    "gross_income": "7083.33",
    "result": "39.50",
    "limit": "39.00",
    "passed": false
  }
  ```

### 5.2 FINTRAC Compliance

**Requirements**:
- Immutable audit trail for all policy evaluations
- 5-year retention period
- Identity verification via `created_by` JWT claim

**Implementation**:
- `PolicyEvaluationLog` table has no UPDATE/DELETE operations
- `created_at` indexed for retention queries
- Row-level security policy: `created_at < NOW() - INTERVAL '5 years'` prevents modifications
- Log retention automated via PostgreSQL partition pruning

### 5.3 CMHC Insurance Logic

**Integration**:
- LTV calculation uses Decimal: `ltv = (loan_amount / property_value) * 100`
- Insurance trigger: `if ltv > Decimal('80.00'): insurance_required = True`
- Premium tier lookup (if requested by decision service):
  ```python
  if Decimal('80.01') <= ltv <= Decimal('85.00'): premium = Decimal('2.80')
  elif Decimal('85.01') <= ltv <= Decimal('90.00'): premium = Decimal('3.10')
  elif Decimal('90.01') <= ltv <= Decimal('95.00'): premium = Decimal('4.00')
  ```

### 5.4 PIPEDA Data Handling

**Encryption**:
- `PolicyVersion.xml_content` encrypted using AES-256-GCM
- Encryption key from Vault/AWS KMS, referenced in `common/config.py`
- Key rotation every 90 days

**Data Minimization**:
- Evaluation request does NOT accept SIN/DOB
- Only financial and property data required for underwriting
- No PII stored in logs or error messages

### 5.5 Authentication & Authorization

**Endpoint Matrix**:
| Endpoint | Authentication | Required Role |
|----------|----------------|---------------|
| GET /policy/lenders | JWT | underwriter, admin |
| GET /policy/{lender_id} | JWT | underwriter, admin |
| POST /policy/evaluate | JWT | decision-service, underwriter |
| PUT /policy/{lender_id} | JWT | admin only |

**mTLS**: For decision-service to policy-service communication (if deployed as microservice)

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy

```python
# modules/xml_policy_service/exceptions.py
class PolicyServiceException(AppException):
    """Base exception for policy service"""
    pass

class PolicyNotFoundError(PolicyServiceException):
    """Lender policy not found in database"""
    pass

class PolicyValidationError(PolicyServiceException):
    """XML malformed or missing required elements"""
    pass

class PolicyXSDError(PolicyValidationError):
    """XSD schema validation failed"""
    pass

class PolicyEvaluationError(PolicyServiceException):
    """Application data failed policy evaluation"""
    pass

class PolicyVersionConflictError(PolicyServiceException):
    """XML content hash matches existing version"""
    pass

class PolicyFileTooLargeError(PolicyServiceException):
    """XML file exceeds 5MB limit"""
    pass
```

### 6.2 Error Code Mapping

| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `PolicyNotFoundError` | 404 | `POLICY_001` | "Lender policy {lender_id} not found" | WARNING |
| `PolicyValidationError` | 422 | `POLICY_002` | "XML validation failed: {detail}" | ERROR |
| `PolicyXSDError` | 422 | `POLICY_003` | "XSD validation error: {detail}" | ERROR |
| `PolicyEvaluationError` | 400 | `POLICY_004` | "Evaluation failed: {reason}" | INFO |
| `PolicyVersionConflictError` | 409 | `POLICY_005` | "Policy version conflict: {detail}" | WARNING |
| `PolicyFileTooLargeError` | 413 | `POLICY_006` | "XML file exceeds maximum size of 5MB" | WARNING |
| `UnauthorizedError` | 401 | `AUTH_001` | "Authentication required" | WARNING |
| `ForbiddenError` | 403 | `AUTH_002` | "Insufficient permissions" | WARNING |

### 6.3 Structured Error Response

All errors return consistent JSON:
```json
{
  "detail": "Lender policy rbc not found",
  "error_code": "POLICY_001",
  "correlation_id": "req-12345-abc-67890",
  "timestamp": "2024-01-20T16:00:00Z"
}
```

**Observability**:
- structlog JSON logs include `error_code`, `lender_id`, `correlation_id`
- OpenTelemetry spans track XML parsing duration and cache hit/miss rates
- Prometheus metrics: `policy_evaluations_total`, `policy_evaluation_failures_total`, `policy_cache_hit_ratio`