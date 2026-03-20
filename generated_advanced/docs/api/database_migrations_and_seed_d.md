# Database Migrations & Seed Data

## Overview

The Database Migrations & Seed Data module manages the schema evolution and initial data population for the Canadian Mortgage Underwriting System. It utilizes **Alembic** for database versioning and ensures that all database changes are reversible, auditable, and compliant with regulatory standards (OSFI, FINTRAC).

This module does not expose public REST API endpoints. Instead, it interacts with the system via the **Command Line Interface (CLI)**.

## Migration Strategy

- **Tool:** Alembic (Async SQLAlchemy 2.0+)
- **Granularity:** One migration file per logical module (total of 12 planned).
- **Reversibility:** All migrations MUST include a fully functional `downgrade()` method to support rollbacks.
- **Compliance:** Migrations involving financial tables must enforce `Decimal` types and include `created_at`/`updated_at` columns for FINTRAC audit trails.

## Seed Data Specification

The seed data script populates the database with baseline users and lending products required for development and integration testing.

### Users (Authentication & Identity)

| Role       | Email                        | Password      | Notes                                      |
| ---------- | ---------------------------- | ------------- | ------------------------------------------ |
| Admin      | `admin@mortgage-uw.local`    | `Admin@12345` | System administrator, full access         |
| Broker     | `broker@mortgage-uw.local`   | `Broker@12345` | Standard broker user                       |
| Client     | `client@mortgage-uw.local`   | `Client@12345` | Applicant for sample application           |

### Lenders (Big 5 Banks)

1.  **RBC** (Royal Bank of Canada)
2.  **TD** (Toronto Dominion Bank)
3.  **BMO** (Bank of Montreal)
4.  **Scotiabank** (Bank of Nova Scotia)
5.  **CIBC** (Canadian Imperial Bank of Commerce)

### Products

Each lender is seeded with two standard products:
1.  **5-Year Fixed:** Standard fixed-rate mortgage product.
2.  **5-Year Variable:** Standard variable-rate mortgage product.

### Sample Application

- A single sample mortgage application is created, linked to the `client` user and one of the seeded lenders/products.
- Includes associated document records and an Underwriting (UW) decision record.

## Usage Guide (CLI)

Since this module manages infrastructure, interactions occur through terminal commands.

### 1. Applying Migrations

To upgrade the database schema to the latest version:

```bash
uv run alembic upgrade head
```

To verify the current version:

```bash
uv run alembic current
```

### 2. Running Seed Data

To populate the database with the initial data set described above:

```bash
uv run python -m modules.database_migrations.seed_data
```

*Note: This script should be idempotent. Running it multiple times should not create duplicate users or lenders.*

### 3. Rolling Back Migrations

To revert the last migration:

```bash
uv run alembic downgrade -1
```

To revert all migrations (destructive):

```bash
uv run alembic downgrade base
```

## Configuration

This module relies on the standard database configuration defined in `common/config.py`.

### Environment Variables

Ensure the following are set in your `.env` file:

```bash
# Database Connection
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mortgage_uw
ASYNC_DB_POOL_SIZE=10
ASYNC_DB_MAX_OVERFLOW=20
```

## Error Handling

- **Migration Conflict:** If a migration fails due to a schema mismatch, do not modify the existing migration file. Create a new migration to resolve the discrepancy.
- **Seed Data Integrity:** The seed script will check for existing records (e.g., by email) before insertion to prevent unique constraint violations.

---

## CHANGELOG.md

```markdown
## [2026-03-02]
### Added
- Database Migrations & Seed Data: Initialized Alembic configuration for async PostgreSQL.
- Database Migrations & Seed Data: Implemented seed data script including 3 users (Admin, Broker, Client), 5 lenders, and 10 products.
- Database Migrations & Seed Data: Added sample mortgage application with documents and UW decision.
- Database Migrations & Seed Data: Enforced reversible migration strategy.

### Changed
- N/A

### Fixed
- N/A
```

## .env.example

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mortgage_uw_dev
ASYNC_DB_POOL_SIZE=10
ASYNC_DB_MAX_OVERFLOW=20

# Security
# SECRET_KEY used for encrypting PII (SIN/DOB)
SECRET_KEY=change_this_to_a_secure_random_string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```