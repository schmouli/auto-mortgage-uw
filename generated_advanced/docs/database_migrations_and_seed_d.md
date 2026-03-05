# Database Migrations & Seed Data
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Database Migrations & Seed Data Design Plan

**Feature Slug:** `database-migrations-seed`
**Design Doc:** `docs/design/database-migrations-seed.md`

---

## 1. Endpoints

### Admin Migration Control Endpoints
*Note: These endpoints are for operational use only (development/staging). In production, migrations run via CI/CD.*

| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `POST` | `/api/v1/admin/migrations/run` | Admin-only | `{"revision": "head"}` | `{"status": "success", "revision": "abc123"}` | `MIGRATION_001`, `MIGRATION_002` |
| `GET` | `/api/v1/admin/migrations/status` | Admin-only | - | `{"current_rev": "abc123", "pending": ["def456"]}` | `MIGRATION_003` |
| `POST` | `/api/v1/admin/seed/baseline` | Admin-only | `{"environment": "dev"}` | `{"seeded": ["users", "lenders", "products"]}` | `SEED_001`, `SEED_002` |
| `POST` | `/api/v1/admin/seed/test-scenarios` | Admin-only | `{"scenario_count": 5}` | `{"created": 5, "scenarios": ["approved", "declined"]}` | `SEED_003` |

**Request/Response Schemas:**

```python
# schemas.py
class MigrationRunRequest(BaseModel):
    revision: str = Field(..., examples=["head", "abc123"])

class MigrationStatusResponse(BaseModel):
    current_rev: Optional[str]
    pending: List[str] = []

class SeedBaselineRequest(BaseModel):
    environment: Literal["dev", "staging", "prod"] = "dev"

class SeedTestScenarioRequest(BaseModel):
    scenario_count: int = Field(5, ge=1, le=100)
```

**Error Responses:**
- `422`: `{"detail": "Invalid revision format", "error_code": "MIGRATION_001"}`
- `409`: `{"detail": "Migration already in progress", "error_code": "MIGRATION_002"}`
- `500`: `{"detail": "Seed data insertion failed", "error_code": "SEED_001"}`

---

## 2. Models & Database

### Core Models Summary (12 migrations = 12 tables)

| Migration # | Table Name | Purpose | Encrypted Fields | Key Indexes |
|-------------|------------|---------|------------------|-------------|
| 1 | `users` | User accounts | - | `idx_users_email`, `idx_users_role` |
| 2 | `lenders` | Lender master data | - | `idx_lenders_name` |
| 3 | `products` | Mortgage products | - | `idx_products_lender_id`, `idx_products_type` |
| 4 | `applications` | Application header | - | `idx_apps_user_id`, `idx_apps_status` |
| 5 | `applicants` | Personal details | `sin`, `dob`, `phone` | `idx_apps_app_id`, `idx_apps_sin_hash` |
| 6 | `properties` | Property details | - | `idx_props_app_id`, `idx_props_address` |
| 7 | `income_verification` | Income docs/metadata | `bank_account` | `idx_inc_app_id`, `idx_inc_type` |
| 8 | `liability_verification` | Debts/liabilities | `account_number` | `idx_liab_app_id` |
| 9 | `documents` | Document storage refs | - | `idx_docs_app_id`, `idx_docs_type` |
| 10 | `underwriting_results` | UW decisions | - | `idx_uw_app_id`, `idx_uw_decision` |
| 11 | `conditions` | Approval conditions | - | `idx_cond_uw_id` |
| 12 | `audit_logs` | FINTRAC audit trail | `payload` (PII masked) | `idx_audit_entity`, `idx_audit_timestamp` |

### Detailed Model Specifications

#### `applicants` (PIPEDA Compliance)
```python
# modules/applicants/models.py
class Applicant(Base):
    __tablename__ = "applicants"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    application_id = Column(UUID, ForeignKey("applications.id"), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    sin_encrypted = Column(LargeBinary, nullable=False)  # AES-256 encrypted
    sin_hash = Column(String(64), nullable=False, index=True)  # SHA256 for lookups
    dob_encrypted = Column(LargeBinary, nullable=False)  # AES-256 encrypted
    phone_encrypted = Column(LargeBinary, nullable=True)
    email = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
```

#### `underwriting_results` (OSFI B-20 Audit)
```python
# modules/underwriting_results/models.py
class UnderwritingResult(Base):
    __tablename__ = "underwriting_results"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    application_id = Column(UUID, ForeignKey("applications.id"), nullable=False, index=True, unique=True)
    gds_ratio = Column(Numeric(5, 2), nullable=False)  # Decimal: e.g., 35.50
    tds_ratio = Column(Numeric(5, 2), nullable=False)
    qualifying_rate = Column(Numeric(5, 2), nullable=False)  # stress test rate
    ltv_ratio = Column(Numeric(5, 2), nullable=False)
    insurance_required = Column(Boolean, nullable=False)
    insurance_premium = Column(Numeric(12, 2), nullable=True)
    decision = Column(Enum("approved", "declined", "conditional"), nullable=False, index=True)
    decision_reason = Column(Text, nullable=True)  # Audit trail
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(String(100), nullable=False)  # FINTRAC: immutable audit
```

