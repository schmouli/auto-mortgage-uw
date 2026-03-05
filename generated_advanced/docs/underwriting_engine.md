# Underwriting Engine
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Underwriting Engine Design Plan

**File:** `docs/design/underwriting-engine.md`  
**Module:** `underwriting`  
**Feature Slug:** `underwriting-engine`

---

## 1. Endpoints

### 1.1 POST /api/v1/underwriting/calculate
**Purpose:** Run a one‑off qualification without persisting data.

| Aspect | Details |
|--------|---------|
| **Authentication** | `authenticated` (JWT) |
| **Request Body** | `UnderwritingCalculateRequest` |
| **Response** | `UnderwritingCalculateResponse` (same shape as `UnderwritingResult`) |
| **Error Responses** | • `400` – `UNDERWRITING_001` (invalid input)<br>• `401` – `AUTH_001` (missing/invalid token)<br>• `422` – `UNDERWRITING_002` (validation error) |
| **Rate‑Limiting** | 10/min per user (avoids abuse of compute‑intensive endpoint) |

#### Request Schema (`UnderwritingCalculateRequest`)
```python
class UnderwritingCalculateRequest(BaseModel):
    # Applicant info (PII encrypted client‑side before sending)
    applicant: ApplicantData
    property: PropertyData
    loan: LoanData
    existing_debts: List[DebtItem] = []
    condo_fees_monthly: Optional[Decimal] = None
    rental_income_monthly: Optional[Decimal] = None
    # Self‑employed income documentation flag
    is_self_employed: bool = False
    # Multi‑property debt aggregation
    other_property_debts: List[OtherPropertyDebt] = []

class ApplicantData(BaseModel):
    # SIN & DOB are encrypted (AES‑256) and sent as base64 strings.
    sin_encrypted: str
    sin_hash: str  # SHA256 for lookup
    dob_encrypted: str
    gross_annual_income: Decimal  # Must be > 0
    employment_status: Literal["employed", "self_employed", "other"]

class PropertyData(BaseModel):
    purchase_price: Decimal  # > 0
    address: str
    property_type: Literal["single_family", "condo", "townhouse", "multi_unit"]
    annual_property_tax: Optional[Decimal] = None  # If not provided, system estimates
    monthly_heating_cost: Optional[Decimal] = None  # If not provided, system estimates

class LoanData(BaseModel):
    requested_amount: Decimal  # > 0
    amortization_years: int  # 5‑30
    contract_rate: Decimal  # > 0
    payment_schedule: Literal["monthly", "bi_weekly", "weekly"]

class DebtItem(BaseModel):
    monthly_payment: Decimal
    outstanding_balance: Decimal
    creditor_type: Literal["credit_card", "line_of_credit", "auto_loan", "student_loan", "other"]

class OtherPropertyDebt(BaseModel):
    # Used for TDS aggregation across properties
    monthly_payment: Decimal
    property_address: str
```

#### Response Schema (`UnderwritingCalculateResponse`)
```python
class UnderwritingCalculateResponse(BaseModel):
    qualifies: bool
    decision: Literal["APPROVED", "CONDITIONAL", "DECLINED"]
    gds_ratio: Decimal
    tds_ratio: Decimal
    ltv_ratio: Decimal
    cmhc_required: bool
    cmhc_premium_amount: Decimal
    qualifying_rate: Decimal  # OSFI stress‑test rate
    max_mortgage: Decimal
    decline_reasons: List[str]  # Human‑readable codes (e.g., "gds_exceeded")
    conditions: List[str]       # e.g., "provide_2023_t4"
    stress_test_passed: bool
    calculation_breakdown: Dict[str, Any]  # Full audit trail
```

---

### 1.2 POST /api/v1/underwriting/applications/{id}/evaluate
**Purpose:** Evaluate and persist an application (creates `underwriting_results` record).

