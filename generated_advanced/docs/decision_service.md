# Decision Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Decision Service Module

**File:** `docs/design/decision-service.md`  
**Module:** `decision_service`  
**Complexity:** reasoning  
**Date:** 2024

---

## 1. Endpoints

### 1.1 POST /api/v1/decision/evaluate
Run deterministic underwriting decision engine against submitted application data.

**Authentication:** Authenticated (JWT, `underwriter` or `system` role)  
**Rate Limit:** 100 req/min per tenant

**Request Body Schema:**
```python
class DecisionEvaluateRequest(BaseModel):
    application_id: UUID  # Link to mortgage application
    borrower_data: BorrowerData  # Extracted from application
    property_data: PropertyData
    loan_data: LoanData
    existing_debts: List[DebtData] = []
    policy_version: str = "v1.0"  # Policy rule set version
    
    class BorrowerData(BaseModel):
        gross_annual_income: Decimal  # Pre-validated, may be self-employed
        employment_type: Literal["salaried", "self_employed", "contractor"]
        credit_score: int  # 300-900
        date_of_birth: date  # For age-based rules, encrypted in storage
        is_first_time_homebuyer: bool
        
    class PropertyData(BaseModel):
        property_value: Decimal
        property_type: Literal["single_family", "condo", "multi_unit"]
        street_address: str  # For audit only, not persisted
        
    class LoanData(BaseModel):
        mortgage_amount: Decimal
        contract_rate: Decimal  # Annual %
        amortization_years: int  # 5-30
        payment_frequency: Literal["monthly", "bi_weekly", "accelerated_bi_weekly"]
        
    class DebtData(BaseModel):
        monthly_payment: Decimal
        debt_type: Literal["credit_card", "auto_loan", "student_loan", "other_mortgage"]
        balance: Decimal
```

**Response Schema (201 Created):**
```python
class DecisionEvaluateResponse(BaseModel):
    application_id: UUID
    decision: Literal["approved", "declined", "exception", "conditional"]
    confidence_score: Decimal  # 0.00 to 1.00
    ratios: RatioBreakdown
    cmhc_required: bool
    cmhc_premium_amount: Decimal | None
    stress_test_rate: Decimal
    policy_flags: List[PolicyFlag]
    exceptions: List[DecisionException]
    audit_trail: AuditSummary
    evaluated_at: datetime
    policy_version: str
    
    class RatioBreakdown(BaseModel):
        gds: Decimal  # Gross Debt Service ratio (%)
        tds: Decimal  # Total Debt Service ratio (%)
        ltv: Decimal  # Loan-to-Value ratio (%)
        qualifying_payment: Decimal  # PITH at stress test rate
        gross_monthly_income: Decimal
        
    class PolicyFlag(BaseModel):
        code: str  # e.g., "HIGH_LTV", "LOW_CREDIT_SCORE"
        severity: Literal["info", "warning", "critical"]
        message: str
        
    class DecisionException(BaseModel):
        rule_id: str
        rule_name: str
        severity: Literal["minor", "major", "critical"]
        description: str
        bypassable: bool  # For conditional approvals
        
    class AuditSummary(BaseModel):
        rules_evaluated: int
        rules_passed: int
        rules_failed: int
        timestamp: datetime
        model_version: str
```

**Error Responses:**
| HTTP Status | Error Code | Detail Message | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 400 | DECISION_001 | "Invalid application_id format" | Malformed UUID |
| 404 | DECISION_002 | "Application not found" | application_id doesn't exist |
| 422 | DECISION_003 | "borrower_data.gross_annual_income: must be positive" | Validation failure |
| 422 | DECISION_004 | "loan_data.contract_rate: must be between 0.01 and 25.0" | Rate out of bounds |
| 409 | DECISION_005 | "Decision already exists for application" | Duplicate evaluation attempt |

---

### 1.2 GET /api/v1/decision/{application_id}
Retrieve the latest decision record for an application.

**Authentication:** Authenticated (JWT, `underwriter`, `broker`, or `system` role)  
**Authorization:** Tenant isolation enforced

