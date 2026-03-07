# Design: Underwriting Engine
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Underwriting Engine Design Plan

**Module:** `underwriting`  
**Design Doc:** `docs/design/underwriting-engine.md`  
**Version:** 1.0  
**Regulatory Coverage:** OSFI B‑20, FINTRAC, CMHC, PIPEDA  

---

## 1. Endpoints

| Method | Path | Auth | Request Body | Response Body | Error Codes |
|--------|------|------|--------------|---------------|-------------|
| **POST** | `/api/v1/underwriting/calculate` | Authenticated user | `UnderwritingCalcRequest` | `UnderwritingResult` | `UNDERWRITING_001` (422), `UNDERWRITING_002` (400) |
| **POST** | `/api/v1/underwriting/applications/{application_id}/evaluate` | Authenticated user | — (uses stored application data) | `UnderwritingResult` | `UNDERWRITING_001` (404), `UNDERWRITING_003` (409) |
| **GET** | `/api/v1/underwriting/applications/{application_id}/result` | Authenticated user | — | `UnderwritingResult` | `UNDERWRITING_001` (404) |
| **POST** | `/api/v1/underwriting/applications/{application_id}/override` | Admin‑only | `UnderwritingOverrideRequest` | `UnderwritingResult` | `UNDERWRITING_004` (403), `UNDERWRITING_005` (422) |

### Request/Response Schemas

#### `UnderwritingCalcRequest` (Pydantic v2)
```python
class UnderwritingCalcRequest(BaseModel):
    # Income (all values annual, converted to monthly inside service)
    gross_annual_income: Decimal
    other_annual_income: Optional[Decimal] = Decimal("0")
    rental_income: Optional[Decimal] = Decimal("0")          # See warning below
    self_employed_income: Optional[Decimal] = Decimal("0")   # See warning below

    # Debts (monthly payments)
    monthly_debts: List[DebtItem] = []   # DebtItem: name, payment: Decimal, balance: Decimal

    # Property & housing costs
    property_value: Decimal
    condo_fees: Optional[Decimal] = Decimal("0")
    property_taxes: Decimal
    heating_costs: Decimal

    # Mortgage terms
    loan_amount: Decimal
    interest_rate: Decimal   # contract annual rate (e.g., 5.24)
    amortization_years: int  # 25 or 30 (CMHC limits)

    # Multi‑property debt aggregation placeholder (see warning)
    other_property_debts: Optional[List[DebtItem]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "gross_annual_income": "78000.00",
                "property_value": "650000.00",
                "loan_amount": "520000.00",
                "interest_rate": "5.24",
                "amortization_years": 25,
                "condo_fees": "300.00",
                "property_taxes": "2400.00",
                "heating_costs": "1200.00",
                "monthly_debts": [{"name": "car_loan", "payment": "450.00", "balance": "18000.00"}]
            }
        }
```

#### `UnderwritingResult` (Pydantic v2)
```python
class UnderwritingResult(BaseModel):
    qualifies: bool
    decision: Literal["APPROVED", "CONDITIONAL", "DECLINED"]
    gds_ratio: Decimal
    tds_ratio: Decimal
    ltv_ratio: Decimal
    cmhc_required: bool
    cmhc_premium_amount: Decimal
    qualifying_rate: Decimal  # OSFI stress‑test rate
    max_mortgage: Decimal      # Maximum loan amount borrower qualifies for
    decline_reasons: List[str]  # Templated reasons, e.g., ["gds_exceeds_39pct", "insufficient_down_payment"]
    conditions: List[str]       # Templated conditions for CONDITIONAL approval
    stress_test_passed: bool

    class Config:
        json_schema_extra = {
            "example": {
                "qualifies": True,
                "decision": "APPROVED",
                "gds_ratio": "32.50",
                "tds_ratio": "41.20",
                "ltv_ratio": "80.00",
                "cmhc_required": False,
                "cmhc_premium_amount": "0.00",
                "qualifying_rate": "7.24",
                "max_mortgage": "520000.00",
                "decline_reasons": [],
                "conditions": [],
                "stress_test_passed": True
            }
        }
```