| Aspect | Details |
|--------|---------|
| **Authentication** | `authenticated` |
| **Path Parameter** | `id: UUID` – the application identifier (must exist in `underwriting_applications` table) |
| **Request Body** | `UnderwritingEvaluateRequest` (same as `UnderwritingCalculateRequest` but without `id`) |
| **Response** | `UnderwritingEvaluateResponse` (includes `result_id`) |
| **Error Responses** | • `404` – `UNDERWRITING_001` (application not found)<br>• `403` – `UNDERWRITING_004` (user does not own application)<br>• `422` – `UNDERWRITING_002` (validation error)<br>• `409` – `UNDERWRITING_003` (application already evaluated) |

#### Request Schema
```python
class UnderwritingEvaluateRequest(UnderwritingCalculateRequest):
    # No additional fields; re‑uses calculate shape.
    pass
```

#### Response Schema
```python
class UnderwritingEvaluateResponse(BaseModel):
    result_id: UUID
    decision: Literal["APPROVED", "CONDITIONAL", "DECLINED"]
    gds_ratio: Decimal
    tds_ratio: Decimal
    ltv_ratio: Decimal
    cmhc_required: bool
    cmhc_premium_amount: Decimal
    qualifying_rate: Decimal
    max_mortgage: Decimal
    decline_reasons: List[str]
    conditions: List[str]
    stress_test_passed: bool
```

---

### 1.3 GET /api/v1/underwriting/applications/{id}/result
**Purpose:** Retrieve the saved underwriting result for an application.

| Aspect | Details |
|--------|---------|
| **Authentication** | `authenticated` |
| **Path Parameter** | `id: UUID` |
| **Response** | `UnderwritingResultResponse` (full result + audit fields) |
| **Error Responses** | • `404` – `UNDERWRITING_001` (no result found)<br>• `403` – `UNDERWRITING_004` (user does not own application) |

#### Response Schema
```python
class UnderwritingResultResponse(BaseModel):
    result_id: UUID
    application_id: UUID
    decision: Literal["APPROVED", "CONDITIONAL", "DECLINED"]
    gds_ratio: Decimal
    tds_ratio: Decimal
    ltv_ratio: Decimal
    cmhc_required: bool
    cmhc_premium_amount: Decimal
    qualifying_rate: Decimal
    max_mortgage: Decimal
    decline_reasons: List[str]
    conditions: List[str]
    stress_test_passed: bool
    calculation_breakdown: Dict[str, Any]
    created_at: datetime
    created_by: UUID  # User who triggered evaluation
```

---

### 1.4 POST /api/v1/underwriting/applications/{id}/override
**Purpose:** Admin‑only override of a decision (e.g., manual approval).

| Aspect | Details |
|--------|---------|
| **Authentication** | `admin‑only` (JWT with `role=admin`) |
| **Path Parameter** | `id: UUID` |
| **Request Body** | `UnderwritingOverrideRequest` |
| **Response** | `UnderwritingOverrideResponse` |
| **Error Responses** | • `403` – `UNDERWRITING_004` (insufficient privileges)<br>• `404` – `UNDERWRITING_001` (application not found)<br>• `422` – `UNDERWRITING_002` (missing reason) |

#### Request Schema
```python
class UnderwritingOverrideRequest(BaseModel):
    new_decision: Literal["APPROVED", "DECLINED"]
    reason: str  # Free‑text justification, min 10 chars
```

#### Response Schema
```python
class UnderwritingOverrideResponse(BaseModel):
    override_id: UUID
    application_id: UUID
    new_decision: str
    reason: str
    created_at: datetime
    created_by: UUID  # Admin user
```

---

## 2. Models & Database

### 2.1 ORM Models (SQLAlchemy 2.0, async)

