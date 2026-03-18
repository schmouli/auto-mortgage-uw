# Database Migrations & Seed Data
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Database Migrations & Seed Data Design Plan

**Feature Slug:** `database-migrations-seed-data`  
**Document Location:** `docs/design/database-migrations-seed-data.md`  
**Version:** 1.0  
**Compliance Frameworks:** OSFI B-20, FINTRAC, CMHC, PIPEDA

---

## 1. Endpoints

This module **does not expose public HTTP endpoints**. Migrations and seeding are executed via Alembic CLI commands:

```bash
# Run pending migrations
uv run alembic upgrade head

# Rollback last migration
uv run alembic downgrade -1

# Seed development data (dev/test environments only)
uv run python -m modules.migrations.seed_data --env=dev

# Verify migration status
uv run alembic current
```

**Admin-Only Utility Endpoints (Optional - Dev/Test Only):**

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/v1/system/migrations/status` | Admin JWT | Returns current Alembic version and pending migrations |
| `POST` | `/api/v1/system/migrations/seed` | Admin JWT | Triggers idempotent seed data insertion (dev/test only) |
| `POST` | `/api/v1/system/migrations/rollback` | Admin JWT | Rolls back N migrations (highly restricted) |

**Response Schema for `GET /status`:**
```json
{
  "current_version": "20240115_001",
  "head_version": "20240115_012",
  "pending_count": 3,
  "migrations": [
    {
      "version": "20240115_010",
      "description": "create_underwriting_tables",
      "applied": true
    }
  ]
}
```

---

## 2. Models & Database

### Core Tables Created Across 12 Migrations

#### Migration 1: `users` Module
**Table:** `users`
| Column | Type | Constraints | Encryption |
|--------|------|-------------|------------|
| id | UUID | PK, default gen_random_uuid() | No |
| email | VARCHAR(255) | UNIQUE, NOT NULL | No |
| hashed_password | VARCHAR(255) | NOT NULL | No |
| role | VARCHAR(50) | CHECK IN ('admin', 'broker', 'client') | No |
| first_name | VARCHAR(100) | NOT NULL | No |
| last_name | VARCHAR(100) | NOT NULL | No |
| sin_encrypted | BYTEA | UNIQUE, NOT NULL | **AES-256** |
| sin_hash | VARCHAR(64) | UNIQUE, NOT NULL | SHA256 for lookups |
| dob_encrypted | BYTEA | NOT NULL | **AES-256** |
| phone | VARCHAR(20) | | No |
| is_active | BOOLEAN | DEFAULT true | No |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL | No |
| updated_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL | No |

**Indexes:** 
- `idx_users_sin_hash` on `sin_hash`
- `idx_users_email` on `email`
- `idx_users_role_active` on `role`, `is_active`

---

#### Migration 2: `lenders` Module
**Table:** `lenders`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| legal_name | VARCHAR(255) | UNIQUE, NOT NULL |
| short_name | VARCHAR(50) | NOT NULL |
| institution_code | VARCHAR(10) | UNIQUE (OSFI identifier) |
| address | JSONB | {street, city, province, postal_code} |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |
| updated_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |

---

#### Migration 3: `products` Module
**Table:** `mortgage_products`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| lender_id | UUID | FK → lenders.id, ON DELETE CASCADE |
| product_name | VARCHAR(255) | NOT NULL |
| product_type | VARCHAR(50) | CHECK IN ('fixed', 'variable') |
| term_years | INTEGER | NOT NULL |
| interest_rate | DECIMAL(5,4) | NOT NULL |
| qualifying_rate | DECIMAL(5,4) | NOT NULL (OSFI B-20: max(rate+2%, 5.25%)) |
| max_amortization | INTEGER | DEFAULT 25 |
| max_ltv | DECIMAL(5,2) | CHECK ≤ 95.00 |
| insurance_required | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |
| updated_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |

**Indexes:**
- `idx_products_lender_rate` on `lender_id`, `interest_rate`
- `idx_products_type_term` on `product_type`, `term_years`

---

#### Migration 4: `applications` Module
**Table:** `applications`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| application_number | VARCHAR(50) | UNIQUE, NOT NULL (format: APP-YYYY-NNNNN) |
| broker_id | UUID | FK → users.id |
| applicant_id | UUID | FK → users.id |
| product_id | UUID | FK → mortgage_products.id |
| status | VARCHAR(50) | CHECK IN ('draft', 'submitted', 'underwriting', 'approved', 'declined', 'conditional') |
| loan_amount | DECIMAL(12,2) | NOT NULL |
| property_value | DECIMAL(12,2) | NOT NULL |
| ltv | DECIMAL(5,2) | GENERATED ALWAYS AS (loan_amount / property_value) STORED |
| insurance_required | BOOLEAN | NOT NULL (CMHC rule: LTV > 80%) |
| insurance_premium | DECIMAL(12,2) | DEFAULT 0.00 |
| purpose | VARCHAR(50) | CHECK IN ('purchase', 'refinance', 'renewal') |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |
| updated_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |

**Indexes:**
- `idx_applications_broker_status` on `broker_id`, `status`
- `idx_applications_applicant` on `applicant_id`
- `idx_applications_ltv` on `ltv`

---

#### Migration 5: `applicants` Module
**Table:** `applicant_details`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| application_id | UUID | FK → applications.id, ON DELETE CASCADE |
| user_id | UUID | FK → users.id |
| employment_status | VARCHAR(50) | CHECK IN ('employed', 'self_employed', 'other') |
| gross_annual_income | DECIMAL(12,2) | NOT NULL |
| monthly_liabilities | DECIMAL(10,2) | NOT NULL |
| credit_score | INTEGER | CHECK ≥ 300 AND ≤ 900 |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |
| updated_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |

---

#### Migration 6: `properties` Module
**Table:** `properties`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| application_id | UUID | FK → applications.id, ON DELETE CASCADE |
| address_encrypted | BYTEA | NOT NULL (AES-256) |
| address_hash | VARCHAR(64) | NOT NULL (SHA256 for FINTRAC reporting) |
| property_type | VARCHAR(50) | CHECK IN ('single_family', 'condo', 'townhouse', 'multi_unit') |
| year_built | INTEGER | |
| property_value | DECIMAL(12,2) | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |
| updated_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |

---

#### Migration 7: `documents` Module
**Table:** `documents`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| application_id | UUID | FK → applications.id, ON DELETE CASCADE |
| document_type | VARCHAR(100) | NOT NULL (e.g., 'pay_stub', 'tax_return', 'property_appraisal') |
| filename | VARCHAR(255) | NOT NULL |
| s3_key | VARCHAR(500) | UNIQUE, NOT NULL |
| file_size_bytes | BIGINT | NOT NULL |
| uploaded_by | UUID | FK → users.id |
| fintrac_flagged | BOOLEAN | DEFAULT false (FINTRAC: >$10K transactions) |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |

**Index:** `idx_documents_application_type` on `application_id`, `document_type`

---

#### Migration 8: `underwriting` Module
**Table:** `underwriting_results`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| application_id | UUID | FK → applications.id, ON DELETE CASCADE |
| decision | VARCHAR(50) | CHECK IN ('approved', 'declined', 'conditional') |
| gds_ratio | DECIMAL(5,2) | NOT NULL (must be ≤ 39%) |
| tds_ratio | DECIMAL(5,2) | NOT NULL (must be ≤ 44%) |
| qualifying_rate_used | DECIMAL(5,4) | NOT NULL (OSFI B-20) |
| stress_test_passed | BOOLEAN | NOT NULL |
| decision_reasons | JSONB | Array of reason codes |
| calculated_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |
| created_by | UUID | FK → users.id |

**Index:** `idx_underwriting_application` on `application_id` (unique)

---

#### Migration 9: `audit_logs` Module
**Table:** `audit_logs` (FINTRAC compliance - immutable)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| table_name | VARCHAR(100) | NOT NULL |
| record_id | UUID | NOT NULL |
| action | VARCHAR(20) | CHECK IN ('INSERT', 'UPDATE', 'DELETE') |
| changed_data | JSONB | NOT NULL |
| created_by | UUID | FK → users.id |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |

**Index:** `idx_audit_logs_table_record` on `table_name`, `record_id`

---

#### Migration 10: `income_verification` Module
**Table:** `income_verification`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| applicant_id | UUID | FK → applicant_details.id |
| verification_method | VARCHAR(50) | CHECK IN ('letter_of_employment', 'noa', 'bank_statement') |
| verified_income | DECIMAL(12,2) | NOT NULL |
| verified_by | UUID | FK → users.id |
| verified_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |

---

#### Migration 11: `liabilities` Module
**Table:** `liabilities`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| applicant_id | UUID | FK → applicant_details.id |
| liability_type | VARCHAR(50) | CHECK IN ('credit_card', 'auto_loan', 'mortgage', 'other') |
| monthly_payment | DECIMAL(10,2) | NOT NULL |
| outstanding_balance | DECIMAL(12,2) | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |
| updated_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |

---

#### Migration 12: `cmhc_premiums` Module
**Table:** `cmhc_premium_tiers`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| ltv_min | DECIMAL(5,2) | NOT NULL |
| ltv_max | DECIMAL(5,2) | NOT NULL |
| premium_rate | DECIMAL(4,2) | NOT NULL (e.g., 2.80, 3.10, 4.00) |
| effective_date | DATE | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT now(), NOT NULL |

**Seed Data:** CMHC premium tiers pre-populated:
- 80.01-85.00: 2.80%
- 85.01-90.00: 3.10%
- 90.01-95.00: 4.00%

---

## 3. Business Logic

### Migration Execution Order
```python
# dependencies.py
migration_order = [
    "001_create_users",          # No dependencies
    "002_create_lenders",        # No dependencies
    "003_create_products",       # Depends on lenders
    "004_create_applications",   # Depends on users, products
    "005_create_applicants",     # Depends on applications, users
    "006_create_properties",     # Depends on applications
    "007_create_documents",      # Depends on applications, users
    "008_create_underwriting",   # Depends on applications, users
    "009_create_audit_logs",     # Depends on users
    "010_create_income_verification", # Depends on applicants, users
    "011_create_liabilities",    # Depends on applicants
    "012_create_cmhc_premiums",  # No dependencies
]
```

### Seed Data Idempotency Logic
```python
# seed_data.py
async def seed_users(session):
    """Idempotent user seeding using email as natural key"""
    for user_data in SEED_USERS:
        existing = await session.execute(
            select(User).where(User.email == user_data["email"])
        )
        if not existing.scalar():
            encrypted_sin = encrypt_pii(user_data["sin"])
            sin_hash = hash_value(user_data["sin"])
            user = User(
                email=user_data["email"],
                hashed_password=hash_password(user_data["password"]),
                role=user_data["role"],
                sin_encrypted=encrypted_sin,
                sin_hash=sin_hash,
                # ... other fields
            )
            session.add(user)
