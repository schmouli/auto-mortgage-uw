# XML Policy Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# XML Policy Service Design Plan

**Module Location:** `modules/xml_policy_service/`  
**Feature Slug:** `xml-policy-service`  
**Documentation Path:** `docs/design/xml-policy-service.md`

---

## 1. Endpoints

### 1.1 GET /api/v1/policy/lenders
List all loaded lender policies with active versions.

**Authentication:** Authenticated (underwriter, admin, decision-service roles)  
**Rate Limit:** 100 requests/minute per API key

**Response Schema (200 OK):**
```python
class LenderPolicySummary(BaseModel):
    lender_id: str = Field(..., pattern=r"^[A-Z]{3,6}$")
    lender_name: str = Field(..., max_length=100)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    is_active: bool
    effective_date: datetime
    xml_hash: str  # SHA256 hash for integrity verification
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 Unauthorized | AUTH_001 | "Invalid or missing JWT token" |
| 403 Forbidden | AUTH_002 | "Insufficient permissions: requires policy:read scope" |

---

### 1.2 GET /api/v1/policy/{lender_id}
Retrieve specific lender policy details (parsed from XML).

**Authentication:** Authenticated  
**Path Parameter:** `lender_id: str` (3-6 uppercase letters)

**Response Schema (200 OK):**
```python
class LenderPolicyDetail(BaseModel):
    lender_id: str
    lender_name: str
    version: str
    is_active: bool
    effective_date: datetime
    policy_rules: PolicyRules  # Parsed XML content
    xml_hash: str
    created_by: str  # Hashed user_id for audit
    created_at: datetime

class PolicyRules(BaseModel):
    ltv_max: LtvLimits
    gds_max: Decimal = Field(..., max_digits=5, decimal_places=2)  # 39.00
    tds_max: Decimal = Field(..., max_digits=5, decimal_places=2)  # 44.00
    credit_score_min: int = Field(..., ge=300, le=900)
    amortization_max: AmortizationLimits
    property_types: PropertyTypeRules

class LtvLimits(BaseModel):
    insured: Decimal = Field(..., max_digits=5, decimal_places=2)  # 95.00
    conventional: Decimal = Field(..., max_digits=5, decimal_places=2)  # 80.00

class AmortizationLimits(BaseModel):
    insured: int = Field(..., le=25)
    conventional: int = Field(..., le=30)

class PropertyTypeRules(BaseModel):
    allowed: List[str]
    excluded: List[str]
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 Unauthorized | AUTH_001 | "Invalid or missing JWT token" |
| 403 Forbidden | AUTH_002 | "policy:read scope required" |
| 404 Not Found | POLICY_001 | "Lender policy {lender_id} not found" |
| 422 Validation Error | VALID_001 | "Invalid lender_id format" |

---

### 1.3 POST /api/v1/policy/evaluate
Evaluate mortgage application data against a lender's policy rules.

**Authentication:** Authenticated (decision-service role or underwriter)  
**Request Schema:**
```python
class PolicyEvaluationRequest(BaseModel):
    lender_id: str = Field(..., pattern=r"^[A-Z]{3,6}$")
    application_id: str = Field(..., min_length=32)  # Hashed application ID
    gross_annual_income: Decimal = Field(..., max_digits=12, decimal_places=2)
    monthly_debt_obligations: Decimal = Field(..., max_digits=10, decimal_places=2)
    property_value: Decimal = Field(..., max_digits=12, decimal_places=2)
    loan_amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    contract_rate: Decimal = Field(..., max_digits=5, decimal_places=3)
    credit_score: int = Field(..., ge=300, le=900)
    property_type: str
    is_insured: bool
    amortization_years: int = Field(..., ge=5, le=30)
    heating_cost_monthly: Decimal = Field(default=Decimal("150"), max_digits=6, decimal_places=2)
    property_tax_monthly: Decimal = Field(..., max_digits=8, decimal_places=2)
```

