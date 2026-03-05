# Testing Suite Documentation

## Overview

The Testing Suite provides comprehensive validation for the Canadian Mortgage Underwriting System. It ensures regulatory compliance (OSFI B-20, FINTRAC, CMHC, PIPEDA), financial accuracy, and security integrity using `pytest`.

### Key Features
- **Coverage:** Enforces >80% code coverage.
- **Isolation:** Unit tests for all business logic modules.
- **Integration:** Full workflow testing with database transactions.
- **Security:** Automated verification of PII encryption and access control.
- **Markers:** `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`.

---

## API Interface

**Note:** The Testing Suite is an internal infrastructure module and does not expose public REST API endpoints. Interaction is performed via the CLI using `uv run pytest`.

### CLI Usage

**Run all tests:**
```bash
uv run pytest
```

**Run with coverage:**
```bash
uv run pytest --cov=mortgage_underwriting --cov-report=html
```

**Run specific markers:**
```bash
# Unit tests only
uv run pytest -m unit

# Integration tests only
uv run pytest -m integration
```

**Run specific module:**
```bash
uv run pytest tests/unit/test_underwriting.py
```

---

## Module Details

### 1. Underwriting Tests (`tests/unit/test_underwriting.py`)
Validates the core financial logic and OSFI B-20 compliance.

**Key Scenarios:**
- **GDS/TDS Calculation:** Verifies accuracy of ratio calculations and enforces hard limits (GDS ≤ 39%, TDS ≤ 44%).
- **Stress Testing:** Ensures qualifying rate uses `max(contract_rate + 2%, 5.25%)`.
- **LTV & CMHC:** Checks Loan-to-Value logic and premium tier application (80.01-85%, etc.).
- **Data Types:** Enforces `Decimal` usage for all monetary values; tests fail if `float` is detected.

### 2. FINTRAC Tests (`tests/unit/test_fintrac.py`)
Ensures compliance with anti-money laundering regulations.

**Key Scenarios:**
- **Cash Thresholds:** Validates flags for transactions > CAD $10,000.
- **Audit Trail:** Verifies `created_at` and `created_by` are immutable.
- **Retention:** Mocks time travel to ensure 5-year retention logic is enforced.
- **Structuring:** Tests detection of sequential transactions just below reporting limits.

### 3. Authentication Tests (`tests/unit/test_auth.py`)
Validates security and session management.

**Key Scenarios:**
- **Token Lifecycle:** Generation, expiration, and refresh of JWT tokens.
- **Logout:** Ensures tokens are invalidated (blacklisted) upon logout.
- **Permissions:** Verifies role-based access control (RBAC) for protected endpoints.

### 4. Documents Tests (`tests/unit/test_documents.py`)
Handles file validation and PII protection.

**Key Scenarios:**
- **File Type:** Restricts uploads to allowed formats (PDF, PNG, JPEG).
- **PII Redaction:** Ensures SIN and DOB are never logged or returned in API responses.
- **Encryption:** Verifies data is encrypted at rest (AES-256) before saving to the database.

---

## Configuration Notes

To run the testing suite, the following environment variables must be configured in `.env` or `.env.test`.

### Environment Variables

```bash
# Testing Configuration
ENVIRONMENT=test
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mortgage_test
SECRET_KEY=test_secret_key_do_not_use_in_prod
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# External Service Mocks
MOCK_CREDIT_CHECK_API=true
MOCK_DOCUMENT_STORAGE=true
```

### Setup Instructions
1. Create a local test database:
   ```sql
   CREATE DATABASE mortgage_test;
   ```
2. Install dependencies:
   ```bash
   uv sync --extra test
   ```
3. Run migrations against the test DB:
   ```bash
   uv run alembic upgrade head --sql
   ```
4. Execute tests:
   ```bash
   uv run pytest
   ```

---

## CHANGELOG

```markdown
## [2026-03-02]
### Added
- Testing Suite: Initial test infrastructure with pytest
- Unit tests for Underwriting (OSFI B-20 compliance, GDS/TDS/LTV)
- Unit tests for FINTRAC (Cash thresholds, audit trails)
- Unit tests for Auth (JWT lifecycle, RBAC)
- Unit tests for Documents (File validation, PII redaction)
- Integration test framework for workflow validation
- Coverage enforcement (minimum 80%)

### Changed
- N/A

### Fixed
- N/A
```