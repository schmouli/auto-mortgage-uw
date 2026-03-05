# Design: Testing Suite
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Testing Suite Design Plan

**File:** `docs/design/testing-suite.md`  
**Module:** testing_suite  
**Purpose:** Comprehensive testing strategy for Canadian Mortgage Underwriting System compliance, calculation accuracy, and access control enforcement

---

## 1. Endpoints

This module does not expose public API endpoints. Instead, it tests endpoints defined in other modules. Key endpoints under test coverage include:

### Underwriting Endpoints (Test Target)
- `POST /api/v1/applications` - Create mortgage application
  - **Test Request:** Pydantic schema validation, Decimal precision, required fields
  - **Test Response:** 201 with application_id, 422 for validation failures, 401/403 for auth
- `GET /api/v1/applications/{id}/ratios` - Retrieve GDS/TDS calculations
  - **Test Response:** 200 with ratio breakdown, stress test rate, audit log trace
- `POST /api/v1/applications/{id}/submit` - Submit for underwriting
  - **Test Response:** 200 with state transition, 409 if business rules violated

### FINTRAC Endpoints (Test Target)
- `POST /api/v1/transactions` - Record financial transaction
  - **Test Request:** Amount threshold detection (>10,000 CAD flagging)
  - **Test Response:** 201 with immutable audit fields, 400 for structuring patterns

### Authentication Endpoints (Test Target)
- `POST /api/v1/auth/token` - JWT generation
  - **Test Request:** Broker/client credentials
  - **Test Response:** 200 with access_token, refresh_token, expiry timestamps
- `POST /api/v1/auth/refresh` - Token refresh
  - **Test Response:** 200 with new token, 401 for expired refresh tokens
- `POST /api/v1/auth/logout` - Token revocation
  - **Test Response:** 204, verification of token blacklisting

### Document Endpoints (Test Target)
- `POST /api/v1/documents/upload` - File upload
  - **Test Request:** Various MIME types, size boundaries (5MB limit)
  - **Test Response:** 201 with document_id, 413 for oversized files, 415 for invalid MIME

**Error Responses to Verify:**
- `400`: FINTRAC structuring detection, OSFI limit violations
- `401`: Invalid/missing JWT, expired tokens
- `403`: Cross-broker/client access attempts
- `404`: Resource not found with proper error_code
- `409`: Business rule violations (GDS/TDS limits, CMHC ineligibility)
- `422`: Pydantic validation errors with field-level detail

---

## 2. Models & Database

### Test Fixture Models (Internal to Test Suite)

**`TestDataFactory` Pattern**
- **Purpose:** Generate valid/invalid test data without duplicating fixtures
- **Key Methods:**
  - `create_application(loan_amount: Decimal, property_value: Decimal, gross_income: Decimal) -> dict`
  - `create_broker_user() -> dict` (with mock credentials)
  - `create_client_user() -> dict` (with encrypted SIN/DOB)
  - `create_transaction(amount: Decimal, structured: bool = False) -> dict`

**`DatabaseSeeder` Helper**
- **Table:** `test_metadata` (temporary test tracking)
  - `test_run_id` (UUID, PK) - Unique test execution identifier
  - `created_at` (TIMESTAMP) - For test duration tracking
  - `cleanup_required` (BOOLEAN) - Flag for transactional rollback

### Database Isolation Strategy
- **Transaction-per-test:** Each unit test runs in nested transaction (SAVEPOINT) rolled back on completion
- **Test database:** Separate PostgreSQL instance (`mortgage_underwriting_test`) seeded with Alembic migrations
- **Connection pooling:** Use `get_async_session(override_url=test_db_url)` fixture
- **Data minimization:** Test SIN/DOB values use deterministic hashes (SHA256 of "TEST_SIN_{i}") never matching real PII patterns

### Encrypted Field Testing
- **Encryption verification:** Tests confirm `encrypt_pii()` produces 256-bit AES ciphertext with proper IV
- **Decryption verification:** Tests confirm round-trip encryption/decryption without data loss
- **Log scanning:** Automated check that no test logs contain plaintext SIN/DOB (regex pattern matching)

