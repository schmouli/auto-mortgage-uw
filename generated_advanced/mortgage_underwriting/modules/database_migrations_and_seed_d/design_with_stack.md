# Design: Database Migrations & Seed Data
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Database Migrations & Seed Data

**File:** `docs/design/database-migrations-seed-data.md`

---

## 1. Endpoints

### 1.1 Migration Health Check
- **GET** `/api/v1/system/migration-status`
  - **Auth:** Admin-only (OAuth 2.0 JWT)
  - **Response:** `MigrationStatusResponse`
    ```python
    {
        "current_revision": str,
        "head_revision": str,
        "pending_migrations": int,
        "last_applied": datetime | None,
        "status": Literal["up_to_date", "pending", "error"]
    }
    ```
  - **Errors:**
    - `401 Unauthorized` → `AUTH_001: "Invalid or expired token"`
    - `403 Forbidden` → `AUTH_002: "Admin access required"`
    - `500 Internal Server Error` → `SYSTEM_001: "Migration system unavailable"`

### 1.2 Seed Data Management (CLI-only, no HTTP endpoints)
- **Command:** `uv run alembic seed --environment={dev|staging|prod}`
- **Auth:** CLI execution requires `SEED_EXECUTION_TOKEN` environment variable
- **Flags:** `--dry-run`, `--force`, `--scenario={approved|declined|conditional}`

---

## 2. Models & Database

### 2.1 Module-to-Migration Mapping (12 Total)

| # | Module | Table Name | Purpose | Encrypted Fields |
|---|--------|------------|---------|------------------|
| 1 | users | `users` | Authentication & roles | None |
| 2 | lenders | `lenders` | Financial institutions | None |
| 3 | products | `products` | Mortgage product catalog | None |
| 4 | applications | `applications` | Main mortgage application | None |
| 5 | applicants | `applicants` | Personal PII data | `sin_encrypted`, `dob_encrypted` |
| 6 | properties | `properties` | Property details | None |
| 7 | documents | `documents` | Uploaded files metadata | None |
| 8 | underwriting_results | `underwriting_results` | Decision engine output | None |
| 9 | income_verification | `income_verification` | Income data | None |
| 10 | credit_bureau | `credit_bureau` | Credit report data | None |
| 11 | audit_logs | `audit_logs` | FINTRAC immutable trail | None |
| 12 | insurance | `insurance` | CMHC insurance details | None |

### 2.2 Detailed Model Specifications

#### **Module 1: users**
```python
Table: users
- id: UUID (PK, default=gen_random_uuid())
- email: VARCHAR(255) (UNIQUE, INDEX)
- hashed_password: VARCHAR(255) (NOT NULL)
- role: VARCHAR(50) (CHECK IN ('admin', 'broker', 'client'))
- is_active: BOOLEAN (DEFAULT true)
- created_at: TIMESTAMP (DEFAULT now(), INDEX)
- updated_at: TIMESTAMP (DEFAULT now(), onupdate=now())
```
- **Indexes:** Composite on `(is_active, role)` for role-based queries
- **Relationships:** One-to-Many → applications

#### **Module 2: lenders**
```python
Table: lenders
- id: UUID (PK)
- name: VARCHAR(255) (UNIQUE)
- code: VARCHAR(10) (UNIQUE, INDEX)  # e.g., 'RBC', 'TD'
- is_active: BOOLEAN (DEFAULT true)
- created_at: TIMESTAMP (DEFAULT now())
- updated_at: TIMESTAMP (DEFAULT now())
```
- **Relationships:** One-to-Many → products

#### **Module 3: products**
```python
Table: products
- id: UUID (PK)
- lender_id: UUID (FK → lenders.id, INDEX)
- name: VARCHAR(255)  # e.g., "5-Year Fixed Closed"
- rate_type: VARCHAR(20) (CHECK IN ('fixed', 'variable'), INDEX)
- interest_rate: DECIMAL(5,4) (NOT NULL)  # e.g., 5.2500
- term_years: INTEGER (CHECK > 0)
- is_active: BOOLEAN (DEFAULT true)
- created_at: TIMESTAMP (DEFAULT now())
- updated_at: TIMESTAMP (DEFAULT now())
```
- **Indexes:** Composite `(lender_id, rate_type, is_active)` for product lookups

