# Design: Testing Suite
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Testing Suite Design Plan

**Feature Slug:** `testing-suite`  
**Module Complexity:** reasoning  
**Document Version:** 1.0  
**Last Updated:** 2024-01-15

---

## 1. Endpoints

The Testing Suite module does not expose public API endpoints in production. Instead, it defines test execution interfaces and utility endpoints for non-production environments.

### Test Execution Interfaces

| Interface | Method | Path/Command | Purpose | Environment |
|-----------|--------|--------------|---------|-------------|
| Pytest Runner | CLI | `uv run pytest -m unit` | Execute unit test suite | Local/CI |
| Pytest Runner | CLI | `uv run pytest -m integration` | Execute integration tests | Local/CI |
| Pytest Runner | CLI | `uv run pytest -m compliance` | Execute regulatory compliance tests | Local/CI/Staging |
| Load Test Trigger | CLI | `uv run locust -f tests/load/locustfile.py` | Execute load tests | Staging Only |
| Test Data Seeder | POST | `/api/v1/test-only/seed-data` | Seed synthetic test data (disabled in prod) | Staging/QA Only |
| Test Data Cleaner | DELETE | `/api/v1/test-only/cleanup` | Truncate test databases (disabled in prod) | Staging/QA Only |

### Test Data Seeder Endpoint (Non-Production Only)

**POST `/api/v1/test-only/seed-data`**
- **Auth:** Admin-only API key (mTLS + secret header)
- **Request Body:**
  ```json
  {
    "scenario": "high_gds_rejection",
    "count": 10,
    "include_audit_trail": true,
    "encrypt_pii": true
  }
  ```
- **Response (201):**
  ```json
  {
    "scenario": "high_gds_rejection",
    "created_applications": 10,
    "test_data_id": "td_01hqk5...",
    "cleanup_token": "ct_01hqk5..."
  }
  ```
- **Error Responses:**
  - `403 Forbidden` - TEST_001: "Test endpoints disabled in production"
  - `422 Unprocessable Entity` - TEST_002: "Invalid scenario name"
  - `429 Too Many Requests` - TEST_003: "Test data seeding rate limit exceeded"

### Test Data Cleanup Endpoint (Non-Production Only)

**DELETE `/api/v1/test-only/cleanup`**
- **Auth:** Admin-only API key + cleanup_token from seeder
- **Request Body:**
  ```json
  {
    "cleanup_token": "ct_01hqk5...",
    "confirm": true
  }
  ```
- **Response (200):**
  ```json
  {
    "deleted_applications": 10,
    "deleted_audit_logs": 45,
    "deleted_documents": 23
  }
  ```

---

## 2. Models & Database

### Test Data Factory Models (Python Classes)

The Testing Suite uses **FactoryBoy** pattern for generating compliant test data.

#### `ApplicationFactory`
- **Module:** `tests/factories/application_factory.py`
- **Purpose:** Generate synthetic mortgage applications with valid financial data
- **Key Methods:**
  - `create_valid_application(ltv=75.0, gds=35.0, tds=42.0)`
  - `create_cmhc_insured_application(ltv=90.0)`
  - `create_high_risk_application(gds=45.0)` (should fail OSFI B-20)
- **Data Generation Rules:**
  - `property_value`: Decimal, range $200,000 - $1,600,000 (respects CMHC $1.5M cap)
  - `loan_amount`: Decimal, calculated from LTV
  - `gross_monthly_income`: Decimal, minimum $5,000
  - `monthly_property_tax`: Decimal, 0.5-1.5% of property_value annually
  - `monthly_heating`: Decimal, $100-400
  - `contract_rate`: Decimal, 3.5-7.5%
  - `qualifying_rate`: Decimal, `max(contract_rate + 2%, 5.25%)` (OSFI B-20 stress test)
  - `sin`: Encrypted bytes (AES-256) + SHA256 hash for lookup
  - `dob`: Encrypted bytes (AES-256)
  - `created_at`: Timestamp with timezone, immutable

