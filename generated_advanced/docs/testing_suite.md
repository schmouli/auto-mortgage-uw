# Testing Suite
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Testing Suite Design Plan

**File:** `docs/design/testing-suite.md`

---

## 1. Endpoints

This section documents all production endpoints that require test coverage, organized by module. Each endpoint includes authentication requirements, critical test scenarios, and compliance verification points.

### 1.1 Authentication & Authorization Endpoints

| Method | Path | Auth | Critical Test Scenarios | Compliance |
|--------|------|------|------------------------|------------|
| `POST` | `/api/v1/auth/token` | Public | Valid credentials, invalid password, locked account, MFA flow | Token expiry, refresh lifecycle |
| `POST` | `/api/v1/auth/refresh` | Authenticated | Valid refresh token, expired token, revoked token | JWT lifecycle verification |
| `POST` | `/api/v1/auth/logout` | Authenticated | Active session, already revoked token | Session termination audit |
| `GET` | `/api/v1/auth/me` | Authenticated | Valid token, expired token, malformed token | Identity verification logging |

### 1.2 Application Management Endpoints

| Method | Path | Auth | Critical Test Scenarios | Compliance |
|--------|------|------|------------------------|------------|
| `POST` | `/api/v1/applications` | Authenticated (Broker) | Valid application, missing required fields, LTV > 95% | PIPEDA data minimization, SIN encryption |
| `GET` | `/api/v1/applications/{id}` | Authenticated (Owner/Admin) | Own application, other broker's application, client access | Access control isolation |
| `PUT` | `/api/v1/applications/{id}` | Authenticated (Broker) | Status transition rules, immutable fields after submission | Audit trail immutability |
| `DELETE` | `/api/v1/applications/{id}` | Admin Only | Soft delete verification, cascade document cleanup | FINTRAC 5-year retention |

### 1.3 Underwriting Calculation Endpoints

| Method | Path | Auth | Critical Test Scenarios | Compliance |
|--------|------|------|------------------------|------------|
| `POST` | `/api/v1/underwriting/calculate` | Authenticated | GDS/TDS at limits, stress test floor 5.25%, LTV 80.01% | OSFI B-20 calculation audit |
| `GET` | `/api/v1/underwriting/{app_id}/ratios` | Authenticated | Verify calculation breakdown logging, Decimal precision | GDS ≤ 39%, TDS ≤ 44% enforcement |
| `POST` | `/api/v1/cmhc/eligibility` | Authenticated | LTV 80.01-85%, 85.01-90%, 90.01-95%, >$1.5M property | CMHC premium tier lookup |

### 1.4 Document Management Endpoints

| Method | Path | Auth | Critical Test Scenarios | Compliance |
|--------|------|------|------------------------|------------|
| `POST` | `/api/v1/documents/upload` | Authenticated | File size limits (10MB), MIME type validation, virus scan | PIPEDA encryption at rest |
| `GET` | `/api/v1/documents/{id}` | Authenticated (Owner) | Access other broker's document, expired presigned URL | Access control, audit logging |
| `DELETE` | `/api/v1/documents/{id}` | Authenticated | Soft delete, FINTRAC retention bypass for admin | Immutable audit trail |

### 1.5 FINTRAC Reporting Endpoints

| Method | Path | Auth | Critical Test Scenarios | Compliance |
|--------|------|------|------------------------|------------|
| `POST` | `/api/v1/transactions/report` | Authenticated | Amounts $9,999, $10,000, $10,001, structured transactions | Threshold detection, flagging |
| `GET` | `/api/v1/transactions/audit/{id}` | Admin Only | 5-year retention verification, immutable record check | FINTRAC audit trail |

---

## 2. Models & Database

### 2.1 Test Fixture Models