```

### CMHC Premium Calculation (CMHC Compliance)
```python
def calculate_insurance_premium(loan_amount: Decimal, ltv: Decimal) -> Decimal:
    """
    Lookup premium rate from cmhc_premium_tiers table
    No floating-point precision loss
    """
    tier = session.execute(
        select(CMHCPremiumTier).where(
            CMHCPremiumTier.ltv_min < ltv,
            CMHCPremiumTier.ltv_max >= ltv
        )
    ).scalar_one()
    return loan_amount * (tier.premium_rate / Decimal('100'))
```

### OSFI B-20 Stress Test Enforcement
```python
def get_qualifying_rate(contract_rate: Decimal) -> Decimal:
    """OSFI B-20: qualifying_rate = max(contract_rate + 2%, 5.25%)"""
    stress_test_rate = contract_rate + Decimal('2.00')
    floor_rate = Decimal('5.25')
    return max(stress_test_rate, floor_rate)
```

---

## 4. Migrations

### Alembic Configuration
**File:** `alembic.ini`
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
file_template = %%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s
truncate_slug_length = 40
```

**File:** `alembic/env.py`
```python
# Async migration support
def run_migrations_online():
    connectable = AsyncEngine(
        create_async_engine(
            config.get_main_option("sqlalchemy.url"),
            echo=True,
        )
    )
    # ... standard Alembic async setup
```

