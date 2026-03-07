# Design: Testing Suite
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Testing Suite Design Plan

**Location:** `docs/design/testing-suite.md`

---

## 1. Endpoints

### Test Execution Interfaces
No REST endpoints are exposed by the testing suite itself. Test execution is triggered via:

- **CLI Entrypoints:**
  - `uv run pytest -m unit` – Unit test suite
  - `uv run pytest -m integration` – Integration test suite
  - `uv run pytest -m e2e` – End-to-end test suite
  - `uv run pytest --cov=mortgage_underwriting --cov-fail-under=80` – Coverage enforcement
  - `uv run pytest --benchmark-only` – Performance baseline validation

- **CI/CD Hooks:**
  - `make test` – Full suite with coverage report
  - `make test-security` – Run `pip-audit` and bandit scans
  - `make test-load` – Execute locust load tests against staging

### Test Reporting (Optional Dashboard Service)
If building a test observability service, these endpoints would be defined:

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/v1/test-runs/{run_id}` | `admin` | Fetch test execution results |
| `GET` | `/api/v1/coverage/{module}` | `admin` | Get module coverage metrics |
| `POST` | `/api/v1/test-runs` | `ci-token` | Record test run from CI |

**Request/Response Schemas:**
```python
# POST /api/v1/test-runs
class TestRunRecord(BaseModel):
    run_id: UUID
    timestamp: datetime
    branch: str
    commit_sha: str
    coverage_percent: Decimal
    tests_passed: int
    tests_failed: int
    compliance_score: Decimal  # Regulatory requirement pass rate
```

**Error Responses:**
- `401 Unauthorized` – Invalid CI token
- `403 Forbidden` – Non-admin access to coverage reports
- `422 Unprocessable` – Malformed test run payload

---

## 2. Models & Database

### Test Infrastructure Models (Stored in separate `test` schema)

```python
# tests/models/test_metadata.py
class TestRun(Base):
    """Audit trail for test executions (FINTRAC 5-year retention applies)"""
    __tablename__ = "test_runs"
    __table_args__ = {"schema": "test"}
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[datetime | None]
    branch: Mapped[str] = mapped_column(String(255))
    commit_sha: Mapped[str] = mapped_column(String(40), index=True)
    coverage_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(20))  # passed, failed, error
    
    # Compliance validation results
    osfi_b20_tests_passed: Mapped[int]
    fintrac_tests_passed: Mapped[int]
    cmhc_tests_passed: Mapped[int]
    pipeda_tests_passed: Mapped[int]

class TestFailure(Base):
    """Immutable failure record for audit"""
    __tablename__ = "test_failures"
    __table_args__ = {"schema": "test"}
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    test_run_id: Mapped[UUID] = mapped_column(ForeignKey("test.test_runs.id"))
    test_path: Mapped[str] = mapped_column(Text)  # e.g., unit/test_underwriting.py::test_gds_calculation
    error_code: Mapped[str] = mapped_column(String(20), index=True)  # TEST_001, etc.
    failure_message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    
    # PIPEDA: Never log PII in failure messages
```

### Test Fixture Data Models (In-memory Pydantic)
```python
# tests/conftest.py
class MockApplicant(BaseModel):
    """Synthetic applicant data with PII sanitization"""
    sin: str  # SHA256 hash only, never raw SIN
    dob: date  # Randomized, not real individuals
    gross_income: Decimal
    property_value: Decimal
    loan_amount: Decimal
    
    class Config:
        json_encoders = {Decimal: str}

class UnderwritingTestCase(BaseModel):
    """OSFI B-20 test scenario"""
    name: str
    contract_rate: Decimal
    qualifying_rate: Decimal  # Must be max(contract_rate + 2%, 5.25%)
    gross_monthly_income: Decimal
    pith: Decimal
    expected_gds: Decimal
    expected_tds: Decimal
    should_approve: bool
```

---

## 3. Business Logic

### Test Categorization & Markers
```python
# pytest.ini
markers =
    unit: Unit tests (no I/O, < 100ms)
    integration: Database and service integration
    e2e: Full workflow with curl commands
    slow: Tests > 1 second
    compliance: OSFI/FINTRAC/CMHC/PIPEDA validation
    security: Auth, encryption, access control
    regression: Known bug prevention
