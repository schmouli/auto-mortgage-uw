# Testing Suite API

## POST /api/v1/testing-suite/run

Execute a specific test suite or all tests to verify system integrity and regulatory compliance.

**Request:**
```json
{
  "suite": "unit",
  "module": "underwriting",
  "verbose": true
}
```

**Response (202):**
```json
{
  "run_id": "uuid-v4",
  "status": "started",
  "message": "Test execution initiated",
  "suite": "unit",
  "module": "underwriting"
}
```

**Errors:**
- 400: Invalid test suite or module specified
- 401: Not authenticated
- 403: Insufficient permissions (Admin only)

---

## GET /api/v1/testing-suite/coverage

Retrieve the latest code coverage metrics to ensure the 80% minimum requirement is met.

**Request:**
Query Parameters: `module` (optional, e.g., `underwriting`)

**Response (200):**
```json
{
  "total_coverage": 87.5,
  "threshold": 80.0,
  "meets_threshold": true,
  "modules": [
    {
      "name": "underwriting",
      "coverage": 92.1,
      "missing_lines": 15
    },
    {
      "name": "fintrac",
      "coverage": 85.4,
      "missing_lines": 42
    }
  ]
}
```

**Errors:**
- 401: Not authenticated
- 403: Insufficient permissions

---

# Testing Suite Module Overview

## Description
The Testing Suite module provides the infrastructure and API endpoints to manage the quality assurance of the Canadian Mortgage Underwriting System. It ensures that all regulatory requirements (OSFI B-20, FINTRAC, CMHC) are validated through automated testing.

## Key Functions
- **Test Execution**: Triggers unit, integration, and end-to-end tests.
- **Coverage Reporting**: Monitors adherence to the 80% minimum code coverage policy.
- **Compliance Verification**: Specific suites for OSFI B-20 calculations and FINTRAC logic.

## Test Suites Structure

### Unit Tests
Located in `tests/unit/`, these tests validate isolated logic.

- **`test_underwriting.py`**
  - Validates GDS/TDS calculations.
  - Ensures Stress Test logic (qualifying rate = max(contract_rate + 2%, 5.25%)).
  - Verifies LTV calculations and CMHC insurance premium tiers.
- **`test_fintrac.py`**
  - Validates cash threshold detection (> $10,000).
  - Tests structuring detection logic.
  - Verifies 5-year retention enforcement (immutable records).
- **`test_auth.py`**
  - Token generation and validation.
  - Expiry and refresh logic.
- **`test_documents.py`**
  - File validation and virus scanning hooks.

### Integration Tests
Located in `tests/integration/`, these tests validate workflows across modules, ensuring database state and API interactions are correct.

### End-to-End (E2E) Tests
Validates full workflows using `curl` commands or automated browsers, simulating real user journeys from application submission to approval.

## Usage Examples

### Running Unit Tests Locally
```bash
# Run all unit tests
uv run pytest tests/unit/ -v

# Run specific regulatory suite
uv run pytest tests/unit/test_underwriting.py -k "stress_test"
```

### Checking Coverage
```bash
uv run pytest --cov=mortgage_underwriting --cov-report=html
```

### Access Control Verification
Tests ensure that endpoints respect role-based access control (RBAC). Admin-only endpoints (like running tests via API) reject standard user tokens.

---

# Configuration Notes

## Environment Variables

Add the following to `.env.example`:

```bash
# Testing Suite Configuration
COVERAGE_THRESHOLD=80
PYTEST_ARGS="-v --tb=short"
TEST_DB_URL="postgresql+asyncpg://test_user:test_pass@localhost:15432/test_mortgage_db"
```

## Dependencies
Ensure `pytest`, `pytest-asyncio`, `pytest-cov`, and `httpx` (for async client testing) are included in `pyproject.toml`.

---

# CHANGELOG.md

```markdown
## [2026-03-02]
### Added
- Testing Suite: Module for managing test execution and coverage reporting.
- Unit tests for OSFI B-20 compliance (GDS/TDS/Stress Test).
- Unit tests for FINTRAC compliance (Cash thresholds/Retention).
- Unit tests for Authentication flows (Token/Refresh).
- Unit tests for Document validation.
- Integration test structure for cross-module workflows.
- E2E test definitions using curl commands.
- Access control verification tests.

### Changed
- Updated CI/CD pipeline to enforce 80% coverage threshold before merge.
```