```python
# tests/conftest.py - Test Data Factory Models
class ApplicationFactory:
    """Factory for creating test mortgage applications with regulatory edge cases"""
    
    # PIPEDA compliance: SIN/DOB encryption verification
    sin_encrypted: str = factory.LazyAttribute(lambda o: encrypt_pii(fake.sin()))
    dob_encrypted: str = factory.LazyAttribute(lambda o: encrypt_pii(fake.date_of_birth()))
    
    # OSFI B-20 edge cases
    gross_monthly_income: Decimal = factory.Iterator([
        Decimal("5000.00"),  # Base case
        Decimal("8333.33"),  # GDS = 39% edge
        Decimal("6818.18"),  # TDS = 44% edge
    ])
    
    # CMHC LTV tiers
    property_value: Decimal = factory.Iterator([
        Decimal("500000.00"),  # LTV 80.01-85%
        Decimal("600000.00"),  # LTV 85.01-90%
        Decimal("750000.00"),  # LTV 90.01-95%
        Decimal("1500000.01"), # CMHC ineligible
    ])
    
    loan_amount: Decimal = factory.LazyAttribute(lambda o: 
        (o.property_value * Decimal("0.85")).quantize(Decimal("0.01"))
    )
    
    # FINTRAC threshold testing
    downpayment_amount: Decimal = factory.Iterator([
        Decimal("9999.99"),   # Below threshold
        Decimal("10000.00"),  # At threshold
        Decimal("10000.01"),  # Above threshold
    ])
    
    # Audit fields (mandatory on ALL test models)
    created_at: datetime = factory.LazyFunction(datetime.utcnow)
    created_by: str = factory.LazyAttribute(lambda o: fake.uuid4())

class DocumentFactory:
    """Factory for testing document validation and PIPEDA compliance"""
    
    file_size: int = factory.Iterator([9_999_999, 10_000_000, 10_000_001])  # 10MB limit
    mime_type: str = factory.Iterator(["application/pdf", "image/jpeg", "application/x-msdownload"])
    content_encrypted: bytes = factory.LazyAttribute(lambda o: encrypt_pii(b"test content"))
    created_at: datetime = factory.LazyFunction(datetime.utcnow)
```

### 2.2 Test Database Isolation Strategy

```sql
-- Test database template for parallel execution
CREATE DATABASE mortgage_test_template TEMPLATE postgres;
-- Enable transaction-based rollback for unit tests
ALTER DATABASE mortgage_test_template SET default_transaction_isolation TO 'read committed';
```

**Isolation Levels:**
- **Unit Tests**: Database transaction rollback after each test (`pytest-asyncio` + `sqlalchemy.ext.asyncio.AsyncSession`)
- **Integration Tests**: Database truncation with `TRUNCATE TABLE ... CASCADE` in `conftest.py` teardown
- **E2E Tests**: Dedicated test database with migration reset: `alembic upgrade head` before suite, `alembic downgrade base` after

### 2.3 Test Data Cleanup & Retention

```python
# tests/utils/cleanup.py
async def enforce_fintrac_retention(test_db: AsyncSession, retention_days: int = 1825):
    """
    FINTRAC 5-year retention compliance for test data.
    Soft-delete test records older than retention period.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    await test_db.execute(
        update(TransactionRecord)
        .where(TransactionRecord.created_at < cutoff_date)
        .values(deleted_at=datetime.utcnow(), deleted_by="test_cleanup")
    )
```

---

## 3. Business Logic

### 3.1 GDS/TDS Calculation Verification Algorithm

