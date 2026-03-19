# Design: Lender Comparison & Submission
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Lender Comparison & Submission Module

**Module Identifier:** `lender_comparison_submission`  
**Feature Slug:** `lender-comparison-submission`  
**Document Path:** `docs/design/lender-comparison-submission.md`

---

## 1. Endpoints

### 1.1 GET /api/v1/lenders
List all active lenders with optional filtering.

**Authentication:** Authenticated user (broker/admin)  
**Authorization:** `lender:read` scope

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | No | Filter by lender type: `bank`, `credit_union`, `monoline`, `private`, `mfc` |
| `is_active` | boolean | No | Default `true` |

**Response Schema (200 OK):**
```json
{
  "lenders": [
    {
      "id": "uuid",
      "name": "Royal Bank of Canada",
      "type": "bank",
      "is_active": true,
      "logo_url": "https://cdn.example.com/rbc-logo.svg",
      "submission_email": "brokers@rbc.com",
      "notes": "Preferred lender for high-ratio deals"
    }
  ],
  "total_count": 25
}
```

**Error Responses:**
| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 401 Unauthorized | `AUTH_001` | Missing or invalid JWT token |
| 403 Forbidden | `AUTH_002` | Insufficient permissions |

---

### 1.2 GET /api/v1/lenders/{lender_id}/products
Retrieve all active products for a specific lender.

**Authentication:** Authenticated user  
**Authorization:** `lender:read` scope

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lender_id` | uuid | Yes | Lender UUID |

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `mortgage_type` | string | No | Filter: `fixed`, `variable`, `heloc` |
| `is_active` | boolean | No | Default `true` |

**Response Schema (200 OK):**
```json
{
  "lender_id": "uuid",
  "products": [
    {
      "id": "uuid",
      "product_name": "5-Year Fixed Closed",
      "mortgage_type": "fixed",
      "term_years": 5,
      "rate": "5.240",
      "rate_type": "discounted",
      "max_ltv_insured": "95.00",
      "max_ltv_conventional": "80.00",
      "max_amortization_insured": 25,
      "max_amortization_conventional": 30,
      "min_credit_score": 680,
      "max_gds": "39.00",
      "max_tds": "44.00",
      "allows_self_employed": true,
      "allows_rental_income": true,
      "allows_gifted_down_payment": true,
      "prepayment_privilege_percent": "20.00",
      "portability": true,
      "assumability": false,
      "is_active": true,
      "effective_date": "2024-01-15",
      "expiry_date": null
    }
  ]
}
```

**Error Responses:**
| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 401 Unauthorized | `AUTH_001` | Missing or invalid JWT token |
| 403 Forbidden | `AUTH_002` | Insufficient permissions |
| 404 Not Found | `LENDER_001` | Lender not found |

---

### 1.3 POST /api/v1/lenders/match
Execute lender matching algorithm against an application.

**Authentication:** Authenticated user  
**Authorization:** `application:read` + `lender:match` scopes; user must own the application

**Request Body Schema:**
```json
{
  "application_id": "uuid",
  "filters": {
    "mortgage_type": "fixed",
    "min_term_years": 3,
    "max_term_years": 7,
    "include_inactive": false
  }
}
```

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "matches": [
    {
      "rank": 1,
      "lender": { "id": "uuid", "name": "RBC", "type": "bank" },
      "product": { "id": "uuid", "product_name": "5-Year Fixed", "rate": "5.240" },
      "eligibility_score": 95,
      "qualification_status": "full_match",
      "conditions": ["Gifted down payment requires donor letter"],
      "gds_actual": "38.50",
      "tds_actual": "42.30",
      "ltv_actual": "85.00",
      "osfi_compliant": true,
      "fintrac_triggered": false
    }
  ],
  "match_count": 5,
  "calculated_at": "2024-01-20T14:30:00Z"
}
```

**Error Responses:**
| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 401 Unauthorized | `AUTH_001` | Missing or invalid JWT token |
| 403 Forbidden | `AUTH_003` | Access denied to application |
| 404 Not Found | `APPLICATION_001` | Application not found |
| 422 Unprocessable Entity | `LENDER_002` | Invalid filter parameters |
| 422 Unprocessable Entity | `LENDER_003` | GDS/TDS calculation failed |