#### `UserFactory`
- **Module:** `tests/factories/user_factory.py`
- **Purpose:** Generate broker, underwriter, and client users
- **Key Methods:**
  - `create_broker(organization_id="org_123")`
  - `create_underwriter(is_admin=False)`
  - `create_client()`
- **Data Generation Rules:**
  - `email`: Unique, valid format
  - `role`: Enum ["broker", "underwriter", "client", "admin"]
  - `organization_id`: Required for brokers (data isolation boundary)

#### `DocumentFactory`
- **Module:** `tests/factories/document_factory.py`
- **Purpose:** Generate test documents with various MIME types and sizes
- **Key Methods:**
  - `create_income_document(size_mb=2.5)`
  - `create_oversized_document(size_mb=15)` (should fail validation)
  - `create_invalid_mime_document()`
- **Data Generation Rules:**
  - `file_size_bytes`: Integer, respects system limits (max 10MB)
  - `mime_type`: Valid MIME types from whitelist
  - `checksum`: SHA256 of file content for integrity verification

### Test Database Configuration

**Test-Only Settings (`tests/conftest.py`):**
```python
# Use separate PostgreSQL instance or isolated database
TEST_DATABASE_URL = "postgresql+asyncpg://test_user:test_pass@localhost:5432/mortgage_test"

# Transaction isolation for each test
@pytest.fixture(scope="function")
async def db_session():
    """Create isolated transaction for each test, rollback after completion."""
    # Uses SQLAlchemy async session with nested transaction
```

**Test Data Retention Policy (FINTRAC Compliance):**
- All seeded test data must be tagged with `test_data_id` for traceability
- Test audit logs must be stored in separate schema `test_audit_logs`
- Cleanup must hard-delete test data within 24 hours (FINTRAC 5-year retention does not apply to synthetic test data)
- Production data must NEVER be used in tests (PIPEDA violation)

---

## 3. Business Logic

### GDS/TDS Calculation Verification Algorithm

**Test Function:** `verify_gds_tds_calculation(application_id: UUID)`

**Verification Steps:**
1. **Extract raw values** from application:
   - `PITH = principal + interest + property_tax + heating`
   - `gross_monthly_income`
   - `other_debt_payments`
   - `contract_rate`, `qualifying_rate`

2. **Calculate expected GDS:**
   ```python
   expected_gds = (PITH / gross_monthly_income) * 100
   expected_gds = round(expected_gds, 2)  # OSFI requires 2 decimal precision
   ```

3. **Calculate expected TDS:**
   ```python
   expected_tds = ((PITH + other_debt_payments) / gross_monthly_income) * 100
   expected_tds = round(expected_tds, 2)
   ```

4. **Verify stress test application:**
   ```python
   expected_qualifying_rate = max(contract_rate + Decimal('2.0'), Decimal('5.25'))
   assert qualifying_rate == expected_qualifying_rate
   ```

5. **Assert OSFI B-20 thresholds:**
   ```python
   assert gds <= Decimal('39.0'), f"GDS {gds}% exceeds 39% limit"
   assert tds <= Decimal('44.0'), f"TDS {tds}% exceeds 44% limit"
   ```

6. **Audit logging verification:**
   - Check that `calculation_breakdown` JSON field exists in audit log
   - Verify all intermediate values are logged (no PII)
   - Confirm `created_by` is set to system user for automated calculations

### FINTRAC Threshold Detection Verification

**Test Function:** `verify_fintrac_threshold_detection(transaction_id: UUID)`

**Verification Steps:**
1. **Check transaction amount:**
   ```python
   if transaction_amount > Decimal('10000.00'):
       assert transaction.is_large_cash_transaction == True
       assert transaction.transaction_type == "LCTR"  # Large Cash Transaction Report
   ```

2. **Verify audit trail immutability:**
   ```python
   original_created_at = transaction.created_at
   # Attempt to modify record (should fail or create new version)
   with pytest.raises(IntegrityError):
       transaction.transaction_amount = Decimal('5000.00')
   assert transaction.created_at == original_created_at
   ```