**Path Parameter:** `application_id: UUID`

**Response Schema (200 OK):**
```python
class DecisionGetResponse(BaseModel):
    application_id: UUID
    decision: Literal["approved", "declined", "exception", "conditional"]
    confidence_score: Decimal
    ratios: RatioBreakdown  # Same as above
    cmhc_required: bool
    cmhc_premium_amount: Decimal | None
    stress_test_rate: Decimal
    policy_flags: List[PolicyFlag]
    exceptions: List[DecisionException]
    evaluated_at: datetime
    policy_version: str
    retention_expiry_date: date  # FINTRAC 5-year rule
```

**Error Responses:**
| HTTP Status | Error Code | Detail Message |
|-------------|------------|----------------|
| 400 | DECISION_001 | "Invalid application_id format" |
| 404 | DECISION_006 | "Decision not found for application" |

---

### 1.3 GET /api/v1/decision/{application_id}/audit
Retrieve full immutable audit trail for regulatory examination.

**Authentication:** Authenticated (JWT, `compliance_officer` or `admin` role only)  
**Audit:** Log access with structlog (who, when, why)

**Path Parameter:** `application_id: UUID`

**Response Schema (200 OK):**
```python
class DecisionAuditResponse(BaseModel):
    application_id: UUID
    decision_snapshot: DecisionGetResponse
    full_audit_log: List[AuditLogEntry]
    
    class AuditLogEntry(BaseModel):
        event_type: Literal["evaluation_started", "rule_evaluated", "ratio_calculated", "decision_rendered"]
        timestamp: datetime
        actor: str  # "system" or user_id
        details: dict  # Rule inputs/outputs, never contains PII
        model_version: str
        correlation_id: UUID
```

**Error Responses:**
| HTTP Status | Error Code | Detail Message |
|-------------|------------|----------------|
| 400 | DECISION_001 | "Invalid application_id format" |
| 404 | DECISION_007 | "Audit trail not found" |
| 403 | AUTH_003 | "Insufficient permissions" |

---

## 2. Models & Database

### 2.1 `decisions` Table
Stores the final decision result. Immutable after creation (FINTRAC compliance).

| Column | Type | Constraints | Index | Description |
|--------|------|-------------|-------|-------------|
| `id` | UUID | PK, default gen_random_uuid() | Primary | Decision record ID |
| `application_id` | UUID | NOT NULL, unique | Composite with created_at | Foreign key to applications |
| `tenant_id` | UUID | NOT NULL | BTREE | Multi-tenant isolation |
| `decision` | VARCHAR(20) | NOT NULL, check in ('approved','declined','exception','conditional') | BTREE | Final decision |
| `confidence_score` | DECIMAL(5,4) | NOT NULL, check 0-1 | - | Model confidence |
| `gds_ratio` | DECIMAL(5,2) | NOT NULL | - | GDS percentage |
| `tds_ratio` | DECIMAL(5,2) | NOT NULL | - | TDS percentage |
| `ltv_ratio` | DECIMAL(5,2) | NOT NULL | - | LTV percentage |
| `qualifying_payment` | DECIMAL(12,2) | NOT NULL | - | PITH at stress rate |
| `gross_monthly_income` | DECIMAL(12,2) | NOT NULL | - | For audit |
| `cmhc_required` | BOOLEAN | NOT NULL, default false | BTREE | Insurance flag |
| `cmhc_premium_amount` | DECIMAL(12,2) | NULL | - | Premium $ |
| `stress_test_rate` | DECIMAL(5,4) | NOT NULL | - | Qualifying rate % |
| `policy_version` | VARCHAR(20) | NOT NULL | BTREE | Rules version |
| `model_version` | VARCHAR(20) | NOT NULL | - | Engine version |
| `evaluated_at` | TIMESTAMPTZ | NOT NULL, default now() | BTREE | Decision timestamp |
| `retention_expiry_date` | DATE | NOT NULL, index | BTREE | FINTRAC 5-year retention |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() | - | Audit field |
| `created_by` | VARCHAR(100) | NOT NULL | - | "system" or user_id |

