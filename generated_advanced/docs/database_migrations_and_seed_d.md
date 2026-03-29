# Database Migrations & Seed Data
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Database Migrations & Seed Data Design Plan

**Module Location:** `mortgage_underwriting/modules/migrations/`

---

## 1. Endpoints

This module **does not expose new API endpoints**. Migrations are executed exclusively via Alembic CLI commands:
- `uv run alembic upgrade head` (apply all migrations)
- `uv run alembic downgrade -1` (rollback one migration)
- `uv run alembic revision --autogenerate -m "description"` (create new migration)

Seed data is inserted via Alembic's `env.py` post-upgrade hook when `ENVIRONMENT=development` or `ENVIRONMENT=staging`.

---

## 2. Models & Database

### Core Models Summary (12 modules)

#### **Module 1: users**
```python
# modules/users/models.py
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)  # bcrypt
    role = Column(Enum("admin", "broker", "client", name="user_role"), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    applications = relationship("Application", back_populates="user")
    documents = relationship("Document", back_populates="uploaded_by_user")
```

#### **Module 2: lenders**
```python
class Lender(Base):
    __tablename__ = "lenders"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    code = Column(String(10), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    products = relationship("Product", back_populates="lender")
```

#### **Module 3: products**
```python
class Product(Base):
    __tablename__ = "products"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    lender_id = Column(UUID, ForeignKey("lenders.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    product_type = Column(Enum("fixed", "variable", name="product_type"), nullable=False, index=True)
    term_years = Column(Integer, nullable=False)
    interest_rate = Column(Numeric(5, 3), nullable=False)  # e.g., 5.250%
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    lender = relationship("Lender", back_populates="products")
```

#### **Module 4: applications**
```python
class Application(Base):
    __tablename__ = "applications"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    application_number = Column(String(20), unique=True, nullable=False, index=True)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(Enum("draft", "submitted", "underwriting", "approved", "declined", "conditional", name="app_status"), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    user = relationship("User", back_populates="applications")
    borrowers = relationship("Borrower", back_populates="application")
    property = relationship("Property", back_populates="application", uselist=False)
```

#### **Module 5: borrowers**
```python
class Borrower(Base):
    __tablename__ = "borrowers"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    application_id = Column(UUID, ForeignKey("applications.id"), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    sin_encrypted = Column(LargeBinary, nullable=False)  # AES-256 encrypted
    sin_hash = Column(String(64), nullable=False, index=True)  # SHA256 for lookups
    dob_encrypted = Column(LargeBinary, nullable=False)  # AES-256 encrypted
    employment_status = Column(Enum("employed", "self_employed", "other", name="emp_status"), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    application = relationship("Application", back_populates="borrowers")
    incomes = relationship("Income", back_populates="borrower")
    assets = relationship("Asset", back_populates="borrower")
    liabilities = relationship("Liability", back_populates="borrower")
```

#### **Module 6: properties**
```python
class Property(Base):
    __tablename__ = "properties"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    application_id = Column(UUID, ForeignKey("applications.id"), unique=True, nullable=False, index=True)
    address = Column(String(500), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    province = Column(String(2), nullable=False, index=True)
    postal_code = Column(String(10), nullable=False)
    property_type = Column(Enum("single_family", "condo", "townhouse", "other", name="prop_type"), nullable=False)
    property_value = Column(Numeric(12, 2), nullable=False)  # DECIMAL for money
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    application = relationship("Application", back_populates="property")
```

#### **Module 7: income_verification**
```python
class Income(Base):
    __tablename__ = "income_verification"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    borrower_id = Column(UUID, ForeignKey("borrowers.id"), nullable=False, index=True)
    income_type = Column(Enum("salary", "bonus", "commission", "rental", "other", name="income_type"), nullable=False)
    gross_annual_income = Column(Numeric(10, 2), nullable=False)
    verification_status = Column(Enum("pending", "verified", "rejected", name="verif_status"), nullable=False, index=True)
    verified_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    borrower = relationship("Borrower", back_populates="incomes")
```