**Response Schema (200 OK):**
```python
class PolicyEvaluationResponse(BaseModel):
    application_id: str
    lender_id: str
    passed: bool
    evaluation_id: str  # UUID for audit trail
    evaluated_at: datetime
    rule_results: Dict[str, RuleResult]
    gds_ratio: Optional[Decimal] = Field(None, max_digits=5, decimal_places=2)
    tds_ratio: Optional[Decimal] = Field(None, max_digits=5, decimal_places=2)
    ltv_ratio: Optional[Decimal] = Field(None, max_digits=5, decimal_places=2)
    failure_reasons: List[str] = []

class RuleResult(BaseModel):
    rule_name: str
    passed: bool
    actual_value: Union[Decimal, int, str]
    threshold_value: Union[Decimal, int, str]
    details: Optional[str]
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 Unauthorized | AUTH_001 | "Invalid JWT token" |
| 403 Forbidden | AUTH_003 | "policy:evaluate scope required" |
| 404 Not Found | POLICY_001 | "Lender policy not found or inactive" |
| 422 Validation Error | VALID_002 | "Application data validation failed: {field}" |
| 422 Business Rule Error | POLICY_004 | "OSFI B-20 stress test calculation failed" |

---

### 1.4 PUT /api/v1/policy/{lender_id}
Upload or update lender policy XML file.

**Authentication:** Admin-only (policy:admin scope)  
**Content-Type:** `multipart/form-data`  
**Path Parameter:** `lender_id: str`

**Request Schema:**
```python
class PolicyUploadForm(BaseModel):
    lender_name: str = Field(..., max_length=100)
    policy_xml: UploadFile = Field(..., description="MISMO 3.0 aligned XML file")
    change_log: str = Field(..., min_length=10, max_length=500)
    effective_date: Optional[datetime] = None
```

**Response Schema (200 OK):**
```python
class PolicyUploadResponse(BaseModel):
    lender_id: str
    version: str  # New semantic version
    xml_hash: str
    effective_date: datetime
    is_active: bool
    validation_warnings: List[str] = []  # XSD validation warnings (non-blocking)
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 Unauthorized | AUTH_001 | "Invalid JWT token" |
| 403 Forbidden | AUTH_004 | "Admin role required" |
| 404 Not Found | POLICY_001 | "Lender_id not found for update" |
| 409 Conflict | POLICY_002 | "XML hash identical to current version" |
| 422 Validation Error | POLICY_003 | "XML validation failed against MISMO 3.0 XSD" |
| 413 Payload Too Large | VALID_003 | "XML file exceeds 5MB limit" |

---

## 2. Models & Database

### 2.1 ORM Models

**Table: `lender_policies`**
```python
class LenderPolicy(Base):
    __tablename__ = "lender_policies"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lender_id: Mapped[str] = mapped_column(String(6), unique=True, nullable=False, index=True)
    lender_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    effective_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Encrypted fields (AES-256)
    policy_xml: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # Encrypted XML
    xml_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 hex digest
    
    # Cached parsed rules (encrypted JSONB)
    parsed_policy_json: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)  # Hashed user_id
    
    # Composite indexes
    __table_args__ = (
        Index('idx_lender_active', 'lender_id', 'is_active'),
        Index('idx_version_effective', 'version', 'effective_date'),
    )
```

**Table: `policy_versions` (Immutable Audit Trail)**
```python
class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lender_policy_id: Mapped[UUID] = mapped_column(ForeignKey("lender_policies.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Encrypted fields
    policy_xml: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    xml_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    change_log: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Audit fields (FINTRAC 5-year retention)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Relationship
    lender_policy: Mapped["LenderPolicy"] = relationship(back_populates="versions")
    
    __table_args__ = (
        Index('idx_version_history', 'lender_policy_id', 'version', 'created_at'),
        UniqueConstraint('lender_policy_id', 'version', name='uq_policy_version'),
    )
```

**Table: `policy_evaluation_logs` (FINTRAC Compliance)**
```python
class PolicyEvaluationLog(Base):
    __tablename__ = "policy_evaluation_logs"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lender_id: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    application_id_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA256
    evaluation_result: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gds_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    tds_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    ltv_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    
    # Audit fields
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)
    evaluated_by: Mapped[str] = mapped_column(String(64), nullable=False)  # Hashed service/user_id
    
    __table_args__ = (
        Index('idx_evaluation_retention', 'evaluated_at', 'lender_id'),  # For 5-year FINTRAC purge
    )
```

---

## 3. Business Logic