**Indexes:**
- `idx_decisions_application_id_created_at` (application_id, created_at DESC) for latest lookup
- `idx_decisions_tenant_id` (tenant_id) for tenant isolation
- `idx_decisions_retention_expiry_date` (retention_expiry_date) for purge job

**Constraints:**
- `decision_records_immutable`: TRIGGER preventing UPDATE/DELETE after creation
- `chk_confidence_score_range`: CHECK (confidence_score BETWEEN 0.0 AND 1.0)

---

### 2.2 `decision_audit_logs` Table
Immutable append-only audit trail (FINTRAC 5-year retention).

| Column | Type | Constraints | Index | Description |
|--------|------|-------------|-------|-------------|
| `id` | UUID | PK | Primary | Log entry ID |
| `decision_id` | UUID | NOT NULL, FK decisions.id | BTREE | Parent decision |
| `application_id` | UUID | NOT NULL | BTREE | Denormalized for queries |
| `correlation_id` | UUID | NOT NULL | BTREE | OpenTelemetry trace |
| `event_type` | VARCHAR(50) | NOT NULL | BTREE | Event classification |
| `actor` | VARCHAR(100) | NOT NULL | - | "system" or user_id |
| `details_json` | JSONB | NOT NULL, default '{}' | GIN | Rule inputs/outputs (no PII) |
| `model_version` | VARCHAR(20) | NOT NULL | - | Engine version at time |
| `timestamp` | TIMESTAMPTZ | NOT NULL, default now() | BTREE | Event time |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() | - | Audit field |

**Indexes:**
- `idx_audit_logs_decision_id_timestamp` (decision_id, timestamp)
- `idx_audit_logs_correlation_id` (correlation_id) for tracing

**Constraints:**
- `audit_logs_immutable`: TRIGGER preventing UPDATE/DELETE

---

### 2.3 `policy_rules` Table
Deterministic rule definitions. Version-controlled, loaded into memory at startup.

| Column | Type | Constraints | Index | Description |
|--------|------|-------------|-------|-------------|
| `id` | UUID | PK | Primary | Rule ID |
| `rule_id` | VARCHAR(50) | NOT NULL, unique | BTREE | Human-readable ID (e.g., "GDS_LIMIT") |
| `policy_version` | VARCHAR(20) | NOT NULL, composite unique | BTREE | Version grouping |
| `rule_name` | VARCHAR(200) | NOT NULL | - | Display name |
| `rule_category` | VARCHAR(50) | NOT NULL, check in ('ratio','credit','income','property','fraud') | BTREE | Category |
| `severity` | VARCHAR(20) | NOT NULL, check in ('minor','major','critical') | BTREE | Impact on decision |
| `bypassable` | BOOLEAN | NOT NULL, default false | BTREE | Allows conditional approval |
| `evaluation_order` | INTEGER | NOT NULL, unique per version | BTREE | Deterministic execution |
| `python_expression` | TEXT | NOT NULL | - | Safe eval expression |
| `decline_reason_template` | TEXT | NULL | - | f-string for decline messages |
| `created_at` | TIMESTAMPTZ | NOT NULL | - | Audit field |
| `updated_at` | TIMESTAMPTZ | NOT NULL | - | Audit field |

**Indexes:**
- `idx_policy_rules_version_order` (policy_version, evaluation_order)
- `idx_policy_rules_category` (rule_category)

**Example Rows:**
```sql
INSERT INTO policy_rules VALUES 
('gds_limit', 'v1.0', 'GDS Ratio ≤ 39%', 'ratio', 'critical', false, 10, 
 'ratios.gds <= Decimal("39.00")', 'GDS ratio {ratios.gds}% exceeds 39% limit'),
('min_credit_score', 'v1.0', 'Minimum Credit Score 600', 'credit', 'critical', false, 5,
 'borrower.credit_score >= 600', 'Credit score {borrower.credit_score} below minimum 600'),
('self_employed_income', 'v1.0', 'Self-Employed Income Verification', 'income', 'major', true, 15,
 'borrower.employment_type != "self_employed" or borrower.income_verified == true',
 'Self-employed income not verified')
```

