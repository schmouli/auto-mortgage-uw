# Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

docs/design/client-intake-application.md

# Client Intake & Application Module Design

**Module Identifier:** `INTAKE`  
**Feature Slug:** `client-intake-application`  
**Regulatory Domain:** OSFI B-20, FINTRAC, CMHC, PIPEDA  

---

## 1. Endpoints

### `POST /api/v1/applications`
Create a new mortgage application with client and optional co-borrower data.

**Authentication:** Authenticated (client or broker)  
**Authorization:** Client can create for self; broker can create for assigned clients  

**Request Body (`CreateApplicationRequest`):**
```python
{
  "client_data": {
    "sin": "123-456-789",  # Plaintext; encrypted at rest per PIPEDA
    "date_of_birth": "1985-06-15",  # ISO 8601; encrypted at rest
    "employment_status": "employed",  # Enum: employed, self_employed, unemployed, retired
    "employer_name": "Acme Corp",
    "years_employed": "3.50",  # Decimal
    "annual_income": "85000.00",  # Decimal
    "other_income": "5000.00",  # Decimal, optional
    "credit_score": 720,  # Integer 300-900
    "marital_status": "married"  # Enum: single, married, common_law, divorced, widowed
  },
  "co_borrowers": [  # Optional; max 3 per CMHC rules
    {
      "full_name": "Jane Doe",
      "sin": "987-654-321",
      "annual_income": "65000.00",
      "employment_status": "employed",
      "credit_score": 680
    }
  ],
  "application_data": {
    "application_type": "purchase",  # Enum: purchase, refinance, renewal, switch
    "property_address": "123 Main St, Toronto, ON",
    "property_type": "single_family",  # Enum: single_family, condo, townhouse, multi_unit, commercial
    "property_value": "750000.00",  # Decimal
    "purchase_price": "750000.00",  # Decimal, must be > 0
    "down_payment": "150000.00",  # Decimal
    "requested_loan_amount": "600000.00",  # Decimal
    "amortization_years": 25,  # Integer 5-30 (insured) / 5-25 (uninsured)
    "term_years": 5,  # Integer 1-10
    "mortgage_type": "fixed"  # Enum: fixed, variable, adjustable
  }
}
```

**Response (`ApplicationResponse`):**
```python
{
  "application_id": "uuid",
  "client_id": "uuid",
  "status": "draft",
  "application_type": "purchase",
  "property_address": "123 Main St, Toronto, ON",
  "property_value": "750000.00",
  "requested_loan_amount": "600000.00",
  "ltv_ratio": "0.8000",
  "insurance_required": True,
  "insurance_premium": "16800.00",
  "created_at": "2024-01-15T10:30:00Z"
}
```
*Note: SIN, DOB, and income values are never returned per PIPEDA.*

**Error Responses:**
- `422 INTAKE_002`: Validation error (e.g., amortization_years out of range)
- `403 INTAKE_004`: Unauthorized access if broker not assigned to client
- `409 INTAKE_003`: Business rule violation (e.g., down_payment < 5% of purchase_price)

---

### `GET /api/v1/applications`
List applications with pagination and filtering.

**Authentication:** Authenticated (client or broker)  
**Authorization:** Client sees own; broker sees assigned  

**Query Parameters:**
- `status`: Optional filter (e.g., `status=submitted`)
- `page`: Integer (default 1)
- `limit`: Integer (default 20, max 100)

**Response (`List[ApplicationSummaryResponse]`):**
```python
{
  "items": [
    {
      "application_id": "uuid",
      "status": "draft",
      "application_type": "purchase",
      "property_address": "123 Main St, Toronto, ON",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 20
}
```

**Error Responses:**
- `403 INTAKE_004`: Access denied if unauthorized filter applied

---

### `GET /api/v1/applications/{id}`
Get single application details.

**Authentication:** Authenticated  
**Authorization:** Client (own apps) or broker (assigned apps) only  

