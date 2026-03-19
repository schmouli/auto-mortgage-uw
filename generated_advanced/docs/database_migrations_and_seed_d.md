# Database Migrations & Seed Data
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Database Migrations & Seed Data Design Plan

**File:** `docs/design/database-migrations-seed-data.md`

---

## 1. Endpoints

### Migration Management Endpoints (Admin Only)

| Method | Path | Auth | Request | Response | Errors |
|--------|------|--------|---------|----------|--------|
| `GET` | `/api/v1/admin/migrations/status` | Admin | - | `{"current_revision": str, "pending_migrations": list[str]}` | `401 Unauthorized`, `403 Forbidden` |
| `POST` | `/api/v1/admin/migrations/seed/{environment}` | Admin | `{"confirm": bool, "truncate_existing": bool}` | `{"status": "success", "records_created": dict}` | `400 Bad Request (SEED_001)`, `404 Not Found (SEED_002)`, `409 Conflict (SEED_003)` |

#### Request/Response Schemas

**Seed Trigger Request (POST)**
```json
{
  "confirm": true,  // Must be explicit to prevent accidental runs
  "truncate_existing": false,  // If true, truncates all tables before seeding (dev only)
  "environment": "development"  // Path parameter: development|staging|demo
}
```

**Seed Trigger Response**
```json
{
  "status": "success",
  "environment": "development",
  "records_created": {
    "users": 3,
    "lenders": 5,
    "products": 10,
    "applications": 1,
    "applicants": 2,
    "properties": 1,
    "incomes": 2,
    "liabilities": 3,
    "documents": 4,
    "underwriting_results": 1
  },
  "execution_time_ms": 1250
}
```

---

## 2. Models & Database Schema

### Core Models Summary (12 modules)

#### **Module 1: users**
```sql
-- Table: users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'broker', 'client')),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    sin_encrypted BYTEA,  -- PIPEDA: AES-256 encrypted
    sin_hash VARCHAR(64),  -- SHA256 for lookups
    dob_encrypted BYTEA,  -- PIPEDA: AES-256 encrypted
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_sin_hash ON users(sin_hash);
CREATE INDEX idx_users_role ON users(role) WHERE is_active = true;
```

#### **Module 2: lenders**
```sql
-- Table: lenders
CREATE TABLE lenders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_lenders_code ON lenders(code);
```

#### **Module 3: products**
```sql
-- Table: products
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_id UUID NOT NULL REFERENCES lenders(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    product_type VARCHAR(50) NOT NULL CHECK (product_type IN ('fixed', 'variable')),
    term_years INTEGER NOT NULL CHECK (term_years > 0),
    interest_rate DECIMAL(5,4) NOT NULL,  -- OSFI: Never use float
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_products_lender ON products(lender_id);
CREATE INDEX idx_products_active_type ON products(is_active, product_type);
```

#### **Module 4: applications**
```sql
-- Table: applications
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_number VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('draft', 'submitted', 'underwriting', 'approved', 'declined', 'conditional')),
    requested_loan_amount DECIMAL(12,2) NOT NULL,
    property_value DECIMAL(12,2) NOT NULL,
    ltv_ratio DECIMAL(5,2) GENERATED ALWAYS AS (requested_loan_amount / property_value * 100) STORED,
    insurance_required BOOLEAN DEFAULT false,
    insurance_premium_amount DECIMAL(12,2),  -- CMHC: Calculated based on LTV tier
    gds_ratio DECIMAL(5,2),  -- OSFI: Must be ≤ 39%
    tds_ratio DECIMAL(5,2),  -- OSFI: Must be ≤ 44%
    qualifying_rate DECIMAL(5,4),  -- OSFI: max(contract_rate + 2%, 5.25%)
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_created_by ON applications(created_by);
CREATE INDEX idx_applications_ltv ON applications(ltv_ratio);
```

#### **Module 5: applicants**
```sql
-- Table: applicants
CREATE TABLE applicants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,  -- Link if system user
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    sin_encrypted BYTEA,  -- PIPEDA: Encrypted
    sin_hash VARCHAR(64),  -- SHA256 for lookups
    dob_encrypted BYTEA,  -- PIPEDA: Encrypted
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_applicants_application ON applicants(application_id);
CREATE INDEX idx_applicants_sin_hash ON applicants(sin_hash);
```