3. **Test structuring detection:**
   ```python
   # Create 3 transactions of $4,000 each within 24h by same client
   transactions = create_structured_transactions(client_id, amount=4000, count=3)
   assert flag_structuring_activity(transactions) == True
   ```

### CMHC Eligibility Verification

**Test Function:** `verify_cmhc_eligibility(property_value: Decimal, loan_amount: Decimal)`

**Verification Steps:**
1. **Calculate LTV:**
   ```python
   ltv = (loan_amount / property_value) * 100
   ltv = round(ltv, 2)
   ```

2. **Check CMHC property cap:**
   ```python
   assert property_value <= Decimal('1500000.00'), "Property exceeds CMHC $1.5M cap"
   ```

3. **Verify premium tier lookup:**
   ```python
   if Decimal('80.01') <= ltv <= Decimal('85.00'):
       expected_premium = Decimal('2.80')
   elif Decimal('85.01') <= ltv <= Decimal('90.00'):
       expected_premium = Decimal('3.10')
   elif Decimal('90.01') <= ltv <= Decimal('95.00'):
       expected_premium = Decimal('4.00')
   else:
       expected_premium = Decimal('0.00')
   
   assert insurance_premium_rate == expected_premium
   ```

4. **Test insurance requirement flag:**
   ```python
   if ltv > Decimal('80.00'):
       assert insurance_required == True
   else:
       assert insurance_required == False
   ```

### PIPEDA Encryption Verification

**Test Function:** `verify_pii_encryption(application_id: UUID)`

**Verification Steps:**
1. **Query raw database values:**
   ```python
   raw_sin = await db.execute("SELECT sin FROM applications WHERE id = :id", {"id": application_id})
   raw_dob = await db.execute("SELECT dob FROM applications WHERE id = :id", {"id": application_id})
   ```

2. **Verify encryption:**
   ```python
   assert raw_sin != "123-456-789"  # Must be encrypted bytes
   assert raw_dob != "1990-01-01"   # Must be encrypted bytes
   ```

3. **Verify hashing for lookups:**
   ```python
   sin_hash = sha256("123-456-789".encode()).hexdigest()
   assert application.sin_hash == sin_hash
   ```

4. **Verify no PII in logs:**
   ```python
   log_content = caplog.text
   assert "123-456-789" not in log_content
   assert "1990-01-01" not in log_content
   assert "50000.00" not in log_content  # Income
   ```

### Access Control Isolation Matrix

**Test Function:** `verify_broker_isolation(broker_id: UUID, other_broker_id: UUID)`

**Verification Steps:**
1. **Create applications for broker A:**
   ```python
   app_1 = create_application(broker_id=broker_a_id)
   app_2 = create_application(broker_id=broker_a_id)
   ```

2. **Attempt access by broker B:**
   ```python
   response = await client.get(f"/api/v1/applications/{app_1.id}", 
                             headers={"Authorization": f"Bearer {broker_b_token}"})
   assert response.status_code == 403
   assert response.json()["error_code"] == "AUTH_003"  # Access denied
   ```

3. **Verify data scope:**
   ```python
   response = await client.get("/api/v1/applications", 
                             headers={"Authorization": f"Bearer {broker_b_token}"})
   assert app_1.id not in [app["id"] for app in response.json()["items"]]
   ```

---

## 4. Migrations

### No Database Migrations Required

The Testing Suite module **does not require Alembic migrations** as it operates on existing application tables. However, it requires:

### Test Infrastructure Setup

**1. Test Database Schema Initialization**
```sql
-- Create isolated test schema
CREATE SCHEMA IF NOT EXISTS test_audit_logs;

-- Create test tracking table (for FINTRAC compliance)
CREATE TABLE test_data_registry (
    test_data_id UUID PRIMARY DEFAULT gen_random_uuid(),
    scenario VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cleanup_due TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
    created_by VARCHAR(255) NOT NULL
);

-- Index for cleanup jobs
CREATE INDEX idx_test_data_cleanup_due ON test_data_registry(cleanup_due);
```

