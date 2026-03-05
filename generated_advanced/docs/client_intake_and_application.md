# Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Client Intake & Application Module Design Plan

**Module Identifier:** `client_intake`  
**Design Document:** `docs/design/client-intake-application.md`  
**Version:** 1.0  
**Regulatory Framework:** OSFI B-20, FINTRAC, CMHC, PIPEDA

---

## 1. Endpoints

### 1.1 POST /api/v1/applications
Create a new mortgage application (draft status).

**Authentication:** Authenticated user (Client or Broker)

**Request Body Schema:**
```python
class ApplicationCreateRequest(BaseModel):
    # Property Details
    property_address: str = Field(..., min_length=5, max_length=500)
    property_type: Literal["single_family", "condo", "townhouse", "multi_unit"]
    property_value: Decimal = Field(..., gt=0, decimal_places=2, max_digits=12)
    purchase_price: Decimal = Field(..., gt=0, decimal_places=2, max_digits=12)
    
    # Mortgage Terms
    down_payment: Decimal = Field(..., ge=0, decimal_places=2, max_digits=12)
    requested_loan_amount: Decimal = Field(..., gt=0, decimal_places=2, max_digits=12)
    amortization_years: int = Field(..., ge=5, le=30)
    term_years: int = Field(..., ge=1, le=10)
    mortgage_type: Literal["fixed", "variable", "hybrid"]
    
    # Co-Borrowers (optional)
    co_borrowers: Optional[List[CoBorrowerCreate]] = Field(default=None, max_items=3)
    
    class CoBorrowerCreate(BaseModel):
        full_name: str = Field(..., min_length=2, max_length=200)
        sin_encrypted: str  # Already encrypted by client-side SDK
        annual_income: Decimal = Field(..., gt=0, decimal_places=2, max_digits=10)
        employment_status: Literal["employed", "self_employed", "other"]
        credit_score: int = Field(..., ge=300, le=900)
```

**Response Schema:**
```python
class ApplicationCreateResponse(BaseModel):
    id: UUID
    status: Literal["draft", "submitted", "underwriting", "approved", "rejected"]
    created_at: datetime
    property_address: str
    property_value: Decimal
    warning_flags: List[str]  # e.g., ["high_ltv", "short_employment"]
```

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 400 | `CLIENT_INTAKE_002` | `purchase_price` ≤ 0 or `down_payment` ≥ `purchase_price` |
| 400 | `CLIENT_INTAKE_003` | LTV > 95% (CMHC maximum) |
| 400 | `CLIENT_INTAKE_003` | Uninsured amortization > 25 years |
| 403 | `CLIENT_INTAKE_004` | Broker accessing unassigned client |
| 422 | `CLIENT_INTAKE_002` | `property_address` fails validation |

---

### 1.2 GET /api/v1/applications
List applications with pagination and role-based filtering.

**Authentication:** Authenticated user (Client or Broker)

**Query Parameters:**
- `status: Optional[str]` - Filter by application status
- `page: int = 1` - Pagination page
- `page_size: int = 20` - Items per page (max 100)

**Response Schema:**
```python
class ApplicationListResponse(BaseModel):
    items: List[ApplicationSummary]
    total: int
    page: int
    page_size: int

class ApplicationSummary(BaseModel):
    id: UUID
    status: str
    property_address: str
    property_value: Decimal
    created_at: datetime
    updated_at: datetime
```

**Access Control:**
- **Client:** Can only list applications where `client.user_id` matches JWT `sub`
- **Broker:** Can only list applications where `broker_id` matches JWT `sub`

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 403 | `CLIENT_INTAKE_004` | User attempting to access unauthorized records |

---

### 1.3 GET /api/v1/applications/{id}
Get full application details (excluding encrypted PII).

**Authentication:** Authenticated user (Client or Broker)

**Response Schema:**
```python
class ApplicationDetailResponse(BaseModel):
    id: UUID
    status: str
    client: ClientSummary  # No SIN/DOB
    property_address: str
    property_value: Decimal
    purchase_price: Decimal
    down_payment: Decimal
    requested_loan_amount: Decimal
    ltv_ratio: Decimal  # Calculated
    insurance_required: bool
    insurance_premium: Optional[Decimal]
    amortization_years: int
    term_years: int
    mortgage_type: str
    co_borrowers: List[CoBorrowerSummary]
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]
```