#### **Module 6: properties**
```sql
-- Table: properties
CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL UNIQUE REFERENCES applications(id) ON DELETE CASCADE,
    address_line1 VARCHAR(255) NOT NULL,
    address_line2 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    province VARCHAR(2) NOT NULL CHECK (province IN ('AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT')),
    postal_code VARCHAR(10) NOT NULL,
    property_type VARCHAR(50) NOT NULL,
    estimated_value DECIMAL(12,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_properties_province ON properties(province);
CREATE INDEX idx_properties_type ON properties(property_type);
```

#### **Module 7: incomes**
```sql
-- Table: incomes
CREATE TABLE incomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    applicant_id UUID NOT NULL REFERENCES applicants(id) ON DELETE CASCADE,
    income_type VARCHAR(50) NOT NULL CHECK (income_type IN ('employment', 'self_employment', 'rental', 'other')),
    monthly_amount DECIMAL(10,2) NOT NULL,
    employer_name VARCHAR(255),
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_incomes_applicant ON incomes(applicant_id);
CREATE INDEX idx_incomes_type ON incomes(income_type);
```

#### **Module 8: liabilities**
```sql
-- Table: liabilities
CREATE TABLE liabilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    applicant_id UUID NOT NULL REFERENCES applicants(id) ON DELETE CASCADE,
    liability_type VARCHAR(50) NOT NULL CHECK (liability_type IN ('credit_card', 'loan', 'mortgage', 'other')),
    monthly_payment DECIMAL(10,2) NOT NULL,
    outstanding_balance DECIMAL(12,2),
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_liabilities_applicant ON liabilities(applicant_id);
CREATE INDEX idx_liabilities_type ON liabilities(liability_type);
```

#### **Module 9: documents**
```sql
-- Table: documents
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    applicant_id UUID REFERENCES applicants(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('identification', 'income_proof', 'property_appraisal', 'bank_statement', 'insurance_certificate')),
    file_name VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL CHECK (file_size > 0),
    content_type VARCHAR(100) NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_documents_application ON documents(application_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_created ON documents(created_at);
```

#### **Module 10: underwriting_results**
```sql
-- Table: underwriting_results
CREATE TABLE underwriting_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL UNIQUE REFERENCES applications(id) ON DELETE CASCADE,
    decision VARCHAR(50) NOT NULL CHECK (decision IN ('approved', 'declined', 'conditional')),
    decision_reason TEXT,
    gds_ratio DECIMAL(5,2) NOT NULL,  -- OSFI: Audit trail
    tds_ratio DECIMAL(5,2) NOT NULL,  -- OSFI: Audit trail
    qualifying_rate DECIMAL(5,4) NOT NULL,  -- OSFI: stress test rate
    stress_test_rate DECIMAL(5,4) NOT NULL,  -- OSFI: max(contract_rate + 2%, 5.25%)
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_underwriting_decision ON underwriting_results(decision);
CREATE INDEX idx_underwriting_created_by ON underwriting_results(created_by);
```

#### **Module 11: audit_logs**
```sql
-- Table: audit_logs (FINTRAC: Immutable audit trail)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    old_values JSONB,
    new_values JSONB,
    created_by UUID REFERENCES users(id),
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_audit_table_record ON audit_logs(table_name, record_id);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at);
CREATE INDEX idx_audit_action ON audit_logs(action);
```

#### **Module 12: transactions**
```sql
-- Table: transactions (FINTRAC: Large transaction tracking)
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    transaction_type VARCHAR(50) NOT NULL CHECK (transaction_type IN ('deposit', 'withdrawal', 'payment', 'fee')),
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'CAD' NOT NULL,
    is_large_transaction BOOLEAN GENERATED ALWAYS AS (amount > 10000) STORED,  -- FINTRAC: Auto-flag >$10K
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_transactions_application ON transactions(application_id);
CREATE INDEX idx_transactions_large ON transactions(is_large_transaction) WHERE is_large_transaction = true;
CREATE INDEX idx_transactions_created_at ON transactions(created_at);
```

---

## 3. Business Logic