**2. Test User Roles**
```sql
-- Create test database user with limited privileges
CREATE USER test_user WITH PASSWORD 'test_pass';
GRANT CONNECT ON DATABASE mortgage_test TO test_user;
GRANT USAGE ON SCHEMA public TO test_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO test_user;
GRANT SELECT, INSERT ON test_audit_logs.* TO test_user;
```

**3. CI/CD Test Database Seed**
```yaml
# .github/workflows/test.yml
- name: Setup Test Database
  run: |
    psql -h localhost -U postgres -c "CREATE DATABASE mortgage_test;"
    psql -h localhost -U postgres -d mortgage_test -f scripts/init_test_schema.sql
```

---

## 5. Security & Compliance

### OSFI B-20 Compliance Testing

**Test Coverage Requirements:**
- **Stress Test Floor Validation:** Must verify `qualifying_rate` never falls below 5.25%
- **GDS/TDS Ceiling Enforcement:** Must test rejection logic when GDS > 39% or TDS > 44%
- **Calculation Audit:** Must verify every ratio calculation is logged with breakdown
- **Edge Cases:**
  - Contract rate 3.5% → qualifying_rate must be 5.25% (floor)
  - Contract rate 4.5% → qualifying_rate must be 6.5% (contract + 2%)
  - GDS exactly 39.00% → must be approved (boundary test)
  - TDS exactly 44.00% → must be approved (boundary test)

**Critical Test Cases:**
```python
def test_osfi_stress_test_floor():
    """Verify 5.25% floor is always applied."""
    app = ApplicationFactory(contract_rate=Decimal('3.0'))
    assert app.qualifying_rate == Decimal('5.25')  # Floor, not 5.0%

def test_osfi_gds_rejection_boundary():
    """Verify GDS > 39% is rejected."""
    app = ApplicationFactory(gds=Decimal('39.01'))
    with pytest.raises(UnderwritingBusinessRuleError) as exc:
        UnderwritingService.evaluate(app)
    assert exc.value.error_code == "UNDERWRITING_003"
```

### FINTRAC Compliance Testing

**Test Coverage Requirements:**
- **Large Transaction Flagging:** Must detect transactions > CAD $10,000
- **Structuring Detection:** Must identify patterns of transactions just below threshold
- **Audit Trail Immutability:** Must verify records cannot be modified after creation
- **Retention Verification:** Must confirm 5-year retention policy is enforced
- **Transaction Type Flagging:** Must verify `LCTR` flag is set for large cash transactions

**Critical Test Cases:**
```python
def test_fintrac_large_transaction_flag():
    """Verify transactions > $10,000 are flagged."""
    tx = TransactionFactory(amount=Decimal('10000.01'))
    assert tx.is_large_cash_transaction == True
    assert tx.transaction_type == "LCTR"
    assert tx.created_at is not None
    assert tx.created_by is not None

def test_fintrac_structuring_detection():
    """Verify 3+ transactions < $10,000 within 24h are flagged."""
    client_id = uuid4()
    for _ in range(3):
        TransactionFactory(client_id=client_id, amount=Decimal('9500.00'))
    
    assert detect_structuring(client_id) == True
```

### CMHC Compliance Testing

**Test Coverage Requirements:**
- **LTV Calculation Precision:** Must use Decimal with no precision loss
- **Premium Tier Lookup:** Must verify correct premium rate for each LTV band
- **Property Cap Enforcement:** Must reject properties > $1.5M
- **Insurance Requirement Flag:** Must set `insurance_required=True` when LTV > 80%

**Critical Test Cases:**
```python
def test_cmhc_ltv_precision():
    """Verify LTV calculation uses Decimal with 2 decimal places."""
    app = ApplicationFactory(loan_amount=Decimal('450000.00'), 
                           property_value=Decimal('500000.00'))
    assert app.ltv == Decimal('90.00')  # Exact, no float rounding errors

def test_cmhc_property_cap_rejection():
    """Verify properties > $1.5M are ineligible for CMHC insurance."""
    app = ApplicationFactory(property_value=Decimal('1500000.01'), ltv=85.0)
    assert app.insurance_required == False  # Cap violation
```