#### `underwriting_applications`
```python
class UnderwritingApplication(Base):
    __tablename__ = "underwriting_applications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))  # draft, submitted, evaluating, approved, conditional, declined

    # JSONB blobs containing encrypted PII and financial data
    applicant_data: Mapped[dict] = mapped_column(JSONB, nullable=False)  # encrypted SIN/DOB, income, employment
    property_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    loan_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    debts_data: Mapped[dict] = mapped_column(JSONB, default=list)
    condo_fees_monthly: Mapped[Optional[Decimal]] = mapped_column(Numeric(10,2))
    rental_income_monthly: Mapped[Optional[Decimal]] = mapped_column(Numeric(10,2))

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # Relationships
    result: Mapped["UnderwritingResult"] = relationship(back_populates="application", uselist=False)
    overrides: Mapped[List["UnderwritingOverride"]] = relationship(back_populates="application")
    conditions: Mapped[List["UnderwritingCondition"]] = relationship(back_populates="application")
    decline_reasons: Mapped[List["UnderwritingDeclineReason"]] = relationship(back_populates="application")

    # Indexes
    __table_args__ = (
        Index("idx_uw_app_user_status", "user_id", "status"),
        Index("idx_uw_app_created_at", "created_at"),
    )
```

#### `underwriting_results`
```python
class UnderwritingResult(Base):
    __tablename__ = "underwriting_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("underwriting_applications.id"), unique=True, index=True)

    qualifies: Mapped[bool]
    decision: Mapped[str] = mapped_column(String(20))
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5,2))
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5,2))
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5,2))
    cmhc_required: Mapped[bool]
    cmhc_premium_amount: Mapped[Decimal] = mapped_column(Numeric(12,2))
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(5,2))
    max_mortgage: Mapped[Decimal] = mapped_column(Numeric(12,2))
    stress_test_passed: Mapped[bool]

    # Store full calculation for audit (immutable)
    calculation_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # Relationships
    application: Mapped["UnderwritingApplication"] = relationship(back_populates="result")
```

#### `underwriting_overrides`
```python
class UnderwritingOverride(Base):
    __tablename__ = "underwriting_overrides"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("underwriting_applications.id"), index=True)
    admin_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    new_decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    application: Mapped["UnderwritingApplication"] = relationship(back_populates="overrides")
```

#### `underwriting_conditions`
```python
class UnderwritingCondition(Base):
    __tablename__ = "underwriting_conditions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("underwriting_applications.id"), index=True)
    condition_text: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    application: Mapped["UnderwritingApplication"] = relationship(back_populates="conditions")
```

#### `underwriting_decline_reasons`
```python
class UnderwritingDeclineReason(Base):
    __tablename__ = "underwriting_decline_reasons"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("underwriting_applications.id"), index=True)
    reason_code: Mapped[str] = mapped_column(String(50))  # e.g., "gds_exceeded"
    reason_text: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    application: Mapped["UnderwritingApplication"] = relationship(back_populates="decline_reasons")
```

### 2.2 Encryption & PII Handling
- **SIN & DOB**: Encrypted with AES‑256 via `common/security.encrypt_pii()` before storing in `applicant_data`. A separate `sin_hash` column (SHA256) is kept for lookup.
- **Logging**: Never log decrypted SIN, DOB, income, or banking details. Logs contain only masked identifiers (e.g., `sin_hash[:8]...`).
- **Data Minimization**: Only collect fields required for underwriting (income, debts, property value, loan amount). No extraneous PII.

### 2.3 Indexes for Query Performance
```sql
CREATE INDEX idx_uw_app_user_status ON underwriting_applications (user_id, status);
CREATE INDEX idx_uw_app_created_at ON underwriting_applications (created_at);
CREATE UNIQUE INDEX idx_uw_results_app_id ON underwriting_results (application_id);
CREATE INDEX idx_uw_overrides_app_id ON underwriting_overrides (application_id);
CREATE INDEX idx_uw_conditions_app_id ON underwriting_conditions (application_id);
CREATE INDEX idx_uw_decline_app_id ON underwriting_decline_reasons (application_id);
```

---

## 3. Business Logic