**Response (`ApplicationDetailResponse`):**
```python
{
  "application_id": "uuid",
  "client_id": "uuid",
  "client_summary": {
    "employment_status": "employed",
    "employer_name": "Acme Corp",
    "years_employed": "3.50",
    # No sin, date_of_birth, or income values per PIPEDA
  },
  "co_borrowers": [
    {
      "full_name": "Jane Doe",
      "employment_status": "employed",
      # No sin or income
    }
  ],
  "property_address": "123 Main St, Toronto, ON",
  "property_value": "750000.00",
  "purchase_price": "750000.00",
  "down_payment": "150000.00",
  "requested_loan_amount": "600000.00",
  "ltv_ratio": "0.8000",
  "insurance_required": True,
  "insurance_premium": "16800.00",
  "amortization_years": 25,
  "term_years": 5,
  "mortgage_type": "fixed",
  "status": "draft",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

**Error Responses:**
- `404 INTAKE_001`: Application not found
- `403 INTAKE_004`: Access denied

---

### `PUT /api/v1/applications/{id}`
Update application (draft status only).

**Authentication:** Authenticated  
**Authorization:** Client (own apps) or broker (assigned apps)  

**Request Body (`UpdateApplicationRequest`):**
Same as `CreateApplicationRequest` but all fields optional. Co-borrowers array replaces existing list.

**Response (`ApplicationResponse`):**
Updated application summary (same structure as POST response).

**Error Responses:**
- `404 INTAKE_001`: Application not found
- `403 INTAKE_004`: Access denied
- `409 INTAKE_006`: Invalid status transition (if status != draft)
- `422 INTAKE_002`: Validation error

---

### `POST /api/v1/applications/{id}/submit`
Submit application for underwriting. Triggers validation, ratio calculation, and status transition.

**Authentication:** Authenticated  
**Authorization:** Client (own apps) or broker (assigned apps)  

**Request Body:** None (idempotent submission)

**Response (`ApplicationResponse`):**
```python
{
  "application_id": "uuid",
  "status": "submitted",
  "submitted_at": "2024-01-15T11:05:00Z",
  # ... other fields
}
```

**Business Logic:**
1. Validate all required fields populated
2. Calculate LTV ratio and CMHC insurance requirement
3. Perform OSFI B-20 stress test calculation (GDS/TDS)
4. Enforce GDS ≤ 39%, TDS ≤ 44%
5. Log calculation breakdown for audit (structlog)
6. Transition status: `draft` → `submitted`
7. Create immutable audit record (FINTRAC compliance)

**Error Responses:**
- `422 INTAKE_003`: GDS/TDS exceeds limits (include calculated values in detail)
- `409 INTAKE_006`: Invalid status transition
- `404 INTAKE_001`: Application not found

---

### `GET /api/v1/applications/{id}/summary`
Get PDF-ready JSON summary for document generation.

**Authentication:** Authenticated  
**Authorization:** Client (own apps) or broker (assigned apps)  

**Response (`ApplicationSummaryPdfSchema`):**
```python
{
  "application_id": "uuid",
  "generated_at": "2024-01-15T12:00:00Z",
  "client": {
    "full_name": "John Doe",  # From user profile
    "employment_status": "employed",
    "employer_name": "Acme Corp",
    "years_employed": "3.50"
    # No PII
  },
  "co_borrowers": [...],
  "property": {
    "address": "123 Main St, Toronto, ON",
    "type": "single_family",
    "value": "750000.00",
    "purchase_price": "750000.00"
  },
  "mortgage": {
    "loan_amount": "600000.00",
    "down_payment": "150000.00",
    "ltv": "80.00%",
    "amortization": 25,
    "term": 5,
    "type": "fixed",
    "insurance_required": True,
    "insurance_premium": "16800.00"
  },
  "compliance": {
    "gds_ratio": "32.50",  # Calculated per OSFI B-20
    "tds_ratio": "38.20",
    "stress_test_rate": "5.25%",
    "fintrac_reportable": False  # If > $10,000 transaction
  }
}
```

---

## 2. Models & Database

### `clients` Table
```python
class Client(Base):
    __tablename__ = "clients"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    
    # PIPEDA: Encrypted at rest
    sin_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sin_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA256 for lookups
    
    date_of_birth_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    employment_status: Mapped[str] = mapped_column(String(50), nullable=False)
    employer_name: Mapped[str] = mapped_column(String(255))
    years_employed: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    
    # Never log these per FINTRAC/PIPEDA
    annual_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    other_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    
    credit_score: Mapped[int] = mapped_column(Integer)
    marital_status: Mapped[str] = mapped_column(String(50))
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="client")
    applications: Mapped[List["Application"]] = relationship(back_populates="client")
    
    __table_args__ = (
        Index("idx_clients_sin_hash", "sin_hash"),
        Index("idx_clients_user_id", "user_id"),
    )