```python
# tests/unit/test_underwriting.py - Verification Logic
def verify_gds_tds_calculation(
    principal: Decimal, 
    interest: Decimal, 
    taxes: Decimal, 
    heating: Decimal,
    gross_income: Decimal,
    other_debt: Decimal,
    contract_rate: Decimal,
) -> dict[str, bool]:
    """
    OSFI B-20 compliance verification with stress test floor 5.25%.
    Returns validation results with audit breakdown.
    """
    qualifying_rate = max(contract_rate + Decimal("0.02"), Decimal("0.0525"))
    
    # Stress test payment calculation (25-year amortization)
    monthly_rate = qualifying_rate / Decimal("12")
    payment_count = Decimal("300")  # 25 years
    
    # Stress-tested mortgage payment
    stress_payment = principal * (
        monthly_rate * (1 + monthly_rate) ** payment_count
    ) / ((1 + monthly_rate) ** payment_count - 1)
    
    # GDS calculation
    gds = (stress_payment + taxes + heating) / gross_income
    
    # TDS calculation
    tds = (stress_payment + taxes + heating + other_debt) / gross_income
    
    return {
        "gds_within_limit": gds <= Decimal("0.39"),
        "tds_within_limit": tds <= Decimal("0.44"),
        "stress_test_floor_applied": qualifying_rate == Decimal("0.0525"),
        "calculation_breakdown": {
            "qualifying_rate": str(qualifying_rate.quantize(Decimal("0.0001"))),
            "gds_percentage": str(gds.quantize(Decimal("0.0001"))),
            "tds_percentage": str(tds.quantize(Decimal("0.0001"))),
        }
    }
```

### 3.2 CMHC Premium Tier Verification Logic

```python
# tests/unit/test_underwriting.py - CMHC Eligibility
def verify_cmhc_eligibility(loan_amount: Decimal, property_value: Decimal) -> dict:
    """
    CMHC insurance requirement logic validation.
    Returns premium rate and eligibility status.
    """
    ltv = (loan_amount / property_value * Decimal("100")).quantize(Decimal("0.01"))
    
    # Property value cap ($1.5M)
    if property_value > Decimal("1500000.00"):
        return {"insurance_required": False, "reason": "property_value_exceeds_cap"}
    
    # LTV tiers
    if ltv <= Decimal("80.00"):
        return {"insurance_required": False, "ltv": str(ltv)}
    elif Decimal("80.01") <= ltv <= Decimal("85.00"):
        premium_rate = Decimal("0.0280")
    elif Decimal("85.01") <= ltv <= Decimal("90.00"):
        premium_rate = Decimal("0.0310")
    elif Decimal("90.01") <= ltv <= Decimal("95.00"):
        premium_rate = Decimal("0.0400")
    else:
        return {"insurance_required": False, "reason": "ltv_exceeds_maximum"}
    
    premium_amount = (loan_amount * premium_rate).quantize(Decimal("0.01"))
    
    return {
        "insurance_required": True,
        "ltv": str(ltv),
        "premium_rate": str(premium_rate),
        "premium_amount": str(premium_amount),
    }
```

### 3.3 FINTRAC Threshold Detection Testing

```python
# tests/unit/test_fintrac.py - Structuring Detection
def detect_structured_transactions(transactions: list[Decimal], threshold: Decimal = Decimal("10000.00")) -> bool:
    """
    Detects potential structuring to avoid FINTRAC reporting.
    Returns True if pattern detected (e.g., 3+ transactions < threshold in 24h).
    """
    suspicious_count = sum(1 for t in transactions if t < threshold)
    total_amount = sum(transactions)
    
    # Pattern: Multiple sub-threshold transactions summing above threshold
    if suspicious_count >= 3 and total_amount >= threshold:
        return True
    
    # Pattern: Sequential transactions just below threshold
    if suspicious_count >= 2 and any(
        threshold - Decimal("100.00") <= t < threshold for t in transactions
    ):
        return True
    
    return False
```

### 3.4 PIPEDA Encryption Verification

```python
# tests/unit/test_encryption.py - SIN/DOB Encryption
async def verify_piped_encryption(sin_plain: str, dob_plain: date) -> dict:
    """
    Verifies AES-256 encryption at rest for PIPEDA compliance.
    Checks that encrypted values differ and are not logged.
    """
    sin_encrypted = encrypt_pii(sin_plain)
    dob_encrypted = encrypt_pii(dob_plain.isoformat())
    
    # Verify encryption produces different ciphertext
    assert sin_encrypted != dob_encrypted
    
    # Verify hashing for lookups
    sin_hashed = hashlib.sha256(sin_plain.encode()).hexdigest()
    
    # Verify decryption works
    sin_decrypted = decrypt_pii(sin_encrypted)
    
    return {
        "encryption_verified": sin_encrypted != sin_plain,
        "hashing_verified": sin_hashed == hashlib.sha256(sin_plain.encode()).hexdigest(),
        "decryption_verified": sin_decrypted == sin_plain,
        "never_in_logs": not contains_pii_in_logs(),  # Custom log scanner
    }
```