---

### 2.4 `decision_flags` Table
Normalized storage of policy flags raised during evaluation.

| Column | Type | Constraints | Index | Description |
|--------|------|-------------|-------|-------------|
| `id` | UUID | PK | Primary | Flag ID |
| `decision_id` | UUID | NOT NULL, FK decisions.id | BTREE | Parent decision |
| `rule_id` | VARCHAR(50) | NOT NULL | BTREE | Policy rule reference |
| `severity` | VARCHAR(20) | NOT NULL | BTREE | Flag severity |
| `message` | TEXT | NOT NULL | - | Human-readable flag |
| `created_at` | TIMESTAMPTZ | NOT NULL | - | Audit field |

**Indexes:**
- `idx_flags_decision_id` (decision_id)

---

## 3. Business Logic

### 3.1 Decision Engine Algorithm

```python
async def evaluate_application(
    application_id: UUID,
    borrower_data: BorrowerData,
    property_data: PropertyData,
    loan_data: LoanData,
    existing_debts: List[DebtData],
    policy_version: str
) -> DecisionResult:
    
    # 1. Initialize audit context (correlation_id from FastAPI request)
    audit = AuditTrail(correlation_id=correlation_id)
    
    # 2. Load policy rules for version (cached in Redis, fallback to DB)
    rules = await policy_repository.get_rules(policy_version)
    
    # 3. Calculate financial ratios (OSFI B-20 compliant)
    ratios = await calculate_ratios(
        borrower_data, loan_data, property_data, existing_debts
    )
    
    # 4. Evaluate rules in deterministic order
    flags = []
    exceptions = []
    passed = 0
    failed = 0
    
    for rule in rules:
        try:
            result = await evaluate_rule(rule, borrower_data, ratios, property_data)
            audit.log_rule_evaluation(rule.rule_id, result, inputs=safe_inputs)
            
            if result is True:
                passed += 1
            else:
                failed += 1
                flag = PolicyFlag.from_rule(rule)
                flags.append(flag)
                
                if rule.severity == "critical" and not rule.bypassable:
                    exceptions.append(DecisionException.from_rule(rule))
                    
        except Exception as e:
            # Rule evaluation error - log but don't fail entire decision
            audit.log_rule_error(rule.rule_id, str(e))
            flags.append(PolicyFlag(
                code="RULE_EVAL_ERROR",
                severity="critical",
                message=f"Rule {rule.rule_id} failed to evaluate"
            ))
    
    # 5. Determine decision and confidence
    decision, confidence = render_decision(
        exceptions, flags, ratios, borrower_data
    )
    
    # 6. Calculate CMHC insurance if required
    cmhc_required, premium = calculate_cmhc_premium(ratios.ltv, loan_data.mortgage_amount)
    
    # 7. Persist immutable decision record
    decision_record = await repository.create_decision(
        application_id=application_id,
        decision=decision,
        confidence_score=confidence,
        ratios=ratios,
        cmhc_required=cmhc_required,
        cmhc_premium_amount=premium,
        stress_test_rate=ratios.stress_test_rate,
        policy_flags=flags,
        exceptions=exceptions,
        policy_version=policy_version,
        audit_trail=audit
    )
    
    # 8. Emit OpenTelemetry span with decision attributes (no PII)
    tracer.add_event("decision.evaluated", {
        "decision": decision,
        "confidence": float(confidence),
        "gds": float(ratios.gds),
        "tds": float(ratios.tds),
        "ltv": float(ratios.ltv)
    })
    
    return decision_record
```

### 3.2 Ratio Calculations (OSFI B-20)

**Stress Test Rate:**
```
qualifying_rate = max(contract_rate + 2%, 5.25%)
```
- `contract_rate`: Annual interest rate from loan_data (Decimal)
- Result stored as Decimal(5,4) (e.g., 7.2500)

**Gross Debt Service (GDS):**
```
PITH = Principal + Interest + Taxes + Heating
GDS = (PITH / gross_monthly_income) × 100
```
- **PITH Calculation:**
  - Principal + Interest: Calculated using stress test rate, amortization, payment frequency
  - Taxes: `property_data.annual_property_tax / 12`
  - Heating: Standard $100/month (configurable via policy rule)
