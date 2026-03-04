# Underwriting Engine
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Underwriting Engine Design Plan

**File:** `docs/design/underwriting-engine.md`

---

## 1. Endpoints

### 1.1 POST /api/v1/underwriting/calculate
**Purpose:** Run qualification calculation without persisting results (pre-submission check).

**Authentication:** Authenticated user (borrower, broker, or underwriter)

**Request Body Schema:**
```python
class UnderwritingCalculationRequest(BaseModel):
    application_id: Optional[UUID] = None  # Reference only, not saved
    borrower_profile: BorrowerProfile
    property_details: PropertyDetails
    loan_details: LoanDetails
    existing_obligations: List[DebtObligation] = []
    other_properties: List[OtherProperty] = []
    
class BorrowerProfile(BaseModel):
    gross_annual_income: Decimal  # Primary borrower
    gross_annual_income_co_borrower: Optional[Decimal] = None
    employment_type: Literal["salaried", "hourly", "self_employed", "other"]
    employment_status: Literal["full_time", "part_time", "contract"]
    months_at_job: int
    credit_score: int
    date_of_birth: date  # PIPEDA: encrypted in storage, not logged
    sin: str  # PIPEDA: encrypted in storage, not logged
    
class PropertyDetails(BaseModel):
    property_value: Decimal
    property_type: Literal["single_family", "condo", "townhouse", "multi_unit"]
    condo_fees_monthly: Decimal = Decimal("0")
    property_tax_annual: Decimal
    heating_cost_annual: Decimal
    rental_income_monthly: Decimal = Decimal("0")
    is_owner_occupied: bool = True
    
class LoanDetails(BaseModel):
    loan_amount: Decimal
    amortization_years: int  # 25 or 30 years
    contract_rate: Decimal  # Annual interest rate
    payment_frequency: Literal["monthly", "bi_weekly", "weekly"]
    down_payment_amount: Decimal
    
class DebtObligation(BaseModel):
    creditor: str
    monthly_payment: Decimal
    outstanding_balance: Decimal
    is_secured: bool
    is_property_related: bool  # For multi-property debt aggregation
    
class OtherProperty(BaseModel):
    address: str
    property_value: Decimal
    mortgage_balance: Decimal
    monthly_mortgage_payment: Decimal
    property_tax_annual: Decimal
    heating_cost_annual: Decimal
    rental_income_monthly: Decimal = Decimal("0")
    is_rental: bool
```

**Response Schema:**
```python
class UnderwritingCalculationResponse(BaseModel):
    request_id: UUID  # Correlation ID for audit
    qualifies: bool
    decision: Literal["APPROVED", "CONDITIONAL", "DECLINED"]
    gds_ratio: Decimal  # Rounded to 2 decimal places
    tds_ratio: Decimal  # Rounded to 2 decimal places
    ltv_ratio: Decimal  # Rounded to 2 decimal places
    cmhc_required: bool
    cmhc_premium_amount: Decimal
    qualifying_rate: Decimal
    max_mortgage: Decimal
    decline_reasons: List[DeclineReason]
    conditions: List[Condition]
    stress_test_passed: bool
    calculation_breakdown: CalculationBreakdown
    
class DeclineReason(BaseModel):
    code: str
    message: str
    priority: int
    
class Condition(BaseModel):
    code: str
    description: str
    is_mandatory: bool
    
class CalculationBreakdown(BaseModel):
    gross_monthly_income: Decimal
    monthly_pith: Decimal  # PITH = Principal + Interest + Taxes + Heat
    monthly_condo_fees: Decimal
    monthly_debt_payments: Decimal
    qualifying_payment: Decimal  # Payment at qualifying_rate
```

**Error Responses:**
- `422`: UnderwritingValidationError - Invalid input (e.g., LTV > 95%, negative values)
- `400`: UnderwritingBusinessRuleError - Violation of underwriting rules (e.g., down payment insufficient for property value)
- `404`: ApplicationNotFoundError - If application_id provided but not found

---

### 1.2 POST /api/v1/underwriting/applications/{id}/evaluate
**Purpose:** Execute full underwriting evaluation and persist results.

**Authentication:** Underwriter role required