### Migration Files (12 Total)

| Version | Filename | Tables Created | Reversible |
|---------|----------|----------------|------------|
| 001 | `20240115_001_create_users.py` | users | Yes (cascade delete audit logs) |
| 002 | `20240115_002_create_lenders.py` | lenders | Yes |
| 003 | `20240115_003_create_products.py` | mortgage_products | Yes (checks lender FK) |
| 004 | `20240115_004_create_applications.py` | applications | Yes (complex FK cascade) |
| 005 | `20240115_005_create_applicants.py` | applicant_details | Yes |
| 006 | `20240115_006_create_properties.py` | properties | Yes |
| 007 | `20240115_007_create_documents.py` | documents | Yes |
| 008 | `20240115_008_create_underwriting.py` | underwriting_results | Yes |
| 009 | `20240115_009_create_audit_logs.py` | audit_logs | **No downgrade** (FINTRAC immutability) |
| 010 | `20240115_010_create_income_verification.py` | income_verification | Yes |
| 011 | `20240115_011_create_liabilities.py` | liabilities | Yes |
| 012 | `20240115_012_create_cmhc_premiums.py` | cmhc_premium_tiers | Yes (seed data re-inserted on upgrade) |

### Seed Data Baseline Values

**Lender Product Rates (as of 2024-01-15):**
```python
SEED_LENDER_PRODUCTS = [
    # RBC
    {"lender": "RBC", "name": "5-Year Fixed Closed", "type": "fixed", "rate": Decimal('5.24'), "term": 5},
    {"lender": "RBC", "name": "5-Year Variable", "type": "variable", "rate": Decimal('6.20'), "term": 5},
    # TD
    {"lender": "TD", "name": "5-Year Fixed Closed", "type": "fixed", "rate": Decimal('5.29'), "term": 5},
    {"lender": "TD", "name": "5-Year Variable", "type": "variable", "rate": Decimal('6.25'), "term": 5},
    # BMO
    {"lender": "BMO", "name": "5-Year Fixed Closed", "type": "fixed", "rate": Decimal('5.19'), "term": 5},
    {"lender": "BMO", "name": "5-Year Variable", "type": "variable", "rate": Decimal('6.15'), "term": 5},
    # Scotiabank
    {"lender": "Scotiabank", "name": "5-Year Fixed Closed", "type": "fixed", "rate": Decimal('5.34'), "term": 5},
    {"lender": "Scotiabank", "name": "5-Year Variable", "type": "variable", "rate": Decimal('6.30'), "term": 5},
    # CIBC
    {"lender": "CIBC", "name": "5-Year Fixed Closed", "type": "fixed", "rate": Decimal('5.22'), "term": 5},
    {"lender": "CIBC", "name": "5-Year Variable", "type": "variable", "rate": Decimal('6.18'), "term": 5},
]
```