#### **Module 8: assets**
```python
class Asset(Base):
    __tablename__ = "assets"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    borrower_id = Column(UUID, ForeignKey("borrowers.id"), nullable=False, index=True)
    asset_type = Column(Enum("savings", "rrsp", "investment", "property", "other", name="asset_type"), nullable=False, index=True)
    value = Column(Numeric(12, 2), nullable=False)
    verification_status = Column(Enum("pending", "verified", "rejected", name="verif_status"), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    borrower = relationship("Borrower", back_populates="assets")
```

#### **Module 9: liabilities**
```python
class Liability(Base):
    __tablename__ = "liabilities"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    borrower_id = Column(UUID, ForeignKey("borrowers.id"), nullable=False, index=True)
    liability_type = Column(Enum("mortgage", "loc", "credit_card", "auto_loan", "student_loan", "other", name="liab_type"), nullable=False, index=True)
    balance = Column(Numeric(12, 2), nullable=False)
    monthly_payment = Column(Numeric(10, 2), nullable=False)
    interest_rate = Column(Numeric(5, 3))
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    borrower = relationship("Borrower", back_populates="liabilities")
```

#### **Module 10: documents**
```python
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    application_id = Column(UUID, ForeignKey("applications.id"), nullable=False, index=True)
    document_type = Column(Enum("id_verification", "income_proof", "property_appraisal", "bank_statement", "other", name="doc_type"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)  # S3 path, not PII
    uploaded_by = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    fintrac_flagged = Column(Boolean, default=False)  # FINTRAC: >$10K transaction
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    application = relationship("Application", back_populates="documents")
    uploaded_by_user = relationship("User", back_populates="documents")
```

#### **Module 11: underwriting_results**
```python
class UnderwritingResult(Base):
    __tablename__ = "underwriting_results"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    application_id = Column(UUID, ForeignKey("applications.id"), unique=True, nullable=False, index=True)
    gds_ratio = Column(Numeric(5, 3), nullable=False)  # Gross Debt Service
    tds_ratio = Column(Numeric(5, 3), nullable=False)  # Total Debt Service
    qualifying_rate = Column(Numeric(5, 3), nullable=False)  # OSFI B-20: max(rate+2%, 5.25%)
    ltv_ratio = Column(Numeric(5, 3), nullable=False)  # Loan-to-Value
    insurance_required = Column(Boolean, nullable=False)  # CMHC: LTV > 80%
    insurance_premium = Column(Numeric(10, 2))  # CMHC tiered premium
    decision = Column(Enum("approved", "declined", "conditional", name="uw_decision"), nullable=False)
    decision_reason = Column(Text)
    stress_test_rate = Column(Numeric(5, 3), nullable=False)  # OSFI B-20
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    application = relationship("Application", back_populates="underwriting_result")
```

#### **Module 12: audit_logs**
```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    table_name = Column(String(100), nullable=False, index=True)
    record_id = Column(UUID, nullable=False, index=True)
    action = Column(Enum("insert", "update", "delete", name="audit_action"), nullable=False)
    old_values = Column(JSONB)  # Before state
    new_values = Column(JSONB)  # After state
    created_by = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    # No updated_at - FINTRAC immutable audit trail
    
    # No relationships - standalone immutable record
```

---

## 3. Business Logic

### Migration Strategy
- **Sequential Dependencies**: Migrations must be applied in dependency order:
  1. `users` → 2. `lenders` → 3. `products` → 4. `applications` → 5. `borrowers` → 6. `properties` → 7-9 (parallel) → 10. `documents` → 11. `underwriting_results` → 12. `audit_logs`