### 3.1 XML Parsing & Validation Service (`services.PolicyParserService`)

**Algorithm:**
```python
async def parse_and_validate_policy(xml_content: bytes) -> Tuple[PolicyRules, str, List[str]]:
    """
    1. Validate XML against MISMO 3.0 XSD schema
    2. Extract policy rules into typed domain model
    3. Calculate SHA256 hash
    4. Return parsed rules, hash, and validation warnings
    """
    # XSD validation (non-blocking warnings)
    schema = await load_mismo_xsd_schema()
    validation_warnings = schema.validate(xml_content)
    
    # Parse XML with defusedxml to prevent XXE attacks
    root = defusedxml.ElementTree.fromstring(xml_content)
    
    # Extract rules with Decimal precision
    ltv_max = LtvLimits(
        insured=Decimal(root.find(".//LTV[@insured]").attrib["insured"]),
        conventional=Decimal(root.find(".//LTV[@conventional]").attrib["conventional"])
    )
    
    # Validate OSFI B-20 thresholds
    if ltv_max.insured > Decimal("95") or ltv_max.conventional > Decimal("80"):
        raise PolicyValidationError("LTV exceeds Canadian regulatory maximums")
    
    # ... additional parsing logic
    
    return PolicyRules(...), hashlib.sha256(xml_content).hexdigest(), validation_warnings
```

### 3.2 Policy Evaluation Engine (`services.PolicyEvaluationEngine`)

**OSFI B-20 Compliant Calculation:**
```python
async def evaluate_against_policy(
    policy: LenderPolicy,
    application: PolicyEvaluationRequest
) -> PolicyEvaluationResponse:
    """
    1. Calculate LTV = loan_amount / property_value (Decimal precision)
    2. Calculate qualifying rate = max(contract_rate + 2%, 5.25%)
    3. Calculate monthly payment PITH using qualifying rate
    4. GDS = (PITH + heating + property_tax) / gross_monthly_income
    5. TDS = (PITH + heating + property_tax + debt) / gross_monthly_income
    6. Enforce hard limits: GDS ≤ 39%, TDS ≤ 44%
    7. Check credit score, property type, amortization
    8. Log complete calculation breakdown for audit
    """
    
    # Stress test rate calculation (OSFI B-20 mandatory)
    qualifying_rate = max(application.contract_rate + Decimal("2.0"), Decimal("5.25"))
    
    # Monthly income conversion
    gross_monthly_income = application.gross_annual_income / Decimal("12")
    
    # Payment calculation using Canadian mortgage formula
    monthly_payment = calculate_canadian_mortgage_payment(
        principal=application.loan_amount,
        annual_rate=qualifying_rate,
        amortization_years=application.amortization_years
    )
    
    # GDS/TDS calculations
    gds_numerator = monthly_payment + application.heating_cost_monthly + application.property_tax_monthly
    gds_ratio = (gds_numerator / gross_monthly_income) * Decimal("100")
    
    tds_numerator = gds_numerator + application.monthly_debt_obligations
    tds_ratio = (tds_numerator / gross_monthly_income) * Decimal("100")
    
    # LTV calculation
    ltv_ratio = (application.loan_amount / application.property_value) * Decimal("100")
    
    # Build rule results
    rule_results = {
        "gds_ratio": RuleResult(
            rule_name="GDS Ratio",
            passed=gds_ratio <= policy.policy_rules.gds_max,
            actual_value=gds_ratio,
            threshold_value=policy.policy_rules.gds_max,
            details=f"OSFI stress test applied: {qualifying_rate}% qualifying rate"
        ),
        # ... additional rules
    }
    
    # Structured logging for audit (no PII)
    logger.info(
        "policy_evaluation_completed",
        evaluation_id=str(uuid4()),
        lender_id=application.lender_id,
        gds_ratio=str(gds_ratio),
        tds_ratio=str(tds_ratio),
        ltv_ratio=str(ltv_ratio),
        passed=all(r.passed for r in rule_results.values())
    )
    
    return PolicyEvaluationResponse(...)
```

### 3.3 Caching Strategy

