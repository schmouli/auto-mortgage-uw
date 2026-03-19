# Database Migrations & Seed Data

## Module Overview

This module manages the database schema evolution and initial data population for the Canadian Mortgage Underwriting System. It utilizes **Alembic** for migration management and ensures that all database changes are versioned, reversible, and compliant with regulatory audit requirements (FINTRAC).

### Key Features
- **Migration Strategy:** One migration file per business module (total 12 planned).
- **Reversibility:** All migrations include a `downgrade()` method to ensure rollback capability.
- **Seeding:** Automated population of base users (Admin, Broker, Client), Lenders (Big 5), Products, and a sample Application.
- **Compliance:** Seed data enforces `Decimal` usage for financial fields and hashes PII (passwords/SIN) using `common/security.py`.

---

## Configuration

### Environment Variables

Ensure the following variables are set in `.env` to allow migration tools to connect to the database.

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mortgage_uw
ASYNC_FOLLOW=true
```

---

## Operational API (CLI)

**Note:** This module interacts with the system via the Alembic CLI and Python scripts, not HTTP endpoints.

### 1. Initialize Alembic

Run this once to set up the migration environment.

```bash
uv run alembic init alembic
```

### 2. Generate a New Migration

Creates a new revision script with `upgrade()` and `downgrade()` methods.

**Command:**
```bash
uv run alembic revision --autogenerate -m "Description of module changes"
```

**Response (File Creation):**
```text
Generating /path/to/mortgage_underwriting/alembic/versions/001_initial_schema.py... done
```

### 3. Apply Migrations (Upgrade)

Upgrades the database schema to the latest version.

**Command:**
```bash
uv run alembic upgrade head
```

**Response (Console):**
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial_schema
```

### 4. Revert Migration (Downgrade)

Rolls back the database schema by one step.

**Command:**
```bash
uv run alembic downgrade -1
```

**Errors:**
- **OperationalError:** Database connection failed (check `DATABASE_URL`).
- **AlembicError:** Revision ID not found (ensure `alembic/versions` is up to date).

---

## Seed Data Script

Populates the database with initial operational data required for development and testing.

### Script Execution

**Command:**
```bash
uv run python -m scripts.seed_data
```

### Data Inventory

The script inserts the following entities:

1.  **Users**
    *   **Admin:** `admin@mortgage-uw.local` (Role: `admin`)
    *   **Broker:** `broker@mortgage-uw.local` (Role: `broker`)
    *   **Client:** `client@mortgage-uw.local` (Role: `client`)
    *   *Note: Passwords are hashed using `hash_password()` before insertion.*

2.  **Lenders (Big 5)**
    *   RBC
    *   TD
    *   BMO
    *   Scotiabank
    *   CIBC

3.  **Lender Products**
    *   2 Products per Lender:
        *   "5-Year Fixed" (Rate: Decimal)
        *   "5-Year Variable" (Rate: Decimal)

4.  **Sample Application**
    *   1 Application linked to the Client user.
    *   Includes associated Documents and Underwriting (UW) records.
    *   *Note: Financial values use `Decimal`; audit fields (`created_at`, `created_by`) are populated.*

---

## Usage Examples

### Creating a Module-Specific Migration

When developing a new module (e.g., `credit_check`), after defining models in `modules/credit_check/models.py`:

```bash
# 1. Generate the migration
uv run alembic revision --autogenerate -m "add credit_check module"

# 2. Review the generated file in alembic/versions/
# Ensure upgrade() creates tables and downgrade() drops them.

# 3. Apply to DB
uv run alembic upgrade head
```

### Resetting Database State

To drop all data and re-seed (Development only):

```bash
# Manually drop tables via SQL client or psql, then:
uv run alembic upgrade head
uv run python -m scripts.seed_data
```

---

## Appendix: CHANGELOG.md Entry

```markdown
## [2026-03-02]
### Added
- Database Migrations & Seed Data: Initialized Alembic configuration.
- Database Migrations & Seed Data: Implemented seed data script for Users, Lenders, and Products.
- Database Migrations & Seed Data: Added standard migration boilerplate with reversible downgrade functions.

### Changed
- Database Migrations & Seed Data: Enforced strict usage of Decimal for all financial seed data.
- Database Migrations & Seed Data: Integrated password hashing for seed user creation.
```

## Appendix: .env.example Entry

```bash
# Database Migrations & Seed Data Configuration
# Connection string used by Alembic and seed scripts
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mortgage_uw_dev

# Security
# Secret key used for hashing seed passwords (if different from app secret)
SECRET_KEY=change-me-in-production
```