```

### Coverage Enforcement Algorithm
```python
# tests/coverage_enforcement.py
def calculate_coverage(module_path: str) -> Decimal:
    """Calculate line coverage with regulatory weighting"""
    base_coverage = run_coverage_tool(module_path)
    
    # OSFI B-20: GDS/TDS calculation paths must be 100% covered
    if module_path.endswith("underwriting/services.py"):
        critical_lines = get_critical_lines(["calculate_gds", "calculate_tds", "apply_stress_test"])
        critical_coverage = calculate_critical_path_coverage(critical_lines)
        base_coverage = min(base_coverage, critical_coverage)  # Floor by critical path coverage
    
    return Decimal(str(base_coverage)).quantize(Decimal("0.01"))

def enforce_coverage(module: str, minimum: Decimal = Decimal("80.0")):
    actual = calculate_coverage(module)
    if actual < minimum:
        raise CoverageViolationError(
            f"Module {module} coverage {actual}% below minimum {minimum}%"
        )
```

### Test Data Generation Strategy
```python
# tests/factories/applicant_factory.py
class ApplicantFactory:
    """Generate compliant test data with no real PII"""
    
    @staticmethod
    def create_sin() -> str:
        """Generate valid format SIN and return SHA256 hash only"""
        sin = f"{random.randint(100, 999)}-{random.randint(100, 999)}-{random.randint(100, 999)}"
        return hashlib.sha256(sin.encode()).hexdigest()
    
    @staticmethod
    def create_ltv_scenario(ltv_percent: Decimal) -> MockApplicant:
        """CMHC tier boundary testing: 80.01%, 85.01%, 90.01%, 95%"""
        property_value = Decimal("500000.00")
        loan_amount = (property_value * ltv_percent / Decimal("100")).quantize(Decimal("0.01"))
        return MockApplicant(
            sin=ApplicantFactory.create_sin(),
            dob=date.today() - timedelta(days=random.randint(18*365, 65*365)),
            gross_income=Decimal("8000.00"),
            property_value=property_value,
            loan_amount=loan_amount
        )
```

### Load Testing Requirements
- **Target:** 100 concurrent mortgage applications/minute
- **Duration:** 15-minute sustained load
- **Metrics:** p95 latency < 2s, error rate < 0.1%
- **Tool:** locustfile.py with realistic user journeys
- **Data:** Pre-generated 10K sanitized applicants in `tests/fixtures/load_data.csv`

### Critical Test Case Implementation Plan

#### GDS/TDS Calculation Correctness
```python
# tests/unit/test_underwriting.py
@pytest.mark.compliance
@pytest.mark.unit
def test_gds_calculation_with_stress_test():
    """OSFI B-20: Verify qualifying_rate = max(contract_rate + 2%, 5.25%)"""
    scenarios = [
        # (contract_rate, expected_qualifying_rate)
        (Decimal("3.00"), Decimal("5.25")),  # 3+2=5 < 5.25 → floor applies
        (Decimal("4.00"), Decimal("6.00")),  # 4+2=6 > 5.25 → contract+2%
        (Decimal("5.25"), Decimal("7.25")),  # 5.25+2=7.25 > 5.25
    ]
    
    for contract_rate, expected_qualifying in scenarios:
        result = UnderwritingService.calculate_qualifying_rate(contract_rate)
        assert result == expected_qualifying, f"Failed for rate {contract_rate}"
        
        # Verify GDS ≤ 39% enforcement
        applicant = ApplicantFactory.create_with_rate(contract_rate)
        gds = UnderwritingService.calculate_gds(applicant)
        assert gds <= Decimal("39.00"), f"GDS {gds}% exceeds OSFI limit"
```

#### CMHC Insurance Eligibility
```python
# tests/unit/test_underwriting.py
@pytest.mark.compliance
@pytest.mark.parametrize("ltv,expected_premium", [
    (Decimal("80.01"), Decimal("2.80")),
    (Decimal("85.00"), Decimal("2.80")),
    (Decimal("85.01"), Decimal("3.10")),
    (Decimal("90.00"), Decimal("3.10")),
    (Decimal("90.01"), Decimal("4.00")),
    (Decimal("95.00"), Decimal("4.00")),
])
def test_cmhc_premium_tiers(ltv, expected_premium):
    """CMHC: Premium lookup by LTV tier with Decimal precision"""
    applicant = ApplicantFactory.create_ltv_scenario(ltv)
    premium = CMHCCalculator.get_insurance_premium(applicant.loan_amount, applicant.property_value)
    assert premium == (applicant.loan_amount * expected_premium / Decimal("100")).quantize(Decimal("0.01"))