**PIPEDA Compliance:** SIN and DOB are **never** returned. Use `sin_hash` for internal correlation only.

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 404 | `CLIENT_INTAKE_001` | Application not found |
| 403 | `CLIENT_INTAKE_004` | User not authorized to view this application |

---

### 1.4 PUT /api/v1/applications/{id}
Update draft application. Locked after submission.

**Authentication:** Authenticated user (Client or Broker)

**Request Body Schema:** Same as `ApplicationCreateRequest` (partial updates allowed)

**Response Schema:** `ApplicationDetailResponse`

**Business Rules:**
- Only editable in `draft` status
- `submitted_at` is immutable once set
- LTV and insurance requirements recalculated on each update

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 400 | `CLIENT_INTAKE_003` | Attempting to update non-draft application |
| 404 | `CLIENT_INTAKE_001` | Application not found |
| 403 | `CLIENT_INTAKE_004` | User not authorized |
| 422 | `CLIENT_INTAKE_002` | Validation failure |

---

### 1.5 POST /api/v1/applications/{id}/submit
Submit application for underwriting. Triggers compliance checks.

**Authentication:** Authenticated user (Client or Broker)

**Request Body:** `None` (state transition only)

**Response Schema:**
```python
class ApplicationSubmitResponse(BaseModel):
    id: UUID
    status: Literal["submitted", "underwriting"]
    message: str
    compliance_flags: List[str]  # e.g., ["FINTRAC_10000", "HIGH_GDS"]
```

**Business Logic:**
1. Validate all required fields present
2. Calculate LTV and determine CMHC insurance requirement
3. Perform OSFI B-20 stress test calculation (GDS/TDS)
4. Check FINTRAC thresholds (transaction > CAD $10,000)
5. Transition status: `draft` → `submitted` → `underwriting` (auto-advance if valid)
6. Create immutable audit log entry

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 400 | `CLIENT_INTAKE_003` | GDS > 39% or TDS > 44% (OSFI B-20) |
| 400 | `CLIENT_INTAKE_003` | Missing required fields |
| 409 | `CLIENT_INTAKE_005` | Application already submitted |
| 404 | `CLIENT_INTAKE_001` | Application not found |

---

### 1.6 GET /api/v1/applications/{id}/summary
Get PDF-ready JSON for disclosure statements.

**Authentication:** Authenticated user (Client or Broker)

**Response Schema:**
```python
class ApplicationPDFSummary(BaseModel):
    application_id: UUID
    generated_at: datetime
    client: ClientDisclosure  # Masked SIN (last 4), no DOB
    property: PropertyDisclosure
    mortgage: MortgageDisclosure
    ratios: RatioDisclosure
    compliance: ComplianceDisclosure
```

**PIPEDA Compliance:** SIN masked as `***-**-1234`. DOB omitted entirely.

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 404 | `CLIENT_INTAKE_001` | Application not found |
| 403 | `CLIENT_INTAKE_004` | Unauthorized access |

---

## 2. Models & Database

### 2.1 clients Table
```python
class Client(Base):
    __tablename__ = "clients"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # PIPEDA: Encrypted PII
    sin_encrypted = Column(LargeBinary, nullable=False)  # AES-256-GCM encrypted
    sin_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA256 for lookups
    date_of_birth_encrypted = Column(LargeBinary, nullable=False)  # AES-256-GCM encrypted
    
    # Financial Profile
    employment_status = Column(String(50), nullable=False)
    employer_name = Column(String(200), nullable=True)
    years_employed = Column(Numeric(4, 2), nullable=False)  # e.g., 2.50 years
    annual_income = Column(Numeric(12, 2), nullable=False)
    other_income = Column(Numeric(12, 2), default=0)
    credit_score = Column(Integer, nullable=False)
    marital_status = Column(String(20), nullable=True)
    
    # Audit
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=False)  # JWT sub
    
    # Relationships
    applications = relationship("Application", back_populates="client")
    
    # Indexes
    __table_args__ = (
        Index("idx_clients_user_id", "user_id"),
        Index("idx_clients_sin_hash", "sin_hash", unique=True),
    )
```

**Constraints:**
- `annual_income > 0`
- `years_employed >= 0`
- `credit_score BETWEEN 300 AND 900`