#### `UnderwritingOverrideRequest` (Pydantic v2)
```python
class UnderwritingOverrideRequest(BaseModel):
    reason: str  # Free‑text justification (max 500 chars)
    new_decision: Literal["APPROVED", "DECLINED"]
```

---

## 2. Models & Database

### `UnderwritingResult` (SQLAlchemy 2.0+)
```python
class UnderwritingResult(Base):
    __tablename__ = "underwriting_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED, CONDITIONAL, DECLINED
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    cmhc_required: Mapped[bool] = mapped_column(nullable=False)
    cmhc_premium_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    max_mortgage: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    decline_reasons: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    conditions: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    stress_test_passed: Mapped[bool] = mapped_column(nullable=False)

    # Audit fields (mandatory on every table)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship(back_populates="underwriting_result")

    # Composite index for common lookups
    __table_args__ = (
        Index("ix_underwriting_results_app_id_created", application_id, created_at.desc()),
    )
```

**Notes:**
- **No PII stored** – underwriting results contain only financial ratios and decisions. If PII is required for manual review, it must be fetched from the (encrypted) `applications` table and never logged.
- **Decimal precision** – `Numeric(10,4)` for ratios, `Numeric(12,2)` for money amounts (matches CMHC premium scale).

---

## 3. Business Logic

### 3.1 Core Algorithms

#### Stress Test (OSFI B‑20)
```python
qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
```

#### Monthly Mortgage Payment (PITH)
```python
# Using qualifying_rate and amortization_years
n = amortization_years * 12
r = qualifying_rate / 12 / 100
pith = loan_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
```

#### GDS & TDS
```python
gross_monthly = gross_annual_income / 12
pith_condo = pith + condo_fees * Decimal("0.5")  # 50% of condo fees included

gds = (pith_condo + property_taxes / 12 + heating_costs / 12) / gross_monthly

total_debt_service = sum(d.payment for d in monthly_debts)
tds = (pith_condo + property_taxes / 12 + heating_costs / 12 + total_debt_service) / gross_monthly
```

#### LTV & Down‑Payment Rules (CMHC)
```python
ltv = loan_amount / property_value

# Minimum down payment
if property_value <= 500_000:
    min_down = property_value * Decimal("0.05")
elif property_value <= 1_500_000:
    min_down = Decimal("500000") * Decimal("0.05") + (property_value - Decimal("500000")) * Decimal("0.10")
else:
    min_down = property_value * Decimal("0.20")

down_payment_met = (property_value - loan_amount) >= min_down
```

#### CMHC Insurance Premium
```python
if ltv > Decimal("0.80"):
    cmhc_required = True
    if Decimal("0.8001") <= ltv <= Decimal("0.85"):
        premium_rate = Decimal("0.0280")
    elif Decimal("0.8501") <= ltv <= Decimal("0.90"):
        premium_rate = Decimal("0.0310")
    elif Decimal("0.9001") <= ltv <= Decimal("0.95"):
        premium_rate = Decimal("0.0400")
    else:
        premium_rate = Decimal("0")  # LTV > 95% is ineligible
    cmhc_premium_amount = loan_amount * premium_rate
else:
    cmhc_required = False
    cmhc_premium_amount = Decimal("0")
```

### 3.2 Decision Tree

| Condition | Outcome |
|-----------|---------|
| `gds <= 39%` **AND** `tds <= 44%` **AND** `stress_test_passed` **AND** `down_payment_met` **AND** `ltv <= 95%` | `APPROVED` |
| `gds > 39%` **OR** `tds > 44%` **OR** `not stress_test_passed` **OR** `not down_payment_met` **OR** `ltv > 95%` | `DECLINED` |
| Some thresholds borderline (e.g., `gds` 38‑39%, `tds` 42‑44%) with compensating factors | `CONDITIONAL` (see 3.3) |

### 3.3 Conditional Approval Criteria *(Design Warning: Incomplete)*
- **Placeholder logic:** If `gds` 37‑39% or `tds` 41‑44% and borrower can provide additional documentation (e.g., proof of bonus income, debt payoff letter), mark as `CONDITIONAL` and populate `conditions` with templated strings:
  - `"provide_most_recent_pay_stub"`
  - `"reduce_other_debt_by_{amount}"`
  - `"increase_down_payment_by_{amount}"`

