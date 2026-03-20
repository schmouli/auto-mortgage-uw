# Design: Decision Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Decision Service Module Design Plan

**File:** `docs/design/decision-service.md`

---

## 1. Endpoints

### `POST /api/v1/decision/evaluate`
Runs the underwriting decision engine against a submitted mortgage application.

**Authentication:** Authenticated (JWT Bearer token with `underwrite:execute` scope)

**Request Body Schema:**
```python
class DecisionEvaluateRequest(BaseModel):
    application_id: UUID  # Reference to application in Application module
    borrower_profile: BorrowerProfileDTO
    property_details: PropertyDetailsDTO
    loan_details: LoanDetailsDTO
    policy_version: str = "v1.2024"  # Policy rule version to apply
    
    class BorrowerProfileDTO(BaseModel):
        gross_annual_income: Decimal  # Must be pre-validated income
        monthly_debt_obligations: Decimal  # Sum of all non-housing debt payments
        credit_score: int  # 300-900
        employment_type: Literal["salaried", "self_employed", "contract"]
        is_first_time_homebuyer: bool = False
        
    class PropertyDetailsDTO(BaseModel):
        property_value: Decimal  # Appraised property value
        property_type: Literal["single_family", "condo", "townhouse", "multi_unit"]
        property_tax_annual: Decimal
        
    class LoanDetailsDTO(BaseModel):
        requested_amount: Decimal
        amortization_years: int  # 5-30
        contract_rate: Decimal  # Annual interest rate
        is_insured: bool = False
        down_payment_amount: Decimal
```

**Response Schema (200 OK):**
```python
class DecisionResponse(BaseModel):
    application_id: UUID
    decision: Literal["approved", "declined", "exception"]
    confidence_score: Decimal  # 0.00 to 1.00
    ratios: RatioBreakdownDTO
    cmhc_required: bool
    stress_test_rate: Decimal
    policy_flags: List[str]  # e.g., ["HIGH_LTV", "LOW_CREDIT_SCORE"]
    exceptions: List[ExceptionDetailDTO]
    audit_trail: AuditSummaryDTO
    
    class RatioBreakdownDTO(BaseModel):
        gds: Decimal  # Gross Debt Service ratio (%)
        tds: Decimal  # Total Debt Service ratio (%)
        ltv: Decimal  # Loan-to-Value ratio (%)
        qualifying_payment: Decimal  # Monthly payment at stress test rate
        monthly_income: Decimal  # Gross monthly income
        
    class ExceptionDetailDTO(BaseModel):
        rule_id: str
        severity: Literal["info", "warning", "critical"]
        message: str
        overrideable: bool = False
        
    class AuditSummaryDTO(BaseModel):
        rules_evaluated: int
        timestamp: datetime
        model_version: str
        evaluated_by: str  # User ID from JWT
```

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger Condition |
|-------------|------------|--------|-------------------|
| 400 | DECISION_001 | "Application ID {id} already evaluated" | Duplicate evaluation attempt |
| 422 | DECISION_002 | "gross_annual_income: must be positive" | Invalid income validation |
| 422 | DECISION_003 | "property_value: must be ≥ $1,000" | Invalid property value |
| 404 | DECISION_004 | "Application {id} not found" | Application ID doesn't exist in system |
| 409 | DECISION_005 | "Policy version v1.2024 is deprecated" | Unsupported policy version |

---

### `GET /api/v1/decision/{application_id}`
Retrieves the most recent decision record for an application.

**Authentication:** Authenticated (JWT Bearer token with `underwrite:read` scope)

**Path Parameters:**
- `application_id`: UUID

**Response Schema (200 OK):** Same as `DecisionResponse` above

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger Condition |
|-------------|------------|--------|-------------------|
| 404 | DECISION_006 | "Decision for application {id} not found" | No decision exists |

---

### `GET /api/v1/decision/{application_id}/audit`
Retrieves the complete immutable audit trail for regulatory examination.

**Authentication:** Admin-only (JWT Bearer token with `audit:read` scope)

**Path Parameters:**
- `application_id`: UUID