---

### 2.2 applications Table
```python
class Application(Base):
    __tablename__ = "applications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    broker_id = Column(UUID(as_uuid=True), ForeignKey("brokers.id"), nullable=True, index=True)
    
    # Application Metadata
    application_type = Column(String(50), nullable=False, default="purchase")
    status = Column(String(50), nullable=False, default="draft", index=True)
    
    # Property Details
    property_address = Column(String(500), nullable=False)
    property_type = Column(String(50), nullable=False)
    property_value = Column(Numeric(12, 2), nullable=False)
    purchase_price = Column(Numeric(12, 2), nullable=False)
    
    # Mortgage Terms
    down_payment = Column(Numeric(12, 2), nullable=False)
    requested_loan_amount = Column(Numeric(12, 2), nullable=False)
    amortization_years = Column(Integer, nullable=False)
    term_years = Column(Integer, nullable=False)
    mortgage_type = Column(String(50), nullable=False)
    
    # Calculated Fields (stored for audit)
    ltv_ratio = Column(Numeric(5, 4), nullable=True)  # e.g., 0.8543
    insurance_required = Column(Boolean, default=False)
    insurance_premium = Column(Numeric(12, 2), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    client = relationship("Client", back_populates="applications")
    co_borrowers = relationship("CoBorrower", back_populates="application", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_applications_client_status", "client_id", "status"),
        Index("idx_applications_broker_id", "broker_id"),
        Index("idx_applications_submitted_at", "submitted_at"),
        CheckConstraint("purchase_price > 0", name="chk_purchase_price_positive"),
        CheckConstraint("down_payment < purchase_price", name="chk_down_payment_lt_price"),
        CheckConstraint("amortization_years BETWEEN 5 AND 30", name="chk_amortization_range"),
        CheckConstraint("term_years BETWEEN 1 AND 10", name="chk_term_range"),
    )
```

---

### 2.3 co_borrowers Table
```python
class CoBorrower(Base):
    __tablename__ = "co_borrowers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)
    
    # PII
    full_name = Column(String(200), nullable=False)
    sin_encrypted = Column(LargeBinary, nullable=False)
    sin_hash = Column(String(64), nullable=False, index=True)
    
    # Financial Profile
    annual_income = Column(Numeric(12, 2), nullable=False)
    employment_status = Column(String(50), nullable=False)
    credit_score = Column(Integer, nullable=False)
    
    # Audit
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    application = relationship("Application", back_populates="co_borrowers")
    
    # Indexes
    __table_args__ = (
        Index("idx_coborrowers_app_id", "application_id"),
        Index("idx_coborrowers_sin_hash", "sin_hash"),
    )
```

**Constraints:**
- `annual_income > 0`
- `credit_score BETWEEN 300 AND 900`

---

## 3. Business Logic

### 3.1 State Machine Transitions
```python
class ApplicationStatus(Enum):
    DRAFT = "draft"          # Initial state, editable
    SUBMITTED = "submitted"  # Submitted, awaiting underwriting
    UNDERWRITING = "underwriting"  # Under review
    APPROVED = "approved"    # Meets all criteria
    REJECTED = "rejected"    # Fails OSFI B-20 or policy

# Valid Transitions
VALID_TRANSITIONS = {
    "draft": ["submitted"],
    "submitted": ["underwriting", "rejected"],
    "underwriting": ["approved", "rejected"],
    "approved": [],  # Terminal
    "rejected": [],  # Terminal
}
```

**Transition Rules:**
- `draft` → `submitted`: Triggered by `/submit` endpoint
- `submitted` → `underwriting`: Auto-advance if validation passes
- Any → `rejected`: If GDS/TDS exceeds OSFI limits or LTV > 95%

---

### 3.2 Validation & Calculation Algorithms

#### 3.2.1 LTV Calculation (CMHC)
```python
def calculate_ltv(loan_amount: Decimal, property_value: Decimal) -> Decimal:
    """
    CMHC LTV = loan_amount / property_value
    Precision: 4 decimal places (e.g., 85.43% = 0.8543)
    """
    if property_value <= 0:
        raise ValueError("Property value must be > 0")
    return (loan_amount / property_value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
```

