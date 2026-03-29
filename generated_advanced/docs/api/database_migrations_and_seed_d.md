Based on the project conventions and the specific design for the Database Migrations & Seed Data module, here are the generated documentation files.

### 1. API Documentation
**File:** `docs/api/database_migrations_and_seed_data.md`

```markdown
# Database Migrations & Seed Data API

> **Note:** This module manages database schema evolution and initial data population via **Alembic CLI** and **Management Scripts**. It does not expose public REST API endpoints for standard operations to ensure security and schema integrity.

## CLI Interface (Alembic)

### Upgrade Database

Applies pending migrations to the database schema.

**Command:**
```bash
uv run alembic upgrade head
```

**Response:**
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial_schema
...
```

**Errors:**
- `FAILED`: Target database is not initialized or connection failed.
- `Alembic.util.exc.CommandError`: Migration dependency conflict.

---

### Downgrade Database

Reverts the last applied migration.

**Command:**
```bash
uv run alembic downgrade -1
```

**Response:**
```text
INFO  [alembic.runtime.migration] Running downgrade 001_initial_schema ->
```

**Errors:**
- `FAILED`: Foreign key constraints prevent reversal (requires manual intervention).

---

### Generate New Migration

Creates a new revision script based on the current ORM models.

**Command:**
```bash
uv run alembic revision --autogenerate -m "description of changes"
```

**Response:**
```text
Generating /path/to/mortgage_underwriting/alembic/versions/12345_description_of_changes.py ... done
```

---

## Seed Data Script

### Populate Initial Data

Inserts the required base data (Admin, Broker, Client, Lenders, Products).

**Command:**
```bash
uv run python -m modules.database_migrations.seed
```

**Response (Console):**
```text
[INFO] Seeding Users...
[INFO] Created Admin: admin@mortgage-uw.local
[INFO] Created Broker: broker@mortgage-uw.local
[INFO] Created Client: client@mortgage-uw.local
[INFO] Seeding Lenders...
[INFO] Created 5 Lenders.
[INFO] Seeding Products...
[INFO] Created 10 Products.
[INFO] Seeding Sample Application...
[INFO] Sample application created successfully.
```

**Errors:**
- `IntegrityError`: Data already exists (Script should be idempotent or check for existence).
- `ValidationError`: Environment variables missing for default passwords.
```

---

### 2. Module README
**File:** `docs/modules/database_migrations_and_seed_data.md`

```markdown
# Database Migrations & Seed Data

## Overview

This module is responsible for the database lifecycle management using **Alembic**. It handles schema versioning, automatic migration generation from SQLAlchemy models, and the population of essential reference data (Seed Data) required for the Canadian Mortgage Underwriting System to operate.

## Key Functions

### Migration Strategy
- **Incremental Revisions:** One migration file per functional module/domain change.
- **Reversibility:** All migrations include a `downgrade()` method to ensure rollback capability.
- **Integrity:** Migrations are transactional by default (PostgreSQL DDL).

### Seed Data Logic
The seed script (`seed.py`) initializes the system with:
1.  **System Users:**
    *   **Admin:** Full system access (`admin@mortgage-uw.local`).
    *   **Broker:** Intermediary access (`broker@mortgage-uw.local`).
    *   **Client:** Borrower access (`client@mortgage-uw.local`).
2.  **Lenders:**
    *   The "Big 5" Canadian banks (RBC, TD, BMO, Scotiabank, CIBC).
3.  **Lending Products:**
    *   2 products per lender: "5-Year Fixed" and "5-Year Variable".
4.  **Sample Data:**
    *   1 sample mortgage application including associated documents and underwriting decision history for testing/demonstration purposes.

## Usage Examples

### Creating a New Module Migration
When developing a new module (e.g., `credit_check`), after defining the SQLAlchemy models:

```bash
# 1. Generate the migration
uv run alembic revision --autogenerate -m "add credit_check module"

# 2. Review the generated file in alembic/versions/
# Ensure the upgrade() and downgrade() logic is correct.

# 3. Apply the migration
uv run alembic upgrade head
```

### Resetting Database (Development Only)
To wipe the database and re-seed it from scratch:

```bash
# Drop all tables (use with caution)
uv run alembic downgrade base

# Recreate tables
uv run alembic upgrade head

# Run seed script
uv run python -m modules.database_migrations.seed
```

### Security & PII
- **Passwords:** Default passwords are injected via environment variables (see `.env.example`). The script hashes passwords using `common/security.py` before storage.
- **PIPEDA Compliance:** Seed data uses synthetic data. Real SINs/PII are never used in seed scripts.
```

---

### 3. Configuration Notes
**File:** `.env.example` (Append to existing)

```ini
# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mortgage_uw

# Seed Data Configuration
# Defaults are provided in code, but can be overridden here for security
SEED_ADMIN_PASSWORD=Admin@12345
SEED_BROKER_PASSWORD=Broker@12345
SEED_CLIENT_PASSWORD=Client@12345
```

---

### 4. Changelog Update
**File:** `CHANGELOG.md` (Append)

```markdown
## [2026-03-02]
### Added
- Database Migrations & Seed Data: Initial Alembic configuration and environment setup.
- Database Migrations & Seed Data: Seed script for system users (Admin, Broker, Client).
- Database Migrations & Seed Data: Seed data for Big 5 lenders and standard lending products.
- Database Migrations & Seed Data: Sample application generation for testing workflows.

### Changed
- N/A

### Fixed
- N/A
```