**Path Parameters:** `id` (UUID) - Application ID

**Request Body Schema:** Same as `UnderwritingCalculationRequest` but `application_id` is ignored (taken from path)

**Response Schema:** `UnderwritingResult` (see Output Structure) with additional audit fields:
```python
class UnderwritingResult(UnderwritingCalculationResponse):
    id: UUID
    application_id: UUID
    version: int  # For audit trail versioning
    evaluated_by: str  # User ID
    evaluated_at: datetime
    fintrac_reportable: bool  # True if loan_amount >= $10,000 CAD
    
class UnderwritingResultResponse(BaseModel):
    result: UnderwritingResult
    audit_trail: AuditEntry  # FINTRAC compliance
```

**Error Responses:**
- `404`: UnderwritingNotFoundError - Application not found
- `409`: UnderwritingBusinessRuleError - Application already evaluated
- `403`: Forbidden - Insufficient permissions
- `422`: Validation errors

---

### 1.3 GET /api/v1/underwriting/applications/{id}/result
**Purpose:** Retrieve persisted underwriting result.

**Authentication:** Authenticated user (borrower can view own, underwriter can view all)

**Path Parameters:** `id` (UUID) - Application ID

**Query Parameters:**
- `version: Optional[int] = None` - Retrieve specific version (audit)

**Response Schema:** `UnderwritingResultResponse`

**Error Responses:**
- `404`: UnderwritingNotFoundError - Result not found
- `403`: Forbidden - Access to unauthorized application

---

### 1.4 POST /api/v1/underwriting/applications/{id}/override
**Purpose:** Admin override of underwriting decision with mandatory reason.

**Authentication:** Admin role + MFA required

**Path Parameters:** `id` (UUID) - Application ID

**Request Body Schema:**
```python
class UnderwritingOverrideRequest(BaseModel):
    override_decision: Literal["APPROVED", "CONDITIONAL", "DECLINED"]
    override_reason: str  # Min 20 chars, max 500 chars
    original_result_id: UUID  # Reference to result being overridden
    conditions: List[Condition] = []  # Required if override_decision is CONDITIONAL
    risk_notes: Optional[str] = None  # Internal risk assessment notes
    
class UnderwritingOverrideResponse(BaseModel):
    override_id: UUID
    original_result: UnderwritingResult
    overridden_result: UnderwritingResult
    overridden_by: str
    overridden_at: datetime
    audit_trail: AuditEntry
```

**Error Responses:**
- `404`: UnderwritingNotFoundError - Original result not found
- `403`: UnderwritingOverrideUnauthorizedError - Insufficient privileges
- `409`: UnderwritingBusinessRuleError - Cannot override funded/closed application
- `422`: ValidationError - Reason too short or missing required conditions

---

## 2. Models & Database

### 2.1 underwriting_results Table
```python
class UnderwritingResult(Base):
    __tablename__ = "underwriting_results"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    
    # Decision fields
    qualifies: Mapped[bool] = mapped_column(nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED, CONDITIONAL, DECLINED
    decline_reasons: Mapped[JSON] = mapped_column(JSONB, nullable=False, default=list)
    conditions: Mapped[JSON] = mapped_column(JSONB, nullable=False, default=list)
    
    # Ratio calculations (OSFI B-20)
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    
    # CMHC fields
    cmhc_required: Mapped[bool] = mapped_column(nullable=False)
    cmhc_premium_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # Stress test (OSFI B-20)
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    contract_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    stress_test_passed: Mapped[bool] = mapped_column(nullable=False)
    
    # Financial details
    max_mortgage: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    loan_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gross_monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monthly_pith: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # FINTRAC compliance
    fintrac_reportable: Mapped[bool] = mapped_column(nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)  # User ID
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("ix_underwriting_results_app_id_version", "application_id", "version", unique=True),
        Index("ix_underwriting_results_decision", "decision"),
        Index("ix_underwriting_results_created_at", "created_at"),
        CheckConstraint("gds_ratio <= 39.0", name="ck_gds_osfi_limit"),
        CheckConstraint("tds_ratio <= 44.0", name="ck_tds_osfi_limit"),
    )
```