**Redis Cache Implementation:**
- **Cache Key Format:** `policy:{lender_id}:{version}`
- **TTL:** 86400 seconds (24 hours)
- **Invalidation:** On PUT policy update, delete cache key and publish invalidation event
- **Fallback:** Cache miss triggers database load + re-cache
- **Cache Value:** Encrypted parsed policy JSON (AES-256) to avoid repeated XML parsing

**Cache Warming:**
- On startup, load all active policies into cache
- Background job refreshes cache every 6 hours

### 3.4 Versioning & Rollback

**Version Management:**
- Semantic versioning: `major.minor.patch`
- `major`: Breaking policy changes (threshold modifications)
- `minor`: New rule additions
- `patch`: Documentation/clarification updates
- On PUT, auto-increment version based on change_log analysis
- Rollback: `POST /api/v1/policy/{lender_id}/rollback?version={target_version}`

---

## 4. Migrations

### 4.1 New Tables

```sql
-- Migration: 202401150001_create_lender_policies.py
CREATE TABLE lender_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_id VARCHAR(6) NOT NULL UNIQUE,
    lender_name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    effective_date TIMESTAMP NOT NULL,
    policy_xml BYTEA NOT NULL,  -- AES-256 encrypted
    xml_hash VARCHAR(64) NOT NULL,
    parsed_policy_json BYTEA,  -- Encrypted cache
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(64) NOT NULL
);

CREATE INDEX idx_lender_active ON lender_policies(lender_id, is_active);
CREATE INDEX idx_version_effective ON lender_policies(version, effective_date);

COMMENT ON TABLE lender_policies IS 'Active lender policy definitions with encrypted XML';
COMMENT ON COLUMN lender_policies.policy_xml IS 'AES-256 encrypted MISMO 3.0 XML policy file';

-- Migration: 202401150002_create_policy_versions.py
CREATE TABLE policy_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_policy_id UUID NOT NULL REFERENCES lender_policies(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    policy_xml BYTEA NOT NULL,
    xml_hash VARCHAR(64) NOT NULL,
    change_log TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(64) NOT NULL
);

CREATE INDEX idx_version_history ON policy_versions(lender_policy_id, version, created_at);
CREATE UNIQUE CONSTRAINT uq_policy_version ON policy_versions(lender_policy_id, version);

COMMENT ON TABLE policy_versions IS 'Immutable audit trail for FINTRAC 5-year retention';

-- Migration: 202401150003_create_policy_evaluation_logs.py
CREATE TABLE policy_evaluation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_id VARCHAR(6) NOT NULL,
    application_id_hash VARCHAR(64) NOT NULL,
    evaluation_result BOOLEAN NOT NULL,
    gds_ratio NUMERIC(5,2),
    tds_ratio NUMERIC(5,2),
    ltv_ratio NUMERIC(5,2),
    evaluated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    evaluated_by VARCHAR(64) NOT NULL
);

CREATE INDEX idx_evaluation_retention ON policy_evaluation_logs(evaluated_at, lender_id);
CREATE INDEX idx_app_lookup ON policy_evaluation_logs(application_id_hash);

COMMENT ON TABLE policy_evaluation_logs IS 'FINTRAC compliance audit trail - DO NOT DELETE';
```

### 4.2 Data Migration Needs
- **Initial Load:** Seed table with 5 major lender policies (RBC, TD, Scotia, BMO, CIBC) from `seeds/initial_policies/`
- **Hash Migration:** On first deploy, calculate xml_hash for existing policies if any

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test Enforcement:** Evaluation engine MUST apply `qualifying_rate = max(contract_rate + 2%, 5.25%)`
- **Hard Limits:** Policy rules cannot exceed GDS 39% / TDS 44% (validated on XML upload)
- **Audit Logging:** Every evaluation must log calculation breakdown with `evaluation_id` for OSFI audits
- **Immutability:** Policy versions cannot be modified after creation (append-only)

### 5.2 FINTRAC Reporting Triggers
- **Transaction Threshold:** When `loan_amount > CAD 10,000`, evaluation log must include `high_value_transaction=True` flag
- **Retention:** All `policy_evaluation_logs` retained for 5 years (automatic purge job after 5 years + 1 day)
- **Identity Verification:** Log `evaluated_by` service principal for every evaluation