### Migration Dependency Chain
```
Migration 1 (users) → Migration 2 (lenders) → Migration 3 (products)
  ↓
Migration 4 (applications) → Migration 5 (applicants) → Migration 6 (properties)
  ↓
Migration 7 (incomes) → Migration 8 (liabilities) → Migration 9 (documents)
  ↓
Migration 10 (underwriting_results) → Migration 11 (audit_logs) → Migration 12 (transactions)
```

### Seed Data Insertion Logic
1. **Idempotency**: All seed operations use `INSERT ... ON CONFLICT DO NOTHING` or truncate-first pattern for dev environments only.
2. **PIPEDA Compliance**: SIN and DOB values are encrypted using AES-256-GCM with environment-specific keys from `common/config.py`.
3. **Password Hashing**: All user passwords hashed with bcrypt (work factor 12).
4. **CMHC Insurance Calculation**: Automatically calculated during application seed based on LTV ratio:
   - 80.01-85%: premium = loan_amount × 0.0280
   - 85.01-90%: premium = loan_amount × 0.0310
   - 90.01-95%: premium = loan_amount × 0.0400
5. **OSFI Stress Test**: Sample underwriting result includes qualifying_rate = max(contract_rate + 2%, 5.25%).
6. **FINTRAC Audit**: Every seeded record generates a corresponding audit_log entry with `action='create'` and `created_by` referencing the admin user.

### Sample Application Scenario (Approved with Conditions)
- **Property**: $500,000 condo in Toronto
- **Loan**: $450,000 (LTV = 90.0%)
- **Applicants**: Primary ($10,000/mo income) + Spouse ($5,000/mo income)
- **Liabilities**: $500/mo car loan, $200/mo credit card
- **Decision**: Conditional approval (pending insurance verification)
- **GDS/TDS**: 36% / 41% (pass OSFI limits at 7.5% stress test rate)
- **Insurance**: $13,950 premium (3.10% of $450,000)

---

## 4. Migrations

### Migration Files (12 total, sequential)

| # | File | Dependencies | Tables Created | Key Operations |
|---|------|--------------|----------------|----------------|
| 001 | `alembic/versions/001_create_users_table.py` | - | users | Create table, indexes, pgcrypto extension |
| 002 | `alembic/versions/002_create_lenders_table.py` | 001 | lenders | Create table, indexes |
| 003 | `alembic/versions/003_create_products_table.py` | 002 | products | Create table, FK to lenders, indexes |
| 004 | `alembic/versions/004_create_applications_table.py` | 001 | applications | Create table, FK to users, indexes, CHECK constraints for OSFI ratios |
| 005 | `alembic/versions/005_create_applicants_table.py` | 004, 001 | applicants | Create table, FKs, encrypted fields, indexes |
| 006 | `alembic/versions/006_create_properties_table.py` | 004 | properties | Create table, FK to applications, spatial-index-ready |
| 007 | `alembiv/versions/007_create_incomes_table.py` | 005 | incomes | Create table, FK to applicants, indexes |
| 008 | `alembic/versions/008_create_liabilities_table.py` | 005 | liabilities | Create table, FK to applicants, indexes |
| 009 | `alembic/versions/009_create_documents_table.py` | 004, 005 | documents | Create table, FKs, storage path validation |
| 010 | `alembic/versions/010_create_underwriting_results_table.py` | 004, 001 | underwriting_results | Create table, FKs, audit trail for OSFI compliance |
| 011 | `alembic/versions/011_create_audit_logs_table.py` | 001 | audit_logs | Create table, FINTRAC immutable trail, indexes |
| 012 | `alembic/versions/012_create_transactions_table.py` | 004, 001 | transactions | Create table, generated column for large transactions, FINTRAC indexes |

### Migration Rollback Testing Strategy
1. **Unit Test**: Each migration's `downgrade()` function tested in isolation using pytest-alembic.
2. **Integration Test**: Full upgrade → downgrade → upgrade cycle on a fresh PostgreSQL 15 container.
3. **Data Integrity**: After downgrade, verify no tables exist and no data leakage in `pg_toast`.
4. **Environment Gates**: Downgrade blocked in production via `common/config.py` setting `ALLOW_MIGRATION_DOWNGRADE=false`.

---

## 5. Security & Compliance