#### 3.2.2 CMHC Insurance Requirement & Premium
```python
def calculate_cmhc_premium(ltv: Decimal, loan_amount: Decimal) -> Tuple[bool, Optional[Decimal]]:
    """
    Returns: (insurance_required, premium_amount)
    Premium tiers per CMHC:
    - 80.01-85%: 2.80%
    - 85.01-90%: 3.10%
    - 90.01-95%: 4.00%
    """
    if ltv <= Decimal("0.80"):
        return False, None
    
    if ltv > Decimal("0.95"):
        raise BusinessRuleError("LTV exceeds CMHC maximum of 95%")
    
    # Determine premium rate
    if ltv <= Decimal("0.85"):
        rate = Decimal("0.0280")
    elif ltv <= Decimal("0.90"):
        rate = Decimal("0.0310")
    else:
        rate = Decimal("0.0400")
    
    premium = (loan_amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return True, premium
```

#### 3.2.3 OSFI B-20 Stress Test (GDS/TDS)
```python
def calculate_gds_tds(
    annual_income: Decimal,
    other_income: Decimal,
    mortgage_payment: Decimal,
    property_tax: Decimal,
    heating_cost: Decimal,
    other_debts: Decimal,
    qualifying_rate: Decimal,  # max(contract_rate + 2%, 5.25%)
) -> Tuple[Decimal, Decimal]:
    """
    GDS = (PITH) / Gross Monthly Income
    TDS = (PITH + Other Debts) / Gross Monthly Income
    
    Where:
    P = Principal & Interest (at qualifying_rate)
    I = Property Tax (annual / 12)
    T = Heating Costs (estimated $100/month)
    H = 50% of condo fees (if applicable)
    
    Limits: GDS ≤ 39%, TDS ≤ 44%
    """
    gross_monthly = (annual_income + other_income) / 12
    
    # Calculate monthly mortgage payment at qualifying_rate
    # Using standard mortgage formula (simplified)
    monthly_payment = calculate_mortgage_payment(
        loan_amount, qualifying_rate, amortization_years
    )
    
    pit = monthly_payment + (property_tax / 12) + 100  # heating estimate
    gds = (pit / gross_monthly) * 100
    tds = ((pit + other_debts) / gross_monthly) * 100
    
    return (
        gds.quantize(Decimal("0.01")),
        tds.quantize(Decimal("0.01"))
    )
```

**Stress Test Rate:** `qualifying_rate = max(contract_rate + 2%, 5.25%)`

---

### 3.3 Decision Tree
```
START: Application Submitted
│
├─► LTV > 95% ? → REJECT (CMHC limit exceeded)
│
├─► GDS > 39% ? → REJECT (OSFI B-20 violation)
│
├─► TDS > 44% ? → REJECT (OSFI B-20 violation)
│
├─► Credit Score < 600 ? → REJECT (Policy minimum)
│
├─► Annual Income < $25,000 ? → REJECT (Policy minimum)
│
└─► PASS → APPROVED (pending final underwriting)
```

---

## 4. Migrations

### 4.1 New Tables
**Alembic Revision:** `2024_01_01_0001_create_client_intake_tables.py`