#### `audit_logs` (FINTRAC 5-year retention)
```python
# modules/audit_logs/models.py
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    entity_type = Column(String(50), nullable=False, index=True)  # e.g., "application"
    entity_id = Column(UUID, nullable=False, index=True)
    action = Column(String(50), nullable=False)  # "created", "updated", "viewed"
    actor = Column(String(100), nullable=False)  # Username or system
    payload = Column(JSONB, nullable=True)  # PII masked per PIPEDA
    ip_address = Column(INET, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    
    # FINTRAC: never updated, never deleted
```

---

## 3. Business Logic

### Migration Execution Logic
1. **Dependency Ordering**: Migrations run sequentially by timestamp. Foreign key constraints ensure referential integrity.
2. **Reversibility**: Every `upgrade()` has a corresponding `downgrade()` that drops tables/columns in reverse order.
3. **Idempotency**: Seed scripts check for existing records by unique keys (email, lender name) before insertion.
4. **Transaction Safety**: Each migration runs in a single transaction. Seed data commits in batches of 100 for performance.

### Seed Data Insertion Rules
```python
# Pseudo-code for seeding logic
def seed_baseline():
    # 1. Hash passwords with bcrypt (never plaintext)
    admin_pw = bcrypt.hash("Admin@12345")
    
    # 2. Insert users with created_at = now(), updated_at = now()
    # 3. Insert lenders (Big 5) with is_active=True
    # 4. Insert products with rates: fixed=5.25%, variable=5.75%
    # 5. Create sample application with:
    #    - LTV = 85% (insurance required per CMHC)
    #    - GDS = 38%, TDS = 43% (within OSFI limits)
    #    - Decision = "approved" with conditions
```

### Sample Application Scenario (Approved with Conditions)
- **Application**: $500,000 loan, $600,000 property (LTV=83.33%)
- **Applicants**: 2 borrowers, total income $120,000/year
- **Stress Test**: Qualifying rate = max(5.25% + 2%, 5.25%) = 7.25%
- **Ratios**: GDS=38%, TDS=42% (both ≤ limits)
- **Insurance**: Required (LTV >80%), premium = 2.80% × $500,000 = $14,000
- **Decision**: "conditional" with 2 conditions (employment letter, property appraisal)

---

## 4. Migrations

### Migration Files Structure
```
alembic/versions/
├── 001_create_users_table.py
├── 002_create_lenders_table.py
├── 003_create_products_table.py
├── 004_create_applications_table.py
├── 005_create_applicants_table.py
├── 006_create_properties_table.py
├── 007_create_income_verification_table.py
├── 008_create_liability_verification_table.py
├── 009_create_documents_table.py
├── 010_create_underwriting_results_table.py
├── 011_create_conditions_table.py
└── 012_create_audit_logs_table.py
```

### Migration 001: Users Table
```python
# alembic/versions/001_create_users_table.py
def upgrade():
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", String(255), nullable=False, unique=True),
        sa.Column("hashed_password", LargeBinary, nullable=False),
        sa.Column("role", Enum("admin", "broker", "client"), nullable=False),
        sa.Column("is_active", Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", DateTime, nullable=False, server_default=func.now()),
        sa.Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    )
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_role", "users", ["role"])

def downgrade():
    op.drop_index("idx_users_role")
    op.drop_index("idx_users_email")
    op.drop_table("users")
```

### Migration 010: Underwriting Results (OSFI B-20)
```python
# alembic/versions/010_create_underwriting_results_table.py
def upgrade():
    op.create_table(
        "underwriting_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("application_id", UUID, nullable=False, unique=True),
        sa.Column("gds_ratio", Numeric(5, 2), nullable=False),
        sa.Column("tds_ratio", Numeric(5, 2), nullable=False),
        sa.Column("qualifying_rate", Numeric(5, 2), nullable=False),
        sa.Column("ltv_ratio", Numeric(5, 2), nullable=False),
        sa.Column("insurance_required", Boolean, nullable=False),
        sa.Column("insurance_premium", Numeric(12, 2), nullable=True),
        sa.Column("decision", Enum("approved", "declined", "conditional"), nullable=False),
        sa.Column("decision_reason", Text, nullable=True),
        sa.Column("created_at", DateTime, nullable=False, server_default=func.now()),
        sa.Column("created_by", String(100), nullable=False),
    )
    op.create_foreign_key("fk_uw_app", "underwriting_results", "applications", ["application_id"], ["id"])
    op.create_index("idx_uw_app_id", "underwriting_results", ["application_id"])
    op.create_index("idx_uw_decision", "underwriting_results", ["decision"])

def downgrade():
    op.drop_index("idx_uw_decision")
    op.drop_index("idx_uw_app_id")
    op.drop_constraint("fk_uw_app", "underwriting_results")
    op.drop_table("underwriting_results")
```