### 2.2 underwriting_calculation_audit Table
```python
class UnderwritingCalculationAudit(Base):
    __tablename__ = "underwriting_calculation_audit"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    request_id: Mapped[UUID] = mapped_column(nullable=False, unique=True)  # Correlation ID
    
    # Calculation inputs (PIPEDA: sensitive fields encrypted)
    borrower_profile_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    property_details_json: Mapped[JSON] = mapped_column(JSONB, nullable=False)
    loan_details_json: Mapped[JSON] = mapped_column(JSONB, nullable=False)
    obligations_json: Mapped[JSON] = mapped_column(JSONB, nullable=False)
    
    # Calculation outputs
    result_snapshot: Mapped[JSON] = mapped_column(JSONB, nullable=False)
    calculation_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # FINTRAC: Immutable audit trail
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)  # IPv6 support
    user_agent: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Indexes for audit queries
    __table_args__ = (
        Index("ix_calc_audit_app_timestamp", "application_id", "calculation_timestamp"),
        Index("ix_calc_audit_created_at", "created_at"),
    )
```

### 2.3 underwriting_overrides Table
```python
class UnderwritingOverride(Base):
    __tablename__ = "underwriting_overrides"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    original_result_id: Mapped[UUID] = mapped_column(ForeignKey("underwriting_results.id"), nullable=False)
    new_result_id: Mapped[UUID] = mapped_column(ForeignKey("underwriting_results.id"), nullable=False)
    
    override_reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_notes_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary)  # PIPEDA encryption
    
    overridden_by: Mapped[str] = mapped_column(String(100), nullable=False)
    overridden_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # FINTRAC: All overrides are reportable events
    fintrac_event_logged: Mapped[bool] = mapped_column(nullable=False, default=False)
    
    __table_args__ = (
        Index("ix_underwriting_overrides_original", "original_result_id"),
        Index("ix_underwriting_overrides_timestamp", "overridden_at"),
    )
```

### 2.4 underwriting_conditions Table
```python
class UnderwritingCondition(Base):
    __tablename__ = "underwriting_conditions"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    result_id: Mapped[UUID] = mapped_column(ForeignKey("underwriting_results.id"), nullable=False, index=True)
    
    condition_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(nullable=False)
    is_satisfied: Mapped[bool] = mapped_column(nullable=False, default=False)
    
    satisfied_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    satisfied_by: Mapped[Optional[str]] = mapped_column(String(100))
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
```

### 2.5 Relationships & Additional Indexes
```python
# Application model (existing) should have:
class Application(Base):
    # ... existing fields ...
    underwriting_results: Mapped[List["UnderwritingResult"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    
# Composite indexes for common queries:
Index("ix_underwriting_results_gds_tds", "gds_ratio", "tds_ratio")
Index("ix_underwriting_results_ltv_cmhc", "ltv_ratio", "cmhc_required")
Index("ix_underwriting_results_fintrac", "fintrac_reportable", "created_at")
```

---

## 3. Business Logic

### 3.1 Algorithm Specifications

#### 3.1.1 Stress Test (OSFI B-20)
```python
qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
# qualifying_rate stored as annual percentage rate
```

#### 3.1.2 GDS Calculation
```python
gross_monthly_income = (gross_annual_income + gross_annual_income_co_borrower) / 12

# PITH Calculation
monthly_principal_interest = calculate_payment(
    loan_amount, qualifying_rate, amortization_years, payment_frequency
)
monthly_taxes = property_tax_annual / 12
monthly_heat = heating_cost_annual / 12
monthly_pith = monthly_principal_interest + monthly_taxes + monthly_heat

# Condo fees: 50% included in GDS
gds_numerator = monthly_pith + (condo_fees_monthly * Decimal("0.50"))
gds_ratio = (gds_numerator / gross_monthly_income) * 100
```