### 3.1 Decision Engine Flow
```mermaid
graph TD
    A[Receive Application] --> B[Validate Input]
    B --> C[Calculate Down Payment Required]
    C --> D{Down Payment >= Required?}
    D -- No --> E[Decline: insufficient_down_payment]
    D -- Yes --> F[Compute LTV]
    F --> G{LTV > 80%?}
    G -- Yes --> H[Set cmhc_required=True; Lookup Premium Tier]
    G -- No --> I[cmhc_required=False; Premium=0]
    H --> J[Compute Qualifying Rate (OSFI stress test)]
    I --> J
    J --> K[Compute PITH (Principal+Interest+Tax+Heating)]
    K --> L[Compute GDS & TDS]
    L --> M{GDS ≤ 39% & TDS ≤ 44%?}
    M -- No --> N[Check if Conditional Possible]
    M -- Yes --> O[Set stress_test_passed=True]
    N -- Yes --> P[Decision=CONDITIONAL; Generate Conditions]
    N -- No --> Q[Decision=DECLINED; Generate Reasons]
    O --> R{Max Mortgage ≥ Requested?}
    R -- Yes --> S[Decision=APPROVED]
    R -- No --> T[Decision=DECLINED; max_mortgage insufficient]
```

### 3.2 Formulas & Thresholds
| Parameter | Formula / Rule |
|-----------|----------------|
| **Down Payment Required** | • ≤ $500k → 5% of purchase price<br>• $500k‑$1.5M → 5%×$500k + 10%×(price‑$500k)<br>• > $1.5M → 20% of purchase price |
| **LTV** | `loan_amount / property_value` (Decimal) |
| **CMHC Premium** | 80.01‑85% → 2.80% of loan<br>85.01‑90% → 3.10%<br>90.01‑95% → 4.00% |
| **Qualifying Rate** | `max(contract_rate + 2%, 5.25%)` |
| **PITH** | `P&I (using qualifying rate) + annual_property_tax/12 + monthly_heating` |
| **GDS** | `(PITH + 0.5×condo_fee) / gross_monthly_income` ≤ **39%** |
| **TDS** | `(PITH + 0.5×condo_fee + sum(monthly_debt_payments)) / gross_monthly_income` ≤ **44%** |
| **Max Mortgage** | Derived from GDS/TDS limits: `min( (gross_income×0.39 – 0.5×condo_fee – tax – heating) / (P&I_factor), (gross_income×0.44 – 0.5×condo_fee – tax – heating – debts) / (P&I_factor) )` |
| **Self‑Employed Income** | Use 2‑year average; apply 20% haircut unless 3‑year history provided. |
| **Rental Income** | Include 50% of verified rental income in `gross_monthly_income`. |
| **Multi‑Property Debt** | Sum all `monthly_payment` from `other_property_debts` into TDS numerator. |

### 3.3 Conditional Approval Criteria
- **Minor GDS/TDS exceedance** (≤ 2% over limit) → condition: "reduce debt by $X".
- **Missing documentation** → condition: "provide 2023 T4 / Notice of Assessment".
- **Down payment source unclear** → condition: "provide 90‑day bank statements".
- **Property appraisal required** → condition: "submit appraisal ≥ purchase price".

### 3.4 Decline Reason Templates (Priority Order)
1. `insufficient_down_payment` – Down payment < required.
2. `gds_exceeded` – GDS > 39% and cannot be remedied.
3. `tds_exceeded` – TDS > 44% and cannot be remedied.
4. `ltv_too_high` – LTV > 95% (CMHC limit).
5. `stress_test_failed` – Qualifying rate results in negative amortization.
6. `max_mortgage_insufficient` – Calculated max mortgage < requested loan.
7. `incomplete_application` – Required fields missing (should be caught earlier).

### 3.5 Audit Logging
- **structlog** JSON payload per evaluation:
  ```json
  {
    "event": "underwriting_evaluation",
    "correlation_id": "...",
    "application_id": "...",
    "user_id": "...",
    "gds_ratio": 0.35,
    "tds_ratio": 0.42,
    "ltv_ratio": 0.85,
    "qualifying_rate": 0.0725,
    "stress_test_passed": true,
    "decision": "APPROVED",
    "calculation_breakdown": { ... }
  }
  ```
- **No PII** in logs; `sin_hash` may be logged for correlation.

---

## 4. Migrations