### OSFI B-20 Implementation
- **Stress Test Rate**: Calculated as `GREATEST(contract_rate + 2.0, 5.25)` in underwriting logic.
- **Hard Limits**: Database CHECK constraints enforce `gds_ratio <= 39.00` and `tds_ratio <= 44.00`.
- **Audit Trail**: `underwriting_results` table logs all calculation inputs/outputs for examiner review.

### FINTRAC Requirements
- **Immutable Records**: All tables lack `DELETE` endpoints; `audit_logs` captures all changes.
- **Large Transaction Flag**: `transactions.is_large_transaction` auto-generated; triggers real-time alert to FINTRAC endpoint.
- **5-Year Retention**: `audit_logs` table partitioned monthly; automated job prevents deletion before 5-year threshold.

### PIPEDA Data Handling
- **Encryption**: `sin_encrypted` and `dob_encrypted` use `pgcrypto`'s `pgp_sym_encrypt()` with AES-256 keys from Vault.
- **Hashing**: `sin_hash` stored for deduplication; uses SHA256 with salt from config.
- **Data Minimization**: Seed data includes only fields required for underwriting; no extraneous PII.

### Authentication & Authorization
- **Seed Endpoint**: Requires `admin` role + valid JWT + MFA token (TOTP).
- **Audit**: Every seed operation logs `created_by` admin user ID and IP address to `audit_logs`.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `MigrationError` | 500 | `MIGRATION_001` | "Migration {revision} failed: {detail}" | Alembic command exits non-zero |
| `SeedDataError` | 500 | `SEED_001` | "Seed data insertion failed: {table}" | Unique constraint violation on rerun |
| `EnvironmentNotFoundError` | 404 | `SEED_002` | "Environment '{env}' not configured" | Invalid `environment` path parameter |
| `SeedConflictError` | 409 | `SEED_003` | "Existing data found. Use truncate_existing=true to override" | Data exists and truncate=false |
| `EncryptionKeyError` | 500 | `SEED_004` | "PIPEDA encryption key not available" | `PII_ENCRYPTION_KEY` missing from config |

### Structured Error Response Format
```json
{
  "detail": "Seed data insertion failed: users table",
  "error_code": "SEED_001",
  "module": "database_migrations",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "c7f2a9e4-3b1d-4f8e-9c6a-5d8e7f1a2b3c"
}
```

---

## Seed Data Specifications

### Environment-Specific Variations
| Environment | Truncate Allowed | Sample Data Volume | SIN Encryption Key | Notes |
|-------------|------------------|--------------------|--------------------|-------|
| `development` | Yes | Full (100+ records) | Dev key (rotated weekly) | Includes edge case test data |
| `staging` | No | Minimal (as above) | Staging key (Vault) | Mirrors production schema |
| `demo` | Yes | Demo scenario only | Demo key (public) | Uses fake but realistic data |
| `production` | No | None (manual setup) | Production key (HSM) | Seed endpoint disabled |

### Baseline Product Rates (CMHC/OSFI Compliant)
| Lender | Product | Rate | Term | Insurance Required |
|--------|---------|------|------|-------------------|
| RBC | 5-Year Fixed | 5.8500 | 5 years | If LTV > 80% |
| RBC | 5-Year Variable | 6.2500 | 5 years | If LTV > 80% |
| TD | 5-Year Fixed | 5.7900 | 5 years | If LTV > 80% |
| TD | 5-Year Variable | 6.1900 | 5 years | If LTV > 80% |
| ... | ... | ... | ... | ... |

*All rates as DECIMAL(5,4) to support basis-point precision.*

---

## Testing Strategy

### Migration Tests (pytest markers: `@pytest.mark.integration`)
1. **Test Upgrade Path**: Apply all migrations to empty DB; verify schema.
2. **Test Downgrade Path**: Rollback each migration; verify clean state.
3. **Test Idempotency**: Run seed data twice; verify no duplicates.
4. **Test Data Integrity**: Query seeded application; verify LTV, GDS, TDS calculations match expected values.

### Seed Data Verification
- **SIN Encryption**: Decrypt `sin_encrypted` and verify matches plain text (dev only).
- **Audit Log Count**: Verify `audit_logs` has 1 entry per seeded record.
- **Large Transaction Flag**: Verify transaction > $10,000 has `is_large_transaction=true`.