**Sample Application Scenario (Approved):**
- **Application Number:** APP-2024-00001
- **Loan Amount:** $450,000.00
- **Property Value:** $600,000.00
- **LTV:** 75.00% (no insurance required)
- **Gross Income:** $120,000/year
- **Monthly Liabilities:** $850
- **GDS Ratio:** 32.1% (PITH: $3,212 / Monthly Income: $10,000)
- **TDS Ratio:** 40.6% (PITH + Liabilities: $4,062 / $10,000)
- **Decision:** Approved (stress test at 7.24%)

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Encryption at Rest:** All `*_encrypted` columns use AES-256-GCM via `common/security.py:encrypt_pii()`
- **Data Minimization:** Seed data only includes fields required for underwriting
- **Log Sanitization:** SIN, DOB, income values are **never** logged; use hashed values for debugging
- **Key Rotation:** Encryption keys managed via `common/config.py`; rotate annually

### FINTRAC Compliance
- **Audit Trail:** `audit_logs` table captures every INSERT/UPDATE/DELETE (5-year retention)
- **Immutable Records:** Downgrade of migration 009 is **prohibited** to maintain FINTRAC audit trail
- **Large Transaction Flag:** `documents.fintrac_flagged` auto-set to true if application loan_amount > $10,000
- **Property Address Hashing:** `properties.address_hash` used for FINTRAC reporting without exposing PII

### OSFI B-20 Compliance
- **Stress Test Field:** `mortgage_products.qualifying_rate` automatically calculated as `max(rate + 2%, 5.25%)`
- **Ratio Limits:** `underwriting_results` enforces CHECK constraints: `gds_ratio ≤ 39.00` and `tds_ratio ≤ 44.00`
- **Audit Logging:** All ratio calculations logged with correlation_id for OSFI examination

### CMHC Compliance
- **LTV Calculation:** `applications.ltv` is `GENERATED ALWAYS` to prevent manual manipulation
- **Premium Tier Lookup:** Foreign key to `cmhc_premium_tiers` ensures valid rates
- **Insurance Flag:** `applications.insurance_required` automatically set when LTV > 80%

### Access Control
- **Migration CLI:** Requires `DATABASE_ADMIN` credentials from environment variables (never hardcoded)
- **Seed Data Endpoint:** Restricted to `role='admin'` AND `environment != 'production'`
- **Rollback Protection:** Production rollback requires manual intervention and dual approval

---

## 6. Error Codes & HTTP Responses

### Migration-Specific Exceptions

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger |
|-----------------|-------------|------------|-----------------|---------|
| `MigrationError` | 500 | MIG_001 | "Migration {version} failed: {detail}" | Alembic upgrade/downgrade failure |
| `SeedDataError` | 422 | MIG_002 | "Seed data conflict: {resource}" | Duplicate unique key during seeding |
| `RollbackNotAllowedError` | 403 | MIG_003 | "Rollback prohibited: {reason}" | Attempting to downgrade migration 009 in prod |
| `EnvironmentProtectionError` | 403 | MIG_004 | "Operation not allowed in {environment}" | Running seed in production |
| `EncryptionKeyError` | 500 | MIG_005 | "PII encryption failed: {field}" | Missing or invalid AES key during seed |