- **Gross Monthly Income:**
  - Salaried: `gross_annual_income / 12`
  - Self-Employed: Two-year average (`(year1 + year2) / 2 / 12`) with add-backs (see 3.4)
- **Threshold:** GDS ≤ 39% (hard fail if exceeded and not bypassable)

**Total Debt Service (TDS):**
```
TDS = ((PITH + sum(monthly_debt_payments)) / gross_monthly_income) × 100
```
- **Monthly Debt Payments:** Sum of all `existing_debts.monthly_payment`
- **Threshold:** TDS ≤ 44% (hard fail if exceeded and not bypassable)

**Loan-to-Value (LTV):**
```
LTV = (mortgage_amount / property_value) × 100
```
- **Thresholds:**
  - Insured: LTV ≤ 95%
  - Conventional: LTV ≤ 80%
- **Precision:** Use Decimal with 2 decimal places; no rounding until final display

**Audit Logging:** Every ratio calculation step logged to `decision_audit_logs` with inputs and outputs (no PII).

---

### 3.3 Decision Rendering Logic

```python
def render_decision(
    exceptions: List[DecisionException],
    flags: List[PolicyFlag],
    ratios: RatioBreakdown,
    borrower_data: BorrowerData
) -> Tuple[Decision, Decimal]:
    
    critical_non_bypassable = [
        e for e in exceptions 
        if e.severity == "critical" and not e.bypassable
    ]
    
    critical_bypassable = [
        e for e in exceptions 
        if e.severity == "critical" and e.bypassable
    ]
    
    # Decision tree
    if len(critical_non_bypassable) == 0 and len(critical_bypassable) == 0:
        # No critical exceptions → Approved
        decision = "approved"
        confidence = Decimal("1.00")
        
    elif len(critical_non_bypassable) == 0 and len(critical_bypassable) > 0:
        # Only bypassable critical exceptions → Conditional approval
        decision = "conditional"
        confidence = Decimal("0.85") - (Decimal("0.05") * len(critical_bypassable))
        
    elif len(critical_non_bypassable) >= 3:
        # 3+ hard failures → Declined
        decision = "declined"
        confidence = Decimal("0.95")
        
    else:
        # 1-2 hard failures → Exception (manual review)
        decision = "exception"
        confidence = Decimal("0.70")
    
    return decision, max(Decimal("0.00"), min(Decimal("1.00"), confidence))
```

---

### 3.4 Self-Employed Income Calculation Rules

**Eligibility:** Must have 2+ years of documented income (T1 General, NOA).

**Calculation:**
```
gross_annual_income = (
    (year_1_net_income + year_2_net_income) / 2
    + add_backs_annual
)

add_backs_annual = sum([
    depreciation_expense,
    business_use_of_home * 0.50,  # 50% of home office
    interest_expense * 0.25,  # 25% of business interest
])
```

**Validation Rules:**
- Minimum 2-year average income: $30,000 CAD
- Maximum add-backs: 15% of net income
- Must verify via `income_verified` boolean flag from application

**Policy Flag:** If `employment_type == "self_employed"` and `income_verified == false`, raise `SELF_EMP_UNVERIFIED` exception (severity: major, bypassable: true).

---

### 3.5 Decline Reason Prioritization

When `decision == "declined"`, sort exceptions by:

1. **Critical Non-Bypassable** (descending severity)
   - `GDS_EXCEEDED` (code: GDS_LIMIT)
   - `TDS_EXCEEDED` (code: TDS_LIMIT)
   - `LTV_EXCEEDED` (code: LTV_LIMIT)
   - `CREDIT_SCORE_TOO_LOW` (code: MIN_CREDIT_SCORE)

2. **Major Non-Bypassable**
   - `INSUFFICIENT_INCOME` (code: MIN_INCOME)
   - `PROPERTY_TYPE_EXCLUDED` (code: PROPERTY_TYPE)

