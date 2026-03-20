# Documentation for Module: Testing Suite

## 1. API Documentation

**Note:** The Testing Suite module does not expose FastAPI routes. The "interface" for this module is the Command Line Interface (CLI) via `pytest`. The documentation below describes the standard commands to execute the test suites.

**File:** `docs/api/Testing Suite.md`

```markdown
# Testing Suite API

The Testing Suite provides the interface for verifying system integrity, regulatory compliance (OSFI, FINTRAC, CMHC), and business logic correctness. Access is granted via the CLI using `uv run pytest`.

## Run All Tests

Execute the complete test suite including unit, integration, and end-to-end tests.

**Request (CLI):**
```bash
uv run pytest
```

**Response (Console):**
```
========================= test session starts ==========================
collected 150 items

tests/unit/test_underwriting.py .....                              [  3%]
tests/unit/test_fintrac.py ....                                 [  6%]
tests/integration/test_mortgage_integration.py ....              [  8%]

========================= 150 passed in 12.45s =========================
```

**Errors:**
- Exit Code 1: One or more tests failed.
- Exit Code 5: No tests collected.

---

## Run Unit Tests

Execute only unit tests (isolated logic, no database/network calls).

**Request (CLI):**
```bash
uv run pytest -m unit
```

**Response (Console):**
```
========================= test session starts ==========================
collected 80 items

tests/unit/test_underwriting.py .....                              [  6%]
tests/unit/test_fintrac.py ....                                   [ 11%]

========================= 80 passed in 4.20s =========================
```

---

## Run Integration Tests

Execute integration tests covering database interactions and API workflows.

**Request (CLI):**
```bash
uv run pytest -m integration
```

**Response (Console):**
```
========================= test session starts ==========================
collected 50 items

tests/integration/test_application_flow.py ....                    [  8%]

========================= 50 passed in 8.12s =========================
```

---

## Generate Coverage Report

Generate a code coverage report to verify the 80% minimum requirement.

**Request (CLI):**
```bash
uv run pytest --cov=mortgage_underwriting --cov-report=term-missing
```

**Response (Console):**
```
Name                                                 Stmts   Miss  Cover   Missing
----------------------------------------------------------------------------------
mortgage_underwriting/modules/underwriting/services.py   50      2    96%   23-24
mortgage_underwriting/common/security.py                 20      0   100%
----------------------------------------------------------------------------------
TOTAL                                                    200     30    85%
```

**Errors:**
- Fail: If coverage is below `COVERAGE_MIN_PERCENT` (default 80%).

---
```

## 2. Module README

**File:** `docs/modules/Testing Suite.md`

```markdown
# Testing Suite Module

## Overview
The Testing Suite ensures the reliability, security, and regulatory compliance of the Canadian Mortgage Underwriting System. It is designed to enforce strict adherence to OSFI B-20, FINTRAC, and PIPEDA standards through automated verification.

## Key Functions

### 1. Underwriting Logic Validation (`tests/unit/test_underwriting.py`)
Validates the core financial calculations to ensure accuracy and compliance.
- **GDS/TDS Calculations:** Verifies ratios are calculated correctly using `Decimal` precision.
- **Stress Testing:** Ensures the qualifying rate is always `max(contract_rate + 2%, 5.25%)`.
- **Limits:** Enforces hard limits (GDS ≤ 39%, TDS ≤ 44%) by asserting exceptions are raised or flags are set when exceeded.

### 2. FINTRAC Compliance (`tests/unit/test_fintrac.py`)
Verifies the immutable audit trail and cash handling logic.
- **Transaction Thresholds:** Ensures transactions > CAD $10,000 trigger the `large_cash_transaction` flag.
- **Audit Immutability:** Tests that `created_at` and `created_by` fields cannot be modified after record creation.
- **Retention:** Verifies that soft-delete mechanisms are in place (records are retained for 5 years).

### 3. Security & Auth (`tests/unit/test_auth.py`)
Tests the authentication and authorization mechanisms.
- **Token Lifecycle:** Validates generation, expiry, and refresh of JWT tokens.
- **Access Control:** Ensures protected endpoints return `401` or `403` without valid credentials.
- **PIPEDA Compliance:** Verifies that SIN and DOB are encrypted at rest and never logged.

### 4. Document Handling (`tests/unit/test_documents.py`)
Validates file upload, validation, and storage logic.
- **Type Validation:** Ensures only allowed MIME types are accepted.
- **Virus Scanning Simulation:** Mocks interaction with security scanners.

## Usage Examples

### Writing a Unit Test
Use `pytest-asyncio` for async service methods.

```python
import pytest
from decimal import Decimal
from mortgage_underwriting.modules.underwriting.services import UnderwritingService

@pytest.mark.unit
async def test_calculate_gds_exceeds_limit():
    service = UnderwritingService()
    income = Decimal("5000.00")
    piti = Decimal("2000.00") # 40% ratio
    
    with pytest.raises(ValueError) as exc_info:
        await service.calculate_gds(income, piti)
    
    assert "GDS exceeds maximum 39%" in str(exc_info.value)
```

### Running a Specific Test File
To debug a specific module:
```bash
uv run pytest tests/unit/test_underwriting.py -v
```

## Coverage Requirements
- **Minimum Coverage:** 80%
- **Critical Paths:** 100% coverage required for all financial calculation logic (GDS/TDS/LTV) and PII encryption functions.
```

## 3. Configuration Notes

**File:** `.env.example`

```ini
# ... existing config ...

# Testing Suite Configuration
# Database URL for running integration tests (usually a separate container or local instance)
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mortgage_test_db

# Minimum code coverage percentage required to pass CI/CD
COVERAGE_MIN_PERCENT=80

# Logging level for tests (DEBUG for verbose output during development)
TEST_LOG_LEVEL=INFO

# Mock external API keys for testing (e.g., credit bureaus)
MOCK_CREDIT_BUREAU_API_KEY=test_key_placeholder
```

## 4. Changelog Updates

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Testing Suite: Initial test infrastructure setup with pytest and pytest-asyncio.
- Unit tests: Added comprehensive coverage for Underwriting (OSFI B-20), FINTRAC compliance, and Auth logic.
- Integration tests: Added workflow tests for the mortgage application lifecycle.
- CI/CD: Enforced minimum 80% code coverage threshold.

### Changed
- Configuration: Added `TEST_DATABASE_URL` to `.env.example` to facilitate local integration testing.

### Fixed
- N/A
```