**Response Schema (200 OK):**
```python
class DecisionAuditTrailResponse(BaseModel):
    application_id: UUID
    decision: DecisionResponse
    rule_evaluations: List[RuleEvaluationDTO]
    calculations: CalculationTraceDTO
    
    class RuleEvaluationDTO(BaseModel):
        rule_id: str
        rule_name: str
        condition: str  # e.g., "gds <= 39.0"
        result: bool
        timestamp: datetime
        evaluated_by: str
        
    class CalculationTraceDTO(BaseModel):
        stress_test_rate: Decimal
        qualifying_payment: Decimal
        gds_numerator: Decimal  # PITH
        gds_denominator: Decimal  # Gross monthly income
        tds_numerator: Decimal  # PITH + debts
        tds_denominator: Decimal  # Gross monthly income
        ltv_numerator: Decimal  # Loan amount
        ltv_denominator: Decimal  # Property value
```

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger Condition |
|-------------|------------|--------|-------------------|
| 403 | AUTH_003 | "Insufficient permissions for audit access" | Non-admin user |
| 404 | DECISION_007 | "Audit trail for {id} not found" | No audit exists |

---

## 2. Models & Database

### `decision_models.py` - ORM Models

```python
class DecisionModel(Base):
    """Primary decision record - immutable per FINTRAC requirements"""
    __tablename__ = "decisions"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # approved, declined, exception
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    cmhc_required: Mapped[bool] = mapped_column(nullable=False)
    stress_test_rate: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    
    # Audit fields (FINTRAC immutable)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)  # User ID from JWT
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)  # Only for corrections
    
    # Relationships
    policy_flags: Mapped[List["PolicyFlagModel"]] = relationship(back_populates="decision")
    exceptions: Mapped[List["DecisionExceptionModel"]] = relationship(back_populates="decision")
    rule_audits: Mapped[List["DecisionRuleAuditModel"]] = relationship(back_populates="decision")
    
    # Indexes
    __table_args__ = (
        Index("idx_decisions_application_created", "application_id", "created_at"),
        Index("idx_decisions_decision_date", "decision", "created_at"),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="chk_confidence_score_range"),
        CheckConstraint("gds_ratio >= 0 AND gds_ratio <= 100", name="chk_gds_range"),
        CheckConstraint("tds_ratio >= 0 AND tds_ratio <= 100", name="chk_tds_range"),
        CheckConstraint("ltv_ratio >= 0 AND ltv_ratio <= 100", name="chk_ltv_range"),
    )


class DecisionRuleAuditModel(Base):
    """Immutable audit trail of every rule evaluation"""
    __tablename__ = "decision_rule_audits"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False)  # Human-readable condition
    result: Mapped[bool] = mapped_column(nullable=False)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Relationships
    decision: Mapped["DecisionModel"] = relationship(back_populates="rule_audits")
    
    __table_args__ = (
        Index("idx_rule_audits_decision_rule", "decision_id", "rule_id"),
    )


class DecisionExceptionModel(Base):
    """Captures policy exceptions and override requests"""
    __tablename__ = "decision_exceptions"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # info, warning, critical
    message: Mapped[str] = mapped_column(Text, nullable=False)
    overrideable: Mapped[bool] = mapped_column(nullable=False, default=False)
    overridden: Mapped[bool] = mapped_column(nullable=False, default=False)
    overridden_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Relationships
    decision: Mapped["DecisionModel"] = relationship(back_populates="exceptions")
    
    __table_args__ = (
        Index("idx_exceptions_decision_severity", "decision_id", "severity"),
        CheckConstraint(
            "NOT (overridden = true AND overridden_by IS NULL)",
            name="chk_override_consistency"
        ),
    )


class PolicyFlagModel(Base):
    """System-generated policy markers for risk categorization"""
    __tablename__ = "policy_flags"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id"), nullable=False, index=True)
    flag_code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "HIGH_LTV"
    flag_name: Mapped[str] = mapped_column(String(255), nullable=False)
    flag_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Additional context
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    decision: Mapped["DecisionModel"] = relationship(back_populates="policy_flags")
    
    __table_args__ = (
        Index("idx_flags_decision_code", "decision_id", "flag_code"),
        UniqueConstraint("decision_id", "flag_code", name="uq_decision_flag"),
    )
```

---

## 3. Business Logic

### Core Calculation Engine (`services.py`)