def test_cmhc_property_cap():
    """CMHC: Properties > $1.5M are ineligible for insurance"""
    applicant = MockApplicant(
        property_value=Decimal("1500000.01"),
        loan_amount=Decimal("1350000.00"),  # 90% LTV
        # ...
    )
    with pytest.raises(CMHCBusinessRuleError, match="Property value exceeds CMHC cap"):
        CMHCCalculator.validate_eligibility(applicant)
```

#### PIPEDA Encryption Validation
```python
# tests/unit/test_encryption.py
@pytest.mark.security
@pytest.mark.compliance
def test_sin_encryption_at_rest():
    """PIPEDA: SIN encrypted before database write, never in logs"""
    applicant = ApplicantFactory.create()
    encrypted_sin = encrypt_pii(applicant.sin)
    
    # Verify encryption
    assert encrypted_sin != applicant.sin
    assert len(encrypted_sin) == 64  # SHA256 hex length
    
    # Verify lookup uses hash only
    lookup_key = hashlib.sha256(applicant.sin.encode()).hexdigest()
    assert "sin" not in str(lookup_key)  # Not in logs
```

#### FINTRAC Audit Trail
```python
# tests/integration/test_fintrac.py
@pytest.mark.compliance
def test_transaction_immutable_audit():
    """FINTRAC: Records never deleted, 5-year retention"""
    application = create_test_application(amount=Decimal("15000.00"))  # > $10K threshold
    
    # Verify transaction flagging
    assert application.transaction_type == "LARGE_CASH"
    
    # Attempt deletion should fail
    with pytest.raises(FINTRACImmutabilityError):
        delete_application(application.id)
    
    # Verify audit fields exist
    assert application.created_at is not None
    assert application.created_by is not None
    assert application.updated_at is None  # Never updated