> **Warning:** Full conditional matrix (self‑employed income treatment, rental income offset, multi‑property debt aggregation) is not yet defined. Implement a stub that logs a compliance‑audit event and returns a generic `CONDITIONAL` decision.

### 3.4 State Machine *(Application Status)*
```
draft → submitted → underwriting → [approved | declined | conditional] → closed
```
- `POST /evaluate` moves status `submitted → underwriting → <decision>`.
- `POST /override` moves any decision status to `approved` or `declined` and logs `created_by` as admin.

---

## 4. Migrations

### New Table: `underwriting_results`
```sql
CREATE TABLE underwriting_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('APPROVED', 'CONDITIONAL', 'DECLINED')),
    gds_ratio NUMERIC(10,4) NOT NULL,
    tds_ratio NUMERIC(10,4) NOT NULL,
    ltv_ratio NUMERIC(10,4) NOT NULL,
    cmhc_required BOOLEAN NOT NULL,
    cmhc_premium_amount NUMERIC(12,2) NOT NULL,
    qualifying_rate NUMERIC(6,4) NOT NULL,
    max_mortgage NUMERIC(12,2) NOT NULL,
    decline_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    stress_test_passed BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    created_by UUID NOT NULL REFERENCES users(id),
    CONSTRAINT chk_gds CHECK (gds_ratio >= 0 AND gds_ratio <= 100),
    CONSTRAINT chk_tds CHECK (tds_ratio >= 0 AND tds_ratio <= 100),
    CONSTRAINT chk_ltv CHECK (ltv_ratio >= 0 AND ltv_ratio <= 100)
);

CREATE INDEX ix_underwriting_results_app_id_created ON underwriting_results (application_id, created_at DESC);
CREATE INDEX ix_underwriting_results_decision ON underwriting_results (decision);
```

### Existing Tables
- Add `underwriting_status` column to `applications` table (if not present) to track state machine:
  ```sql
  ALTER TABLE applications ADD COLUMN underwriting_status VARCHAR(30) DEFAULT 'draft';
  CREATE INDEX ix_applications_underwriting_status ON applications (underwriting_status);
  ```

---

## 5. Security & Compliance

### OSFI B‑20 (Stress Test & GDS/TDS Limits)
- **Mandatory Calculation:** `qualifying_rate = max(contract_rate + 2%, 5.25%)` applied to every evaluation.
- **Hard Limits:** GDS ≤ 39%, TDS ≤ 44%. Violations log a `regulatory.audit` event with `correlation_id`.
- **Audit Trail:** Every ratio, rate, and decision is written to `underwriting_results` and emitted as a structured log (`structlog`) with `event="underwriting_decision"` and `correlation_id`.

### FINTRAC
- **Transaction > $10 000:** If `loan_amount` ≥ 10 000, the evaluation logs a `fintrac.large_loan` event containing `application_id`, `loan_amount`, `created_by`, and `timestamp`. This event is immutable and retained for 5 years.
- **Identity Verification:** Underwriting does **not** store SIN/DOB; if manual review requires identity check, the system must call the `identity_verification` module and log the verification attempt (no PII in logs).

### CMHC Insurance
- **LTV > 80 %** triggers `cmhc_required = True` and premium lookup using the exact tiers (2.80 %, 3.10 %, 4.00 %). Premium amount stored as `Decimal` with two decimal places.
- **Down‑Payment Rules:** Enforced as per CMHC (5 %/10 %/20 %). If `down_payment_met = False`, decline reason includes `"insufficient_down_payment"`.

### PIPEDA
- **No PII Storage:** Underwriting engine **never** persists SIN, DOB, or bank account numbers. All PII remains encrypted at rest in the `applications` module.
- **Data Minimization:** Only financial fields required for ratio calculations are accepted in `UnderwritingCalcRequest`. Extra fields are rejected with `422`.