#### 3.1.3 TDS Calculation
```python
# Aggregate all debt obligations
monthly_debt_payments = sum(
    obligation.monthly_payment for obligation in existing_obligations
)

# Multi-property debt aggregation
for property in other_properties:
    if property.is_rental:
        # 50% of rental income offset
        rental_offset = property.rental_income_monthly * Decimal("0.50")
        property_pith = (
            property.monthly_mortgage_payment +
            (property.property_tax_annual / 12) +
            (property.heating_cost_annual / 12)
        )
        monthly_debt_payments += max(Decimal("0"), property_pith - rental_offset)
    else:
        monthly_debt_payments += property.monthly_mortgage_payment

tds_numerator = gds_numerator + monthly_debt_payments
tds_ratio = (tds_numerator / gross_monthly_income) * 100
```

#### 3.1.4 LTV & Down Payment Rules
```python
ltv_ratio = (loan_amount / property_value) * 100

# CMHC/Insurer minimum down payment rules
if property_value <= Decimal("500000"):
    min_down = property_value * Decimal("0.05")
elif property_value <= Decimal("1500000"):
    min_down = (Decimal("500000") * Decimal("0.05")) + \
               ((property_value - Decimal("500000")) * Decimal("0.10"))
else:
    min_down = property_value * Decimal("0.20")  # 20% minimum for $1.5M+

if down_payment_amount < min_down:
    raise UnderwritingBusinessRuleError("DOWN_PAYMENT_INSUFFICIENT")
```

#### 3.1.5 CMHC Insurance Premium
```python
if ltv_ratio <= Decimal("80.00"):
    cmhc_required = False
    cmhc_premium_amount = Decimal("0")
else:
    cmhc_required = True
    if Decimal("80.01") <= ltv_ratio <= Decimal("85.00"):
        premium_rate = Decimal("0.0280")
    elif Decimal("85.01") <= ltv_ratio <= Decimal("90.00"):
        premium_rate = Decimal("0.0310")
    elif Decimal("90.01") <= ltv_ratio <= Decimal("95.00"):
        premium_rate = Decimal("0.0400")
    else:
        raise UnderwritingValidationError("LTV_EXCEEDS_MAXIMUM")
    
    cmhc_premium_amount = loan_amount * premium_rate
```

#### 3.1.6 Self-Employed Income Calculation
```python
if employment_type == "self_employed":
    # Require 2-year T1 General average
    # Use net business income after expenses
    # Apply 15% gross-up for non-taxable income
    # Minimum 2-year history required
    if months_at_job < 24:
        raise UnderwritingValidationError("SELF_EMPLOYED_INSUFFICIENT_HISTORY")
    
    # Income verified via NOA (Notice of Assessment)
    # 2-year average with documentation
    gross_monthly_income = calculate_self_employed_income_average() / 12
```

### 3.2 Decision Tree

```python
def evaluate_underwriting(request) -> UnderwritingResult:
    # Step 1: Validate input
    validate_minimum_requirements(request)
    
    # Step 2: Calculate ratios
    ltv = calculate_ltv(request.loan_details.loan_amount, request.property_details.property_value)
    qualifying_rate = calculate_qualifying_rate(request.loan_details.contract_rate)
    gds, tds = calculate_gds_tds(request, qualifying_rate)
    
    # Step 3: Apply OSFI B-20 limits
    stress_test_passed = gds <= Decimal("39.00") and tds <= Decimal("44.00")
    
    # Step 4: Determine CMHC requirement
    cmhc_required, cmhc_premium = calculate_cmhc_insurance(ltv, request.loan_details.loan_amount)
    
    # Step 5: Build decision
    decline_reasons = []
    conditions = []
    
    if not stress_test_passed:
        if gds > Decimal("39.00"):
            decline_reasons.append(DeclineReason(
                code="GDS_EXCEEDS_LIMIT",
                message=f"GDS ratio {gds}% exceeds OSFI limit of 39%",
                priority=1
            ))
        if tds > Decimal("44.00"):
            decline_reasons.append(DeclineReason(
                code="TDS_EXCEEDS_LIMIT",
                message=f"TDS ratio {tds}% exceeds OSFI limit of 44%",
                priority=2
            ))
    
    if request.borrower_profile.credit_score < 600:
        decline_reasons.append(DeclineReason(
            code="CREDIT_SCORE_INSUFFICIENT",
            message="Credit score below minimum threshold of 600",
            priority=3
        ))
    
    if ltv > Decimal("95.00"):
        decline_reasons.append(DeclineReason(
            code="LTV_EXCEEDS_MAXIMUM",
            message="LTV exceeds maximum 95%",
            priority=4
        ))
    
    # Step 6: Determine final decision
    if decline_reasons:
        decision = "DECLINED"
        decline_reasons.sort(key=lambda x: x.priority)
    elif conditions_needed(request):
        decision = "CONDITIONAL"
        conditions = generate_standard_conditions(request)
    else:
        decision = "APPROVED"
    
    return UnderwritingResult(
        qualifies=(decision in ["APPROVED", "CONDITIONAL"]),
        decision=decision,
        gds_ratio=gds,
        tds_ratio=tds,
        ltv_ratio=ltv,
        cmhc_required=cmhc_required,
        cmhc_premium_amount=cmhc_premium,
        qualifying_rate=qualifying_rate,
        max_mortgage=calculate_max_mortgage(request, qualifying_rate),
        decline_reasons=decline_reasons,
        conditions=conditions,
        stress_test_passed=stress_test_passed,
    )
```