3. **Minor Non-Bypassable**
   - `INVALID_AMORTIZATION` (code: AMORTIZATION_RANGE)

**Display Logic:** Return top 3 exceptions only to client (prevents information overload). Full list always in audit trail.

---

### 3.6 Conditional Approval Criteria

Decision = **"conditional"** when:
- Only bypassable critical exceptions exist
- Borrower meets all hard ratio limits (GDS, TDS, LTV)
- Credit score ≥ 600
- No fraud flags

**Common Conditions:**
- `SELF_EMP_UNVERIFIED`: Require T1 General + NOA before closing
- `HIGH_LTV`: Require proof of down payment source
- `DEBT_RATIO_ELEVATED`: Require debt payoff letter

**Workflow:** Conditions must be cleared within 30 days, otherwise decision auto-expires and reverts to "declined".

---

## 4. Migrations

### Migration `001_create_decision_service_tables.py`

```python
def upgrade():
    # decisions table
    op.create_table(
        'decisions',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('application_id', UUID(), nullable=False),
        sa.Column('tenant_id', UUID(), nullable=False),
        sa.Column('decision', sa.VARCHAR(20), nullable=False),
        sa.Column('confidence_score', sa.DECIMAL(precision=5, scale=4), nullable=False),
        sa.Column('gds_ratio', sa.DECIMAL(precision=5, scale=2), nullable=False),
        sa.Column('tds_ratio', sa.DECIMAL(precision=5, scale=2), nullable=False),
        sa.Column('ltv_ratio', sa.DECIMAL(precision=5, scale=2), nullable=False),
        sa.Column('qualifying_payment', sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column('gross_monthly_income', sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column('cmhc_required', sa.BOOLEAN(), nullable=False),
        sa.Column('cmhc_premium_amount', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('stress_test_rate', sa.DECIMAL(precision=5, scale=4), nullable=False),
        sa.Column('policy_version', sa.VARCHAR(20), nullable=False),
        sa.Column('model_version', sa.VARCHAR(20), nullable=False),
        sa.Column('evaluated_at', sa.TIMESTAMPTZ(), nullable=False),
        sa.Column('retention_expiry_date', sa.DATE(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMPTZ(), nullable=False),
        sa.Column('created_by', sa.VARCHAR(100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('application_id'),
        sa.CheckConstraint('confidence_score BETWEEN 0.0 AND 1.0', name='chk_confidence_score_range'),
        sa.CheckConstraint("decision IN ('approved','declined','exception','conditional')", name='chk_decision_enum')
    )
    
    # decision_audit_logs table
    op.create_table(
        'decision_audit_logs',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('decision_id', UUID(), nullable=False),
        sa.Column('application_id', UUID(), nullable=False),
        sa.Column('correlation_id', UUID(), nullable=False),
        sa.Column('event_type', sa.VARCHAR(50), nullable=False),
        sa.Column('actor', sa.VARCHAR(100), nullable=False),
        sa.Column('details_json', sa.JSONB(), nullable=False),
        sa.Column('model_version', sa.VARCHAR(20), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMPTZ(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMPTZ(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['decision_id'], ['decisions.id'], ondelete='CASCADE')
    )
    
    # policy_rules table (seeded)
    op.create_table(
        'policy_rules',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('rule_id', sa.VARCHAR(50), nullable=False),
        sa.Column('policy_version', sa.VARCHAR(20), nullable=False),
        sa.Column('rule_name', sa.VARCHAR(200), nullable=False),
        sa.Column('rule_category', sa.VARCHAR(50), nullable=False),
        sa.Column('severity', sa.VARCHAR(20), nullable=False),
        sa.Column('bypassable', sa.BOOLEAN(), nullable=False),
        sa.Column('evaluation_order', sa.INTEGER(), nullable=False),
        sa.Column('python_expression', sa.TEXT(), nullable=False),
        sa.Column('decline_reason_template', sa.TEXT(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMPTZ(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rule_id', 'policy_version'),
        sa.CheckConstraint("severity IN ('minor','major','critical')", name='chk_severity_enum')
    )
    
    # decision_flags table
    op.create_table(
        'decision_flags',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('decision_id', UUID(), nullable=False),
        sa.Column('rule_id', sa.VARCHAR(50), nullable=False),
        sa.Column('severity', sa.VARCHAR(20), nullable=False),
        sa.Column('message', sa.TEXT(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMPTZ(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['decision_id'], ['decisions.id'], ondelete='CASCADE')
    )
    
    # Create indexes
    op.create_index('idx_decisions_application_id_created_at', 'decisions', ['application_id', 'created_at'])
    op.create_index('idx_decisions_tenant_id', 'decisions', ['tenant_id'])
    op.create_index('idx_decisions_retention_expiry_date', 'decisions', ['retention_expiry_date'])
    op.create_index('idx_audit_logs_decision_id_timestamp', 'decision_audit_logs', ['decision_id', 'timestamp'])
    op.create_index('idx_audit_logs_correlation_id', 'decision_audit_logs', ['correlation_id'])
    op.create_index('idx_policy_rules_version_order', 'policy_rules', ['policy_version', 'evaluation_order'])
    
    # Create immutability triggers
    op.execute("""
        CREATE TRIGGER decisions_immutable
        BEFORE UPDATE OR DELETE ON decisions
        FOR EACH ROW EXECUTE FUNCTION prevent_mutation();
        
        CREATE TRIGGER audit_logs_immutable
        BEFORE UPDATE OR DELETE ON decision_audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_mutation();
    """)

def downgrade():
    op.drop_table('decision_flags')
    op.drop_table('policy_rules')
    op.drop_table('decision_audit_logs')
    op.drop_table('decisions')
```