### 4.1 New Tables (Alembic revision: `2024_06_underwriting_engine_init`)
```python
def upgrade():
    # underwriting_applications
    op.create_table(
        "underwriting_applications",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.UUID(), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("applicant_data", postgresql.JSONB(), nullable=False),
        sa.Column("property_data", postgresql.JSONB(), nullable=False),
        sa.Column("loan_data", postgresql.JSONB(), nullable=False),
        sa.Column("debts_data", postgresql.JSONB(), server_default="[]"),
        sa.Column("condo_fees_monthly", sa.Numeric(10,2), nullable=True),
        sa.Column("rental_income_monthly", sa.Numeric(10,2), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("created_by", sa.UUID(), nullable=False),
    )
    op.create_index("idx_uw_app_user_status", "underwriting_applications", ["user_id", "status"])
    op.create_index("idx_uw_app_created_at", "underwriting_applications", ["created_at"])

    # underwriting_results
    op.create_table(
        "underwriting_results",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("application_id", sa.UUID(), nullable=False, unique=True, index=True),
        sa.Column("qualifies", sa.Boolean(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("gds_ratio", sa.Numeric(5,2), nullable=False),
        sa.Column("tds_ratio", sa.Numeric(5,2), nullable=False),
        sa.Column("ltv_ratio", sa.Numeric(5,2), nullable=False),
        sa.Column("cmhc_required", sa.Boolean(), nullable=False),
        sa.Column("cmhc_premium_amount", sa.Numeric(12,2), nullable=False),
        sa.Column("qualifying_rate", sa.Numeric(5,2), nullable=False),
        sa.Column("max_mortgage", sa.Numeric(12,2), nullable=False),
        sa.Column("stress_test_passed", sa.Boolean(), nullable=False),
        sa.Column("calculation_breakdown", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("created_by", sa.UUID(), nullable=False),
    )
    op.create_foreign_key("fk_uw_results_app", "underwriting_results", "underwriting_applications", ["application_id"], ["id"])

    # underwriting_overrides
    op.create_table(
        "underwriting_overrides",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("application_id", sa.UUID(), nullable=False, index=True),
        sa.Column("admin_user_id", sa.UUID(), nullable=False),
        sa.Column("new_decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_foreign_key("fk_uw_overrides_app", "underwriting_overrides", "underwriting_applications", ["application_id"], ["id"])

    # underwriting_conditions
    op.create_table(
        "underwriting_conditions",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("application_id", sa.UUID(), nullable=False, index=True),
        sa.Column("condition_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_foreign_key("fk_uw_conditions_app", "underwriting_conditions", "underwriting_applications", ["application_id"], ["id"])

    # underwriting_decline_reasons
    op.create_table(
        "underwriting_decline_reasons",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("application_id", sa.UUID(), nullable=False, index=True),
        sa.Column("reason_code", sa.String(50), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_foreign_key("fk_uw_decline_app", "underwriting_decline_reasons", "underwriting_applications", ["application_id"], ["id"])
```

### 4.2 Data Migration Needs
- **None** for this feature; all data is newly created. Future migration may backfill `sin_hash` for existing users if SIN collection is added later.

---

## 5. Security & Compliance

### 5.1 OSFI B‑20 (Stress Test & GDS/TDS)
- **Qualifying rate** always computed as `max(contract_rate + 2%, 5.25%)`.
- **Hard limits**: GDS ≤ 39%, TDS ≤ 44%. Any exceedance results in `DECLINED` or `CONDITIONAL`.
- **Audit trail**: `calculation_breakdown` stored immutably for each evaluation.

### 5.2 FINTRAC
- **Transaction > $10,000**: All mortgage applications exceed this; flag `transaction_type = "mortgage"` in audit logs.
- **5‑year retention**: All `underwriting_applications` and related records are retained (soft‑delete only via `status = "archived"`).
- **Immutable records**: No `UPDATE` or `DELETE` on financial records; only `INSERT` new versions.

### 5.3 CMHC Insurance
- **LTV > 80%** triggers `cmhc_required = True`.
- **Premium tiers** stored in a read‑only config table (or enum) for auditability.
- **Premium amount** added to loan amount for LTV recalculation.