- **Reversibility**: Every migration includes full `downgrade()` function that drops tables/indexes in reverse order
- **Idempotency**: Seed data uses `INSERT ... ON CONFLICT DO NOTHING` to prevent duplicate inserts
- **Environment Gates**: Seed data only executes when `ENVIRONMENT=development` or `staging`

### Seed Data Insertion Logic
```python
# In alembic/env.py post-upgrade hook
def run_seed_data(connection):
    if config.get_main_option("ENVIRONMENT") not in ["development", "staging"]:
        return
    
    # 1. Insert users with bcrypt hashed passwords
    # 2. Insert lenders (Big 5)
    # 3. Insert products (2 per lender)
    # 4. Insert sample application workflow
    # 5. Insert underwriting result demonstrating OSFI B-20 calculation
    # 6. Insert audit logs for FINTRAC compliance demonstration
```

### Rollback Testing Strategy
- **Unit Test**: Each migration's `upgrade()` and `downgrade()` tested in isolation using separate test DB
- **Integration Test**: Full `upgrade head` → `downgrade base` → `upgrade head` cycle verification
- **Data Integrity**: After rollback, verify no orphaned records or constraint violations
- **Encrypted Data**: Verify that `downgrade` properly cleans up encryption keys from memory

---

## 4. Migrations

### Migration 1: Create Users Table
**File:** `alembic/versions/001_create_users.py`
- **Creates**: `users` table with UUID primary key, email index, role index
- **Indexes**: `idx_users_email`, `idx_users_role`, `idx_users_is_active`
- **Downgrade**: Drop table and indexes

### Migration 2: Create Lenders Table
**File:** `alembic/versions/002_create_lenders.py`
- **Creates**: `lenders` table
- **Indexes**: `idx_lenders_code`, `idx_lenders_is_active`
- **Downgrade**: Drop table and indexes

### Migration 3: Create Products Table
**File:** `alembic/versions/003_create_products.py`
- **Creates**: `products` table with FK to `lenders`
- **Indexes**: `idx_products_lender_id`, `idx_products_type`, `idx_products_is_active`
- **Downgrade**: Drop table, indexes, and FK constraint

### Migration 4: Create Applications Table
**File:** `alembic/versions/004_create_applications.py`
- **Creates**: `applications` table with FK to `users`
- **Indexes**: `idx_applications_number`, `idx_applications_user_id`, `idx_applications_status`
- **Downgrade**: Drop table, indexes, and FK constraint

### Migration 5: Create Borrowers Table
**File:** `alembic/versions/005_create_borrowers.py`
- **Creates**: `borrowers` table with encrypted SIN/DOB fields, FK to `applications`
- **Indexes**: `idx_borrowers_app_id`, `idx_borrowers_sin_hash`
- **Downgrade**: Drop table, indexes, and FK constraint

### Migration 6: Create Properties Table
**File:** `alembic/versions/006_create_properties.py`
- **Creates**: `properties` table with FK to `applications`
- **Indexes**: `idx_properties_app_id`, `idx_properties_province`, `idx_properties_city`
- **Downgrade**: Drop table, indexes, and FK constraint

### Migration 7: Create Income Verification Table
**File:** `alembic/versions/007_create_income_verification.py`
- **Creates**: `income_verification` table with FK to `borrowers`
- **Indexes**: `idx_income_borrower_id`, `idx_income_verif_status`
- **Downgrade**: Drop table, indexes, and FK constraint

### Migration 8: Create Assets Table
**File:** `alembic/versions/008_create_assets.py`
- **Creates**: `assets` table with FK to `borrowers`
- **Indexes**: `idx_assets_borrower_id`, `idx_assets_type`
- **Downgrade**: Drop table, indexes, and FK constraint

### Migration 9: Create Liabilities Table
**File:** `alembic/versions/009_create_liabilities.py`
- **Creates**: `liabilities` table with FK to `borrowers`
- **Indexes**: `idx_liabilities_borrower_id`, `idx_liabilities_type`
- **Downgrade**: Drop table, indexes, and FK constraint