### 3.3 State Machine

**Application Status Flow:**
```
DRAFT → SUBMITTED → UNDER_REVIEW → EVALUATING → 
    ├── APPROVED → FUNDED
    ├── CONDITIONAL → (conditions satisfied) → APPROVED → FUNDED
    └── DECLINED → (override possible) → OVERRIDDEN → APPROVED/CONDITIONAL
```

**Transitions:**
- `EVALUATING`: Underwriting evaluation in progress
- `APPROVED`: All criteria met, no conditions
- `CONDITIONAL`: Criteria met subject to conditions
- `DECLINED`: Criteria not met
- `OVERRIDDEN`: Admin override applied (creates new result version)

### 3.4 Conditional Approval Criteria

**Standard Conditions (is_mandatory=True):**
- `DOWN_PAYMENT_VERIFICATION`: Provide 90-day bank statements showing down payment funds
- `EMPLOYMENT_VERIFICATION`: Letter of employment or recent pay stubs
- `PROPERTY_APPRAISAL`: Independent appraisal required if LTV > 80%
- `DEBT_RESTRUCTURE`: Pay off specified debts before closing
- `INSURANCE_APPLICATION`: CMHC/insurer application must be approved

**Optional Conditions (is_mandatory=False):**
- `CO_BORROWER_GUARANTOR`: Add co-borrower or guarantor
- `INCREASE_DOWN_PAYMENT`: Increase down payment to reduce LTV

### 3.5 Decline Reason Priority

| Priority | Code | Trigger |
|----------|------|---------|
| 1 | GDS_EXCEEDS_LIMIT | GDS > 39% |
| 2 | TDS_EXCEEDS_LIMIT | TDS > 44% |
| 3 | CREDIT_SCORE_INSUFFICIENT | Score < 600 |
| 4 | LTV_EXCEEDS_MAXIMUM | LTV > 95% |
| 5 | INSUFFICIENT_DOWN_PAYMENT | Down payment < minimum |
| 6 | UNSTABLE_EMPLOYMENT | < 3 months at job |
| 7 | SELF_EMPLOYED_INSUFFICIENT_HISTORY | < 2 years |
| 8 | RENTAL_INCOME_UNVERIFIABLE | No lease agreements |

---

## 4. Migrations