```

### `applications` Table
```python
class Application(Base):
    __tablename__ = "applications"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    broker_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    
    application_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    property_address: Mapped[str] = mapped_column(Text, nullable=False)
    property_type: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Financial values: Decimal only
    property_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    down_payment: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    requested_loan_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # CMHC LTV calculation (stored for audit)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    insurance_required: Mapped[bool] = mapped_column(Boolean, default=False)
    insurance_premium: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    
    amortization_years: Mapped[int] = mapped_column(Integer, nullable=False)
    term_years: Mapped[int] = mapped_column(Integer, nullable=False)
    mortgage_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # OSFI B-20 calculated ratios (stored at submission)
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=True)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=True)
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=True)
    
    # FINTRAC: Flag for transactions > $10,000
    fintrac_reportable: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    client: Mapped["Client"] = relationship(back_populates="applications")
    co_borrowers: Mapped[List["CoBorrower"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_applications_client_status", "client_id", "status"),
        Index("idx_applications_broker_submitted", "broker_id", "submitted_at"),
        CheckConstraint("purchase_price > 0", name="chk_purchase_price_positive"),
        CheckConstraint("amortization_years BETWEEN 5 AND 30", name="chk_amortization_range"),
        CheckConstraint("term_years BETWEEN 1 AND 10", name="chk_term_range"),
    )
```

### `co_borrowers` Table
```python
class CoBorrower(Base):
    __tablename__ = "co_borrowers"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # PIPEDA: Encrypted at rest
    sin_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sin_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    annual_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    employment_status: Mapped[str] = mapped_column(String(50), nullable=False)
    credit_score: Mapped[int] = mapped_column(Integer)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="co_borrowers")
    
    __table_args__ = (
        Index("idx_coborrowers_app_sin", "application_id", "sin_hash"),
    )
```

---

## 3. Business Logic

### Application Status State Machine
```python
STATUS_FLOW = {
    "draft": ["submitted"],
    "submitted": ["underwriting", "rejected"],
    "underwriting": ["approved", "rejected", "conditions"],
    "conditions": ["approved", "rejected"],
    "approved": ["closed"],
    "rejected": [],  # Terminal
    "closed": []     # Terminal
}
```

**Transition Rules:**
- Only `draft` → `submitted` via API endpoint (user-initiated)
- All other transitions via underwriting module (system-controlled)
- Once `submitted`, application data is immutable (FINTRAC audit trail)
- Co-borrowers cannot be added/removed after `submitted`

### OSFI B-20 GDS/TDS Calculation (Stress Test)
**Formula:**
```
gross_monthly_income = (client.annual_income + client.other_income) / 12
# Include co-borrowers if present
for cb in co_borrowers:
    gross_monthly_income += cb.annual_income / 12

# Stress test rate per OSFI B-20
qualifying_rate = max(contract_rate + 2.0%, 5.25%)

# Monthly payment at qualifying rate (using mortgage formula)
monthly_payment = calculate_payment(requested_loan_amount, qualifying_rate, amortization_years)

# GDS = (PITH) / gross_monthly_income
# TDS = (PITH + other_debt) / gross_monthly_income
# Assume property_taxes = 1% of property_value annually
# Assume heating = $100/month
# other_debt from external credit bureau (mocked for this module)

gds_ratio = (monthly_payment + property_taxes + heating) / gross_monthly_income
tds_ratio = gds_ratio + (other_debt / gross_monthly_income)