---

## 4. Migrations

### 4.1 Test Database Setup Migration

```python
# alembic/versions/test_setup_001.py
"""Create test isolation schema and utility functions"""

def upgrade():
    # Create test cleanup function for FINTRAC retention
    op.execute("""
        CREATE OR REPLACE FUNCTION test_cleanup_old_records()
        RETURNS void AS $$
        BEGIN
            DELETE FROM applications 
            WHERE created_at < NOW() - INTERVAL '5 years' 
            AND environment = 'test';
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Add environment column for test data identification
    op.add_column('applications', sa.Column('environment', sa.String(), server_default='production'))
    op.create_index('ix_applications_environment_created_at', 'applications', ['environment', 'created_at'])

def downgrade():
    op.drop_index('ix_applications_environment_created_at')
    op.drop_column('applications', 'environment')
    op.execute("DROP FUNCTION IF EXISTS test_cleanup_old_records()")
```

### 4.2 Test Results Storage Table

```python
# tests/models/test_results.py - Non-production table for test metrics
class TestResult(Base):
    """Stores test execution results for CI/CD reporting"""
    __tablename__ = "test_results"
    __table_args__ = {"schema": "test_metadata"}
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    test_name: Mapped[str] = mapped_column(String(255), index=True)
    test_type: Mapped[str] = mapped_column(String(50))  # unit, integration, e2e
    status: Mapped[str] = mapped_column(String(20))  # passed, failed, skipped
    duration_ms: Mapped[int]
    coverage_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    compliance_tag: Mapped[str] = mapped_column(String(100))  # OSFI, FINTRAC, CMHC, PIPEDA
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by: Mapped[str] = mapped_column(String(100))  # CI pipeline ID
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Test Verification Matrix

| Test Scenario | Expected Behavior | Test File | Compliance Evidence |
|---------------|-------------------|-----------|---------------------|
| GDS = 38.9%, TDS = 43.9% | **APPROVE** | `test_underwriting.py` | Log calculation breakdown |
| GDS = 39.1%, TDS = 43.9% | **REJECT** | `test_underwriting.py` | Error code: `OSFI_001` |
| Contract rate 3.5% | Qualifying rate = 5.25% floor | `test_underwriting.py` | Log: `stress_test_floor_applied: true` |
| Contract rate 4.5% | Qualifying rate = 6.50% | `test_underwriting.py` | Log: `qualifying_rate: 6.5000` |

### 5.2 FINTRAC Test Triggers

```python
# tests/integration/test_fintrac.py - Reporting Triggers
FINTRAC_TEST_CASES = [
    {
        "amount": Decimal("9999.99"),
        "expected_flagged": False,
        "reason": "Below $10,000 threshold"
    },
    {
        "amount": Decimal("10000.00"),
        "expected_flagged": True,
        "reason": "At threshold - requires reporting"
    },
    {
        "amount": Decimal("9999.00"),
        "transactions": 3,
        "total": Decimal("29997.00"),
        "expected_flagged": True,
        "reason": "Structuring pattern detected"
    }
]
```

**Retention Test**: Verify records created 1825 days ago are still queryable; records marked for deletion after 1826 days are soft-deleted but retrievable by admin.

### 5.3 CMHC Test Coverage

```python
# tests/unit/test_underwriting.py - CMHC Edge Cases
CMHC_TEST_MATRIX = [
    # (property_value, loan_amount, expected_insurance, expected_rate)
    (Decimal("500000"), Decimal("400000"), False, None),  # LTV 80.00%
    (Decimal("500000"), Decimal("400001"), True, "0.0280"),  # LTV 80.01%
    (Decimal("600000"), Decimal("510000"), True, "0.0310"),  # LTV 85.01%
    (Decimal("750000"), Decimal("712500"), True, "0.0400"),  # LTV 95.00%
    (Decimal("1500000.01"), Decimal("1350000"), False, None),  # Exceeds cap
]
```

### 5.4 PIPEDA Data Handling Rules

**Test Verification Requirements:**
1. **SIN Encryption**: Assert `sin` field never appears in plaintext in database dumps, logs, or error responses
2. **DOB Encryption**: Verify `dob` encrypted at rest, only age used in calculations
3. **Data Minimization**: Test that optional PII fields are rejected if not required for underwriting
4. **Hash Lookups**: Verify SHA256 hash matching for SIN-based queries without decryption

**Log Scanning Test:**
```python
def test_no_pii_in_logs(caplog):
    """Scan logs for SIN, DOB, income, banking data patterns"""
    forbidden_patterns = [
        r"\d{3}-\d{3}-\d{3}",  # SIN format
        r"\d{4}-\d{2}-\d{2}",  # DOB format
        r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?"  # Dollar amounts
    ]
    for record in caplog.records:
        for pattern in forbidden_patterns:
            assert not re.search(pattern, record.message), f"PII detected in logs: {record.message}"
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Test Infrastructure Error Codes

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `TestDataIsolationError` | 500 | `TEST_001` | "Test database not isolated: {detail}" | Dirty state detected in unit test |
| `FixtureSetupError` | 500 | `TEST_002` | "Failed to create test fixture: {fixture}" | Factory validation failed |
| `ComplianceAssertionError` | 500 | `TEST_003` | "Compliance check failed: {regulation}" | OSFI/FINTRAC/CMHC/PIPEDA violation in test |
| `CoverageThresholdError` | 500 | `TEST_004` | "Coverage {actual}% below minimum {required}%" | Coverage < 80% |