### 4.1 New Tables
```sql
-- Create underwriting_results table
CREATE TABLE underwriting_results (
    id UUID PRIMARY KEY,
    application_id UUID NOT NULL REFERENCES applications(id),
    version INTEGER NOT NULL,
    qualifies BOOLEAN NOT NULL,
    decision VARCHAR(20) NOT NULL,
    gds_ratio NUMERIC(5,2) NOT NULL,
    tds_ratio NUMERIC(5,2) NOT NULL,
    ltv_ratio NUMERIC(5,2) NOT NULL,
    cmhc_required BOOLEAN NOT NULL,
    cmhc_premium_amount NUMERIC(12,2) NOT NULL,
    qualifying_rate NUMERIC(5,2) NOT NULL,
    contract_rate NUMERIC(5,2) NOT NULL,
    stress_test_passed BOOLEAN NOT NULL,
    max_mortgage NUMERIC(12,2) NOT NULL,
    loan_amount NUMERIC(12,2) NOT NULL,
    gross_monthly_income NUMERIC(12,2) NOT NULL,
    monthly_pith NUMERIC(12,2) NOT NULL,
    decline_reasons JSONB NOT NULL DEFAULT '[]',
    conditions JSONB NOT NULL DEFAULT '[]',
    fintrac_reportable BOOLEAN NOT NULL,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_gds_osfi_limit CHECK (gds_ratio <= 39.0),
    CONSTRAINT ck_tds_osfi_limit CHECK (tds_ratio <= 44.0)
);

-- Create indexes
CREATE UNIQUE INDEX ix_underwriting_results_app_id_version 
    ON underwriting_results(application_id, version);
CREATE INDEX ix_underwriting_results_decision ON underwriting_results(decision);
CREATE INDEX ix_underwriting_results_created_at ON underwriting_results(created_at);
CREATE INDEX ix_underwriting_results_gds_tds ON underwriting_results(gds_ratio, tds_ratio);
CREATE INDEX ix_underwriting_results_ltv_cmhc ON underwriting_results(ltv_ratio, cmhc_required);
CREATE INDEX ix_underwriting_results_fintrac ON underwriting_results(fintrac_reportable, created_at);

-- Create underwriting_calculation_audit table
CREATE TABLE underwriting_calculation_audit (
    id UUID PRIMARY KEY,
    application_id UUID NOT NULL REFERENCES applications(id),
    request_id UUID NOT NULL UNIQUE,
    borrower_profile_encrypted BYTEA NOT NULL,  -- AES-256 encrypted
    property_details_json JSONB NOT NULL,
    loan_details_json JSONB NOT NULL,
    obligations_json JSONB NOT NULL,
    result_snapshot JSONB NOT NULL,
    calculation_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT NOT NULL
);

CREATE INDEX ix_calc_audit_app_timestamp ON underwriting_calculation_audit(application_id, calculation_timestamp);
CREATE INDEX ix_calc_audit_created_at ON underwriting_calculation_audit(created_at);

-- Create underwriting_overrides table
CREATE TABLE underwriting_overrides (
    id UUID PRIMARY KEY,
    original_result_id UUID NOT NULL REFERENCES underwriting_results(id),
    new_result_id UUID NOT NULL REFERENCES underwriting_results(id),
    override_reason TEXT NOT NULL,
    risk_notes_encrypted BYTEA,  -- AES-256 encrypted
    overridden_by VARCHAR(100) NOT NULL,
    overridden_at TIMESTAMP NOT NULL DEFAULT NOW(),
    fintrac_event_logged BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX ix_underwriting_overrides_original ON underwriting_overrides(original_result_id);
CREATE INDEX ix_underwriting_overrides_timestamp ON underwriting_overrides(overridden_at);

-- Create underwriting_conditions table
CREATE TABLE underwriting_conditions (
    id UUID PRIMARY KEY,
    result_id UUID NOT NULL REFERENCES underwriting_results(id),
    condition_code VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    is_mandatory BOOLEAN NOT NULL,
    is_satisfied BOOLEAN NOT NULL DEFAULT FALSE,
    satisfied_at TIMESTAMP,
    satisfied_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_underwriting_conditions_result ON underwriting_conditions(result_id);
```

### 4.2 Data Migration Needs
- **None** - New module, no existing data to migrate
- **Future migration**: When self-employed income verification module is added, will need to link to T1 documents

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Compliance
- **Stress Test**: Implemented in `calculate_qualifying_rate()` - always uses `max(contract_rate + 2%, 5.25%)`
- **GDS/TDS Limits**: Database constraints enforce `GDS ≤ 39%` and `TDS ≤ 44%`
- **Auditability**: Every calculation stored in `underwriting_calculation_audit` with full breakdown
- **Logging**: structlog includes `correlation_id`, `application_id`, `gds_ratio`, `tds_ratio`, `qualifying_rate` - **NO PII**