---

### 1.4 GET /api/v1/applications/{application_id}/lender-matches
Retrieve previously saved lender matches for an application.

**Authentication:** Authenticated user  
**Authorization:** `application:read` scope; user must own the application

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `application_id` | uuid | Yes | Application UUID |

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string | No | Filter: `full_match`, `conditional` |

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "matches": [ /* Same as POST /match response */ ],
  "generated_at": "2024-01-20T14:30:00Z"
}
```

**Error Responses:**
| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 401 Unauthorized | `AUTH_001` | Missing or invalid JWT token |
| 403 Forbidden | `AUTH_003` | Access denied to application |
| 404 Not Found | `APPLICATION_001` | Application not found |

---

### 1.5 POST /api/v1/applications/{application_id}/submissions
Create a new lender submission record.

**Authentication:** Authenticated user  
**Authorization:** `submission:create` scope; user must own the application

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `application_id` | uuid | Yes | Application UUID |

**Request Body Schema:**
```json
{
  "lender_id": "uuid",
  "product_id": "uuid",
  "submission_notes": "Client prefers RBC due to existing relationship",
  "rate_lock_requested": true,
  "rate_lock_duration_days": 30
}
```

**Response Schema (201 Created):**
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "lender": { "id": "uuid", "name": "RBC" },
  "product": { "id": "uuid", "product_name": "5-Year Fixed" },
  "submitted_by": "uuid",
  "submitted_at": "2024-01-20T15:00:00Z",
  "status": "pending",
  "lender_conditions": [],
  "approved_rate": null,
  "approved_amount": null,
  "expiry_date": null,
  "notes": "Client prefers RBC due to existing relationship",
  "created_at": "2024-01-20T15:00:00Z",
  "updated_at": "2024-01-20T15:00:00Z"
}
```

**Error Responses:**
| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 401 Unauthorized | `AUTH_001` | Missing or invalid JWT token |
| 403 Forbidden | `AUTH_003` | Access denied to application |
| 404 Not Found | `APPLICATION_001` | Application not found |
| 404 Not Found | `LENDER_001` | Lender not found |
| 409 Conflict | `LENDER_004` | Duplicate submission to same lender |
| 422 Unprocessable Entity | `LENDER_005` | Product not eligible for application |

---

### 1.6 GET /api/v1/applications/{application_id}/submissions
List all submissions for an application.

**Authentication:** Authenticated user  
**Authorization:** `submission:read` scope; user must own the application

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `application_id` | uuid | Yes | Application UUID |

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string | No | Filter: `pending`, `approved`, `declined`, `countered` |
| `lender_id` | uuid | No | Filter by lender |

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "submissions": [
    {
      "id": "uuid",
      "lender": { "id": "uuid", "name": "RBC" },
      "status": "pending",
      "submitted_at": "2024-01-20T15:00:00Z",
      "approved_rate": null,
      "expiry_date": null
    }
  ],
  "total_count": 3
}
```

**Error Responses:**
| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 401 Unauthorized | `AUTH_001` | Missing or invalid JWT token |
| 403 Forbidden | `AUTH_003` | Access denied to application |
| 404 Not Found | `APPLICATION_001` | Application not found |

---

### 1.7 PUT /api/v1/applications/{application_id}/submissions/{submission_id}
Update submission status (e.g., lender responds with approval/decline).

**Authentication:** Authenticated user  
**Authorization:** `submission:update` scope; user must own the application

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `application_id` | uuid | Yes | Application UUID |
| `submission_id` | uuid | Yes | Submission UUID |

**Request Body Schema:**
```json
{
  "status": "approved",
  "lender_reference_number": "RBC-2024-ABC123",
  "lender_conditions": ["Proof of property insurance", "Updated pay stub"],
  "approved_rate": "5.190",
  "approved_amount": "650000.00",
  "expiry_date": "2024-02-20",
  "notes": "Approved with conditions"
}
```

**Response Schema (200 OK):**
```json
{
  "id": "uuid",
  "status": "approved",
  "updated_at": "2024-01-22T10:00:00Z",
  "lender_reference_number": "RBC-2024-ABC123",
  "lender_conditions": ["Proof of property insurance", "Updated pay stub"],
  "approved_rate": "5.190",
  "approved_amount": "650000.00",
  "expiry_date": "2024-02-20",
  "notes": "Approved with conditions"
}
```

**Error Responses:**
| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 401 Unauthorized | `AUTH_001` | Missing or invalid JWT token |
| 403 Forbidden | `AUTH_003` | Access denied |
| 404 Not Found | `SUBMISSION_001` | Submission not found |
| 409 Conflict | `SUBMISSION_002` | Invalid status transition |
| 422 Unprocessable Entity | `SUBMISSION_003` | Validation failed |

---

## 2. Models & Database

### 2.1 lenders Table
```python
class Lender(Base):
    __tablename__ = "lenders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    type = Column(
        Enum("bank", "credit_union", "monoline", "private", "mfc", name="lender_type"),
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    logo_url = Column(String(500), nullable=True)
    submission_email = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationships
    products = relationship("LenderProduct", back_populates="lender")
    submissions = relationship("LenderSubmission", back_populates="lender")