### Migration `002_seed_policy_rules_v1.py`
Seed initial OSFI B-20 compliant rule set.

### Migration `003_add_self_employed_income_rule.py`
Add rule for self-employed income verification (bypassable).

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test:** Qualifying rate calculation logged in `decision_audit_logs` with contract_rate and result
- **Hard Limits:** GDS ≤ 39%, TDS ≤ 44% enforced as critical non-bypassable rules
- **Auditability:** Every ratio component (P, I, T, H) stored in `details_json` of audit log
- **Immutability:** Decision records cannot be updated or deleted after creation

### 5.2 FINTRAC Compliance
- **Audit Trail:** All decision evaluations captured in `decision_audit_logs` with correlation_id
- **Retention:** `retention_expiry_date` auto-calculated as `evaluated_at + 5 years`
- **PII Handling:** No SIN, DOB, or full address stored in decision service tables (only application_id reference)
- **Access Logging:** All `/audit` endpoint access logged with structlog for examination trails

### 5.3 CMHC Insurance Logic
```python
def calculate_cmhc_premium(ltv: Decimal, mortgage_amount: Decimal) -> Tuple[bool, Decimal]:
    if ltv <= Decimal("80.00"):
        return False, Decimal("0.00")
    
    # Premium tiers (use Decimal for precision)
    if Decimal("80.01") <= ltv <= Decimal("85.00"):
        premium_rate = Decimal("0.0280")
    elif Decimal("85.01") <= ltv <= Decimal("90.00"):
        premium_rate = Decimal("0.0310")
    elif Decimal("90.01") <= ltv <= Decimal("95.00"):
        premium_rate = Decimal("0.0400")
    else:
        raise DecisionBusinessRuleError("LTV exceeds maximum insurable limit")
    
    premium = mortgage_amount * premium_rate
    return True, premium.quantize(Decimal("0.01"))
```

### 5.4 PIPEDA Data Handling
- **Encryption:** No PII fields (SIN, DOB) stored in decision service; reference only `application_id`
- **Data Minimization:** `decision_audit_logs.details_json` must never include PII; use hashed IDs only
- **Logging:** structlog configured with `drop_fields=["sin", "dob", "income"]` filter
- **Error Messages:** Never include income values or credit scores in error responses

### 5.5 Authentication & Authorization
```python
# FastAPI dependencies
async def require_underwriter(token: JWTToken = Depends(verify_token)):
    if "underwriter" not in token.roles and "system" not in token.roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

async def require_compliance_officer(token: JWTToken = Depends(verify_token)):
    if "compliance_officer" not in token.roles:
        raise HTTPException(status_code=403, detail="Compliance access only")
```