### PIPEDA Compliance Testing

**Test Coverage Requirements:**
- **Encryption at Rest:** Must verify SIN and DOB are encrypted in database
- **Hash-Based Lookups:** Must verify SIN hash is used for queries, not plaintext
- **Data Minimization:** Must verify only required fields are collected
- **No PII in Logs:** Must scan logs for SIN, DOB, income, banking data
- **Secure Deletion:** Must verify encrypted data is properly purged

**Critical Test Cases:**
```python
def test_piped_sin_encryption():
    """Verify SIN is encrypted at rest."""
    sin = "123-456-789"
    app = ApplicationFactory(sin=sin)
    
    # Raw database query should return encrypted bytes
    raw_result = await db.execute("SELECT sin FROM applications WHERE id = :id", 
                                  {"id": app.id})
    assert raw_result != sin
    assert isinstance(raw_result, bytes)

def test_piped_no_pii_in_logs(caplog):
    """Verify PII never appears in logs."""
    app = ApplicationFactory(sin="123-456-789", income=Decimal('75000.00'))
    
    # Force log generation
    logger.info(f"Processing application {app.id}")
    
    assert "123-456-789" not in caplog.text
    assert "75000.00" not in caplog.text
    assert app.id in caplog.text  # UUID is safe to log
```

---

## 6. Error Codes & HTTP Responses

### Test Failure Categorization

The Testing Suite defines standardized error codes for test failures to enable automated reporting and alerting.

| Exception Class | HTTP Status | Error Code | Message Pattern | Test Type |
|-----------------|-------------|------------|-----------------|-----------|
| TestAssertionError | N/A | TEST_ASSERT_001 | "Expected {expected}, got {actual}" | All |
| ComplianceViolationError | N/A | COMPLY_001 | "OSFI B-20 violation: {detail}" | Compliance |
| EncryptionVerificationError | N/A | ENCRYPT_001 | "PII encryption failure: {field}" | Security |
| AuditTrailMissingError | N/A | AUDIT_001 | "Missing audit log for {action}" | Compliance |
| AccessControlBypassError | 403 (detected) | AUTH_003 | "Access control bypassed: {resource}" | Integration |
| PerformanceRegressionError | N/A | PERF_001 | "Response time {actual}ms > baseline {baseline}ms" | Performance |
| LoadTestFailureError | N/A | LOAD_001 | "Throughput {actual} < target {target} RPS" | Load |

### Test Reporting Schema

**Test Result Response:**
```json
{
  "test_run_id": "tr_01hqk5...",
  "timestamp": "2024-01-15T14:30:00Z",
  "environment": "staging",
  "summary": {
    "total": 150,
    "passed": 148,
    "failed": 2,
    "skipped": 0,
    "coverage": "82.5%"
  },
  "failures": [
    {
      "test_name": "test_osfi_gds_rejection_boundary",
      "error_code": "TEST_ASSERT_001",
      "message": "Expected UnderwritingBusinessRuleError, got None",
      "regulatory_impact": ["OSFI_B20"],
      "severity": "CRITICAL"
    }
  ],
  "compliance_status": {
    "osfi_b20": "PASSED",
    "fintrac": "PASSED",
    "cmhc": "PASSED",
    "pipeda": "FAILED"  // Due to encryption test failure
  }
}
```

### CI/CD Integration

**GitHub Actions Failure Conditions:**
```yaml
- name: Check Compliance Tests
  run: |
    uv run pytest -m compliance --json-report --json-report-file=compliance.json
    if grep -q '"pipeda": "FAILED"' compliance.json; then
      echo "::error::PIPEDA compliance test failed"
      exit 1
    fi
```

**Performance Regression Gates:**
```yaml
- name: Performance Benchmark
  run: |
    uv run pytest tests/performance/test_benchmarks.py --benchmark-json=perf.json
    # Fail if response time increased > 10% from baseline
    uv run python scripts/check_regression.py perf.json --threshold 10
```

