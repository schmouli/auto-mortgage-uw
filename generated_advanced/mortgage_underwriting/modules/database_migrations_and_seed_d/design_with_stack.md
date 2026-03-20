# Design: Database Migrations & Seed Data
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Database Migrations & Seed Data Design Plan

**Feature Slug:** `database-migrations-seed-data`  
**Document Path:** `docs/design/database-migrations-seed-data.md`  
**Module Complexity:** Reasoning (foundational infrastructure)

---

## 1. Endpoints

This module provides admin-only API endpoints for migration control and seed management. All endpoints require `admin` role and are prefixed with `/api/v1/admin/database`.

| Method | Path | Request Schema | Response Schema | Error Codes | Auth |
|--------|------|----------------|-----------------|-------------|------|
| `POST` | `/migrate/up` | `{"revision": "head"}` | `{"status": "ok", "revision": "abc123"}` | `DB_001`, `DB_003` | admin-only |
| `POST` | `/migrate/down` | `{"revision": "-1"}` | `{"status": "ok", "revision": "abc123"}` | `DB_001`, `DB_003` | admin-only |
| `GET` | `/migrate/status` | None | `{"current_rev": "abc123", "pending": ["def456"]}` | `DB_001` | admin-only |
| `POST` | `/seed/{environment}` | `{"confirm": true, "truncate_first": false}` | `{"status": "ok", "seeded": {"users": 3, "lenders": 5, ...}}` | `DB_002`, `DB_004` | admin-only |
| `POST` | `/seed/rollback-test` | `{"test_scenario": "approved_application"}` | `{"status": "ok", "rollback_verified": true}` | `DB_003`, `DB_005` | admin-only |

**Request/Response Details:**