### 5.2 FINTRAC Compliance
- **Immutable Records**: `underwriting_results` and `underwriting_calculation_audit` have no UPDATE/DELETE operations
- **Transaction Flagging**: `fintrac_reportable` automatically set when `loan_amount >= 10,000 CAD`
- **5-Year Retention**: Database retention policy set on `underwriting_calculation_audit` (soft delete via archive table after 5 years)
- **Audit Trail**: Every evaluation logs IP address, user agent, timestamp, and user ID
- **Override Reporting**: All overrides create FINTRAC reportable event in `underwriting_overrides`

### 5.3 CMHC Insurance Rules
- **LTV Calculation**: Uses `Decimal` with no precision loss: `loan_amount / property_value`
- **Premium Tiers**: Exact lookup table implemented:
  - 80.01-85%: 2.80%
  - 85.01-90%: 3.10%
  - 90.01-95%: 4.00%
- **Minimum Down Payment**: Enforced per property value tier ($500k, $1.5M thresholds)

### 5.4 PIPEDA Data Handling
- **Encryption at Rest**: 
  - `sin` and `date_of_birth` encrypted via `encrypt_pii()` before storage
  - `risk_notes` in overrides encrypted
  - AES-256-GCM implementation in `common/security.py`
- **Data Minimization**: Only collects fields required for underwriting decision
- **Log Sanitization**: All schemas use `__repr__` and `__str__` overrides to exclude PII
- **Lookup Hashing**: SIN stored as SHA256 hash for duplicate checking (separate `sin_hash` column)

### 5.5 Authentication/Authorization
| Endpoint | Required Role | MFA | Rate Limit |
|----------|--------------|-----|------------|
| POST /calculate | Authenticated | No | 10/min per user |
| POST /evaluate | Underwriter | Yes | 5/min per user |
| GET /result | Authenticated | No | 30/min per user |
| POST /override | Admin | Yes | 2/min per user |

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Definitions

```python
# modules/underwriting/exceptions.py
class UnderwritingException(AppException):
    """Base exception for underwriting module"""
    pass

class UnderwritingNotFoundError(UnderwritingException):
    """Resource not found"""
    def __init__(self, resource: str, resource_id: UUID):
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} not found: {resource_id}")

class UnderwritingValidationError(UnderwritingException):
    """Input validation failed"""
    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")

class UnderwritingBusinessRuleError(UnderwritingException):
    """OSFI B-20 or CMHC rule violation"""
    def __init__(self, rule: str, detail: str):
        self.rule = rule
        self.detail = detail
        super().__init__(f"{rule} violated: {detail}")

class UnderwritingOverrideUnauthorizedError(UnderwritingException):
    """User lacks permission to override"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User {user_id} not authorized for override")
```

### 6.2 HTTP Mapping

| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `UnderwritingNotFoundError` | 404 | `UNDERWRITING_001` | "{Resource} not found: {id}" | WARNING |
| `UnderwritingValidationError` | 422 | `UNDERWRITING_002` | "{field}: {reason}" | INFO |
| `UnderwritingBusinessRuleError` | 409 | `UNDERWRITING_003` | "{rule} violated: {detail}" | WARNING |
| `UnderwritingOverrideUnauthorizedError` | 403 | `UNDERWRITING_004` | "Override not authorized for user" | ERROR |
| `ApplicationNotFoundError` | 404 | `APPLICATION_001` | "Application not found: {id}" | WARNING |

### 6.3 Structured Error Response
All errors return:
```json
{
  "detail": "Human-readable error message",
  "error_code": "UNDERWRITING_001",
  "correlation_id": "uuid-correlation-id",
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "uuid-request-id"
}
```

### 6.4 Edge Cases & Error Handling
- **Division by zero**: If `gross_monthly_income == 0`, raise `UnderwritingValidationError` with code `INCOME_ZERO`
- **LTV precision**: Use `Decimal` with 5 decimal places for intermediate calculations, round final to 2
- **Rate precision**: Store rates as `Decimal(5,2)` (e.g., 5.25%)
- **Property value > $1.5M**: Enforce 20% down payment, no CMHC insurance available
- **Rental property**: Apply 50% rental income offset, require lease agreement
- **Multiple evaluations**: Version control via `version` column, latest is `max(version)`

---