**Stress Test Rate Calculation (OSFI B-20)**
```python
def calculate_stress_test_rate(contract_rate: Decimal) -> Decimal:
    """
    OSFI B-20 Guideline: Qualifying rate = max(contract_rate + 2%, 5.25%)
    """
    stress_rate = contract_rate + Decimal("2.00")
    floor_rate = Decimal("5.25")
    qualifying_rate = max(stress_rate, floor_rate)
    
    # Audit logging per OSFI requirement
    logger.info(
        "stress_test_calculation",
        contract_rate=contract_rate,
        stress_rate=stress_rate,
        floor_rate=floor_rate,
        qualifying_rate=qualifying_rate
    )
    return qualifying_rate.quantize(Decimal("0.001"))
```

**GDS/TDS Calculation (OSFI B-20)**
```python
def calculate_service_ratios(
    gross_annual_income: Decimal,
    qualifying_payment: Decimal,
    monthly_debts: Decimal,
    annual_property_tax: Decimal
) -> tuple[Decimal, Decimal]:
    """
    GDS = (PITH) / Gross Monthly Income × 100
    TDS = (PITH + All Debts) / Gross Monthly Income × 100
    
    PITH = Principal + Interest + Taxes + Heat
    Heat estimate = $100/month (OSFI standard)
    """
    monthly_income = gross_annual_income / Decimal("12")
    monthly_property_tax = annual_property_tax / Decimal("12")
    heat_estimate = Decimal("100.00")
    
    pith = qualifying_payment + monthly_property_tax + heat_estimate
    
    gds = (pith / monthly_income) * Decimal("100")
    tds = ((pith + monthly_debts) / monthly_income) * Decimal("100")
    
    # Audit breakdown for regulatory examination
    logger.info(
        "ratio_calculation",
        monthly_income=monthly_income,
        pith=pith,
        qualifying_payment=qualifying_payment,
        monthly_property_tax=monthly_property_tax,
        heat_estimate=heat_estimate,
        monthly_debts=monthly_debts,
        gds=gds.quantize(Decimal("0.01")),
        tds=tds.quantize(Decimal("0.01"))
    )
    
    return gds.quantize(Decimal("0.01")), tds.quantize(Decimal("0.01"))
```

**LTV Calculation (CMHC)**
```python
def calculate_ltv(loan_amount: Decimal, property_value: Decimal) -> Decimal:
    """
    LTV = (Mortgage Amount / Property Value) × 100
    CMHC: No precision loss, use Decimal throughout
    """
    if property_value <= 0:
        raise DecisionValidationError("property_value must be positive")
    
    ltv = (loan_amount / property_value) * Decimal("100")
    return ltv.quantize(Decimal("0.01"))
```

**CMHC Insurance Requirement Logic**
```python
def determine_cmhc_requirement(
    ltv: Decimal,
    property_type: str,
    is_insured: bool
) -> tuple[bool, Decimal | None]:
    """
    CMHC Requirement: IF LTV > 80% THEN insurance_required = True
    Premium tiers based on LTV range:
    - 80.01-85%: 2.80%
    - 85.01-90%: 3.10%
    - 90.01-95%: 4.00%
    """
    if ltv <= Decimal("80.00"):
        return False, None
    
    if ltv > Decimal("95.00"):
        raise DecisionBusinessRuleError("LTV cannot exceed 95% for insured mortgages")
    
    # Determine premium tier
    if ltv <= Decimal("85.00"):
        premium_rate = Decimal("2.80")
    elif ltv <= Decimal("90.00"):
        premium_rate = Decimal("3.10")
    else:
        premium_rate = Decimal("4.00")
    
    return True, premium_rate.quantize(Decimal("0.01"))
```

### Decision Flow & State Machine

**Decision Rules Evaluation Order:**
1. **Hard Decline Rules** (non-overrideable)
   - Credit score < 600 → DECLINE (reason: "CREDIT_SCORE_TOO_LOW")
   - LTV > 95% → DECLINE (reason: "LTV_EXCEEDS_MAXIMUM")
   - Income validation failed → DECLINE (reason: "INSUFFICIENT_VERIFIED_INCOME")

2. **Ratio Validation (OSFI B-20)**
   - GDS > 39% → EXCEPTION (overrideable with senior underwriter approval)
   - TDS > 44% → EXCEPTION (overrideable with senior underwriter approval)
   - Both ratios ≤ thresholds → PASS

3. **Policy Flag Detection**
   - LTV 80.01-85% → Flag: "MEDIUM_LTV_RISK"
   - LTV 85.01-95% → Flag: "HIGH_LTV_RISK"
   - Credit score 600-650 → Flag: "LOW_CREDIT_TIER"
   - Self-employed < 2 years → Flag: "SHORT_EMPLOYMENT_HISTORY"