#### **Module 4: applications**
```python
Table: applications
- id: UUID (PK)
- application_number: VARCHAR(20) (UNIQUE, INDEX)  # Format: APP-yyyymmdd-#####
- user_id: UUID (FK → users.id, INDEX)
- product_id: UUID (FK → products.id, INDEX)
- loan_amount: DECIMAL(12,2) (NOT NULL)
- property_value: DECIMAL(12,2) (NOT NULL)
- ltv_ratio: DECIMAL(5,2) (GENERATED ALWAYS AS (loan_amount/property_value*100) STORED, INDEX)
- status: VARCHAR(30) (CHECK IN ('draft', 'submitted', 'underwriting', 'approved', 'declined', 'conditional'), INDEX)
- purpose: VARCHAR(50) (CHECK IN ('purchase', 'refinance', 'renewal'))  # FINTRAC: >$10K flagging
- created_at: TIMESTAMP (DEFAULT now(), INDEX)
- updated_at: TIMESTAMP (DEFAULT now())
```
- **Indexes:** Composite `(status, created_at)` for workflow queues
- **Triggers:** FINTRAC logging on INSERT for loan_amount > 10000

#### **Module 5: applicants**
```python
Table: applicants
- id: UUID (PK)
- application_id: UUID (FK → applications.id, UNIQUE, INDEX)
- first_name: VARCHAR(100) (NOT NULL)
- last_name: VARCHAR(100) (NOT NULL)
- sin_encrypted: BYTEA (NOT NULL)  # PIPEDA: AES-256
- sin_hash: VARCHAR(64) (UNIQUE, INDEX)  # SHA256 for lookups
- dob_encrypted: BYTEA (NOT NULL)  # PIPEDA: AES-256
- email: VARCHAR(255)
- phone: VARCHAR(20)
- created_at: TIMESTAMP (DEFAULT now())
- updated_at: TIMESTAMP (DEFAULT now())
```
- **Security:** `sin_encrypted` and `dob_encrypted` use `encrypt_pii()` from `common.security`

#### **Module 6: properties**
```python
Table: properties
- id: UUID (PK)
- application_id: UUID (FK → applications.id, UNIQUE, INDEX)
- address: TEXT (NOT NULL)
- city: VARCHAR(100) (NOT NULL)
- province: VARCHAR(2) (CHECK IN ('AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT'))
- postal_code: VARCHAR(7)
- property_type: VARCHAR(50) (CHECK IN ('single_family', 'condo', 'townhouse', 'multi_unit'))
- purchase_price: DECIMAL(12,2) (NOT NULL)
- created_at: TIMESTAMP (DEFAULT now())
- updated_at: TIMESTAMP (DEFAULT now())
```

#### **Module 7: documents**
```python
Table: documents
- id: UUID (PK)
- application_id: UUID (FK → applications.id, INDEX)
- document_type: VARCHAR(50) (CHECK IN ('t4', 'paystub', 'bank_statement', 'id_verification', 'property_appraisal'))
- file_path: VARCHAR(500) (NOT NULL)  # S3 path or local storage
- file_hash: VARCHAR(64) (NOT NULL)  # SHA256 for integrity
- uploaded_by: UUID (FK → users.id)
- fintrac_flag: BOOLEAN (GENERATED ALWAYS AS (document_type = 'bank_statement') STORED)  # >$10K
- created_at: TIMESTAMP (DEFAULT now(), INDEX)
- updated_at: TIMESTAMP (DEFAULT now())
```
- **Indexes:** Composite `(application_id, document_type)`

#### **Module 8: underwriting_results**
```python
Table: underwriting_results
- id: UUID (PK)
- application_id: UUID (FK → applications.id, UNIQUE, INDEX)
- gds_ratio: DECIMAL(5,2) (NOT NULL)  # OSFI: ≤39%
- tds_ratio: DECIMAL(5,2) (NOT NULL)  # OSFI: ≤44%
- qualifying_rate: DECIMAL(5,4) (NOT NULL)  # OSFI: max(rate+2%, 5.25%)
- stress_test_passed: BOOLEAN (NOT NULL)
- insurance_required: BOOLEAN (NOT NULL)  # CMHC: LTV > 80%
- insurance_premium: DECIMAL(12,2) (DEFAULT 0.00)
- decision: VARCHAR(30) (CHECK IN ('approved', 'declined', 'conditional'))
- reason: JSONB  # Auditable calculation breakdown
- created_at: TIMESTAMP (DEFAULT now())
- updated_at: TIMESTAMP (DEFAULT now())
```
- **Audit:** `reason` field must contain `{gds_calculation, tds_calculation, stress_test_rate}` for OSFI compliance