---

## 7. Missing Details Implementation Strategy

### Test Fixture and Mocking Strategy

**Shared Fixtures (`tests/conftest.py`):**
```python
@pytest.fixture(scope="session")
async def test_db():
    """Create test database with migrations applied."""
    # Use testcontainers for PostgreSQL in CI
    # Run Alembic migrations on test DB
    yield db
    # Teardown: drop test schema

@pytest.fixture(scope="function")
async def db_session(test_db):
    """Provide isolated transaction for each test."""
    async with test_db.begin_nested() as transaction:
        yield session
        await transaction.rollback()

@pytest.fixture
def mock_encryption_service(monkeypatch):
    """Mock encryption for performance testing."""
    def mock_encrypt(data: str) -> bytes:
        return f"encrypted_{data}".encode()
    monkeypatch.setattr("common.security.encrypt_pii", mock_encrypt)
```

**Mocking Strategy:**
- **External Services:** Mock FINTRAC reporting API, credit bureau calls
- **Encryption:** Use deterministic mock in unit tests, real encryption in integration tests
- **Time:** Freeze time for date-dependent calculations using `freezegun`
- **File Storage:** Use `pytest-mock` for S3/document storage

### Load Testing Requirements and Targets

**Load Test Configuration (`tests/load/locustfile.py`):**
```python
class MortgageUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def submit_application(self):
        # Simulate complete application submission
        self.client.post("/api/v1/applications", json=self.factory.create_application())
    
    @task(1)
    def get_application_status(self):
        self.client.get(f"/api/v1/applications/{self.application_id}")

# Targets
# - Peak Load: 100 concurrent users (brokers)
# - Throughput: 50 applications/minute
# - Response Time p95: < 500ms
# - Error Rate: < 0.1%
```

**Performance Baselines:**
- GDS/TDS Calculation: < 50ms
- Full Underwriting Decision: < 200ms
- Document Upload: < 5s (up to 10MB)
- Database Query (indexed): < 20ms

### Test Data Cleanup and Isolation

**Isolation Strategy:**
- **Unit Tests:** In-memory SQLite with mocked dependencies
- **Integration Tests:** PostgreSQL with transaction rollback per test
- **E2E Tests:** Dedicated staging database, cleaned before/after suite
- **Load Tests:** Separate database instance, restored from snapshot

**Cleanup Automation:**
```python
# tests/conftest.py
@pytest.fixture(autouse=True, scope="session")
def cleanup_test_data():
    """Ensure test data is cleaned up after 24 hours."""
    yield
    # Run at end of test session
    asyncio.run(cleanup_old_test_data(hours=24))
```

### CI/CD Pipeline Integration Tests

**Pipeline Stages:**
1. **Lint & Type Check:** `ruff check && mypy .`
2. **Unit Tests:** `pytest -m unit --cov=modules --cov-fail-under=80`
3. **Integration Tests:** `pytest -m integration --cov=modules`
4. **Compliance Tests:** `pytest -m compliance --json-report`
5. **Security Scan:** `uv run pip-audit`
6. **Load Test (Staging):** `locust -f tests/load/locustfile.py --headless -u 100 -r 10`
7. **Performance Benchmark:** `pytest tests/performance --benchmark-compare`

### Accessibility (a11y) Testing Requirements

**A11y Test Suite (`tests/a11y/test_accessibility.py`):**
- Use `pytest-axe` for automated accessibility scanning
- Test all user-facing endpoints (broker portal, client portal)
- Verify WCAG 2.1 AA compliance
- Critical checks:
  - Form labels for SIN, DOB, income fields
  - Error message announcements
  - Document upload alternative text
  - Color contrast ratios

**Test Example:**
```python
def test_application_form_a11y(client):
    response = client.get("/api/v1/applications/new")
    results = axe.run(response.content)
    assert len(results["violations"]) == 0, f"Accessibility violations: {results['violations']}"
```

---