4. **Conditional Approval Criteria**
   - If EXCEPTION triggered but overrideable → "CONDITIONAL_APPROVAL" status
   - Requires additional conditions: co-signer, increased down payment, or rate premium

### Self-Employed Income Calculation Rules

```python
def calculate_self_employed_income(
    net_business_income: Decimal,
    two_year_average: bool = True,
    add_backs: List[Decimal] = None
) -> Decimal:
    """
    Self-employed income verification:
    - Use 2-year average of T1 General line 150 (net business income)
    - Add back non-cash expenses: depreciation, amortization
    - Deduct personal draws/dividends from corporation
    - Minimum 2-year history required unless exception granted
    """
    if two_year_average:
        # Requires two years of NOA documents
        validated_income = net_business_income * Decimal("0.85")  # 15% haircut for volatility
    else:
        raise DecisionBusinessRuleError("Self-employed < 2 years requires manual exception")
    
    if add_backs:
        for add_back in add_backs:
            validated_income += add_back
    
    logger.info(
        "self_employed_income_calculation",
        net_business_income=net_business_income,
        validated_income=validated_income.quantize(Decimal("0.01"))
    )
    return validated_income.quantize(Decimal("0.01"))
```

### Decline Reason Prioritization

When multiple decline conditions exist, prioritize in this order:
1. **CREDIT_SCORE_TOO_LOW** (highest priority)
2. **LTV_EXCEEDS_MAXIMUM**
3. **INSUFFICIENT_VERIFIED_INCOME**
4. **GDS_EXCEEDS_THRESHOLD**
5. **TDS_EXCEEDS_THRESHOLD**
6. **PROPERTY_TYPE_NOT_SUPPORTED**

Only the highest priority reason is returned to the client; all are logged in audit trail.

---

## 4. Migrations

### Alembic Migration: `create_decision_tables.py`

```python
def upgrade():
    # decisions table
    op.create_table(
        "decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("gds_ratio", sa.Numeric(5, 2), nullable=False),
        sa.Column("tds_ratio", sa.Numeric(5, 2), nullable=False),
        sa.Column("ltv_ratio", sa.Numeric(5, 2), nullable=False),
        sa.Column("cmhc_required", sa.Boolean(), nullable=False),
        sa.Column("stress_test_rate", sa.Numeric(5, 3), nullable=False),
        sa.Column("policy_version", sa.String(20), nullable=False),
        sa.Column("model_version", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.CheckConstraint("confidence_score BETWEEN 0 AND 1", name="chk_confidence_score_range"),
        sa.CheckConstraint("gds_ratio >= 0 AND gds_ratio <= 100", name="chk_gds_range"),
        sa.CheckConstraint("tds_ratio >= 0 AND tds_ratio <= 100", name="chk_tds_range"),
        sa.CheckConstraint("ltv_ratio >= 0 AND ltv_ratio <= 100", name="chk_ltv_range"),
    )
    op.create_index("idx_decisions_application_created", "decisions", ["application_id", "created_at"])
    op.create_index("idx_decisions_decision_date", "decisions", ["decision", "created_at"])
    
    # decision_rule_audits table
    op.create_table(
        "decision_rule_audits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("decision_id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("rule_name", sa.String(255), nullable=False),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("result", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"]),
    )
    op.create_index("idx_rule_audits_decision_rule", "decision_rule_audits", ["decision_id", "rule_id"])
    
    # decision_exceptions table
    op.create_table(
        "decision_exceptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("decision_id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("overrideable", sa.Boolean(), nullable=False),
        sa.Column("overridden", sa.Boolean(), nullable=False),
        sa.Column("overridden_by", sa.String(255), nullable=True),
        sa.Column("overridden_at", sa.DateTime(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"]),
        sa.CheckConstraint(
            "NOT (overridden = true AND overridden_by IS NULL)",
            name="chk_override_consistency"
        ),
    )
    op.create_index("idx_exceptions_decision_severity", "decision_exceptions", ["decision_id", "severity"])
    
    # policy_flags table
    op.create_table(
        "policy_flags",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("decision_id", sa.UUID(), nullable=False),
        sa.Column("flag_code", sa.String(50), nullable=False),
        sa.Column("flag_name", sa.String(255), nullable=False),
        sa.Column("flag_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"]),
        sa.UniqueConstraint("decision_id", "flag_code", name="uq_decision_flag"),
    )
    op.create_index("idx_flags_decision_code", "policy_flags", ["decision_id", "flag_code"])


def downgrade():
    op.drop_table("policy_flags")
    op.drop_table("decision_exceptions")
    op.drop_table("decision_rule_audits")
    op.drop_table("decisions")
```