### 6.2 Expected Production Error Codes (Test Assertions)

| HTTP Status | Error Code | Regulatory Context | Test Assertion |
|-------------|------------|-------------------|----------------|
| 422 | `UNDERWRITING_001` | OSFI B-20 GDS > 39% | `assert response.json()["error_code"] == "UNDERWRITING_001"` |
| 422 | `UNDERWRITING_002` | OSFI B-20 TDS > 44% | Verify calculation breakdown in logs |
| 422 | `CMHC_001` | Property value > $1.5M | Assert LTV calculation correct |
| 400 | `FINTRAC_001` | Transaction > $10k without flag | Verify flag forced to `True` |
| 403 | `AUTH_001` | Cross-broker access attempt | Assert isolation enforced |
| 422 | `PIPEDA_001` | SIN in plaintext response | Assert encryption applied |

### 6.3 Structured Error Response Validation

```python
# tests/utils/validators.py
def assert_error_response(response: Response, expected_status: int, expected_code: str):
    """Validate error response structure for all endpoints"""
    assert response.status_code == expected_status
    data = response.json()
    assert "detail" in data
    assert "error_code" in data
    assert data["error_code"] == expected_code
    # PIPEDA: Verify no PII in error messages
    assert "sin" not in data["detail"].lower()
    assert "dob" not in data["detail"].lower()
```

---

## 7. Test Execution Strategy (Additional Section)

### 7.1 Fixture & Mocking Strategy

```python
# tests/conftest.py - Shared Fixtures
@pytest.fixture(scope="function")
async def isolated_db_session():
    """Provides transaction-isolated database session"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.rollback()  # Ensure isolation
        finally:
            await session.close()

@pytest.fixture
def mock_osfi_qualifying_rate(monkeypatch):
    """Mock OSFI stress test rate to 5.25% floor"""
    def mock_max(rate, floor):
        return Decimal("0.0525")
    monkeypatch.setattr("modules.underwriting.services.max", mock_max)

@pytest.fixture
def fintrac_threshold():
    """Provides FINTRAC $10,000 threshold as Decimal"""
    return Decimal("10000.00")
```