- **POST /migrate/up**: Runs `alembic upgrade head`. The `revision` field accepts `"head"` or specific revision ID.
- **POST /migrate/down**: Runs `alembic downgrade`. The `revision` field accepts `"-"`, `"-1"`, or specific revision ID.
- **GET /migrate/status**: Returns current Alembic version and pending migrations by reading `alembic_version` table.
- **POST /seed/{environment}`: Seeds data for `dev`, `staging`, or `prod` environments. `confirm` flag required to prevent accidental execution. `truncate_first` uses `TRUNCATE ... CASCADE` for idempotent seeding.
- **POST /seed/rollback-test**: Creates temporary database, runs migrations up/down, verifies schema integrity and data consistency.

**Error Responses:**
- `400`: `{"detail": "Invalid revision format", "error_code": "DB_001"}`
- `409`: `{"detail": "Migration in progress", "error_code": "DB_003"}`
- `422`: `{"detail": "Environment must be one of: dev, staging, prod", "error_code": "DB_002"}`

---

## 2. Models & Database

### 2.1 Module-to-Migration Mapping

| Migration # | Module Name | Dependencies | Tables Created |
|-------------|-------------|--------------|----------------|
| 001 | `users` | None | `users`, `user_roles` |
| 002 | `lenders` | None | `lenders` |
| 003 | `products` | 002 | `products`, `product_rates` |
| 004 | `applications` | 001, 002 | `applications` |
| 005 | `borrowers` | 001, 004 | `borrowers`, `employment_history` |
| 006 | `properties` | 004 | `properties`, `property_valuations` |
| 007 | `documents` | 001, 004, 005, 006 | `documents`, `document_versions` |
| 008 | `credit_reports` | 005 | `credit_reports`, `credit_inquiries` |
| 009 | `income_verification` | 005 | `income_verification`, `bank_statements` |
| 010 | `underwriting_results` | 004, 005, 008 | `underwriting_results`, `debt_calculations` |
| 011 | `audit_logs` | All previous | `audit_logs`, `compliance_events` |
| 012 | `compliance_reports` | 011 | `compliance_reports`, `fintrac_flags` |

### 2.2 Detailed Model Specifications

#### Migration 001: Users Module

**Table: `users`**
```python
# Table: users
id: UUID (PK, default=gen_random_uuid())
email: VARCHAR(255) (UNIQUE, NOT NULL, encrypted at rest)
hashed_password: VARCHAR(255) (NOT NULL)
role: VARCHAR(50) (NOT NULL, CHECK role IN ('admin', 'broker', 'client'))
first_name: VARCHAR(100) (encrypted)
last_name: VARCHAR(100) (encrypted)
sin_hash: VARCHAR(64) (UNIQUE, NOT NULL, SHA256 hash for lookups only)
sin_encrypted: BYTEA (AES-256 encrypted, never logged)
dob_encrypted: BYTEA (AES-256 encrypted, never logged)
phone: VARCHAR(20) (encrypted)
is_active: BOOLEAN (default=True)
created_at: TIMESTAMPTZ (NOT NULL, default=now())
updated_at: TIMESTAMPTZ (NOT NULL, default=now())
# Indexes: (email), (sin_hash), (role, is_active)
```

**Table: `user_roles`**
```python
# Table: user_roles
id: UUID (PK)
user_id: UUID (FK users.id, CASCADE)
org_id: UUID (FK lenders.id, optional)
created_at: TIMESTAMPTZ (NOT NULL)
# Composite index: (user_id, org_id)
```

#### Migration 002: Lenders Module

**Table: `lenders`**
```python
# Table: lenders
id: UUID (PK)
legal_name: VARCHAR(255) (NOT NULL)
operating_name: VARCHAR(255)
institution_code: VARCHAR(10) (UNIQUE, NOT NULL)  # OSFI institution code
address_encrypted: BYTEA (AES-256)
created_at: TIMESTAMPTZ (NOT NULL)
updated_at: TIMESTAMPTZ (NOT NULL)
# Index: (institution_code)
```

#### Migration 003: Products Module

**Table: `products`**
```python
# Table: products
id: UUID (PK)
lender_id: UUID (FK lenders.id, RESTRICT)
product_code: VARCHAR(50) (NOT NULL)
product_type: VARCHAR(50) (NOT NULL, CHECK IN ('fixed', 'variable'))
term_years: INTEGER (NOT NULL, CHECK term_years > 0)
amortization_max_years: INTEGER (NOT NULL)
is_insurable: BOOLEAN (default=True)
created_at: TIMESTAMPTZ (NOT NULL)
updated_at: TIMESTAMPTZ (NOT NULL)
# Composite UNIQUE: (lender_id, product_code)
# Index: (product_type, term_years)
```

**Table: `product_rates`**
```python
# Table: product_rates
id: UUID (PK)
product_id: UUID (FK products.id, CASCADE)
effective_date: DATE (NOT NULL)
contract_rate: DECIMAL(5,4) (NOT NULL)  # e.g., 5.2400%
qualifying_rate: DECIMAL(5,4) (GENERATED ALWAYS AS (GREATEST(contract_rate + 2.0, 5.25)))  # OSFI B-20 stress test
prime_rate: DECIMAL(5,4) (nullable, for variable products)
created_at: TIMESTAMPTZ (NOT NULL)
# Composite UNIQUE: (product_id, effective_date)
# Index: (effective_date DESC)
```

#### Migration 004: Applications Module

**Table: `applications`**
```python
# Table: applications
id: UUID (PK)
application_number: VARCHAR(50) (UNIQUE, NOT NULL, generated: APP-yyyy-######)
broker_id: UUID (FK users.id, SET NULL)
lender_id: UUID (FK lenders.id, RESTRICT)
product_id: UUID (FK products.id, RESTRICT)
loan_amount: DECIMAL(12,2) (NOT NULL)
property_value: DECIMAL(12,2) (NOT NULL)
ltv_ratio: DECIMAL(5,2) (GENERATED ALWAYS AS (loan_amount / property_value * 100))
purpose: VARCHAR(50) (NOT NULL, CHECK IN ('purchase', 'refinance', 'renewal'))
fintrac_transaction_id: VARCHAR(100) (NULL, populated if loan_amount >= 10000)
status: VARCHAR(50) (NOT NULL, CHECK IN ('draft', 'submitted', 'underwriting', 'approved', 'declined', 'conditional'))
status_reason: TEXT (nullable)
submitted_at: TIMESTAMPTZ (nullable)
created_at: TIMESTAMPTZ (NOT NULL)
updated_at: TIMESTAMPTZ (NOT NULL)
# Indexes: (application_number), (broker_id, status), (lender_id, status), (ltv_ratio)
# CHECK: loan_amount >= 0, property_value > 0
```

#### Migration 005: Borrowers Module

**Table: `borrowers`**
```python
# Table: borrowers
id: UUID (PK)
application_id: UUID (FK applications.id, CASCADE)
user_id: UUID (FK users.id, SET NULL)
is_primary: BOOLEAN (NOT NULL)
relationship_type: VARCHAR(50) (NOT NULL, CHECK IN ('borrower', 'co_borrower', 'guarantor'))
monthly_income: DECIMAL(10,2) (NOT NULL)
monthly_debt: DECIMAL(10,2) (NOT NULL, default=0)
credit_score: INTEGER (nullable, CHECK credit_score BETWEEN 300 AND 900)
created_at: TIMESTAMPTZ (NOT NULL)
updated_at: TIMESTAMPTZ (NOT NULL)
# Composite index: (application_id, is_primary)
```

**Table: `employment_history`**
```python
# Table: employment_history
id: UUID (PK)
borrower_id: UUID (FK borrowers.id, CASCADE)
employer_name_encrypted: BYTEA (AES-256)
position: VARCHAR(100) (nullable)
start_date: DATE (NOT NULL)
end_date: DATE (nullable)
is_current: BOOLEAN (NOT NULL)
created_at: TIMESTAMPTZ (NOT NULL)
# Index: (borrower_id, is_current)
```

#### Migration 006: Properties Module

**Table: `properties`**
```python
# Table: properties
id: UUID (PK)
application_id: UUID (FK applications.id, CASCADE)
address_encrypted: BYTEA (AES-256)
postal_code: VARCHAR(10) (encrypted)
property_type: VARCHAR(50) (NOT NULL, CHECK IN ('single_family', 'condo', 'townhouse', 'multi_unit'))
year_built: INTEGER (nullable)
property_tax_annual: DECIMAL(10,2) (NOT NULL, default=0)
created_at: TIMESTAMPTZ (NOT NULL)
updated_at: TIMESTAMPTZ (NOT NULL)
# Index: (postal_code)
```

**Table: `property_valuations`**
```python
# Table: property_valuations
id: UUID (PK)
property_id: UUID (FK properties.id, CASCADE)
valuation_date: DATE (NOT NULL)
appraised_value: DECIMAL(12,2) (NOT NULL)
appraiser_license: VARCHAR(100) (NOT NULL)
created_at: TIMESTAMPTZ (NOT NULL)
# Composite UNIQUE: (property_id, valuation_date)
```

#### Migration 007: Documents Module

**Table: `documents`**
```python
# Table: documents
id: UUID (PK)
application_id: UUID (FK applications.id, CASCADE)
document_type: VARCHAR(100) (NOT NULL, CHECK IN ('identification', 'income_proof', 'property_appraisal', 'bank_statement'))
filename: VARCHAR(255) (NOT NULL)
storage_path: VARCHAR(500) (NOT NULL, S3 path)
file_hash: VARCHAR(64) (NOT NULL, SHA256 for integrity)
created_by: UUID (FK users.id, SET NULL)
created_at: TIMESTAMPTZ (NOT NULL)
# Composite index: (application_id, document_type)
```

**Table: `document_versions`**
```python
# Table: document_versions
id: UUID (PK)
document_id: UUID (FK documents.id, CASCADE)
version_number: INTEGER (NOT NULL)
file_hash: VARCHAR(64) (NOT NULL)
created_at: TIMESTAMPTZ (NOT NULL)
# Composite UNIQUE: (document_id, version_number)
```

#### Migration 008: Credit Reports Module

**Table: `credit_reports`**
```python
# Table: credit_reports
id: UUID (PK)
borrower_id: UUID (FK borrowers.id, CASCADE)
report_date: DATE (NOT NULL)
credit_bureau: VARCHAR(50) (NOT NULL, CHECK IN ('equifax', 'transunion'))
report_data_encrypted: BYTEA (AES-256, full report JSON)
created_at: TIMESTAMPTZ (NOT NULL)
# Composite index: (borrower_id, report_date DESC)
```

**Table: `credit_inquiries`**
```python
# Table: credit_inquiries
id: UUID (PK)
credit_report_id: UUID (FK credit_reports.id, CASCADE)
inquiry_date: DATE (NOT NULL)
inquiry_type: VARCHAR(50) (NOT NULL)
created_at: TIMESTAMPTZ (NOT NULL)
```

#### Migration 009: Income Verification Module

**Table: `income_verification`**
```python
# Table: income_verification
id: UUID (PK)
borrower_id: UUID (FK borrowers.id, CASCADE)
verification_method: VARCHAR(50) (NOT NULL, CHECK IN ('pay_stub', 'noa', 'bank_statement', 'employer_letter'))
verified_income: DECIMAL(10,2) (NOT NULL)
verified_date: DATE (NOT NULL)
verifier_id: UUID (FK users.id, SET NULL)
created_at: TIMESTAMPTZ (NOT NULL)
# Index: (borrower_id, verified_date DESC)
```

**Table: `bank_statements`**
```python
# Table: bank_statements`
id: UUID (PK)
borrower_id: UUID (FK borrowers.id, CASCADE)
statement_date: DATE (NOT NULL)
account_balance: DECIMAL(12,2) (NOT NULL)
transaction_volume: DECIMAL(12,2) (NOT NULL, CHECK transaction_volume >= 0)
# FINTRAC flag auto-populated if transaction_volume >= 10000
fintrac_flag: BOOLEAN (GENERATED ALWAYS AS (transaction_volume >= 10000))
created_at: TIMESTAMPTZ (NOT NULL)
# Index: (borrower_id, statement_date)
```

#### Migration 010: Underwriting Results Module

**Table: `underwriting_results`**
```python
# Table: underwriting_results
id: UUID (PK)
application_id: UUID (FK applications.id, CASCADE)
underwriter_id: UUID (FK users.id, SET NULL)
decision: VARCHAR(50) (NOT NULL, CHECK IN ('approved', 'declined', 'conditional'))
gds_ratio: DECIMAL(5,2) (NOT NULL, CHECK gds_ratio <= 39.0)  # OSFI B-20 limit
tds_ratio: DECIMAL(5,2) (NOT NULL, CHECK tds_ratio <= 44.0)  # OSFI B-20 limit
stress_test_rate: DECIMAL(5,4) (NOT NULL)  # From product_rates.qualifying_rate
cmhc_insurance_required: BOOLEAN (NOT NULL)
cmhc_premium_amount: DECIMAL(10,2) (nullable)
debt_service_calculation_encrypted: BYTEA (AES-256, JSON breakdown for audit)
created_at: TIMESTAMPTZ (NOT NULL)
# Composite UNIQUE: (application_id)
# Index: (underwriter_id, decision)
```

**Table: `debt_calculations`**
```python
# Table: debt_calculations
id: UUID (PK)
underwriting_result_id: UUID (FK underwriting_results.id, CASCADE)
debt_type: VARCHAR(100) (NOT NULL)
monthly_payment: DECIMAL(10,2) (NOT NULL)
is_included_in_tds: BOOLEAN (NOT NULL)
created_at: TIMESTAMPTZ (NOT NULL)
# Index: (underwriting_result_id, is_included_in_tds)
```

#### Migration 011: Audit Logs Module

**Table: `audit_logs`**
```python
# Table: audit_logs
id: UUID (PK)
entity_type: VARCHAR(100) (NOT NULL)  # e.g., 'applications', 'borrowers'
entity_id: UUID (NOT NULL)  # Generic FK pattern
action: VARCHAR(50) (NOT NULL, CHECK IN ('create', 'update', 'view', 'delete'))
actor_id: UUID (FK users.id, SET NULL)
actor_role: VARCHAR(50) (NOT NULL)
ip_address: INET (nullable)
user_agent: VARCHAR(500) (nullable)
changes_encrypted: BYTEA (AES-256, JSON diff)
created_at: TIMESTAMPTZ (NOT NULL)  # Immutable per FINTRAC
# Composite index: (entity_type, entity_id, created_at DESC)
# Index: (actor_id, created_at)
```

**Table: `compliance_events`**
```python
# Table: compliance_events
id: UUID (PK)
event_type: VARCHAR(100) (NOT NULL, CHECK IN ('fintrac_threshold', 'pii_access', 'ratio_limit_breach'))
application_id: UUID (FK applications.id, CASCADE)
event_data_encrypted: BYTEA (AES-256)
created_at: TIMESTAMPTZ (NOT NULL)
# Index: (event_type, created_at)
```

#### Migration 012: Compliance Reports Module

**Table: `compliance_reports`**
```python
# Table: compliance_reports
id: UUID (PK)
report_type: VARCHAR(100) (NOT NULL, CHECK IN ('fintrac_daily', 'osfi_monthly', 'cmhc_quarterly'))
report_period_start: DATE (NOT NULL)
report_period_end: DATE (NOT NULL)
report_data_encrypted: BYTEA (AES-256, full report payload)
generated_by: UUID (FK users.id, SET NULL)
created_at: TIMESTAMPTZ (NOT NULL)
# Composite UNIQUE: (report_type, report_period_start)
```

**Table: `fintrac_flags`**
```python
# Table: fintrac_flags
id: UUID (PK)
application_id: UUID (FK applications.id, CASCADE)
transaction_amount: DECIMAL(12,2) (NOT NULL)
flag_reason: VARCHAR(200) (NOT NULL)
reported_to_fintrac: BOOLEAN (default=False)
reported_at: TIMESTAMPTZ (nullable)
created_at: TIMESTAMPTZ (NOT NULL)  # 5-year retention marker
# Index: (application_id, reported_to_fintrac)
```

---

## 3. Business Logic

### 3.1 Migration Ordering & Dependencies

```python
# Dependency DAG for migrations:
# 001 (users) -> 004 (applications) -> 005 (borrowers) -> 008 (credit) -> 010 (uw)
# 001 -> 005 -> 009 (income) -> 010
# 002 (lenders) -> 003 (products) -> 004 -> 010
# 002 -> 004 -> 006 (properties) -> 007 (documents) -> 010
# 004 -> 010 -> 011 (audit) -> 012 (compliance)
```

**Reversal Logic:** Each migration must implement `downgrade()` that:
- Drops tables in reverse dependency order (leaf tables first)
- Uses `IF EXISTS` to handle partial states
- Preserves `alembic_version` integrity
- Fails fast if child migrations exist (foreign key RESTRICT enforcement)

### 3.2 Seed Data Insertion Logic

**Idempotency Strategy:**
```python
# Pseudocode for seeding:
async def seed_environment(env: str):
    async with transaction():
        if env == "dev":
            await truncate_tables(exclude=["alembic_version"])
        await seed_users()  # ON CONFLICT (email) DO NOTHING
        await seed_lenders()  # ON CONFLICT (institution_code) DO NOTHING
        await seed_products()  # ON CONFLICT (lender_id, product_code) DO UPDATE rate
        await seed_sample_application()  # Only in dev/staging
```

**Password Hashing:** Use `bcrypt` with cost factor 12. Store hashed passwords only.

### 3.3 Environment-Specific Variations

| Environment | Lender Rates | Sample Data | Truncate Allowed |
|-------------|--------------|-------------|------------------|
| `dev` | Prime - 0.5% (simulated) | Full sample apps | Yes |
| `staging` | Production rates + 0.25% | Minimal samples | No |
| `prod` | Production rates from API | No samples | No |

### 3.4 Sample Application Scenarios

**Scenario A: Approved Application**
- Loan: $400,000, Property: $500,000 (LTV 80%)
- Income: $8,333/month, Debts: $500/month
- GDS: 32.1% (PITH $2,677 / $8,333), TDS: 38.1% (incl. debts)
- Stress test: 7.24% (contract 5.24% + 2%)
- CMHC: Not required (LTV ≤ 80%)

**Scenario B: Declined Application**
- Loan: $475,000, Property: $500,000 (LTV 95%)
- Income: $5,000/month, Debts: $1,200/month
- GDS: 52.3% (violates OSFI limit), TDS: 76.3%
- Decision: Declined with reason code `OSFI_GDS_EXCEEDED`

**Scenario C: Conditional Approval**
- Loan: $450,000, Property: $500,000 (LTV 90%)
- Income: $7,500/month, Debts: $800/month
- GDS: 38.2%, TDS: 42.9% (within limits)
- CMHC: Required, premium $13,950 (3.10% tier)
- Conditions: Provide updated income verification

---

## 4. Migrations

### 4.1 Complete Migration List

| Revision ID | Migration Name | Tables Created | Indexes Added | FK Constraints |
|-------------|----------------|----------------|---------------|----------------|
| `a1b2c3d4e5f6` | `001_create_users` | users, user_roles | 3 | 1 |
| `b2c3d4e5f6g7` | `002_create_lenders` | lenders | 1 | 0 |
| `c3d4e5f6g7h8` | `003_create_products` | products, product_rates | 4 | 2 |
| `d4e5f6g7h8i9` | `004_create_applications` | applications | 4 | 3 |
| `e5f6g7h8i9j0` | `005_create_borrowers` | borrowers, employment_history | 3 | 2 |
| `f6g7h8i9j0k1` | `006_create_properties` | properties, property_valuations | 2 | 1 |
| `g7h8i9j0k1l2` | `007_create_documents` | documents, document_versions | 3 | 2 |
| `h8i9j0k1l2m3` | `008_create_credit_reports` | credit_reports, credit_inquiries | 2 | 1 |
| `i9j0k1l2m3n4` | `009_create_income_verification` | income_verification, bank_statements | 3 | 2 |
| `j0k1l2m3n4o5` | `010_create_underwriting_results` | underwriting_results, debt_calculations | 4 | 2 |
| `k1l2m3n4o5p6` | `011_create_audit_logs` | audit_logs, compliance_events | 4 | 1 |
| `l2m3n4o5p6q7` | `012_create_compliance_reports` | compliance_reports, fintrac_flags | 3 | 1 |

### 4.2 Key Constraints for Compliance

**OSFI B-20 Check Constraints:**
```sql
-- In underwriting_results table
ALTER TABLE underwriting_results 
ADD CONSTRAINT chk_gds_ratio CHECK (gds_ratio <= 39.0),
ADD CONSTRAINT chk_tds_ratio CHECK (tds_ratio <= 44.0);
```

**CMHC Premium Tier Lookup (Generated Column):**
```sql
-- In applications table
ALTER TABLE applications
ADD COLUMN cmhc_premium_tier VARCHAR(50) GENERATED ALWAYS AS (
  CASE 
    WHEN ltv_ratio > 95 THEN 'ineligible'
    WHEN ltv_ratio > 90 THEN 'tier_95'
    WHEN ltv_ratio > 85 THEN 'tier_90'
    WHEN ltv_ratio > 80 THEN 'tier_85'
    ELSE 'not_required'
  END
) STORED;
```

**FINTRAC Immutable Audit:**
```sql
-- In audit_logs table
ALTER TABLE audit_logs
ALTER COLUMN created_at SET DEFAULT now(),
ALTER COLUMN created_at SET NOT NULL;
-- No UPDATE or DELETE triggers will be added per FINTRAC requirements
```

### 4.3 Data Migration Needs

**Migration 003:** Seed initial product rates from `seeds/product_rates_baseline.csv` (included in repo, not in migration file). Use `COPY` command for performance.

**Migration 011:** Backfill `compliance_events` for historical applications >$10,000 using:
```sql
INSERT INTO compliance_events (event_type, application_id, event_data_encrypted, created_at)
SELECT 'fintrac_threshold', id, encrypt(jsonb_build_object('amount', loan_amount)), created_at
FROM applications 
WHERE loan_amount >= 10000 AND created_at < now();
```

---

## 5. Security & Compliance

### 5.1 PIPEDA Data Handling

**Encryption at Rest:**
- All `*_encrypted` columns use `pgcrypto` extension with AES-256-CBC
- Encryption key rotation: Keys stored in HashiCorp Vault, referenced via `common/config.py`
- Key ID stored in separate `encryption_keys` table (migration 001)
- Never log decrypted values; use `sin_hash` for lookups

**Data Minimization:**
- `borrowers` table only collects income/debt required for ratios
- `employment_history` limited to 2 years (configurable via `common/config.py`)
- `documents` table stores only metadata; actual files in S3 with AES-256 encryption

### 5.2 FINTRAC Requirements

**Transaction Monitoring:**
- `applications.loan_amount >= 10000` triggers `fintrac_transaction_id` generation
- `bank_statements.finrac_flag` auto-populated via generated column
- `fintrac_flags` table captures all threshold breaches with 5-year retention marker

**Audit Immutability:**
- `audit_logs` and `compliance_events` have `AFTER INSERT` trigger that raises exception on UPDATE/DELETE
- `created_at` is immutable; no `updated_at` column on audit tables

### 5.3 OSFI B-20 Enforcement

**Stress Test Calculation:**
- `product_rates.qualifying_rate` is GENERATED column ensuring formula: `max(contract_rate + 2%, 5.25%)`
- `underwriting_results` must calculate GDS/TDS using qualifying rate, not contract rate
- Check constraints enforce hard limits; attempts to insert violating ratios raise `IntegrityError`

**Audit Trail:**
- `debt_service_calculation_encrypted` stores full breakdown: PITH, income, debts, ratios, rates
- Logged via `structlog` with `correlation_id` and `audit=True` flag for Splunk indexing

### 5.4 CMHC Insurance Logic

**Premium Tier Lookup:**
```python
# In seed data: premium_rates table (migration 003)
premium_tiers = {
    'tier_85': {'min_ltv': 80.01, 'max_ltv': 85.00, 'rate': Decimal('0.0280')},
    'tier_90': {'min_ltv': 85.01, 'max_ltv': 90.00, 'rate': Decimal('0.0310')},
    'tier_95': {'min_ltv': 90.01, 'max_ltv': 95.00, 'rate': Decimal('0.0400')},
}
```
- `applications.cmhc_insurance_required` = `ltv_ratio > 80`
- Premium calculated: `loan_amount * premium_rate` (rounded to 2 decimal places)

---

## 6. Error Codes & HTTP Responses

### 6.1 Migration/Seed Exceptions

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `MigrationError` | 500 | `DB_001` | "Migration failed: {detail}" | Alembic command failure, DB connection lost |
| `SeedEnvironmentError` | 422 | `DB_002` | "Invalid environment: {env}" | Environment not in {dev, staging, prod} |
| `MigrationInProgressError` | 409 | `DB_003` | "Migration already in progress: {pid}" | Lock file exists in `migrations/locks/` |
| `SeedDataError` | 422 | `DB_004` | "Seed data validation failed: {field}" | Duplicate SIN hash, invalid LTV |
| `RollbackTestError` | 500 | `DB_005` | "Rollback verification failed: {reason}" | Schema mismatch after downgrade/up cycle |

### 6.2 Database Constraint Violations

| Constraint Name | Error Code | HTTP Mapping | User Message |
|-----------------|------------|--------------|--------------|
| `chk_gds_ratio` | `DB_006` | 409 | "GDS ratio exceeds OSFI limit of 39%" |
| `chk_tds_ratio` | `DB_007` | 409 | "TDS ratio exceeds OSFI limit of 44%" |
| `unique_application_number` | `DB_008` | 409 | "Application number already exists" |
| `unique_sin_hash` | `DB_009` | 409 | "SIN already registered in system" |

### 6.3 Security & Compliance Errors

| Exception Class | HTTP Status | Error Code | Message Pattern | Logging Rule |
|-----------------|-------------|------------|-----------------|--------------|
| `PIIAccessError` | 403 | `DB_010` | "Unauthorized PII access attempt" | Log with `warning`, include actor_id, exclude PII |
| `EncryptionKeyError` | 500 | `DB_011` | "Encryption key unavailable: {key_id}" | Log with `error`, include key_id only |
| `ImmutableRecordError` | 403 | `DB_012` | "Audit record cannot be modified" | Log with `critical`, include table name |

---

## 7. Rollback Testing Strategy

### 7.1 pytest Integration Test

```python
# tests/integration/test_migration_rollback.py
@pytest.mark.integration
async def test_migration_rollback_cycle(test_db):
    """Verify all 12 migrations can be rolled back and forward without data loss."""
    # 1. Migrate to head
    await alembic_upgrade("head")
    
    # 2. Seed minimal data
    await seed_environment("staging", truncate_first=False)
    
    # 3. Record schema snapshot
    schema_before = await get_table_schemas()
    
    # 4. Rollback all
    await alembic_downgrade("base")
    
    # 5. Rollback verification: ensure no tables exist
    assert await table_exists("users") is False
    
    # 6. Migrate up again
    await alembic_upgrade("head")
    
    # 7. Verify schema integrity
    schema_after = await get_table_schemas()
    assert schema_before == schema_after
    
    # 8. Verify constraint enforcement
    with pytest.raises(IntegrityError, match="chk_gds_ratio"):
        await insert_invalid_ratios()
```

### 7.2 CI/CD Pipeline Integration

- **Pre-deploy:** Run rollback test on ephemeral PostgreSQL container
- **Post-deploy:** Execute `GET /api/v1/admin/database/migrate/status` health check
- **Rollback Procedure:** If deployment fails, run `POST /migrate/down` with `revision="-1"`

---

## 8. Missing Details Specification

### 8.1 Lender Product Rates Baseline

**File:** `seeds/product_rates_baseline.csv`
```csv
lender_code,product_code,product_type,term_years,amortization_max_years,contract_rate,prime_rate,effective_date
RBC,RBC-5FIX,fixed,5,25,5.2400,,2024-01-01
RBC,RBC-5VAR,variable,5,25,5.9500,6.4500,2024-01-01
TD,TD-5FIX,fixed,5,25,5.1900,,2024-01-01
TD,TD-5VAR,variable,5,25,5.9000,6.4000,2024-01-01
BMO,BMO-5FIX,fixed,5,25,5.2200,,2024-01-01
BMO,BMO-5VAR,variable,5,25,5.9200,6.4200,2024-01-01
SCOTIA,SCO-5FIX,fixed,5,25,5.2500,,2024-01-01
SCOTIA,SCO-5VAR,variable,5,25,5.9600,6.4600,2024-01-01
CIBC,CIBC-5FIX,fixed,5,25,5.2100,,2024-01-01
CIBC,CIBC-5VAR,variable,5,25,5.9100,6.4100,2024-01-01
```

### 8.2 Sample Application Scenarios

**Dev Environment Seed:**
- 3 applications (approved, declined, conditional) as per Section 3.3
- Each with full borrower, property, document, credit, income, and UW result data
- Document files stored in `s3://mortgage-uw-dev-seed-documents/` with public-read for testing

### 8.3 Test Data for Stress Testing

**File:** `seeds/stress_test_cases.csv`
```csv
case_name,loan_amount,property_value,income,debts,expected_gds,expected_tds,expected_decision
max_gds_39,450000,500000,7500,800,38.99,42.99,approved
gds_39_01,450000,500000,7490,800,39.01,42.99,declined
max_tds_44,450000,500000,6500,1200,38.50,43.99,approved
tds_44_01,450000,500000,6500,1210,38.50,44.01,declined
ltv_80_01,400050,500000,8000,500,32.00,38.00,approved_with_insurance
```

### 8.4 Environment-Specific Seed Variations

**Config:** `common/config.py`
```python
class SeedConfig(BaseSettings):
    dev_truncate_allowed: bool = True
    staging_sample_count: int = 1
    prod_seed_enabled: bool = False
    rate_adjustment_dev: Decimal = Decimal("-0.50")  # Simulate lower rates
    rate_adjustment_staging: Decimal = Decimal("0.25")  # Buffer for testing
```

---

## 9. Deployment Checklist

- [ ] Run `uv run alembic check` to verify no pending migrations
- [ ] Execute `uv run pytest -m integration tests/integration/test_migration_rollback.py`
- [ ] Run `uv run pip-audit` to ensure no vulnerable dependencies
- [ ] Verify `encryption_keys` table has active key for environment
- [ ] Confirm `seeds/` directory is included in Docker image but not in production container
- [ ] Set `prod_seed_enabled=False` in production config
- [ ] Create migration lock directory `migrations/locks/` with proper permissions
- [ ] Document rollback procedure in `runbooks/rollback-database.md`

---

**WARNING:** This design plan assumes all 12 modules are independent but sequentially dependent. If module dependencies change, the migration order must be updated via topological sort of the dependency graph. Always run `alembic check` before deployment.