### Data Migration Needs
- **None** - This is a new module with no existing data dependencies

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Stress Test Enforcement:** All calculations MUST use `qualifying_rate = max(contract_rate + 2%, 5.25%)` for debt service ratios
- **Hard Limits:** GDS ≤ 39%, TDS ≤ 44% - violations trigger automatic exception workflow
- **Auditability:** Every ratio calculation must log complete breakdown (numerator, denominator, result) with timestamp and user ID
- **Versioning:** Policy rule versions must be tracked and immutable once used in a decision

### FINTRAC Compliance
- **Immutable Audit Trail:** All `decision_rule_audits` records are INSERT-ONLY; no updates or deletes permitted
- **5-Year Retention:** `decisions` table records must be retained for 5 years minimum; implement soft-delete only with retention policy
- **Transaction Monitoring:** Decisions involving loan amounts > CAD $10,000 must be flagged for FINTRAC reporting (auto-generate report in separate module)
- **Identity Verification:** Log `created_by` user ID for all decision evaluations to satisfy FINTRAC record-keeping

### PIPEDA Data Handling
- **No PII in Logs:** Never log income values, SIN, DOB, or banking details in calculation logs
- **Encrypted Data:** Borrower income data is referenced by `application_id` only; actual PII remains encrypted in Application module
- **Data Minimization:** Decision module only stores derived ratios and flags; no raw borrower financial data retained
- **Access Control:** Audit trail endpoint (`/audit`) restricted to admin role with `audit:read` scope

### Authentication & Authorization
| Endpoint | Auth Required | Required Scopes | Admin Only |
|----------|---------------|-----------------|------------|
| POST /decision/evaluate | Yes | `underwrite:execute` | No |
| GET /decision/{id} | Yes | `underwrite:read` | No |
| GET /decision/{id}/audit | Yes | `audit:read` | Yes |

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy

```python
# exceptions.py
class DecisionException(AppException):
    """Base exception for Decision Service module"""
    pass

class DecisionNotFoundError(DecisionException):
    """Decision or application not found"""
    pass

class DecisionValidationError(DecisionException):
    """Input validation failed"""
    pass

class DecisionBusinessRuleError(DecisionException):
    """Business rule violation (e.g., LTV > 95%)"""
    pass

class DecisionPolicyViolationError(DecisionException):
    """OSFI B-20 ratio limits exceeded"""
    pass
```

### Error Code Mapping

| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `DecisionNotFoundError` | 404 | DECISION_001 | "Decision for application {id} not found" | WARNING |
| `DecisionValidationError` | 422 | DECISION_002 | "{field}: {reason}" | INFO |
| `DecisionBusinessRuleError` | 409 | DECISION_003 | "Business rule violated: {rule_id} - {detail}" | ERROR |
| `DecisionPolicyViolationError` | 409 | DECISION_004 | "OSFI B-20 {ratio_type} ratio {value}% exceeds limit {limit}%" | WARNING |
| `AppException` (base) | 500 | DECISION_999 | "Internal decision engine error" | CRITICAL |

### Structured Error Response Format
All errors return consistent JSON structure:
```json
{
  "detail": "GDS ratio 42.50% exceeds OSFI B-20 limit of 39.00%",
  "error_code": "DECISION_004",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "req-1234567890",
  "context": {
    "application_id": "a1b2c3d4-e5f6-7890",
    "ratio_type": "gds",
    "ratio_value": "42.50",
    "policy_limit": "39.00"
  }
}
```

### Edge Cases & Error Handling
- **Division by Zero:** If property_value = 0 → raise `DecisionValidationError` before LTV calculation
- **Negative Income:** If gross_annual_income ≤ 0 → raise `DecisionValidationError`
- **Invalid Policy Version:** If policy_version not in registry → raise `DecisionBusinessRuleError` with 409 status
- **Concurrent Evaluation:** If `POST /evaluate` called twice for same `application_id` → return 400 with `DECISION_001` (idempotent behavior)
- **Missing Application:** If `application_id` doesn't exist in `applications` table → return 404 with `DECISION_006` (cascading validation)