```python
def upgrade():
    # clients table
    op.create_table(
        "clients",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("user_id", UUID(), nullable=False),
        sa.Column("sin_encrypted", LargeBinary(), nullable=False),
        sa.Column("sin_hash", sa.String(64), nullable=False),
        sa.Column("date_of_birth_encrypted", LargeBinary(), nullable=False),
        sa.Column("employment_status", sa.String(50), nullable=False),
        sa.Column("employer_name", sa.String(200), nullable=True),
        sa.Column("years_employed", Numeric(4, 2), nullable=False),
        sa.Column("annual_income", Numeric(12, 2), nullable=False),
        sa.Column("other_income", Numeric(12, 2), server_default="0"),
        sa.Column("credit_score", sa.Integer(), nullable=False),
        sa.Column("marital_status", sa.String(20), nullable=True),
        sa.Column("created_at", DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("sin_hash"),
    )
    op.create_index("idx_clients_user_id", "clients", ["user_id"])
    op.create_index("idx_clients_sin_hash", "clients", ["sin_hash"], unique=True)
    
    # applications table
    op.create_table(
        "applications",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("client_id", UUID(), nullable=False),
        sa.Column("broker_id", UUID(), nullable=True),
        sa.Column("application_type", sa.String(50), server_default="purchase"),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("property_address", sa.String(500), nullable=False),
        sa.Column("property_type", sa.String(50), nullable=False),
        sa.Column("property_value", Numeric(12, 2), nullable=False),
        sa.Column("purchase_price", Numeric(12, 2), nullable=False),
        sa.Column("down_payment", Numeric(12, 2), nullable=False),
        sa.Column("requested_loan_amount", Numeric(12, 2), nullable=False),
        sa.Column("amortization_years", sa.Integer(), nullable=False),
        sa.Column("term_years", sa.Integer(), nullable=False),
        sa.Column("mortgage_type", sa.String(50), nullable=False),
        sa.Column("ltv_ratio", Numeric(5, 4), nullable=True),
        sa.Column("insurance_required", sa.Boolean(), server_default="false"),
        sa.Column("insurance_premium", Numeric(12, 2), nullable=True),
        sa.Column("created_at", DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("submitted_at", DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"]),
        sa.CheckConstraint("purchase_price > 0", name="chk_purchase_price_positive"),
        sa.CheckConstraint("down_payment < purchase_price", name="chk_down_payment_lt_price"),
        sa.CheckConstraint("amortization_years BETWEEN 5 AND 30", name="chk_amortization_range"),
        sa.CheckConstraint("term_years BETWEEN 1 AND 10", name="chk_term_range"),
    )
    op.create_index("idx_applications_client_status", "applications", ["client_id", "status"])
    op.create_index("idx_applications_broker_id", "applications", ["broker_id"])
    op.create_index("idx_applications_submitted_at", "applications", ["submitted_at"])
    
    # co_borrowers table
    op.create_table(
        "co_borrowers",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("application_id", UUID(), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("sin_encrypted", LargeBinary(), nullable=False),
        sa.Column("sin_hash", sa.String(64), nullable=False),
        sa.Column("annual_income", Numeric(12, 2), nullable=False),
        sa.Column("employment_status", sa.String(50), nullable=False),
        sa.Column("credit_score", sa.Integer(), nullable=False),
        sa.Column("created_at", DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
    )
    op.create_index("idx_coborrowers_app_id", "co_borrowers", ["application_id"])
    op.create_index("idx_coborrowers_sin_hash", "co_borrowers", ["sin_hash"])
```

### 4.2 Data Migration Needs
- **None** for initial creation. Future migrations must preserve `sin_encrypted` data integrity during key rotations.

---

## 5. Security & Compliance

### 5.1 PIPEDA Data Handling
- **SIN Encryption:** AES-256-GCM with 12-byte nonce, 16-byte tag. Key stored in `common/security.py` via `pydantic.BaseSettings` (KMS-backed in production).
- **DOB Encryption:** Same encryption scheme as SIN.
- **Key Rotation:** Every 90 days. Old keys retained for decryption only.
- **API Responses:** SIN/DOB **never** serialized. Use `sin_hash` for deduplication.
- **Logging:** Strict redaction of PII fields via `structlog` processor.

### 5.2 OSFI B-20 Compliance
- **Stress Test:** Automatically applied on `/submit`. Qualifying rate = `max(contract_rate + 2%, 5.25%)`.
- **Hard Limits:** GDS ≤ 39%, TDS ≤ 44%. Violations return `CLIENT_INTAKE_003`.
- **Audit Trail:** Calculation breakdown logged with `correlation_id`:
  ```json
  {
    "event": "osfi_b20_calculation",
    "correlation_id": "...",
    "application_id": "...",
    "gds": "38.50",
    "tds": "42.10",
    "qualifying_rate": "7.25",
    "pass": true
  }
  ```

### 5.3 FINTRAC Reporting Triggers
- **Threshold:** `purchase_price >= CAD $10,000` (always true for mortgages)
- **Flag:** `applications.insurance_required` or `purchase_price > 10000` sets `transaction_type = "large_currency_transaction"`
- **Audit:** Immutable `compliance_log` table entry created on submit:
  ```python
  class ComplianceLog(Base):
      __tablename__ = "compliance_log"
      id = Column(UUID, primary_key=True)
      application_id = Column(UUID, ForeignKey("applications.id"))
      fintrac_triggered = Column(Boolean, default=False)
      transaction_amount = Column(Numeric(12, 2))
      created_at = Column(DateTime, server_default=func.now())
      # 5-year retention enforced by PostgreSQL partitioning
  ```