# Enforcement
if gds_ratio > 0.39 or tds_ratio > 0.44:
    raise ApplicationBusinessRuleError("OSFI B-20 thresholds exceeded")
```

**Audit Logging:**
```python
log.info(
    "osfi_b20_calculation",
    application_id=app.id,
    gross_monthly_income=gross_monthly_income,
    qualifying_rate=qualifying_rate,
    monthly_payment=monthly_payment,
    gds_ratio=gds_ratio,
    tds_ratio=tds_ratio,
    # NEVER log income source data or PII
)
```

### CMHC Insurance Premium Calculation
```python
ltv_ratio = requested_loan_amount / property_value

if ltv_ratio > Decimal("0.80"):
    insurance_required = True
    if Decimal("0.8001") <= ltv_ratio <= Decimal("0.85"):
        premium_rate = Decimal("0.0280")
    elif Decimal("0.8501") <= ltv_ratio <= Decimal("0.90"):
        premium_rate = Decimal("0.0310")
    elif Decimal("0.9001") <= ltv_ratio <= Decimal("0.95"):
        premium_rate = Decimal("0.0400")
    else:
        raise ApplicationValidationError("LTV exceeds 95% CMHC maximum")
    
    insurance_premium = requested_loan_amount * premium_rate
else:
    insurance_required = False
    insurance_premium = Decimal("0.00")