---

## 3. Business Logic

### Unit Test Algorithms

**GDS/TDS Calculation Verification**
```
Test Formula:
gds_ratio = (principal + interest + taxes + heat) / gross_monthly_income
tds_ratio = (pith + other_debt) / gross_monthly_income
stress_rate = max(contract_rate + 2%, Decimal('5.25'))

Assertion Rules:
- stress_rate must be ≥ 5.25% (floor validation)
- gds_ratio must be ≤ 39% (hard OSFI limit)
- tds_ratio must be ≤ 44% (hard OSFI limit)
- Decimal precision must be maintained to 4 decimal places
```

**CMHC Premium Tier Lookup Test Matrix**
| LTV Range | Expected Premium | Test loan_amount | Test property_value |
|-----------|------------------|------------------|---------------------|
| ≤80% | 0% | 400,000 | 500,000 |
| 80.01-85% | 2.80% | 425,000 | 500,000 |
| 85.01-90% | 3.10% | 450,000 | 500,000 |
| 90.01-95% | 4.00% | 475,000 | 500,000 |
| >95% | Ineligible | 485,000 | 500,000 |

**Property Price Cap Test**
- **CMHC limit:** Applications with property_value > $1,500,000 must return `insurance_required=False` regardless of LTV
- **Test data:** Edge cases at $1,499,999.99 (eligible) and $1,500,000.01 (ineligible)

### Integration Test Workflows

**Full Application Flow (`test_application_flow.py`)**
1. **Setup:** Broker creates client profile (encrypted SIN/DOB)
2. **Action:** Submit application with loan_amount, property_value, income
3. **Verify:** 
   - Ratios calculated with stress test
   - CMHC premium determined correctly
   - Application state transitions: `draft → submitted → underwriting → approved`
   - Audit trail created with `created_by` broker_id
   - FINTRAC flag set if transaction > $10,000

**Auth Flow (`test_auth_flow.py`)**
1. **Token lifecycle:** Generate → Verify → Refresh → Verify → Logout → Verify revocation
2. **Expiry test:** Mock time forward 15 minutes past expiry, verify 401
3. **Refresh token reuse:** Attempt double-use of refresh token, verify blacklisting

**Access Control Isolation Tests**
- **Broker A** cannot access **Client B**'s applications (403 expected)
- **Client A** cannot access **Broker B**'s other clients (403 expected)
- **Admin** can access all resources (200 expected)
- **Unauthenticated** requests return 401 for all protected endpoints

### FINTRAC Compliance Verification
- **Structuring detection:** Split $15,000 transaction into $7,500 + $7,500 within 24h, verify 400 error
- **Retention audit:** Query 5-year-old test records, verify immutability (no `updated_at` changes)
- **Threshold flagging:** Single $10,000.01 transaction must have `fintrac_reportable=True`

---

## 4. Migrations

### Test Database Setup
- **No new migrations** for test suite - uses existing Alembic migrations from modules
- **Test-specific schema:** `test_cleanup` table for tracking orphaned test data (if rollback fails)