#### **Module 9: income_verification**
```python
Table: income_verification
- id: UUID (PK)
- application_id: UUID (FK → applications.id, UNIQUE, INDEX)
- gross_annual_income: DECIMAL(10,2) (NOT NULL)
- income_source: VARCHAR(50) (CHECK IN ('employment', 'self_employed', 'rental', 'investment'))
- verification_status: VARCHAR(20) (CHECK IN ('pending', 'verified', 'failed'))
- verified_at: TIMESTAMP | None
- created_at: TIMESTAMP (DEFAULT now())
- updated_at: TIMESTAMP (DEFAULT now())
```

#### **Module 10: credit_bureau**
```python
Table: credit_bureau
- id: UUID (PK)
- application_id: UUID (FK → applications.id, UNIQUE, INDEX)
- credit_score: INTEGER (CHECK >= 300 AND <= 900)
- beacon_score: INTEGER | None
- report_date: DATE (NOT NULL)
- created_at: TIMESTAMP (DEFAULT now())
- updated_at: TIMESTAMP (DEFAULT now())
```

#### **Module 11: audit_logs**
```python
Table: audit_logs
- id: UUID (PK)
- action: VARCHAR(50) (NOT NULL, INDEX)  # e.g., 'application_submitted'
- table_name: VARCHAR(100) (NOT NULL, INDEX)
- record_id: UUID (NOT NULL, INDEX)
- user_id: UUID (FK → users.id, INDEX)
- timestamp: TIMESTAMP (DEFAULT now(), INDEX)
- ip_address: INET
- details: JSONB  # Immutable FINTRAC trail
```
- **Constraints:** `CHECK (timestamp >= '2019-01-01')` for 5-year retention
- **Policy:** No UPDATE/DELETE allowed (immutable)

#### **Module 12: insurance**
```python
Table: insurance
- id: UUID (PK)
- application_id: UUID (FK → applications.id, UNIQUE, INDEX)
- ltv_ratio: DECIMAL(5,2) (NOT NULL)
- premium_rate: DECIMAL(4,2) (NOT NULL)  # CMHC tiers: 2.80, 3.10, 4.00
- premium_amount: DECIMAL(12,2) (NOT NULL)
- insurer_name: VARCHAR(100) (DEFAULT 'CMHC')
- policy_number: VARCHAR(50) | None
- created_at: TIMESTAMP (DEFAULT now())
- updated_at: TIMESTAMP (DEFAULT now())
```

---

## 3. Business Logic

### 3.1 Seed Data Baseline Rates
**Lender Product Rates (as of 2024-Q1):**
```python
# 5-Year Fixed
RBC: 5.45%, TD: 5.50%, BMO: 5.40%, Scotiabank: 5.55%, CIBC: 5.48%

# 5-Year Variable
RBC: 6.15%, TD: 6.20%, BMO: 6.10%, Scotiabank: 6.25%, CIBC: 6.18%
```

### 3.2 Sample Application Scenarios

#### **Scenario A: Approved Application**
- **Application Number:** `APP-20240115-0001`
- **User:** client@mortgage-uw.local
- **Loan Amount:** $500,000.00
- **Property Value:** $650,000.00
- **LTV:** 76.92% (No insurance required)
- **Income:** $120,000/year
- **Credit Score:** 750
- **GDS:** 32.5% (PITH: $3,250 / Gross Monthly: $10,000)
- **TDS:** 38.2% (PITH + Debts: $3,820 / Gross Monthly: $10,000)
- **Qualifying Rate:** max(5.45% + 2%, 5.25%) = 7.45%
- **Decision:** `approved`

#### **Scenario B: Declined Application (High TDS)**
- **Application Number:** `APP-20240115-0002`
- **LTV:** 89.00% (Insurance required, premium 3.10%)
- **GDS:** 42.1% (FAIL - exceeds 39%)
- **TDS:** 48.5% (FAIL - exceeds 44%)
- **Decision:** `declined`
- **Reason:** `{"osfi_b20_violation": ["gds_exceeds_39", "tds_exceeds_44"]}`