### 5.4 Authentication & Authorization
- **JWT Claims:** `sub` (user_id), `role` (client|broker|admin), `broker_id` (if applicable)
- **Client Access:** `WHERE applications.client.user_id = :jwt_sub`
- **Broker Access:** `WHERE applications.broker_id = :jwt_broker_id`
- **Admin Access:** No filtering (rare, audited)
- **Forbidden:** 403 with `CLIENT_INTAKE_004`

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
# modules/client_intake/exceptions.py
class ClientIntakeException(AppException):
    """Base exception for client intake module"""
    pass

class ApplicationNotFoundError(ClientIntakeException):
    """Application ID not found in system"""
    pass

class ApplicationValidationError(ClientIntakeException):
    """Request fails Pydantic or business validation"""
    pass

class BusinessRuleViolationError(ClientIntakeException):
    """OSFI B-20, CMHC, or policy rule violation"""
    pass

class UnauthorizedAccessError(ClientIntakeException):
    """User lacks permission for this resource"""
    pass

class InvalidStateTransitionError(ClientIntakeException):
    """Status transition not allowed"""
    pass
```

### 6.2 Error Code Mapping
| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `ApplicationNotFoundError` | 404 | `CLIENT_INTAKE_001` | "Application {id} not found" | WARNING |
| `ApplicationValidationError` | 422 | `CLIENT_INTAKE_002` | "{field}: {reason}" | INFO |
| `BusinessRuleViolationError` | 400 | `CLIENT_INTAKE_003` | "{rule} violated: {detail}" | WARNING |
| `UnauthorizedAccessError` | 403 | `CLIENT_INTAKE_004` | "Access denied to application {id}" | ERROR |
| `InvalidStateTransitionError` | 409 | `CLIENT_INTAKE_005` | "Invalid transition from {from} to {to}" | INFO |

### 6.3 Structured Error Response Format
```json
{
  "detail": "GDS ratio 42.50% exceeds OSFI B-20 limit of 39%",
  "error_code": "CLIENT_INTAKE_003",
  "correlation_id": "c4a3b2e1-f8d7-6c5b-4a3d-2e1f0c9b8a7d",
  "timestamp": "2024-01-15T14:30:00Z",
  "context": {
    "application_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "gds": "42.50",
    "qualifying_rate": "7.25"
  }
}
```

---

## 7. Additional Considerations

### 7.1 SIN Encryption Key Management
- **Development:** Use `DOTENV` key in `.env` (never commit)
- **Staging/Production:** AWS KMS or Azure Key Vault integration via `common/security.py`
- **Key ID:** Stored alongside encrypted data (`sin_encrypted` header includes key version)
- **Rotation:** Async background job re-encrypts data with new key; old key retained for 30 days

### 7.2 Default Values
- `application_type`: `"purchase"` (other: `"refinance"`, `"transfer"`)
- `mortgage_type`: `"fixed"` (other: `"variable"`, `"hybrid"`)
- `status`: `"draft"`

### 7.3 Co-Borrower Management
- **Add:** Via `PUT /applications/{id}` (full replacement of co_borrowers list)
- **Remove:** Set list to `[]` or omit from update
- **Limit:** Max 3 co-borrowers per application (OSFI guideline)

### 7.4 Audit Logging
All service methods decorated with `@audit_log()` capturing:
- `correlation_id`
- `user_id`
- `action` (create, update, submit)
- `application_id`
- `changes` (JSON diff for updates)

---

## 8. Testing Strategy

### 8.1 Unit Tests (`tests/unit/test_client_intake.py`)
- LTV calculation edge cases (0.01 increments)
- CMHC premium tier boundaries
- GDS/TDS stress test with various rates
- State transition validation

### 8.2 Integration Tests (`tests/integration/test_client_intake_integration.py`)
- Full workflow: create → update → submit → approve
- Role-based access control
- FINTRAC flagging for $10,000+ transactions
- PII encryption/decryption round-trip
- Concurrent submission attempts (idempotency)

---

**Document Version Control:** This design follows semantic versioning. Any changes to regulatory logic require major version bump and re-audit.