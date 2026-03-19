# docs/api/testing_suite.md

# Testing Suite API

**Note:** The Testing Suite is an internal infrastructure component and does not expose public REST API endpoints for end-users. It is executed via the Command Line Interface (CLI) using `pytest`.

## CLI Interface

### Run All Tests

Execute the full test suite including unit, integration, and E2E tests.

```bash
uv run pytest
```

### Run Unit Tests Only

Execute tests marked with the `unit` marker. This isolates logic testing without database dependencies.

```bash
uv run pytest -m unit
```

**Response:** Console output with pass/fail status and coverage report.

### Run Integration Tests

Execute tests marked with the `integration` marker. This validates workflows against the test database.

```bash
uv run pytest -m integration
```

### Run Specific Regulatory Tests

Target specific compliance modules (OSFI B-20, FINTRAC).

```bash
# Run Underwriting calculation tests
uv run pytest tests/unit/test_underwriting.py

# Run FINTRAC compliance tests
uv run pytest tests/unit/test_fintrac.py
```

### Generate Coverage Report

Generate an HTML report to verify the 80% coverage requirement.

```bash
uv run pytest --cov=mortgage_underwriting --cov-report=html
```

**Response:** Creates an `htmlcov/index.html` file detailing line-by-line coverage.

---

# docs/testing_suite.md

# Testing Suite Module

## Overview

The Testing Suite ensures the reliability, security, and regulatory compliance of the Canadian Mortgage Underwriting System. It enforces a strict **80% minimum code coverage** requirement and validates business logic against OSFI B-20, FINTRAC, and CMHC standards.

The suite is divided into three categories:
1.  **Unit Tests:** Isolated logic tests for services and models.
2.  **Integration Tests:** Database and workflow validation.
3.  **End-to-End (E2E) Tests:** Full API lifecycle verification using `curl`.

## Test Suites

### 1. Underwriting Tests (`tests/unit/test_underwriting.py`)
Validates the core financial logic mandated by OSFI B-20.
- **GDS/TDS Calculations:** Ensures ratios are calculated correctly using `Decimal`.
- **Stress Testing:** Verifies the qualifying rate logic (`max(contract_rate + 2%, 5.25%)`).
- **Limits:** Enforces hard limits (GDS ≤ 39%, TDS ≤ 44%).

### 2. FINTRAC Compliance (`tests/unit/test_fintrac.py`)
Ensures the system meets anti-money laundering (AML) obligations.
- **Cash Thresholds:** Validates flags for transactions > CAD $10,000.
- **Retention:** Checks that immutable audit trails (`created_at`, `created_by`) are preserved.
- **Structuring Detection:** (Future) Tests for detecting split transactions.

### 3. Authentication Tests (`tests/unit/test_auth.py`)
Security validation for access control.
- **Token Lifecycle:** Generation, expiration, and refresh logic.
- **Logout:** Verifies token invalidation.
- **Permissions:** Ensures endpoints are protected by role-based access control (RBAC).

### 4. Document Tests (`tests/unit/test_documents.py`)
Validates file handling and PII protection.
- **Encryption:** Ensures SIN and DOB are encrypted at rest.
- **Validation:** Checks file type and size restrictions.

## Usage Examples

### Running a specific test case
```bash
uv run pytest tests/unit/test_underwriting.py::test_calculate_gds_stress_test
```

### Running with verbose output
```bash
uv run pytest -vv -s
```

### E2E Workflow Test
The E2E suite uses shell scripts to verify the live API.
```bash
# Example: Simulate creating a borrower
curl -X POST "http://localhost:8000/api/v1/borrowers" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "first_name": "Jane", "last_name": "Doe", "sin": "046454286" }'
```

## Configuration Notes

To run the testing suite, the following environment variables must be configured in `.env`:

```bash
# Testing Configuration
ENVIRONMENT=test
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/mortgage_test
# Secrets for testing auth flows
TEST_JWT_SECRET_KEY=test_secret_key_do_not_use_in_prod
```

---

# .env.example

```bash
# ... existing config ...

# Testing Suite Configuration
# -------------------------
# Database URL used exclusively for pytest isolation
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/mortgage_test

# Environment indicator
ENVIRONMENT=test

# Secret key for generating test tokens (must match JWT_SECRET_KEY logic)
TEST_JWT_SECRET_KEY=change_me_in_production
```