#### **Scenario C: Conditional Approval**
- **Application Number:** `APP-20240115-0003`
- **LTV:** 92.00% (Insurance required, premium 4.00%)
- **GDS:** 36.8% (PASS)
- **TDS:** 43.2% (PASS)
- **Decision:** `conditional`
- **Conditions:** `["reduce_loan_amount_by_10000", "provide_additional_income_proof"]`

### 3.3 Stress Testing Seed Data
**High-Volume Test Set:**
- 1,000 applications with randomized:
  - Loan amounts: $100,000 - $1,500,000
  - Property values: $150,000 - $2,000,000
  - LTV distribution: 60% below 80%, 30% 80-95%, 10% >95%
  - Credit scores: 600-850
  - Income: $50,000 - $250,000
- **Purpose:** Performance testing of GDS/TDS calculations and CMHC premium lookups

---

## 4. Migrations

### 4.1 Migration File Naming Convention
```
alembic/versions/{timestamp}_{module_name}_init.py
Example: 2024_01_15_143200_users_init.py
```

### 4.2 Migration Rollback Testing Strategy

**Automated Rollback Verification:**
```python
# In each migration's downgrade()
def downgrade():
    # 1. Check for dependent data
    op.execute("SELECT COUNT(*) FROM dependent_table WHERE fk_id IS NOT NULL")
    # 2. Archive data before deletion
    op.execute("CREATE TABLE IF NOT EXISTS _backup_{table} AS SELECT * FROM {table}")
    # 3. Drop table
    op.drop_table('{table}')
    # 4. Log rollback
    op.execute("INSERT INTO migration_rollback_log (revision, timestamp) VALUES (...)")
```

**Test Case Requirements:**
- Each migration must have `test_{module}_migration_rollback.py`
- Use separate PostgreSQL test container
- Verify data integrity post-downgrade-upgrade cycle
- Check foreign key constraints are properly restored

### 4.3 Environment-Specific Seed Variations

**Dev Environment:**
- All 3 sample applications (approved, declined, conditional)
- 100 stress test applications
- Clear-text logging enabled for debugging

**Staging Environment:**
- Same as dev but with production-like data volumes
- 10,000 stress test applications
- Encrypted logging only

**Production Environment:**
- **NO AUTO-SEED** - manual execution only
- Only admin/broker/client users
- No sample applications
- `SEED_EXECUTION_TOKEN` requires 2FA approval

---

## 5. Security & Compliance

### 5.1 PIPEDA Data Handling
- **Encryption:** `encrypt_pii()` uses AES-256-GCM with environment-specific keys from `common.config.PII_ENCRYPTION_KEY`
- **Key Rotation:** Keys must be rotated annually; old keys retained for decryption
- **Hashing:** `sin_hash` = SHA256(sin + STATIC_PEPPER from config)
- **Log Sanitization:** All loggers must use `structlog` with `drop_pii=True` processor

### 5.2 FINTRAC Compliance
- **Trigger:** `applications.purpose = 'purchase'` AND `loan_amount > 10000.00`
- **Logging:** Automatic insert into `audit_logs` on application submission
- **Retention:** PostgreSQL policy prevents deletion from `audit_logs` before 5 years
- **Immutability:** `audit_logs` table has NO UPDATE/DELETE triggers

### 5.3 OSFI B-20 Implementation
- **Stress Test Formula:** `qualifying_rate = MAX(product.interest_rate + 2.0%, 5.25%)`
- **GDS Formula:** `(principal + interest + taxes + heat) / gross_monthly_income`
- **TDS Formula:** `(PITH + other_debts) / gross_monthly_income`
- **Audit:** `underwriting_results.reason` must contain:
  ```json
  {
    "gds_calculation": {"pith": 3250.00, "income": 10000.00, "ratio": 32.5},
    "tds_calculation": {"pith_plus_debts": 3820.00, "income": 10000.00, "ratio": 38.2},
    "stress_test_rate": 7.45,
    "osfi_limits": {"gds_max": 39.0, "tds_max": 44.0}
  }
  ```