```

**Indexes:**
- `idx_lenders_type` (type)
- `idx_lenders_is_active` (is_active)
- `idx_lenders_name` (name)
- Composite: `idx_lenders_active_type` (is_active, type)

---

### 2.2 lender_products Table
```python
class LenderProduct(Base):
    __tablename__ = "lender_products"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lender_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    product_name = Column(String(255), nullable=False)
    mortgage_type = Column(
        Enum("fixed", "variable", "heloc", name="mortgage_type"),
        nullable=False,
        index=True
    )
    term_years = Column(Integer, nullable=False)
    rate = Column(Numeric(5, 3), nullable=False)  # e.g., 5.240%
    rate_type = Column(
        Enum("posted", "discounted", "prime_plus", name="rate_type"),
        nullable=False
    )
    
    # Underwriting thresholds
    max_ltv_insured = Column(Numeric(5, 2), nullable=False)  # e.g., 95.00
    max_ltv_conventional = Column(Numeric(5, 2), nullable=False)  # e.g., 80.00
    max_amortization_insured = Column(Integer, nullable=False)
    max_amortization_conventional = Column(Integer, nullable=False)
    min_credit_score = Column(Integer, nullable=False)
    max_gds = Column(Numeric(5, 2), nullable=False)  # OSFI B-20: typically 39.00
    max_tds = Column(Numeric(5, 2), nullable=False)  # OSFI B-20: typically 44.00
    
    # Borrower profile flags
    allows_self_employed = Column(Boolean, default=False, nullable=False)
    allows_rental_income = Column(Boolean, default=False, nullable=False)
    allows_gifted_down_payment = Column(Boolean, default=False, nullable=False)
    
    # Product features
    prepayment_privilege_percent = Column(Numeric(5, 2), default=Decimal("0.00"))
    portability = Column(Boolean, default=False)
    assumability = Column(Boolean, default=False)
    
    # Status and validity
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationships
    lender = relationship("Lender", back_populates="products")
    submissions = relationship("LenderSubmission", back_populates="product")
```

**Indexes:**
- `idx_lender_products_lender_id` (lender_id)
- `idx_lender_products_mortgage_type` (mortgage_type)
- `idx_lender_products_is_active` (is_active)
- `idx_lender_products_rate` (rate)
- Composite: `idx_lender_products_effective_expiry` (effective_date, expiry_date)
- Composite: `idx_lender_products_lender_active` (lender_id, is_active)

---

### 2.3 lender_submissions Table
```python
class LenderSubmission(Base):
    __tablename__ = "lender_submissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    lender_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lenders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lender_products.id", ondelete="RESTRICT"),
        nullable=False
    )
    submitted_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Status workflow
    status = Column(
        Enum("pending", "approved", "declined", "countered", name="submission_status"),
        nullable=False,
        index=True
    )
    
    # Lender response fields
    lender_reference_number = Column(String(100), nullable=True)
    lender_conditions = Column(JSONB, nullable=True)  # Immutable array of conditions
    approved_rate = Column(Numeric(5, 3), nullable=True)
    approved_amount = Column(Numeric(12, 2), nullable=True)
    expiry_date = Column(Date, nullable=True)
    
    # Internal notes
    notes = Column(Text, nullable=True)
    
    # Audit fields (FINTRAC compliance)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationships
    application = relationship("Application", back_populates="lender_submissions")
    lender = relationship("Lender", back_populates="submissions")
    product = relationship("LenderProduct", back_populates="submissions")
    submitted_by_user = relationship("User")