### Seed Data Baseline Rates
| Lender | Product Type | Rate | Term | Amortization |
|--------|--------------|------|------|--------------|
| RBC | 5-year fixed | 5.25% | 5 years | 25 years |
| RBC | 5-year variable | 5.75% | 5 years | 25 years |
| TD | 5-year fixed | 5.30% | 5 years | 25 years |
| TD | 5-year variable | 5.80% | 5 years | 25 years |
| ... | ... | ... | ... | ... |

---

## 5. Security & Compliance

### FINTRAC Requirements
- **Immutable Audit**: All seed data inserts log to `audit_logs` with `action="seeded"` and `actor="system"`.
- **$10K+ Transactions**: Sample application flagged as `is_large_transaction=True` if loan_amount ≥ $10,000 (default for all mortgages).
- **5-year Retention**: `audit_logs` table has `PARTITION BY RANGE (created_at)` for automatic archival.

### PIPEDA Requirements
- **Encryption**: `sin_encrypted`, `dob_encrypted`, `phone_encrypted`, `bank_account_encrypted` use AES-256-GCM via `common/security.encrypt_pii()`.
- **Hashing**: `sin_hash` used for duplicate detection queries; never log plaintext SIN.
- **Data Minimization**: Seed data includes only fields required for underwriting (no extraneous PII).

### OSFI B-20 Requirements
- **Stress Test**: Seed UW result includes `qualifying_rate` calculated per OSFI formula.
- **Ratio Limits**: Sample application demonstrates GDS=38% (≤39%) and TDS=42% (≤44%).
- **Auditability**: `underwriting_results.decision_reason` contains calculation breakdown JSON.

### Authentication & Authorization
- Admin endpoints require `role="admin"` JWT token with `scope=migration:execute`.
- Rate limiting: 1 migration request per 30 seconds to prevent DB overload.
- All seed operations are idempotent and can be rerun safely.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger |
|-----------------|-------------|------------|-----------------|---------|
| `MigrationInProgressError` | 409 | `MIGRATION_001` | "Migration {rev} already running" | Concurrent migration attempt |
| `MigrationRevisionError` | 422 | `MIGRATION_002` | "Invalid revision: {rev}" | Alembic can't find revision |
| `MigrationStatusError` | 500 | `MIGRATION_003` | "Failed to get migration status" | DB connection lost |
| `SeedDataConflictError` | 409 | `SEED_001` | "Seed data exists: {entity}" | Duplicate user/lender detected |
| `SeedDataValidationError` | 422 | `SEED_002` | "Seed validation failed: {field}" | PII encryption failed |
| `SeedDataInsertionError` | 500 | `SEED_003` | "Failed to seed {entity}: {detail}" | DB constraint violation |

### Error Response Format
```json
{
  "detail": "Seed data exists: lender 'RBC' already present",
  "error_code": "SEED_001",
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "abc-123-def-456"
}
```

**Note**: No PII or financial data appears in error messages or logs.

---

## Missing Details Resolution

### Seed Data Lender Product Rates Baseline
- **Fixed Rate**: 5.25% (OSFI minimum qualifying rate)
- **Variable Rate**: 5.75% (prime + 0.5%)
- **Rate Source**: `common/config.py` setting `BASELINE_SEED_RATES={"fixed": "5.25", "variable": "5.75"}`

### Sample Application Scenarios
- **Approved**: LTV 75%, GDS 35%, TDS 40%, no insurance
- **Declined**: LTV 95%, GDS 45%, TDS 50% (exceeds OSFI limits)
- **Conditional**: LTV 85%, GDS 38%, TDS 42%, requires insurance + employment letter

### Test Data for Stress Testing
- **High Volume**: 1000 applications with random LTV ratios (70%-95%)
- **Boundary Testing**: Applications at exactly GDS=39%, TDS=44%
- **Encryption Load**: 500 applicants with encrypted SIN/DOB to test performance

### Migration Rollback Testing Strategy
1. **Unit Test**: Each migration's `downgrade()` drops exactly what `upgrade()` creates
2. **Integration Test**: Run `upgrade()` → verify schema → run `downgrade()` → verify clean state
3. **Staging Gate**: Automated rollback test required before production deploy

### Environment-Specific Seed Variations
```python
# common/config.py
class SeedConfig(BaseSettings):
    seed_admin_email: str = "admin@mortgage-uw.local"
    seed_admin_password: str = "Admin@12345"
    seed_lender_count: int = Field(default=5, env="SEED_LENDER_COUNT")
    seed_test_data: bool = Field(default=False, env="SEED_TEST_DATA")
```
- **Production**: Zero seed data; manual admin creation only
- **Staging**: 5 lenders, 10 test applications
- **Development**: Full baseline + test scenarios

---

**Next Steps**: Implement migration scripts and seed functions following this plan. Ensure all team members run `uv run alembic upgrade head` after pulling changes.