### Migration 10: Create Documents Table
**File:** `alembic/versions/010_create_documents.py`
- **Creates**: `documents` table with FKs to `applications` and `users`
- **Indexes**: `idx_docs_app_id`, `idx_docs_type`, `idx_docs_uploaded_by`, `idx_docs_fintrac_flagged`
- **Downgrade**: Drop table, indexes, and FK constraints

### Migration 11: Create Underwriting Results Table
**File:** `alembic/versions/011_create_underwriting_results.py`
- **Creates**: `underwriting_results` table with FK to `applications`
- **Indexes**: `idx_uw_app_id`, `idx_uw_decision`
- **Check Constraints**: `gds_ratio <= 0.39`, `tds_ratio <= 0.44` (OSFI B-20)
- **Downgrade**: Drop table, indexes, constraints, and FK

### Migration 12: Create Audit Logs Table
**File:** `alembic/versions/012_create_audit_logs.py`
- **Creates**: `audit_logs` table with FK to `users`
- **Indexes**: `idx_audit_table_name`, `idx_audit_record_id`, `idx_audit_created_by`
- **No updated_at column** (FINTRAC immutability)
- **Downgrade**: Drop table, indexes, and FK constraint

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Encryption**: `sin_encrypted` and `dob_encrypted` use AES-256-GCM via `common/security.py:encrypt_pii()`
- **Hashing**: `sin_hash` uses SHA256 for lookup without revealing SIN
- **Data Minimization**: Only collect fields required for underwriting (no SIN in logs/responses)
- **Key Rotation**: Encryption keys managed via `common/config.py` with environment-specific key vaults

### OSFI B-20 Requirements
- **Stress Test Data**: `underwriting_results.qualifying_rate` and `stress_test_rate` stored for audit
- **Hard Limits**: Database check constraints enforce GDS ≤ 39% and TDS ≤ 44%
- **Immutability**: Once `underwriting_results.decision` is set, updates require new audit log entry

### FINTRAC Compliance
- **Audit Trail**: `audit_logs` table captures all inserts/updates/deletes with `old_values`/`new_values` JSONB
- **Transaction Flagging**: `documents.finrac_flagged` automatically set when document_type="bank_statement" and property_value > 10,000
- **5-Year Retention**: `audit_logs` table has `created_at` index for retention policy enforcement
- **Immutable Records**: No DELETE or UPDATE operations allowed on `audit_logs` (enforced at app layer)

### CMHC Insurance Logic
- **LTV Calculation**: `(loan_amount / property_value)` computed in underwriting service, stored as `ltv_ratio`
- **Premium Tiers**: Lookup table (seeded) for insurance premiums:
  - 80.01-85%: 2.80%
  - 85.01-90%: 3.10%
  - 90.01-95%: 4.00%
- **Insurance Flag**: `insurance_required` boolean set when LTV > 0.80

---

## 6. Error Codes & HTTP Responses

This module **does not add HTTP error responses** (no API endpoints). Migration-specific errors are handled at CLI level:

| Error Scenario | Exit Code | Log Level | Remediation |
|----------------|-----------|-----------|-------------|
| Migration dependency conflict | 1 | ERROR | Run `alembic history` to check dependency tree |
| Encrypted column key mismatch | 2 | CRITICAL | Verify `PII_ENCRYPTION_KEY` in environment config |
| Seed data duplicate key violation | 3 | WARNING | Use `ON CONFLICT DO NOTHING` or reset database |
| Downgrade constraint violation | 4 | ERROR | Manually resolve orphaned records before rollback |
| FINTRAC audit log tampering detected | 5 | CRITICAL | Alert compliance team, investigate unauthorized access |

**Loop Prevention Note**: If migration fails during CI/CD, the pipeline must **STOP** and **NOT retry automatically** to prevent partial state. Manual intervention required to maintain data integrity.