```

---

## 4. Migrations

### New Tables (in `test` schema)
```sql
-- migrations/versions/2024_01_add_test_audit_schema.py
def upgrade():
    # FINTRAC compliance: Test run audit trail retained 5 years
    op.execute("CREATE SCHEMA IF NOT EXISTS test")
    
    op.create_table(
        "test_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("branch", sa.String(255), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False, index=True),
        sa.Column("coverage_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("osfi_b20_tests_passed", sa.Integer(), nullable=False),
        sa.Column("fintrac_tests_passed", sa.Integer(), nullable=False),
        sa.Column("cmhc_tests_passed", sa.Integer(), nullable=False),
        sa.Column("pipeda_tests_passed", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="test"
    )
    
    op.create_table(
        "test_failures",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("test_run_id", sa.UUID(), nullable=False),
        sa.Column("test_path", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(20), nullable=False, index=True),
        sa.Column("failure_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.ForeignKeyConstraint(["test_run_id"], ["test.test_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="test"
    )
    
    # 5-year retention policy (FINTRAC compliance)
    op.execute("""
        ALTER TABLE test.test_runs 
        SET (autovacuum_enabled = true, log_autovacuum_min_duration = 0)
    """)

def downgrade():
    op.drop_table("test_failures", schema="test")
    op.drop_table("test_runs", schema="test")
    op.execute("DROP SCHEMA IF EXISTS test")
```

---

## 5. Security & Compliance

### PIPEDA Test Data Handling
- **Synthetic Data Only:** All test fixtures use Faker with seeded RNG (deterministic)
- **PII Sanitization:** Raw SIN/DOB never committed; use SHA256 hashes or encrypted values
- **Log Redaction:** `tests/conftest.py` installs structlog processor to redact PII patterns
- **Environment Isolation:** Test database uses separate schema (`test_*`) with automatic teardown

### OSFI B-20 Compliance Validation
- **Stress Test Floor:** Dedicated test verifies qualifying_rate never below 5.25%
- **GDS/TDS Ceilings:** Parameterized tests for boundary values (39.00%, 44.00%)
- **Audit Log Verification:** Tests confirm calculation breakdowns are logged with correlation_id

### FINTRAC Reporting Triggers
- **Cash Threshold Test:** `test_fintrac_large_transaction_flag` verifies > $10,000 flagging
- **Structuring Detection:** Integration test simulates 3x $9,999 transactions (should trigger alert)
- **Retention Validation:** Test attempts to delete audit record, expects `IMMUTABILITY_ERROR`
- **5-Year Retention:** `test_fintrac_audit_retention_policy` queries records older than 5 years

### CMHC Insurance Logic
- **LTV Precision:** Tests use Decimal quantization to prevent float precision loss
- **Tier Boundaries:** Tests at exact tier edges (80.01%, 85.01%, 90.01%)
- **Property Cap:** Test at $1,500,000.00 (eligible) and $1,500,000.01 (ineligible)

### Access Control Verification
```python
# tests/integration/test_broker_access.py
@pytest.mark.security
def test_broker_cannot_access_other_broker_client():
    """Broker isolation: Broker A cannot view Broker B's applications"""
    broker_a_token = create_test_token(broker_id="BROKER_A")
    broker_b_application = create_application(broker_id="BROKER_B")
    
    response = client.get(
        f"/api/v1/applications/{broker_b_application.id}",
        headers={"Authorization": f"Bearer {broker_a_token}"}
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH_003"
```

---

## 6. Error Codes & HTTP Responses

### Test Failure Categories
| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `CoverageViolationError` | 500 (CI) | `TEST_001` | "Coverage {actual}% < {minimum}%" | Coverage below 80% |
| `ComplianceTestFailure` | 500 (CI) | `TEST_002` | "OSFI B-20 test failed: {detail}" | GDS/TDS calculation error |
| `PerformanceRegressionError` | 500 (CI) | `TEST_003` | "p95 latency {actual}ms > {baseline}ms" | Load test threshold exceeded |
| `SecurityTestFailure` | 500 (CI) | `TEST_004` | "PII detected in logs: {field}" | Log redaction failure |
| `TestDataLeakError` | 500 (CI) | `TEST_005` | "Test database not isolated: {detail}" | Cross-test contamination |
| `AccessControlTestFailure` | 500 (CI) | `TEST_006` | "Broker isolation violated" | AuthZ bypass detected |

### API Error Response Validation Tests
```python
# tests/unit/test_exceptions.py
@pytest.mark.unit
def test_error_response_structure():
    """All errors must return structured JSON with detail and error_code"""
    from common.exceptions import AppException
    
    exc = AppException("Test error", error_code="TEST_123")
    response = exc.to_response()
    
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "error_code" in response.json()
    assert response.json()["error_code"] == "TEST_123"
```

### E2E Test Curl Commands
```bash
# tests/e2e/test_workflow_curls.sh
#!/bin/bash
# FINTRAC Large Transaction E2E Test

# Step 1: Authenticate broker
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=broker_a&password=test" | jq -r .access_token)

# Step 2: Submit application > $10K
APP_ID=$(curl -s -X POST http://localhost:8000/api/v1/applications \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"loan_amount": 15000.00, "property_value": 500000.00}' | jq -r .id)

# Step 3: Verify FINTRAC flag
curl -s http://localhost:8000/api/v1/applications/$APP_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.fintrac_flag'

# Step 4: Attempt deletion (should fail)
curl -X DELETE http://localhost:8000/api/v1/applications/$APP_ID \
  -H "Authorization: Bearer $TOKEN" -w "%{http_code}" | grep -q "409"
```

---

## 7. Missing Details Implementation

### Test Fixture & Mocking Strategy
- **FactoryBoy:** Replace manual factories with declarative factories for SQLAlchemy models
- **pytest-mock:** All external API calls (credit bureau, property valuation) mocked with `responses` library
- **Database Isolation:** Each test runs in nested transaction (`@pytest.mark.asyncio` with `rollback`)
- **Async Fixtures:** All DB fixtures return async session, cleaned up via `yield` pattern

### Load Testing Requirements
- **Tool:** Locust with `tests/locustfile.py` defining `MortgageApplicantUser` behavior
- **Targets:** 100 req/s sustained, 500 req/s burst, p99 < 3s
- **Data:** Pre-generate 50K synthetic applicants in `tests/fixtures/load_test_seed.sql`
- **Metrics:** Capture CPU, memory, DB connection pool saturation

### Test Data Cleanup & Isolation
- **Transaction Rollback:** Every test wrapped in `BEGIN; ... ROLLBACK;`
- **Schema-per-Runner:** Parallel CI jobs use `test_schema_{uuid4()}` to avoid collisions
- **Teardown Hook:** `pytest_sessionfinish` drops temporary schemas
- **PII Scrubbing:** `conftest.py` adds `request.addfinalizer(scrub_test_logs)`

### CI/CD Pipeline Integration
```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: uv sync
      - run: uv run pytest -m "not e2e" --cov --cov-fail-under=80
      - run: uv run pytest -m e2e --curl-commands
      - run: uv run locust -f tests/locustfile.py --headless -u 100 -r 10 --run-time=15m
      - run: uv run pip-audit
      - uses: codecov/codecov-action@v3
```

### Performance Benchmark Baselines
- **File:** `tests/benchmarks/baselines.json`
- **Metrics:** GDS calculation < 50ms, DB query < 100ms, full underwriting workflow < 500ms
- **Regression Gate:** 10% slowdown fails build (`pytest-benchmark` compare)
- **Tracking:** Stored in `test.benchmark_history` table

### Accessibility (a11y) Testing
- **Tool:** pytest-axe for API documentation (OpenAPI schemas)
- **Scope:** All `/api/v1` endpoints must have descriptive `summary` and `description`
- **Validation:** Error messages must be clear, field names human-readable
- **Exclusion:** No UI, so a11y limited to API contract clarity

---

## 8. File Structure

```
tests/
├── conftest.py                    # Global fixtures, log redaction, DB isolation
├── factories/
│   ├── __init__.py
│   ├── applicant_factory.py       # Mock data generation
│   ├── application_factory.py
│   └── document_factory.py
├── fixtures/
│   ├── load_test_seed.sql         # 50K synthetic records
│   └── regulatory_scenarios.json  # OSFI/CMHC test vectors
├── benchmarks/
│   ├── baselines.json
│   └── benchmark_history.py
├── unit/
│   test_underwriting.py           # GDS/TDS/LTV calculations
│   test_fintrac.py                # Cash thresholds, retention
│   test_auth.py                   # JWT lifecycle
│   test_documents.py              # File validation
│   test_encryption.py             # PIPEDA compliance
│   test_exceptions.py             # Error response structure
│   test_decimal_precision.py      # No float anywhere
├── integration/
│   test_application_flow.py       # Full pipeline
│   test_auth_flow.py              # Auth workflow
│   test_broker_access.py          # Broker isolation
│   test_client_access.py          # Client isolation
│   test_fintrac_audit.py          # Immutable audit trail
├── e2e/
│   test_workflow_curls.sh         # Curl-based E2E
│   test_performance.py            # Load test orchestration
├── locustfile.py                  # Load test scenarios
├── coverage_enforcement.py        # 80% gate with critical path weighting
└── security_scan.py               # pip-audit wrapper
```

---

## 9. Compliance Validation Matrix

| Requirement | Test File | Coverage Target | Critical Path |
|-------------|-----------|-----------------|---------------|
| OSFI B-20 stress test | `unit/test_underwriting.py` | 100% | Yes |
| OSFI GDS/TDS ceilings | `unit/test_underwriting.py` | 100% | Yes |
| FINTRAC > $10K flagging | `integration/test_fintrac.py` | 100% | Yes |
| FINTRAC immutability | `integration/test_fintrac.py` | 100% | Yes |
| CMHC LTV tiers | `unit/test_underwriting.py` | 100% | Yes |
| CMHC property cap | `unit/test_underwriting.py` | 100% | Yes |
| PIPEDA SIN encryption | `unit/test_encryption.py` | 100% | Yes |
| PIPEDA log redaction | `unit/test_encryption.py` | 100% | Yes |
| JWT token lifecycle | `unit/test_auth.py` | 90% | No |
| Access control | `integration/test_broker_access.py` | 100% | Yes |

**Total Module Coverage Requirement:** 80% overall, 100% on all critical paths marked above.