### 5.4 CMHC Insurance Premium Tiers
```python
def calculate_premium(ltv: Decimal) -> tuple[bool, Decimal, Decimal]:
    if ltv <= 80.00:
        return False, Decimal('0.00'), Decimal('0.00')
    elif ltv <= 85.00:
        return True, Decimal('2.80'), loan_amount * Decimal('0.0280')
    elif ltv <= 90.00:
        return True, Decimal('3.10'), loan_amount * Decimal('0.0310')
    elif ltv <= 95.00:
        return True, Decimal('4.00'), loan_amount * Decimal('0.0400')
    else:
        raise ValueError("LTV exceeds CMHC maximum")
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Migration-Specific Exceptions

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger |
|-----------------|-------------|------------|-----------------|---------|
| `MigrationFailedError` | 500 | `MIGRATION_001` | "Migration {revision} failed: {detail}" | Alembic upgrade/downgrade exception |
| `SeedDataExistsError` | 409 | `SEED_001` | "Seed data for {environment} already exists" | Duplicate seed execution detection |
| `SeedValidationError` | 422 | `SEED_002` | "Seed data validation failed: {field}" | Pydantic validation of seed DTOs |
| `EncryptionKeyMissingError` | 500 | `SECURITY_001` | "PII encryption key not configured" | `PII_ENCRYPTION_KEY` is None |
| `RollbackVerificationError` | 500 | `MIGRATION_002` | "Rollback verification failed: {table}" | Data integrity check post-downgrade |

### 6.2 Seed Execution Flow & Error Handling

```python
# Pseudocode for seed CLI command
async def seed_environment(env: str, scenario: str):
    try:
        # 1. Check existing data
        if await has_existing_data() and not force:
            raise SeedDataExistsError(env)
        
        # 2. Validate encryption keys
        if not config.PII_ENCRYPTION_KEY:
            raise EncryptionKeyMissingError()
        
        # 3. Seed users (with hashed passwords)
        users = await seed_users()  # bcrypt(Admin@12345)
        
        # 4. Seed lenders & products
        lenders = await seed_lenders()
        products = await seed_products(lenders)
        
        # 5. Seed applications based on scenario
        apps = await seed_applications(scenario, users, products)
        
        # 6. Verify OSFI calculations
        for app in apps:
            if not verify_osfi_compliance(app):
                raise SeedValidationError(f"OSFI violation in {app.id}")
        
        # 7. Log FINTRAC seeding event
        await audit_log("seed_data_executed", "system", user_id=None)
        
    except Exception as e:
        # Rollback transaction
        await db.rollback()
        structlog.error("seed_failed", error=str(e), environment=env)
        raise
```

### 6.3 Structured Error Response Format
All errors return:
```json
{
  "detail": "Human-readable message",
  "error_code": "MODULE_###",
  "timestamp": "2024-01-15T14:32:00Z",
  "correlation_id": "req-12345",
  "environment": "dev|staging|prod"
}
```

---

## 7. Implementation Checklist

### Pre-Migration
- [ ] Run `uv run alembic init` with async template
- [ ] Configure `alembic.ini` with PostgreSQL async DSN from `common.config`
- [ ] Create `alembic/env.py` with `get_async_session()` integration
- [ ] Set up `PII_ENCRYPTION_KEY` in `.env` and `.env.example`

### Migration Creation
- [ ] Generate 12 migration files using `uv run alembic revision --autogenerate -m "{module}_init"`
- [ ] **NEVER modify existing migrations** - create new revisions for changes
- [ ] Add manual SQL for GENERATED columns (LTV, FINTRAC flags)
- [ ] Implement downgrade with data backup tables

### Seed Data Execution
- [ ] Create `scripts/seed_data.py` with CLI interface
- [ ] Implement `--dry-run` mode that validates without writing
- [ ] Add `--force` flag to override existing data check
- [ ] Use `bcrypt` for password hashing in seed data
- [ ] Log all seed operations to `audit_logs` table

### Testing
- [ ] Unit tests: `tests/unit/test_seed_validation.py`
- [ ] Integration tests: `tests/integration/test_migration_rollback.py`
- [ ] Performance tests: Seed 10K records, verify <30s execution
- [ ] Compliance tests: Verify no PII in logs, encryption works

### Security Scanning
- [ ] Run `uv run pip-audit` before committing migrations
- [ ] Scan seed script for hardcoded secrets (should use config)
- [ ] Verify `SEED_EXECUTION_TOKEN` is not committed to git

---

**WARNING:** This design plan addresses the 12 core database modules. The remaining 8 modules (e.g., payments, valuations, compliance_reports) will require separate migrations if they persist data. Always follow the **NEVER modify existing Alembic migrations** rule—create new revisions for any schema changes.