```

**Indexes:**
- `idx_lender_submissions_application_id` (application_id)
- `idx_lender_submissions_lender_id` (lender_id)
- `idx_lender_submissions_status` (status)
- `idx_lender_submissions_submitted_by` (submitted_by)
- Composite: `idx_lender_submissions_app_status` (application_id, status)

---

## 3. Business Logic

### 3.1 LenderMatcher Service

**Class:** `LenderMatcherService` (in `services.py`)

**Algorithm Specification:**

```python
async def match_lenders(
    self,
    application_id: UUID,
    filters: Optional[LenderMatchFilters] = None
) -> List[LenderMatchResult]:
```

**Step-by-Step Logic:**

1. **Fetch Application Data**
   - Retrieve application from `applications` module
   - Extract: gross_monthly_income, total_monthly_debts, property_value, loan_amount, down_payment, credit_score, employment_type, income_sources
   - **WARNING:** If application contains PII (SIN, DOB), access through encrypted fields only

2. **Calculate Key Ratios (OSFI B-20 Compliant)**
   ```python
   # LTV Calculation
   ltv = (loan_amount / property_value) * 100  # Decimal precision
   
   # Determine insurance requirement (CMHC)
   insurance_required = ltv > Decimal("80.00")
   
   # Stress Test Rate (OSFI B-20)
   contract_rate = product.rate
   qualifying_rate = max(contract_rate + Decimal("2.00"), Decimal("5.25"))
   
   # GDS = (PITH + Heating + Property Taxes) / Gross Income
   # PITH = Principal + Interest + Taxes + Heating
   # Use qualifying_rate for stress test calculation
   monthly_payment = calculate_pith(loan_amount, qualifying_rate, amortization)
   gds = (monthly_payment + monthly_heating + monthly_taxes) / gross_monthly_income * 100
   
   # TDS = (PITH + All Other Debts) / Gross Income
   tds = (monthly_payment + monthly_heating + monthly_taxes + total_monthly_debts) / gross_monthly_income * 100
   
   # Log calculation breakdown for audit (structlog)
   log.info(
       "lender_match_ratios_calculated",
       application_id=application_id,
       ltv=str(ltv),
       gds=str(gds),
       tds=str(tds),
       qualifying_rate=str(qualifying_rate),
       insurance_required=insurance_required,
       osfi_compliant=(gds <= 39.0 and tds <= 44.0)
   )
   ```

3. **Filter Products**
   - Query `lender_products` where `is_active = true` and `effective_date <= today <= expiry_date`
   - Apply filters:
     - `ltv <= max_ltv_insured` if insurance_required else `ltv <= max_ltv_conventional`
     - `gds <= max_gds`
     - `tds <= max_tds`
     - `credit_score >= min_credit_score`
     - `allows_self_employed = true` if employment_type == "self_employed"
     - `allows_rental_income = true` if rental_income > 0
     - `allows_gifted_down_payment = true` if down_payment_gifted > 0

4. **Rank Results**
   - Sort by `rate ASC` (lowest rate first)
   - Secondary sort: `max_gds DESC, max_tds DESC` (most flexible)

5. **Flag Conditions**
   - If `allows_gifted_down_payment = false` and down_payment_gifted > 0 → Add condition flag
   - If rental_income > 0 and product doesn't explicitly allow → Add condition flag
   - If credit_score < 720 → Add "rate premium may apply" flag

6. **Return Ranked List**
   - Each match includes eligibility score (0-100), qualification status, and condition flags

**FINTRAC Compliance:** Log all match operations with `correlation_id` for audit trail.

---

### 3.2 SubmissionPackageGenerator Service

**Class:** `SubmissionPackageGenerator` (in `services.py`)

**Package Components:**

1. **Application Summary**
   - Borrower details (hashed SIN for reference only)
   - Property details
   - Loan request details

2. **Underwriting Results**
   - GDS/TDS calculations with OSFI B-20 stress test
   - LTV and CMHC insurance determination
   - Credit score
   - **Audit Log:** Include calculation timestamps and version

3. **Document Manifest**
   - List of uploaded documents (IDs only, no PII)
   - Document verification status

4. **FINTRAC Flags**
   - Transaction > CAD $10,000 flag
   - Identity verification status
   - **Immutable record:** All flags written to `lender_submissions.lender_conditions` JSONB

5. **Broker Notes**
   - Structured notes from broker
   - Rate lock request details

**Output Formats:**
- JSON payload for API submission
- PDF generation for email submission (optional)
- **Security:** Never include SIN, DOB, or banking details in clear text

---

### 3.3 State Machine Transitions

**Submission Status Workflow:**

```
pending → approved (lender accepts)
pending → declined (lender rejects)
pending → countered (lender offers different terms)
countered → approved (broker accepts counter)
countered → declined (broker rejects counter)
```

**Rules:**
- Only `pending` submissions can be updated
- `approved_rate` and `approved_amount` required for `approved` status
- `expiry_date` automatically set to 30 days from approval unless specified
- All status changes logged with `structlog` and stored in `updated_at` audit trail

---

## 4. Migrations

### 4.1 New Tables

**Migration File:** `alembic/versions/20240120_create_lender_comparison_tables.py`

```python
def upgrade():
    # Create lenders table
    op.create_table(
        "lenders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.Enum("bank", "credit_union", "monoline", "private", "mfc", name="lender_type"), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("submission_email", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create lender_products table
    op.create_table(
        "lender_products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("lender_id", UUID(as_uuid=True), sa.ForeignKey("lenders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("mortgage_type", sa.Enum("fixed", "variable", "heloc", name="mortgage_type"), nullable=False),
        sa.Column("term_years", sa.Integer, nullable=False),
        sa.Column("rate", sa.Numeric(5, 3), nullable=False),
        sa.Column("rate_type", sa.Enum("posted", "discounted", "prime_plus", name="rate_type"), nullable=False),
        sa.Column("max_ltv_insured", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_ltv_conventional", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_amortization_insured", sa.Integer, nullable=False),
        sa.Column("max_amortization_conventional", sa.Integer, nullable=False),
        sa.Column("min_credit_score", sa.Integer, nullable=False),
        sa.Column("max_gds", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_tds", sa.Numeric(5, 2), nullable=False),
        sa.Column("allows_self_employed", sa.Boolean, default=False, nullable=False),
        sa.Column("allows_rental_income", sa.Boolean, default=False, nullable=False),
        sa.Column("allows_gifted_down_payment", sa.Boolean, default=False, nullable=False),
        sa.Column("prepayment_privilege_percent", sa.Numeric(5, 2), default=0),
        sa.Column("portability", sa.Boolean, default=False),
        sa.Column("assumability", sa.Boolean, default=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create lender_submissions table
    op.create_table(
        "lender_submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lender_id", UUID(as_uuid=True), sa.ForeignKey("lenders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("lender_products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.Enum("pending", "approved", "declined", "countered", name="submission_status"), nullable=False),
        sa.Column("lender_reference_number", sa.String(100), nullable=True),
        sa.Column("lender_conditions", sa.JSONB, nullable=True),
        sa.Column("approved_rate", sa.Numeric(5, 3), nullable=True),
        sa.Column("approved_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create indexes
    op.create_index("idx_lenders_type", "lenders", ["type"])
    op.create_index("idx_lenders_is_active", "lenders", ["is_active"])
    op.create_index("idx_lender_products_lender_id", "lender_products", ["lender_id"])
    op.create_index("idx_lender_products_rate", "lender_products", ["rate"])
    op.create_index("idx_lender_submissions_application_id", "lender_submissions", ["application_id"])
    op.create_index("idx_lender_submissions_status", "lender_submissions", ["status"])
    
    # Seed data for Big 5 banks
    seed_big_five_banks()
```

### 4.2 Seed Data
**Function:** `seed_big_five_banks()` in migration

```python
def seed_big_five_banks():
    banks = [
        {
            "id": uuid.uuid4(),
            "name": "Royal Bank of Canada",
            "type": "bank",
            "submission_email": "mortgage.brokers@rbc.com",
        },
        {
            "id": uuid.uuid4(),
            "name": "Toronto-Dominion Bank",
            "type": "bank",
            "submission_email": "brokerage@td.com",
        },
        # ... CIBC, BMO, Scotiabank
    ]
    
    for bank in banks:
        op.execute(
            sa.text(
                "INSERT INTO lenders (id, name, type, submission_email) "
                "VALUES (:id, :name, :type, :submission_email)"
            ),
            parameters=bank
        )
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test:** All GDS/TDS calculations must use `qualifying_rate = max(contract_rate + 2%, 5.25%)`
- **Hard Limits:** Reject products where `gds > 39%` or `tds > 44%` (log rejection reason)
- **Audit Trail:** Log every ratio calculation with breakdown values for regulatory audit
- **Rate Precision:** Use `Decimal(5,3)` for rates to avoid floating-point errors

### 5.2 FINTRAC Compliance
- **Immutable Records:** `lender_submissions` table has no DELETE or UPDATE on critical fields; only `status` and response fields can be updated
- **Transaction Flagging:** If `loan_amount >= 10000`, set `fintrac_triggered = true` in match results
- **5-Year Retention:** All submission records must be retained; implement soft-delete only (no physical deletion)
- **Audit Logging:** Log all submission events with `correlation_id` and `user_id`

### 5.3 PIPEDA Data Handling
- **No PII in Module:** This module stores only references (`application_id`) to PII
- **Encrypted References:** `application_id` links to `applications` table where SIN/DOB are encrypted at rest (AES-256)
- **Data Minimization:** Only collect lender-specific data required for submission
- **Logging:** Never log SIN, DOB, income, or banking data in this module

### 5.4 Authentication & Authorization
| Endpoint | Auth Required | Scope | Ownership Check |
|----------|---------------|-------|-----------------|
| GET /lenders | Yes | `lender:read` | No |
| GET /lenders/{id}/products | Yes | `lender:read` | No |
| POST /lenders/match | Yes | `lender:match` | Must own application |
| GET /applications/{id}/lender-matches | Yes | `application:read` | Must own application |
| POST /applications/{id}/submissions | Yes | `submission:create` | Must own application |
| GET /applications/{id}/submissions | Yes | `submission:read` | Must own application |
| PUT /applications/{id}/submissions/{sub_id} | Yes | `submission:update` | Must own application |

**Rate Limiting:** 10 match requests per minute per user to prevent abuse

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
# exceptions.py
class LenderComparisonException(AppException):
    """Base exception for lender comparison module"""
    pass

class LenderNotFoundError(LenderComparisonException):
    """Lender entity not found"""
    pass

class LenderProductNotFoundError(LenderComparisonException):
    """Product not found or inactive"""
    pass

class LenderSubmissionNotFoundError(LenderComparisonException):
    """Submission record not found"""
    pass

class LenderValidationError(LenderComparisonException):
    """Input validation failed"""
    pass

class LenderBusinessRuleError(LenderComparisonException):
    """Business rule violation (e.g., GDS/TDS exceed limits)"""
    pass

class DuplicateSubmissionError(LenderComparisonException):
    """Submission already exists for lender"""
    pass

class InvalidStatusTransitionError(LenderComparisonException):
    """Invalid submission status change"""
    pass
```

### 6.2 Error Mapping Table

| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `LenderNotFoundError` | 404 | `LENDER_001` | "Lender {lender_id} not found" | warning |
| `LenderProductNotFoundError` | 404 | `LENDER_002` | "Product {product_id} not found or inactive" | warning |
| `LenderValidationError` | 422 | `LENDER_003` | "{field}: {reason}" | info |
| `LenderBusinessRuleError` | 409 | `LENDER_004` | "OSFI B-20 limit exceeded: GDS {gds}% > 39%" | error |
| `DuplicateSubmissionError` | 409 | `LENDER_005` | "Submission already exists for lender {lender_id}" | warning |
| `LenderSubmissionNotFoundError` | 404 | `SUBMISSION_001` | "Submission {submission_id} not found" | warning |
| `InvalidStatusTransitionError` | 409 | `SUBMISSION_002` | "Cannot transition from {old} to {new}" | error |
| `ApplicationAccessDeniedError` | 403 | `AUTH_003` | "Access denied to application {application_id}" | warning |

### 6.3 Structured Error Response Format
```json
{
  "detail": "OSFI B-20 limit exceeded: GDS 42.50% > 39.00%",
  "error_code": "LENDER_004",
  "module": "lender_comparison_submission",
  "timestamp": "2024-01-20T15:30:00Z",
  "correlation_id": "req-1234567890",
  "context": {
    "application_id": "uuid",
    "gds_actual": "42.50",
    "tds_actual": "45.20",
    "ltv_actual": "87.00"
  }
}
```

---

## 7. Additional Considerations

### 7.1 Rate Update Mechanism
- **Frequency:** Daily batch updates via secure SFTP from lender rate sheets
- **API:** `POST /api/v1/admin/lenders/{id}/products/bulk-update` (admin-only)
- **Validation:** New rates must be within ±2% of previous rate to prevent errors
- **Audit:** Log all rate changes with `old_rate`, `new_rate`, `updated_by`

### 7.2 Rate Lock Mechanism
- **Duration:** 30-120 days (configurable per lender)
- **Storage:** `rate_lock_until` field in `lender_submissions` table
- **Expiration:** Daily cron job to check and update expired locks
- **Fee:** Track rate lock fees in separate `rate_lock_fees` table (FINTRAC compliance)

### 7.3 Automated Rate Comparison Reporting
- **Daily Report:** Generate PDF report of top 3 matches per active application
- **Distribution:** Secure email to broker (PIPEDA compliant)
- **Retention:** Store report metadata for 5 years (FINTRAC)
- **Metrics:** Track `rate_comparison_generated` metric for Prometheus

### 7.4 Lender Submission Format Standardization
- **Template Engine:** Use Jinja2 templates for lender-specific submission formats
- **Storage:** Templates stored in `lender_submission_templates` table
- **Versioning:** Template versions tracked for audit
- **API:** Standardized JSON payload converted to lender-specific format

---

## 8. Testing Strategy

### 8.1 Unit Tests
- `test_lender_matcher.py`: Test GDS/TDS calculations with OSFI B-20 stress test
- `test_submission_package_generator.py`: Test FINTRAC flagging logic
- `test_rate_ranking.py`: Test product sorting algorithm

### 8.2 Integration Tests
- `test_lender_submission_workflow.py`: End-to-end submission flow
- `test_rate_lock_expiration.py`: Test rate lock cron job
- `test_fintrac_audit_trail.py`: Verify 5-year retention compliance

### 8.3 Test Markers
```python
@pytest.mark.unit
def test_osfi_stress_test_calculation():
    pass

@pytest.mark.integration
def test_lender_submission_fintrac_compliance():
    pass
```

---

**Design Review Checklist:**
- [ ] All financial fields use `Decimal` type
- [ ] All tables include `created_at`, `updated_at` audit fields
- [ ] OSFI B-20 stress test logic implemented
- [ ] FINTRAC immutable audit trail enforced
- [ ] PIPEDA PII handling respected (no SIN/DOB in module)
- [ ] Error codes follow module naming convention
- [ ] Authentication/authorization scopes defined
- [ ] Indexes support common query patterns
- [ ] Seed data includes Big 5 banks
- [ ] Rate lock mechanism designed
- [ ] Submission package generator handles FINTRAC flags