### Authentication / Authorization
| Endpoint | Required Scope |
|----------|----------------|
| `POST /calculate` | `underwriting:read` (any authenticated user) |
| `POST /evaluate` | `underwriting:write` (underwriter role) |
| `GET /result` | `underwriting:read` (owner or underwriter) |
| `POST /override` | `underwriting:override` (admin role) |

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | When Raised |
|-----------------|-------------|------------|-----------------|-------------|
| `UnderwritingNotFoundError` | 404 | `UNDERWRITING_001` | "Application {id} not found" | `application_id` does not exist |
| `UnderwritingValidationError` | 422 | `UNDERWRITING_002` | "{field}: {reason}" | Missing required field or malformed Decimal |
| `UnderwritingBusinessRuleError` | 409 | `UNDERWRITING_003` | "{rule} violated: {detail}" | Down payment < minimum, LTV > 95 % |
| `UnderwritingOverrideUnauthorizedError` | 403 | `UNDERWRITING_004` | "Admin override required" | Non‑admin attempts override |
| `UnderwritingOverrideReasonError` | 422 | `UNDERWRITING_005` | "Override reason missing or too long" | Reason empty or > 500 chars |

### Example Error Response
```json
{
  "detail": "gds_ratio: value must be <= 39.0",
  "error_code": "UNDERWRITING_002"
}
```

---

## 7. Design Warnings & Future Considerations

| Topic | Status | Recommendation |
|-------|--------|----------------|
| **Conditional Approval Criteria** | Not fully defined | Implement stub logic that flags borderline ratios and logs for manual review. Expand in a follow‑up story with business‑approved condition matrix. |
| **Decline Reason Templates** | Partially defined | Create an enum `DeclineReason` (`gds_exceeds_39pct`, `tds_exceeds_44pct`, `stress_test_failed`, `insufficient_down_payment`, `ltv_too_high`). Add new reasons via migration only. |
| **Self‑Employed Income Calculation** | Not specified | Use 2‑year average of net income after expenses; require `self_employed_income` to be pre‑validated by a separate income verification module before underwriting. |
| **Rental Income Treatment** | Not specified | Apply 50 % offset for existing rental income; 100 % for proposed rental (subject to appraisal). Define in a future `IncomePolicy` module. |
| **Multi‑Property Debt Aggregation** | Not specified | Accept `other_property_debts` in request; sum payments into `total_debt_service`. Full aggregation rules (e.g., netting rental income) deferred. |
| **Audit Log Retention** | Required | Configure `structlog` to ship `underwriting_decision` events to a 5‑year immutable archive (e.g., S3 with WORM). |

---

## 8. Observability & Metrics

- **Prometheus Metrics:**
  - `underwriting_evaluations_total{decision="approved/conditional/declined"}` (Counter)
  - `underwriting_calculation_duration_seconds` (Histogram)
  - `underwriting_stress_test_failures_total` (Counter)
- **OpenTelemetry Tracing:** Span per evaluation covering `calculate_ratios`, `apply_stress_test`, `lookup_cmhc_premium`.
- **Structured Logging:** Every evaluation logs `event="underwriting_decision"`, `application_id`, `gds`, `tds`, `ltv`, `decision`, `correlation_id`.

---

## 9. Testing Strategy

- **Unit Tests** (`tests/unit/test_underwriting.py`):
  - Stress test rate calculation edge cases (contract_rate + 2% vs 5.25%).
  - GDS/TDS formula with condo fee 50% rule.
  - CMHC premium tier boundaries (80.01%, 85.01%, 90.01%).
  - Down‑payment rule per property value bracket.

- **Integration Tests** (`tests/integration/test_underwriting_integration.py`):
  - Full flow: `POST /calculate` → `POST /evaluate` → `GET /result`.
  - Override flow with admin token.
  - FINTRAC event emission for loan ≥ $10 k.
  - Audit log verification in structlog output.

---

**Next Steps:**  
1. Implement the `UnderwritingCalcService` with the above algorithms.  
2. Create Alembic migration for `underwriting_results` table.  
3. Add enum for `DeclineReason` and `Condition` templates.  
4. Stub conditional logic and log warning for future refinement.  
5. Wire Prometheus metrics and OpenTelemetry instrumentation.