### 7.2 Load Testing Requirements

**Tool:** `locust` with FastAPI integration

```python
# tests/load/locustfile.py
class MortgageUnderwritingLoadTest(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def calculate_underwriting(self):
        """Load test underwriting calculation endpoint"""
        self.client.post("/api/v1/underwriting/calculate", json={
            "loan_amount": 500000,
            "property_value": 600000,
            "gross_monthly_income": 8000,
            "other_debt": 500,
            "contract_rate": 0.045
        }, headers={"Authorization": f"Bearer {self.token}"})
    
    @task(1)
    def upload_document(self):
        """Load test document upload with size validation"""
        self.client.post("/api/v1/documents/upload", 
            files={"file": ("test.pdf", b"x" * 9_999_999, "application/pdf")},
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

**Targets:**
- **Baseline:** 100 concurrent users, < 500ms p95 latency
- **Peak:** 500 concurrent users, < 1000ms p95 latency
- **Stress:** 1000 concurrent users, system degrades gracefully

### 7.3 CI/CD Pipeline Integration

```yaml
# .github/workflows/test-pipeline.yml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15.2
        env:
          POSTGRES_DB: mortgage_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    - name: Run migrations on test DB
      run: alembic upgrade head
    - name: Unit tests with coverage
      run: pytest -m unit --cov=modules --cov-fail-under=80 --cov-report=xml
    - name: Integration tests
      run: pytest -m integration --cov-append
    - name: Compliance audit tests
      run: pytest -m compliance --log-cli-level=INFO
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### 7.4 Performance Benchmark Baselines

```python
# tests/performance/baselines.py
PERFORMANCE_BASELINES = {
    "underwriting_calculation": {"max_ms": 200, "target_ms": 100},
    "document_upload_10mb": {"max_ms": 1000, "target_ms": 500},
    "auth_token_generation": {"max_ms": 50, "target_ms": 25},
    "database_query_application_by_id": {"max_ms": 30, "target_ms": 10},
}
```

### 7.5 Accessibility (A11y) Testing Requirements

**Tool:** `axe-core` with Playwright

```python
# tests/a11y/test_accessibility.py
async def test_application_form_a11y(page: Page):
    """Verify accessibility of mortgage application form"""
    await page.goto("/applications/new")
    results = await page.evaluate("""async () => {
        return await axe.run(document, {
            rules: {
                'color-contrast': { enabled: true },
                'label': { enabled: true }
            }
        });
    }""")
    assert len(results["violations"]) == 0, f"Accessibility violations: {results['violations']}"
```

**Coverage:** All user-facing endpoints must pass WCAG 2.1 AA standard.

---

## 8. Test Data Management & Retention

### 8.1 Test Data Lifecycle

```python
# tests/utils/test_data.py
class TestDataManager:
    """Manages test data lifecycle for FINTRAC 5-year retention compliance"""
    
    async def cleanup_test_run(self, test_run_id: uuid.UUID, retention_days: int = 30):
        """
        Soft-delete test data after retention period.
        FINTRAC requires 5-year retention for production;
        test data can be cleaned after 30 days.
        """
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        await db.execute(
            update(Application)
            .where(
                Application.created_at < cutoff,
                Application.environment == "test",
                Application.test_run_id == test_run_id
            )
            .values(deleted_at=datetime.utcnow())
        )
```

### 8.2 Test Isolation Verification

```python
# tests/conftest.py - Verify isolation
@pytest.fixture(autouse=True)
def verify_test_isolation():
    """Pre-test hook to verify database is clean"""
    # Check for leftover test data
    count = await db.execute(select(func.count()).where(Application.environment == "test"))
    assert count == 0, "Test database not clean - isolation violation"
```

---

**WARNING:** This design plan addresses the testing suite infrastructure itself. All test code must comply with the same regulatory requirements as production code, especially regarding PIPEDA (no logging of SIN/DOB) and FINTRAC (test transaction data must follow retention rules even in test environment).