### 5.4 PIPEDA
- **Encryption at rest**: SIN, DOB encrypted via AES‑256 before storage; keys managed via `common/security.py` and rotated annually.
- **Hash for lookup**: `sin_hash` column allows identity verification without decryption.
- **No PII in logs**: Mask SIN (`sin_hash[:8]...`) and never log DOB/income.
- **Data minimization**: Only fields needed for underwriting are collected; extra fields rejected at validation.

### 5.5 Authentication & Authorization
| Endpoint | Required Scope |
|----------|----------------|
| `POST /calculate` | `underwriting:read` (any authenticated user) |
| `POST /evaluate` | `underwriting:write` (owner of application) |
| `GET /result` | `underwriting:read` (owner of application) |
| `POST /override` | `admin:underwrite` (admin role) |

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | When Raised |
|-----------------|-------------|------------|-----------------|-------------|
| `UnderwritingNotFoundError` | 404 | `UNDERWRITING_001` | "Application {id} not found" | Application or result missing |
| `UnderwritingValidationError` | 422 | `UNDERWRITING_002` | "{field}: {reason}" | Pydantic validation failure |
| `UnderwritingBusinessRuleError` | 409 | `UNDERWRITING_003` | "Business rule violated: {detail}" | Down payment insufficient, LTV > 95%, etc. |
| `UnderwritingOverrideUnauthorizedError` | 403 | `UNDERWRITING_004` | "Admin privilege required" | Non‑admin attempts override |
| `UnderwritingAlreadyEvaluatedError` | 409 | `UNDERWRITING_005` | "Application {id} already evaluated" | Duplicate evaluate call |

**Response Format (consistent across errors):**
```json
{
  "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "UNDERWRITING_001"
}
```

---

## 7. Missing Details & Recommendations

### 7.1 Conditional Approval Criteria
**Recommendation**: Store a configurable rule set in `common/config.py` (e.g., `CONDITIONAL_THRESHOLDS = {"gds_max": 0.41, "tds_max": 0.46}`). Admin UI can update rules without code deploy.

### 7.2 Decline Reason Templates
**Recommendation**: Maintain an enum `DeclineReasonCode` in `underwriting/constants.py` mapping to human‑readable text. New reasons require a new migration to insert into a `decline_reason_templates` table for audit consistency.

### 7.3 Self‑Employed Income Calculation
**Recommendation**: Add `self_employed_income_docs: List[IncomeDoc]` to `ApplicantData`. If `is_self_employed = True`, require at least 2 years of docs; apply 20% haircut unless 3+ years provided. Logic encapsulated in `services.calculate_self_employed_income()`.

### 7.4 Rental Income Treatment
**Recommendation**: Accept `rental_income_monthly` and `rental_lease_agreement` (boolean). Only 50% of verified rental income is added to gross monthly income. Verification flag stored in `calculation_breakdown`.

### 7.5 Multi‑Property Debt Aggregation
**Recommendation**: Accept `other_property_debts` list. For each debt, verify address matches property registry (future integration). Sum all `monthly_payment` values into TDS numerator. Store aggregated total in `calculation_breakdown`.

### 7.6 Future Enhancements
- **Rate shopping**: Allow multiple `contract_rate` scenarios in a single request.
- **Co‑borrower support**: Extend `applicant_data` to support multiple borrowers.
- **Integration with credit bureau**: Real‑time debt data via `services.fetch_credit_report()` (FINTRAC‑compliant consent required).

---

## 8. Observability & Metrics

- **Prometheus** counters:
  - `underwriting_evaluations_total{decision="approved/conditional/declined"}`
  - `underwriting_stress_test_failures_total`
  - `underwriting_cmhc_required_total`
- **OpenTelemetry** spans: Trace each evaluation step (`validate`, `calculate_ltv`, `calculate_gds_tds`).
- **Structured logs**: Use `structlog` with `correlation_id` for end‑to‑end audit.

---

**Next Steps**: Implement the module following the above plan, ensuring zero `mypy` errors, `ruff` formatting, and `pytest` coverage (unit + integration). Run `pip‑audit` before merging.