```sql
-- Only created if test transaction rollback fails
CREATE TABLE test_cleanup (
    test_run_id UUID PRIMARY KEY,
    created_tables TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Data Migration Needs
- **None** - test data is ephemeral and seeded per-test-run

---

## 5. Security & Compliance

### OSFI B-20 Compliance Testing
- **Stress test floor:** Assert `qualifying_rate >= 5.25%` for all test cases
- **GDS/TDS ceiling:** Assert rejection when GDS > 39% or TDS > 44%
- **Audit logging:** Verify `structlog` JSON logs contain `correlation_id`, `calculation_breakdown`, `timestamp` for all ratio calculations

### FINTRAC Reporting Triggers
- **Test threshold:** $10,000 CAD (exact value: `Decimal('10000.00')`)
- **Structuring pattern:** Multiple transactions summing to >$10,000 within 24h must be flagged
- **Immutability test:** Attempt UPDATE on `transactions` table, verify database constraint violation

### PIPEDA Data Handling Rules
- **SIN encryption:** Test that plaintext SIN never appears in:
  - Database (check ciphertext pattern)
  - Logs (scan log files post-test)
  - Error messages (intentionally cause errors with SIN data, verify redaction)
- **DOB encryption:** Same as SIN
- **Lookup hashing:** Verify SIN lookup uses SHA256 hash, not plaintext
- **Data minimization:** Test that API responses exclude SIN/DOB fields entirely

### JWT Security Testing
- **Token tampering:** Modify payload signature, verify 401
- **Algorithm downgrade:** Attempt to use `none` algorithm, verify rejection
- **Expiry enforcement:** Token valid at `exp-1s`, invalid at `exp+1s`
- **Refresh token rotation:** Verify new refresh token issued on each use, old token blacklisted

### Access Control Matrix
| Role | Application Read | Application Write | Client Data | Broker Data |
|------|------------------|-------------------|-------------|-------------|
| Broker (owner) | 200 | 200 | 200 (own) | 200 (self) |
| Broker (other) | 403 | 403 | 403 | 403 |
| Client (owner) | 200 | 200 (limited) | 200 (own) | 403 |
| Client (other) | 403 | 403 | 403 | 403 |
| Admin | 200 | 200 | 200 | 200 |

---

## 6. Error Codes & HTTP Responses

### Expected Exception Testing

Tests must verify the following error patterns from other modules:

| Exception Class | HTTP Status | Error Code | Test Scenario |
|-----------------|-------------|------------|---------------|
| `UnderwritingRatioViolation` | 409 | UNDERWRITING_001 | GDS > 39% or TDS > 44% |
| `StressTestFloorViolation` | 400 | UNDERWRITING_002 | qualifying_rate < 5.25% |
| `FintracStructuringDetected` | 400 | FINTRAC_001 | Transaction splitting pattern |
| `FintracThresholdExceeded` | 201* | FINTRAC_002 | Transaction > $10,000 (flagged) |
| `ApplicationNotFoundError` | 404 | APPLICATION_001 | Invalid application_id |
| `DocumentSizeExceeded` | 413 | DOCUMENTS_001 | File > 5MB |
| `DocumentTypeInvalid` | 415 | DOCUMENTS_002 | MIME type not in whitelist |
| `AuthenticationExpired` | 401 | AUTH_001 | JWT expiry |
| `AuthorizationDenied` | 403 | AUTH_002 | Cross-broker/client access |
| `TokenRevoked` | 401 | AUTH_003 | Logout blacklisted token |

*201 returned but record flagged for FINTRAC reporting

### Custom Test Exceptions
```python
class TestDataError(Exception):
    """Raised when fixture data violates test invariants"""
    error_code = "TEST_001"

class CoverageThresholdError(Exception):
    """Raised when coverage < 80%"""
    error_code = "TEST_002"
```

---

## 7. Test Execution Strategy

### Fixture & Mocking Strategy
- **Factories:** `pytest_factoryboy` integration for SQLAlchemy models
- **Encryption mocking:** `unittest.mock.patch` on `encrypt_pii()` to avoid real AES overhead in unit tests
- **External services:** Mock credit bureau API, property valuation service with `aioresponses`
- **Time mocking:** `freezegun` for JWT expiry tests, rate limit tests
- **Database:** `pytest-asyncio` with async transaction fixtures

### Load Testing Requirements
- **Target:** 100 concurrent mortgage applications/minute
- **Tool:** `locust` with custom FastAPI client
- **Scenarios:**
  - Sustained ratio calculations (CPU-bound)
  - Document uploads (I/O-bound)
  - Mixed read/write workload (realistic broker pipeline)
- **Metrics:** p95 latency < 500ms, p99 < 1000ms, zero 5xx errors

### Test Data Cleanup & Isolation
- **Unit tests:** Automatic rollback via `SAVEPOINT`
- **Integration tests:** Truncate tables in `test_metadata.cleanup_required` list
- **E2E tests:** Dedicated test environment with nightly cleanup job
- **PII scrubbing:** Post-test scan of test DB/logs for accidental plaintext SIN/DOB

### CI/CD Pipeline Integration
```yaml
# .github/workflows/test.yml
- name: Run unit tests
  run: uv run pytest -m unit --cov-fail-under=80