### CLI Error Handling
```python
# alembic/seed_data.py
class MigrationError(Exception):
    """Base exception for migration failures"""
    error_code = "MIG_001"
    
class RollbackNotAllowedError(MigrationError):
    """Raised when attempting to rollback immutable FINTRAC audit logs"""
    error_code = "MIG_003"
    
    def __init__(self, migration_version: str):
        super().__init__(
            f"Rollback prohibited: Migration {migration_version} contains "
            "FINTRAC audit tables that must remain immutable for 5 years"
        )
```

### Testing Strategy for Rollback

**Unit Test:** `tests/unit/test_migrations.py`
```python
@pytest.mark.unit
async def test_migration_009_downgrade_blocked():
    """FINTRAC compliance: audit_logs table must never be dropped"""
    with pytest.raises(RollbackNotAllowedError):
        await downgrade_migration("009")

@pytest.mark.integration
async def test_migration_rollback_chain():
    """Test full downgrade chain except migration 009"""
    # Downgrade from 012 → 010 (skipping 009)
    await downgrade_migration("010")
    # Verify audit_logs still exists and has data
    count = await session.execute(select(func.count()).select_from(AuditLog))
    assert count.scalar() > 0
```

### Environment-Specific Seed Variations

```python
# config.py
class SeedConfig(BaseSettings):
    environment: str = "development"
    
    @property
    def seed_users(self):
        if self.environment == "production":
            return []  # No seed users in prod
        return SEED_USERS
    
    @property
    def seed_lenders(self):
        if self.environment == "testing":
            return SEED_LENDERS[:2]  # Only 2 lenders for test speed
        return SEED_LENDERS
```

---

## 7. Missing Details Resolution

### Seed Data Lender Product Rates Baseline
- **Source:** Bank of Canada posted rates + typical lender spreads
- **Fixed Rates:** 5.19% - 5.34% (based on Jan 2024 Big 5 rates)
- **Variable Rates:** Prime (7.20%) + 0% to 0.10% margin
- **Update Frequency:** Seed data script includes `effective_date` and should be re-run quarterly

### Sample Application Scenarios
- **Approved Scenario:** Included in seed data (APP-2024-00001)
- **Declined Scenario:** To be added as APP-2024-00002 (TDS = 47%, GDS = 42%)
- **Conditional Scenario:** To be added as APP-2024-00003 (requires additional 5% down payment)

### Test Data for Stress Testing
```python
# Separate stress_test_data.py (not run in production)
STRESS_TEST_SCENARIOS = [
    {"loan": Decimal('950000'), "value": Decimal('1000000'), "ltv": 95.0},  # Max LTV
    {"income": Decimal('50000'), "pith": Decimal('2500'), "gds": 50.0},  # Exceeds GDS
    {"liabilities": Decimal('5000'), "pith": Decimal('3000'), "tds": 60.0},  # Exceeds TDS
]
```

### Migration Rollback Testing Strategy
- **Pre-deploy:** Run `alembic upgrade head && alembic downgrade base` in CI
- **Post-deploy:** Keep last 3 migrations reversible; older migrations become immutable
- **Production:** Rollback requires database snapshot restore + manual audit log reconciliation

### Environment-Specific Seed Variations
- **Development:** Full seed data + 100 random applications for load testing
- **Staging:** Minimal seed (3 users, 2 lenders, 1 product each) + 5 applications
- **Production:** **NO SEED DATA** - Only migrations run; users created via registration flow

---

## 8. Implementation Checklist

- [ ] Initialize Alembic with asyncpg driver
- [ ] Create 12 migration files with full downgrade functions
- [ ] Implement `encrypt_pii()` and `hash_value()` in `common/security.py`
- [ ] Write idempotent seed data script with environment guards
- [ ] Add CHECK constraints for OSFI B-20 ratios
- [ ] Create composite indexes for common query patterns
- [ ] Write unit tests for each migration's downgrade logic
- [ ] Write integration test for full upgrade/downgrade cycle (excluding migration 009)
- [ ] Document encryption key rotation procedure
- [ ] Add `pip-audit` to CI pipeline before migration deployment

---

**WARNING:** Migration 009 (`audit_logs`) is **FINTRAC-compliant immutable**. Downgrade functions for this migration raise `RollbackNotAllowedError` in production environments to maintain 5-year audit retention requirements.