```

### FINTRAC Compliance Triggers
- `fintrac_reportable = True` if `requested_loan_amount >= 10000.00`
- On submission, create immutable audit record in `fintrac_reports` table
- Log identity verification event: `log.info("identity_verified", application_id=app.id)`
- Retention: PostgreSQL policy prevents deletion for 5 years

### Validation Rules
| Field | Rule | Error Code |
|-------|------|------------|
| purchase_price | > 0 | INTAKE_002 |
| down_payment | ≥ 5% of purchase_price | INTAKE_003 |
| amortization_years | 5-30 if insured, 5-25 if uninsured | INTAKE_002 |
| term_years | 1-10 | INTAKE_002 |
| annual_income | > 0 | INTAKE_002 |
| credit_score | 300-900 | INTAKE_002 |
| co_borrowers | Max 3 per application | INTAKE_003 |

---

## 4. Migrations

Create new Alembic revision: `202401150001_create_intake_tables.py`

**Operations:**
1. **Create `clients` table**
   - All columns as defined in Models section
   - Indexes: `idx_clients_user_id`, `idx_clients_sin_hash`
   - Row-level security policy (RLS) for multi-tenant isolation

2. **Create `applications` table**
   - All columns as defined
   - Indexes: `idx_applications_client_id`, `idx_applications_broker_id`, `idx_applications_status`
   - Composite index: `idx_applications_client_status` (client_id, status)
   - Check constraints for validation rules
   - RLS policy: clients see own, brokers see assigned

3. **Create `co_borrowers` table**
   - All columns as defined
   - Indexes: `idx_coborrowers_application_id`, `idx_coborrowers_app_sin`
   - Foreign key with cascade delete on application deletion (draft only)

4. **Create `fintrac_audit_log` table**
   - `id`, `application_id`, `event_type`, `event_data` (JSONB), `created_at`
   - Insert-only, no update/delete permissions
   - Partition by `created_at` for 5-year retention

5. **Data Migration**
   - None for new module; if migrating from legacy, use separate ETL revision

**Post-Deployment:**
- Apply RLS policies: `ALTER TABLE applications ENABLE ROW LEVEL SECURITY;`
- Create audit trigger function for `applications` table (insert only after submission)

---

## 5. Security & Compliance

### PIPEDA Data Protection
- **Encryption:** All SIN/DOB fields encrypted with AES-256-GCM via `EncryptionService` in `common/security.py`
  - Key rotation: Support `SIN_ENCRYPTION_KEY_2024`, `SIN_ENCRYPTION_KEY_2025` with version prefix in ciphertext
  - DOB uses separate encryption context to prevent correlation attacks
- **Data Minimization:** API responses exclude sin, date_of_birth, and income values
- **Logging:** NEVER log SIN, DOB, or income; use `sin_hash` for correlation only
- **Key Management:** Keys loaded from `config.SIN_ENCRYPTION_KEY` (BaseSettings); production uses AWS KMS envelope encryption

### OSFI B-20 Implementation
- Stress test rate calculated at submission and stored in `qualifying_rate` column
- GDS/TDS ratios stored for audit; calculation breakdown logged with `correlation_id`
- Hard limits enforced: `gds_ratio ≤ 39.00` and `tds_ratio ≤ 44.00`
- Rejection reason logged if thresholds exceeded

### FINTRAC AML/ATF
- **Immutability:** After `status = submitted`, row is UPDATE-protected via database trigger
- **Transaction Flagging:** `fintrac_reportable` boolean set if loan_amount ≥ $10,000
- **Audit Trail:** All status changes written to `fintrac_audit_log` with immutable policy
- **Retention:** PostgreSQL partition manager auto-archives after 5 years

### Authorization Matrix
| Role | Create | Read Own | Read Assigned | Update Draft | Submit | Delete |
|------|--------|----------|---------------|--------------|--------|--------|
| Client | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ (draft only) |
| Broker | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ (draft only) |
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (any status) |

**Implementation:** Use FastAPI dependencies `get_current_user()` and `check_application_access()` that applies RLS filters at query level.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `ApplicationNotFoundError` | 404 | INTAKE_001 | "Application {id} not found" | GET /applications/{invalid_uuid} |
| `ApplicationValidationError` | 422 | INTAKE_002 | "{field}: {reason}" | amortization_years=35 |
| `ApplicationBusinessRuleError` | 409 | INTAKE_003 | "{rule} violated: {detail}" | down_payment < 5% of price |
| `UnauthorizedAccessError` | 403 | INTAKE_004 | "Access denied to application {id}" | Client accessing broker's app |
| `ClientNotFoundError` | 404 | INTAKE_005 | "Client {id} not found" | Foreign key violation |
| `InvalidStatusTransitionError` | 409 | INTAKE_006 | "Invalid transition from {from} to {to}" | Submitting approved app |
| `OSFIThresholdExceededError` | 422 | INTAKE_007 | "GDS/TDS exceeds limit: GDS={gds}%, TDS={tds}%" | GDS=42%, TDS=46% |
| `PIPEDAEncryptionError` | 500 | INTAKE_008 | "Encryption service unavailable" | Missing encryption key |

**Error Response Format (consistent across all endpoints):**
```json
{
  "detail": "Application business rule violated: down payment must be at least 5% of purchase price",
  "error_code": "INTAKE_003",
  "timestamp": "2024-01-15T12:00:00Z",
  "correlation_id": "req-1234567890"
}
```

**Implementation Notes:**
- All exceptions inherit from `AppException` (defined in `common/exceptions.py`)
- Use FastAPI exception handlers to map to structured JSON responses
- Log errors with `structlog` at `warning` level; never include PII in log messages
- Include `correlation_id` in all log entries for distributed tracing

---

## Appendix: Missing Details Resolution

**Application Status Workflow:**
- Default initial status: `draft`
- Submission triggers: `draft` → `submitted`
- Underwriting module handles: `submitted` → `underwriting` → `approved|rejected|conditions`
- Conditions resolution: `conditions` → `approved` via separate conditions module

**Default Types:**
- `application_type`: `purchase` (default), `refinance`, `renewal`, `switch`
- `mortgage_type`: `fixed` (default), `variable`, `adjustable`

**Co-Borrower Management:**
- Add/remove allowed only in `draft` status via PUT endpoint (full replacement)
- Once `submitted`, co-borrowers immutable; errors on modification attempt
- Max 3 co-borrowers enforced at validation layer

**SIN Encryption Key Management:**
- Primary key: `SIN_ENCRYPTION_KEY` (32-byte AES-256, base64-encoded) in environment
- Key versioning: Ciphertext prefixed with key version (e.g., `v1:{nonce}:{ciphertext}:{tag}`)
- Rotation: Deploy new key, update config; old keys retained for decryption
- Production: Use AWS KMS with envelope encryption; key ID in `KMS_KEY_ID` setting