- name: Run integration tests
  run: uv run pytest -m integration --cov-append
- name: Security audit
  run: uv run pip-audit && uv run bandit -r modules/
- name: Load test
  run: uv run locust -f tests/load/locustfile.py --headless -u 100 -r 10 --run-time=5m
- name: Coverage report
  run: uv run coverage xml && codecov upload
```

### Performance Benchmark Baselines
- **GDS/TDS calculation:** < 50ms per application (unit)
- **Full application workflow:** < 2s end-to-end (integration)
- **Token generation/validation:** < 10ms per operation
- **Document upload (1MB):** < 500ms including virus scan

### Accessibility (a11y) Testing
- **Tool:** `axe-core` via `pytest-axe` for any frontend components
- **Scope:** Admin dashboard (if applicable), client portal
- **Checks:** Color contrast, keyboard navigation, screen reader labels
- **Integration:** Run as separate test marker `@pytest.mark.a11y`

---

## 8. E2E Test Specifications

### E2E Test with curl Commands

**Test: Full Application Submission**
```bash
#!/bin/bash
# Setup: Get auth token
TOKEN=$(curl -s -X POST https://api.underwriting.local/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"test_broker","password":"test_pass"}' | jq -r .access_token)

# Step 1: Create client (encrypted SIN/DOB)
CLIENT_ID=$(curl -s -X POST https://api.underwriting.local/api/v1/clients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sin":"encrypted_test_sin","dob":"encrypted_test_dob","name":"Test Client"}' | jq -r .client_id)

# Step 2: Submit application
APP_ID=$(curl -s -X POST https://api.underwriting.local/api/v1/applications \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"client_id\":\"$CLIENT_ID\",
    \"loan_amount\":475000.00,
    \"property_value\":500000.00,
    \"gross_annual_income\":120000.00,
    \"contract_rate\":5.50
  }" | jq -r .application_id)

# Step 3: Verify ratios with stress test
curl -X GET https://api.underwriting.local/api/v1/applications/$APP_ID/ratios \
  -H "Authorization: Bearer $TOKEN" | jq '.stress_test_rate, .gds_ratio, .tds_ratio'

# Step 4: Verify CMHC premium
curl -X GET https://api.underwriting.local/api/v1/applications/$APP_ID/cmhc \
  -H "Authorization: Bearer $TOKEN" | jq '.insurance_required, .premium_amount'

# Cleanup: Revoke token
curl -X POST https://api.underwriting.local/api/v1/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

**Verification Points:**
- Stress rate = max(5.50 + 2, 5.25) = 7.50%
- GDS/TDS ≤ limits (39%/44%)
- CMHC premium = 4.00% (LTV = 95%)
- All responses exclude SIN/DOB plaintext
- Audit logs contain correlation_id

---

## 9. Coverage Enforcement

### Minimum 80% Coverage Breakdown
- **Unit tests:** 70% (individual functions)
- **Integration tests:** 20% (workflow paths)
- **E2E tests:** 10% (critical user journeys)

### Exclusions from Coverage
- `__init__.py` files
- Exception class definitions (tested indirectly)
- Alembic migration scripts
- `if __name__ == "__main__"` blocks

### Coverage Gates
- **CI failure:** If coverage < 80% or any critical path uncovered
- **Critical paths:** All OSFI B-20 calculations, FINTRAC flagging, encryption/decryption, auth checks

---

**WARNING:** This design assumes all modules follow the defined conventions (Decimal types, encrypt_pii() usage, structlog logging). If conventions are violated, tests may need adjustment.