**Endpoint Protection:**
- `POST /evaluate`: `@require_underwriter`
- `GET /{application_id}`: `@require_underwriter` + tenant isolation
- `GET /{application_id}/audit`: `@require_compliance_officer` + audit logging

---

## 6. Error Codes & HTTP Responses

### Module Exception Hierarchy

| Exception Class | HTTP Status | Error Code | Message Pattern | Retryable |
|-----------------|-------------|------------|-----------------|-----------|
| `DecisionNotFoundError` | 404 | DECISION_006 | "Decision for application {id} not found" | No |
| `DecisionValidationError` | 422 | DECISION_003 | "{field}: {reason}" | No |
| `DecisionBusinessRuleError` | 409 | DECISION_005 | "{rule} violated: {detail}" | No |
| `PolicyRuleEvaluationError` | 500 | DECISION_008 | "Rule engine error: {rule_id}" | Yes |
| `RatioCalculationError` | 422 | DECISION_009 | "Cannot calculate {ratio}: {reason}" | No |
| `DuplicateDecisionError` | 409 | DECISION_005 | "Decision already exists for application {id}" | No |

### Exception Definitions

```python
# modules/decision_service/exceptions.py
from common.exceptions import AppException

class DecisionNotFoundError(AppException):
    status_code = 404
    error_code = "DECISION_006"
    message_template = "Decision for application {id} not found"

class DecisionValidationError(AppException):
    status_code = 422
    error_code = "DECISION_003"
    message_template = "{field}: {reason}"

class DecisionBusinessRuleError(AppException):
    status_code = 409
    error_code = "DECISION_005"
    message_template = "{rule} violated: {detail}"

class PolicyRuleEvaluationError(AppException):
    status_code = 500
    error_code = "DECISION_008"
    message_template = "Rule engine error: {rule_id}"
    is_retryable = True

class RatioCalculationError(AppException):
    status_code = 422
    error_code = "DECISION_009"
    message_template = "Cannot calculate {ratio}: {reason}"
```

### Global Error Handler

```python
# modules/decision_service/routes.py
@router.exception_handler(DecisionBusinessRuleError)
async def handle_business_rule_error(request: Request, exc: DecisionBusinessRuleError):
    logger.warning(
        "business_rule_violated",
        error_code=exc.error_code,
        application_id=request.path_params.get("application_id"),
        detail=exc.detail,
        correlation_id=request.state.correlation_id
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "rule_violated": exc.detail.get("rule_id"),
            "suggestion": "Review policy rules or request manual exception review"
        }
    )
```

---

## 7. Additional Design Considerations

### 7.1 Performance
- **Caching:** Policy rules cached in Redis with 24h TTL; reload on version change
- **Async DB:** All repository methods use `asyncpg` with connection pooling
- **Batch Evaluation:** Support for `POST /decision/evaluate/batch` (future enhancement)

### 7.2 Testing Strategy
- **Unit Tests:** Mock policy rules, test calculation edge cases (LTV 80.01%, GDS 39.01%)
- **Integration Tests:** Full flow with PostgreSQL, verify immutability triggers
- **Compliance Tests:** Verify FINTRAC retention dates, audit log completeness
- **Load Tests:** 1000 decisions/sec target; use pytest-benchmark

### 7.3 Monitoring & Observability
- **Metrics:** Prometheus counters for `decision_{type}_total`, `decision_evaluation_duration_seconds`
- **Alerts:** Alert if `decision_declined_total` > 70% or `policy_rule_evaluation_errors_total` > 5%
- **Tracing:** Each rule evaluation gets a Span; correlation_id propagated via headers

### 7.4 Future Enhancements
- **Rule DSL:** Replace `python_expression` with safer DSL (e.g., JSONLogic)
- **Machine Learning:** Confidence score augmentation with ML model (separate service)
- **gRPC Endpoint:** For high-throughput batch evaluation from underwriting orchestrator

---