### 5.3 PIPEDA Data Handling
- **Encryption at Rest:** `policy_xml` and `parsed_policy_json` fields encrypted with AES-256-GCM
- **Key Management:** Use `common/security.py` `encrypt_pii()` with envelope encryption (KMS)
- **No PII in Logs:** Application data (income, debts) NEVER logged; only ratios and hashes
- **Data Minimization:** Evaluation endpoint accepts only required underwriting fields

### 5.4 Authentication & Authorization
```python
# Required scopes per endpoint
ENDPOINT_SCOPES = {
    "GET /policy/lenders": ["policy:read"],
    "GET /policy/{lender_id}": ["policy:read"],
    "POST /policy/evaluate": ["policy:evaluate"],
    "PUT /policy/{lender_id}": ["policy:admin"]
}

# mTLS for inter-service communication (decision service → policy service)
# JWT for human users with role-based access
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
# exceptions.py
class XmlPolicyServiceException(AppException):
    """Base exception for XML Policy Service module"""
    pass

class PolicyNotFoundError(XmlPolicyServiceException):
    """Lender policy does not exist or is inactive"""
    pass

class PolicyValidationError(XmlPolicyServiceException):
    """XML validation failed against MISMO 3.0 XSD"""
    pass

class PolicyBusinessRuleError(XmlPolicyServiceException):
    """Policy rule violates OSFI B-20 or CMHC requirements"""
    pass

class PolicyEvaluationError(XmlPolicyServiceException):
    """Application data failed policy evaluation"""
    pass

class PolicyAccessDeniedError(XmlPolicyServiceException):
    """Insufficient permissions for policy operation"""
    pass
```

### 6.2 Error Mapping Table

| Exception Class | HTTP Status | Error Code | Message Pattern | Retryable |
|-----------------|-------------|------------|-----------------|-----------|
| `PolicyNotFoundError` | 404 | POLICY_001 | "Lender policy {lender_id} not found or inactive" | No |
| `PolicyValidationError` | 422 | POLICY_002 | "XML validation failed: {xsd_error}" | No |
| `PolicyBusinessRuleError` | 409 | POLICY_003 | "OSFI B-20 violation: {rule} exceeds {threshold}" | No |
| `PolicyEvaluationError` | 422 | POLICY_004 | "Evaluation failed: {field} {reason}" | Yes (with corrected data) |
| `PolicyAccessDeniedError` | 403 | POLICY_005 | "Admin role required for policy updates" | No |
| `PolicyConflictError` | 409 | POLICY_006 | "Policy version {version} already exists" | No |

### 6.3 Structured Error Response Format
```json
{
  "detail": "Lender policy RBC001 not found or inactive",
  "error_code": "POLICY_001",
  "module": "xml_policy_service",
  "correlation_id": "c82b2f8a-7d1a-4e1e-8b3d-2c4e8f6a9b1c",
  "timestamp": "2024-01-15T14:30:22.123456Z",
  "request_id": "req_8f7e6d5c4b3a2910"
}
```

---

## 7. Additional Design Considerations

### 7.1 XSD Schema Management
- Store MISMO 3.0 XSD files in `common/xsd/mismo_v3_0_canadian_mortgage.xsd`
- Load schema on service startup, cache in memory
- Version XSD files with git LFS (large file storage)

### 7.2 Background Jobs
- **Cache Warmer:** Daily at 02:00 UTC, refresh Redis cache for all active policies
- **Retention Purge:** Monthly job to delete evaluation logs older than 5 years (FINTRAC compliance)
- **XML Hash Integrity:** Weekly job to verify xml_hash matches encrypted content

### 7.3 Monitoring & Observability
- **Metrics:** Prometheus counters for `policy_evaluations_total`, `policy_uploads_total`, `cache_hit_rate`
- **Tracing:** OpenTelemetry spans for XML parsing, policy evaluation, and cache operations
- **Alerts:** PagerDuty alert if cache hit rate < 90% or policy validation error rate > 5%

### 7.4 Rate Limiting
- **GET endpoints:** 100 req/min per API key
- **POST evaluate:** 1000 req/min per decision-service principal
- **PUT upload:** 10 req/min per admin user (prevent abuse)

---

**Design Approval:** This plan must be reviewed by Architecture Review Board (ARB) and OSFI compliance officer before implementation.