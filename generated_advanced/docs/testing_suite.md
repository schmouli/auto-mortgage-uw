# Testing Suite
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Testing Suite Design Plan

**File:** `docs/design/testing-suite.md`  
**Module:** Testing Suite  
**Purpose:** Comprehensive test strategy for Canadian Mortgage Underwriting System regulatory compliance

---

## 1. Endpoints

### 1.1 Underwriting Calculation Endpoints

| Method | Path | Test Scenarios | Auth Level |
|--------|------|----------------|------------|
| `POST` | `/api/v1/underwriting/calculate-gds` | Standard calculation, ceiling enforcement (39%), stress test floor validation | Authenticated (Broker) |
| `POST` | `/api/v1/underwriting/calculate-tds` | Standard calculation, ceiling enforcement (44%), stress test floor validation | Authenticated (Broker) |
| `POST` | `/api/v1/underwriting/calculate-ltv` | LTV precision (Decimal), CMHC tier boundaries, $1.5M+ exclusion | Authenticated (Broker) |
| `POST` | `/api/v1/underwriting/qualify` | Full qualification workflow, stress test rate = max(rate+2%, 5.25%) | Authenticated (Broker) |

**Request Schema (Example):**
```json
{
  "gross_monthly_income": "Decimal",
  "mortgage_payment": "Decimal",
  "property_taxes": "Decimal",
  "heating_costs": "Decimal",
  "other_debts": "Decimal",
  "loan_amount": "Decimal",
  "property_value": "Decimal",
  "contract_rate": "Decimal"
}
```

**Response Schema:**
```json
{
  "gds_ratio": "Decimal",
  "tds_ratio": "Decimal",
  "ltv_ratio": "Decimal",
  "qualifying_rate": "Decimal",
  "insurance_required": "bool",
  "insurance_premium": "Decimal|null",
  "passes_gds": "bool",
  "passes_tds": "bool"
}
```

**Error Responses to Test:**
- `422 UNPROCESSABLE_ENTITY` (`UNDERWRITING_002`): Invalid decimal precision or negative values
- `422 UNPROCESSABLE_ENTITY` (`UNDERWRITING_005`): Property value exceeds CMHC cap ($1.5M)

---

### 1.2 FINTRAC Reporting Endpoints

| Method | Path | Test Scenarios | Auth Level |
|--------|------|----------------|------------|
| `POST` | `/api/v1/transactions` | Cash threshold detection ($10,000+), structuring pattern detection | Authenticated (Broker) |
| `GET` | `/api/v1/transactions/{id}/audit` | 5-year retention verification, immutable audit trail | Admin-only |

**Critical Test Cases:**
- Transaction amount = $9,999.99 (no flag)
- Transaction amount = $10,000.00 (flag triggered)
- Multiple transactions $3,000 + $4,000 + $3,500 (structuring detection)
- Verify `created_at` immutability (attempt update → should fail)

---

### 1.3 Authentication Endpoints

| Method | Path | Test Scenarios | Auth Level |
|--------|------|----------------|------------|
| `POST` | `/api/v1/auth/login` | JWT generation, SIN hash validation, password bcrypt | Public |
| `POST` | `/api/v1/auth/refresh` | Token rotation, expiry validation | Authenticated |
| `POST` | `/api/v1/auth/logout` | Token revocation, blacklist | Authenticated |
| `POST` | `/api/v1/auth/introspect` | Token metadata, expiry check | Authenticated |

**Token Lifecycle Tests:**
- Access token expiry (15 min)
- Refresh token expiry (7 days)
- Token refresh limit (max 3 uses)
- Revoked token access denial

---

### 1.4 Document Management Endpoints

| Method | Path | Test Scenarios | Auth Level |
|--------|------|----------------|------------|
| `POST` | `/api/v1/documents/upload` | MIME validation, size limit (10MB), virus scan | Authenticated |
| `GET` | `/api/v1/documents/{id}` | Access control, broker isolation | Authenticated |

**Validation Tests:**
- File size: 10.1MB → `422` (`DOCUMENT_003`)
- MIME type: `application/x-msdownload` → `422` (`DOCUMENT_002`)
- Virus signature → `422` (`DOCUMENT_004`)

---

### 1.5 Application Flow Endpoints

| Method | Path | Test Scenarios | Auth Level |
|--------|------|----------------|------------|
| `POST` | `/api/v1/applications` | Full pipeline, state transitions (draft→submitted→underwriting→approved) | Authenticated (Broker) |
| `GET` | `/api/v1/applications/{id}` | Broker isolation, client access control | Authenticated |
| `PATCH` | `/api/v1/applications/{id}/status` | State machine enforcement, audit logging | Authenticated (Broker) |

**State Machine Tests:**
```
draft → submitted (valid)
submitted → underwriting (valid)
underwriting → approved (valid)
draft → approved (invalid → 409 error)
```

---

## 2. Models & Database

### 2.1 Test Fixture Factories

**Location:** `tests/factories/`

```python
# factories/underwriting_factory.py
class UnderwritingScenarioFactory:
    """Generates compliant and edge-case scenarios"""
    
    @staticmethod
    def create_gds_compliant(gross_income="8333.33", mortgage="2000.00", 
                             taxes="300.00", heating="100.00") -> dict:
        """GDS = 28.8% (compliant)"""
        return {
            "gross_monthly_income": Decimal(gross_income),
            "mortgage_payment": Decimal(mortgage),
            "property_taxes": Decimal(taxes),
            "heating_costs": Decimal(heating)
        }
    
    @staticmethod
    def create_gds_violation() -> dict:
        """GDS = 40.8% (violates 39% ceiling)"""
        return {
            "gross_monthly_income": Decimal("8333.33"),
            "mortgage_payment": Decimal("2800.00"),
            "property_taxes": Decimal("300.00"),
            "heating_costs": Decimal("100.00")
        }

# factories/fintrac_factory.py
class FintracTransactionFactory:
    """Generates FINTRAC reportable scenarios"""
    
    @staticmethod
    def create_structured_transactions() -> list:
        """Returns 3 transactions that sum to $10,500"""
        return [
            {"amount": Decimal("3500.00"), "type": "deposit"},
            {"amount": Decimal("4000.00"), "type": "deposit"},
            {"amount": Decimal("3000.00"), "type": "deposit"}
        ]
```

### 2.2 Database Isolation Strategy

**Test Database:** Separate PostgreSQL 15 instance `mortgage_underwriting_test`

**Isolation Methods:**
```python
# conftest.py
@pytest.fixture(scope="function")
async def db_session():
    """Transactional isolation: each test runs in rollback"""
    async with test_engine.begin() as connection:
        await connection.begin_nested()
        async with AsyncSession(bind=connection) as session:
            yield session
            await session.rollback()
```

**Cleanup Strategy:**
- **Unit tests:** Transaction rollback (no cleanup needed)
- **Integration tests:** Truncate tables in `teardown_module`
- **E2E tests:** Full schema drop/create between runs

### 2.3 Encrypted Field Testing

**Test Encryption Keys:** Separate test key in `.env.test`
```python
# conftest.py
@pytest.fixture
def test_encryption_key():
    """AES-256 test key - never use production keys"""
    return os.getenv("TEST_ENCRYPTION_KEY")

# factories/client_factory.py
class ClientFactory:
    @staticmethod
    def create_with_encrypted_sin(sin="123-456-789"):
        """Stores encrypted SIN, returns plaintext for assertion"""
        encrypted_sin = encrypt_pii(sin, test_encryption_key)
        return {
            "sin_encrypted": encrypted_sin,
            "sin_hash": hashlib.sha256(sin.encode()).hexdigest(),
            "plaintext_sin": sin  # For test assertions only
        }
```

---

## 3. Business Logic

### 3.1 GDS/TDS Calculation Verification Algorithm

**Test Formula:**
```
GDS = (PITH) / gross_monthly_income
PITH = mortgage_payment + property_taxes + heating_costs
Stress test rate = max(contract_rate + 2%, 5.25%)

TDS = (PITH + other_debts) / gross_monthly_income
```

**Test Cases:**
| Scenario | Income | Mortgage | Taxes | Heating | Debts | Contract Rate | Expected GDS | Expected TDS | Passes? |
|----------|--------|----------|-------|---------|-------|---------------|--------------|--------------|---------|
| Standard | $8,333 | $2,000 | $300 | $100 | $500 | 3.5% | 28.8% | 34.8% | Yes |
| Stress Floor | $8,333 | $2,000 | $300 | $100 | $500 | 3.0% | 28.8% | 34.8% | Yes |
| GDS Violation | $8,333 | $2,800 | $300 | $100 | $500 | 3.5% | 38.4% | 44.4% | No (GDS) |
| TDS Violation | $8,333 | $2,000 | $300 | $100 | $1,200 | 3.5% | 28.8% | 42.0% | No (TDS) |

**Stress Test Validation:**
```python
# tests/unit/test_underwriting.py
def test_stress_test_floor():
    """OSFI B-20: qualifying_rate must never be below 5.25%"""
    scenario = UnderwritingScenario(contract_rate=2.5%)  # 2.5+2 = 4.5
    result = calculate_qualifying_rate(scenario)
    assert result == Decimal("5.25")  # Floor enforced
```

### 3.2 CMHC Premium Tier Decision Tree

**Test Logic:**
```
IF LTV > 80% THEN insurance_required = True
LTV = loan_amount / property_value

Premium Tiers:
├─ 80.01-85.00% → 2.80%
├─ 85.01-90.00% → 3.10%
├─ 90.01-95.00% → 4.00%
└─ >95% → Ineligible (test rejection)
```

**Boundary Test Cases:**
```python
# tests/unit/test_underwriting.py
@pytest.mark.parametrize("ltv,premium_rate", [
    (Decimal("80.00"), Decimal("0")),           # No insurance
    (Decimal("80.01"), Decimal("0.0280")),      # Tier 1
    (Decimal("85.00"), Decimal("0.0280")),      # Tier 1 max
    (Decimal("85.01"), Decimal("0.0310")),      # Tier 2
    (Decimal("90.00"), Decimal("0.0310")),      # Tier 2 max
    (Decimal("90.01"), Decimal("0.0400")),      # Tier 3
    (Decimal("95.00"), Decimal("0.0400")),      # Tier 3 max
    (Decimal("95.01"), None)                    # Ineligible
])
def test_cmhc_premium_tiers(ltv, premium_rate):
    # Test implementation
```

### 3.3 State Machine Transition Matrix

**Application States:** `draft → submitted → underwriting → approved/rejected`

**Test Transition Validation:**
```python
# tests/integration/test_application_flow.py
INVALID_TRANSITIONS = [
    ("draft", "approved"),
    ("rejected", "approved"),
    ("approved", "underwriting")
]

@pytest.mark.parametrize("from_status,to_status", INVALID_TRANSITIONS)
def test_invalid_state_transitions(from_status, to_status):
    app = ApplicationFactory(status=from_status)
    with pytest.raises(StateTransitionError) as exc:
        await update_application_status(app.id, to_status)
    assert exc.value.error_code == "APPLICATION_003"
```

---

## 4. Migrations

### 4.1 Test Database Setup Migration

**File:** `alembic/versions/test_setup_001_create_test_schemas.py`

```sql
-- Create test schemas for isolation
CREATE SCHEMA IF NOT EXISTS test_underwriting;
CREATE SCHEMA IF NOT EXISTS test_fintrac;
CREATE SCHEMA IF NOT EXISTS test_auth;

-- Grant permissions to test user
GRANT ALL PRIVILEGES ON SCHEMA test_underwriting TO test_user;
GRANT ALL PRIVILEGES ON SCHEMA test_fintrac TO test_user;
```

### 4.2 Test Data Seeding Migration

**File:** `tests/data/seed_regulatory_test_data.sql`

```sql
-- Seed CMHC LTV boundary test cases
INSERT INTO test_underwriting.ltv_scenarios (loan_amount, property_value, expected_ltv, cmhc_eligible)
VALUES 
    (400000.00, 500000.00, 80.00, true),   -- Boundary: exactly 80%
    (400001.00, 500000.00, 80.01, false),  -- Boundary: just over 80%
    (425000.00, 500000.00, 85.00, true),   -- Tier 1 max
    (450000.00, 500000.00, 90.00, true),   -- Tier 2 max
    (475000.00, 500000.00, 95.00, true),   -- Tier 3 max
    (475001.00, 500000.00, 95.01, false);  -- Ineligible
```

### 4.3 Cleanup Migration (Post-Test)

**File:** `tests/data/truncate_all_test_tables.sql`

```sql
-- Truncate all test tables while preserving structure
TRUNCATE TABLE test_underwriting.applications CASCADE;
TRUNCATE TABLE test_fintrac.transactions CASCADE;
TRUNCATE TABLE test_auth.tokens CASCADE;
TRUNCATE TABLE test_documents.files CASCADE;
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Compliance Testing

**Audit Logging Verification:**
```python
# tests/integration/test_underwriting.py
def test_gds_calculation_audit_trail():
    """Every ratio calculation must be logged for audit"""
    await calculate_gds(scenario)
    
    # Verify structured log output
    log_record = caplog.records[-1]
    assert log_record.correlation_id is not None
    assert "gds_ratio" in log_record.msg
    assert "qualifying_rate" in log_record.msg
    assert log_record.sin is None  # PIPEDA: never log SIN
```

**Stress Test Enforcement:**
```python
def test_qualifying_rate_never_below_floor():
    """OSFI B-20: 5.25% floor must be absolute"""
    for rate in [1.0, 2.0, 3.0, 3.25]:  # All produce <5.25%
        result = calculate_qualifying_rate(rate)
        assert result == Decimal("5.25"), f"Failed for rate {rate}"
```

### 5.2 FINTRAC Compliance Testing

**Immutable Audit Trail Test:**
```python
# tests/unit/test_fintrac.py
def test_transaction_immutability():
    tx = TransactionFactory(amount=Decimal("15000.00"))
    tx.amount = Decimal("9999.00")  # Attempt modification
    
    with pytest.raises(ImmutableAuditError):
        await db_session.commit()
    
    # Verify original still exists
    original = await Transaction.get(tx.id)
    assert original.amount == Decimal("15000.00")
```

**5-Year Retention Test:**
```python
def test_retention_policy_enforcement():
    """Transactions older than 5 years cannot be deleted"""
    old_tx = TransactionFactory(created_at=datetime.now() - timedelta(days=1826))
    
    with pytest.raises(RetentionPolicyError):
        await delete_transaction(old_tx.id)
```

### 5.3 PIPEDA Encryption Testing

**SIN Encryption/Decryption:**
```python
# tests/unit/test_security.py
def test_sin_encryption_at_rest():
    plaintext_sin = "123-456-789"
    encrypted = encrypt_pii(plaintext_sin, encryption_key)
    
    # Verify AES-256 encryption
    assert encrypted != plaintext_sin
    assert len(encrypted) == 44  # Base64 encoded
    
    decrypted = decrypt_pii(encrypted, encryption_key)
    assert decrypted == plaintext_sin

def test_sin_hash_for_lookups():
    """SIN lookups must use SHA256 hash, never plaintext"""
    sin = "123-456-789"
    expected_hash = hashlib.sha256(sin.encode()).hexdigest()
    
    client = ClientFactory(sin=sin)
    assert client.sin_hash == expected_hash
    assert client.sin_encrypted is not None
```

**No PII in Logs Test:**
```python
def test_pii_never_logged():
    """SIN, DOB, income, banking data must never appear in logs"""
    sin = "123-456-789"
    await create_application(sin=sin)
    
    # Search all logs for PII patterns
    for record in caplog.records:
        assert not re.search(r"\d{3}-\d{3}-\d{3}", record.msg)  # SIN pattern
        assert "income" not in record.msg.lower()
```

### 5.4 Access Control Testing

**Broker Isolation Test:**
```python
# tests/integration/test_broker_access.py
def test_broker_cannot_access_other_broker_client():
    broker1 = AuthFactory(role="broker", id="b1")
    broker2 = AuthFactory(role="broker", id="b2")
    client = ClientFactory(broker_id="b1")
    
    # Broker 2 attempts access
    with pytest.raises(AccessDeniedError) as exc:
        await get_client(client.id, current_user=broker2)
    
    assert exc.value.error_code == "AUTH_003"
```

**Client Self-Access Only Test:**
```python
def test_client_can_only_access_own_data():
    client1 = AuthFactory(role="client", id="c1")
    client2 = AuthFactory(role="client", id="c2")
    
    # Client 1 accessing own data → OK
    await get_application(app_id, current_user=client1)
    
    # Client 1 accessing client 2 data → 403
    with pytest.raises(AccessDeniedError):
        await get_application(other_app_id, current_user=client1)
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Underwriting Module Errors

| Exception Class | HTTP Status | Error Code | Message Pattern | Test Scenario |
|-----------------|-------------|------------|-----------------|---------------|
| `UnderwritingNotFoundError` | 404 | `UNDERWRITING_001` | "Underwriting scenario {id} not found" | GET non-existent scenario |
| `UnderwritingValidationError` | 422 | `UNDERWRITING_002` | "{field}: {reason}" | Negative income value |
| `GDSLimitExceededError` | 409 | `UNDERWRITING_003` | "GDS ratio {value}% exceeds 39% limit" | GDS = 40.5% |
| `TDSLimitExceededError` | 409 | `UNDERWRITING_004` | "TDS ratio {value}% exceeds 44% limit" | TDS = 45.2% |
| `CMHCIneligibleError` | 422 | `UNDERWRITING_005` | "Property value ${value} exceeds CMHC cap" | Property = $1,500,001 |
| `InvalidLTVError` | 422 | `UNDERWRITING_006` | "LTV {value}% exceeds maximum 95%" | LTV = 95.01% |

### 6.2 FINTRAC Module Errors

| Exception Class | HTTP Status | Error Code | Message Pattern | Test Scenario |
|-----------------|-------------|------------|-----------------|---------------|
| `TransactionNotFoundError` | 404 | `FINTRAC_001` | "Transaction {id} not found" | Audit lookup failure |
| `StructuringDetectedError` | 409 | `FINTRAC_002` | "Potential structuring detected: {detail}" | 3 deposits in 24h |
| `ImmutableAuditError` | 403 | `FINTRAC_003` | "FINTRAC records cannot be modified" | Attempt update |
| `RetentionPolicyError` | 403 | `FINTRAC_004` | "5-year retention policy prohibits deletion" | Delete old record |

### 6.3 Authentication Module Errors

| Exception Class | HTTP Status | Error Code | Message Pattern | Test Scenario |
|-----------------|-------------|------------|-----------------|---------------|
| `InvalidCredentialsError` | 401 | `AUTH_001` | "Invalid SIN or password" | Wrong password |
| `TokenExpiredError` | 401 | `AUTH_002` | "Token expired at {timestamp}" | Expired JWT |
| `AccessDeniedError` | 403 | `AUTH_003` | "Access denied to resource {resource}" | Cross-broker access |
| `TokenRevokedError` | 401 | `AUTH_004` | "Token has been revoked" | Logged out token |

### 6.4 Document Module Errors

| Exception Class | HTTP Status | Error Code | Message Pattern | Test Scenario |
|-----------------|-------------|------------|-----------------|---------------|
| `InvalidMimeTypeError` | 422 | `DOCUMENT_001` | "MIME type {mime} not allowed" | Upload .exe file |
| `FileSizeExceededError` | 413 | `DOCUMENT_002` | "File size {size} exceeds limit {limit}" | Upload 11MB file |
| `VirusDetectedError` | 422 | `DOCUMENT_003` | "Virus detected in file" | EICAR test file |
| `DocumentNotFoundError` | 404 | `DOCUMENT_004` | "Document {id} not found" | Wrong doc ID |

---

## 7. Test Execution Strategy

### 7.1 Test Markers & Categories

```python
# pytest.ini
[pytest]
markers =
    unit: Unit tests (no DB, isolated)
    integration: Integration tests (DB, async)
    e2e: End-to-end tests (full stack)
    compliance: Regulatory compliance tests (OSFI/FINTRAC/PIPEDA)
    security: Security-specific tests (auth, encryption)
    performance: Load and performance tests
    accessibility: a11y compliance tests
```

### 7.2 CI/CD Pipeline Integration

**GitHub Actions Workflow:**
```yaml
# .github/workflows/test.yml
name: Test Suite

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: uv sync
      - run: uv run pytest -m unit --cov=modules --cov-fail-under=80
      
  integration-tests:
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: mortgage_underwriting_test
    steps:
      - run: uv run pytest -m integration --asyncio-mode=auto
      
  compliance-tests:
    steps:
      - run: uv run pytest -m compliance --log-cli-level=INFO
      - run: uv run pip-audit  # Security scan
      
  e2e-tests:
    steps:
      - run: docker-compose -f docker-compose.test.yml up -d
      - run: ./tests/e2e/run_curl_tests.sh
```

### 7.3 Load Testing Requirements

**Targets:**
- **API Response Time:** P95 < 200ms, P99 < 500ms
- **Throughput:** 100 req/s per endpoint
- **Concurrent Users:** 50 simultaneous brokers
- **Database Connections:** Pool size 20, max overflow 10

**Tool:** `locust` with custom mortgage scenarios
```python
# tests/performance/locustfile.py
class UnderwritingUser(HttpUser):
    @task
    def calculate_gds(self):
        self.client.post("/api/v1/underwriting/calculate-gds", 
                        json=UnderwritingScenarioFactory.create_gds_compliant())
```

### 7.4 Test Data Management

**Factory Boy Integration:**
```python
# factories/base_factory.py
from factory.alchemy import SQLAlchemyModelFactory

class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session = None  # Set in conftest
    
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)
```

**Data Cleanup Hooks:**
```python
# conftest.py
@pytest.fixture(autouse=True)
def cleanup_database():
    """Truncate between integration tests"""
    yield
    async with db_session.begin():
        for table in reversed(Base.metadata.sorted_tables):
            await db_session.execute(table.delete())
```

---

## 8. Missing Details Implementation

### 8.1 Test Fixture & Mocking Strategy

**Mock External Services:**
```python
# tests/unit/mocks/
class MockCMHCApi:
    """Mock CMHC premium calculation API"""
    def calculate_premium(self, ltv):
        tiers = {
            (80.01, 85.00): Decimal("0.0280"),
            (85.01, 90.00): Decimal("0.0310"),
            (90.01, 95.00): Decimal("0.0400")
        }
        return tiers.get(ltv, Decimal("0"))

# conftest.py
@pytest.fixture
def mock_cmhc_client(monkeypatch):
    monkeypatch.setattr("modules.underwriting.services.CMHCClient", MockCMHCApi)
```

### 8.2 Performance Benchmark Baselines

**Baseline Metrics (Stored in `tests/performance/baselines.json`):**
```json
{
  "underwriting_calculate_gds": {"p50": 50, "p95": 150, "p99": 300},
  "fintrac_transaction_create": {"p50": 30, "p95": 80, "p99": 200},
  "auth_token_generate": {"p50": 20, "p95": 60, "p99": 150}
}
```

**Regression Detection:**
```python
# tests/performance/test_baselines.py
def test_performance_regression():
    current = run_benchmark()
    baseline = load_baseline()
    
    assert current.p95 < baseline.p95 * 1.2, "20% performance regression detected"
```

### 8.3 Accessibility (a11y) Testing

**Tool:** `axe-core` via `pytest-axe`
```python
# tests/a11y/test_document_upload.py
def test_document_upload_form_a11y(browser):
    browser.get("/upload")
    results = axe.run(browser)
    
    assert results.violations_count == 0, f"a11y violations: {results.violations}"
```

---

## 9. E2E Test Curl Commands

**File:** `tests/e2e/test_workflows.sh`

```bash
#!/bin/bash
# E2E Workflow: Broker creates application → Underwriting → Approval

# 1. Authenticate broker
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"sin_hash":"'$(echo -n "123-456-789" | sha256sum | cut -d' ' -f1)'","password":"testpass"}' \
  | jq -r '.access_token')

# 2. Create application
APP_ID=$(curl -s -X POST http://localhost:8000/api/v1/applications \
  -H "Authorization: Bearer $TOKEN" \
  -d @tests/data/scenario_gds_compliant.json \
  | jq -r '.application_id')

# 3. Run underwriting
curl -X POST http://localhost:8000/api/v1/underwriting/qualify/$APP_ID \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.passes_gds, .passes_tds, .insurance_required'

# 4. Verify audit log
curl -X GET http://localhost:8000/api/v1/applications/$APP_ID/audit \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.created_by, .created_at'
```

---

## 10. Coverage Gates & Quality Metrics

**Coverage Requirements:**
- **Overall:** 80% minimum
- **Critical Paths:** 100% (GDS/TDS/LTV calculations, auth, FINTRAC)
- **Error Handling:** 90% minimum
- **Compliance Code:** 100%

**Quality Gates in CI:**
```yaml
- name: Check coverage
  run: |
    uv run pytest --cov=modules --cov-report=xml
    coverage report --fail-under=80
    
- name: Verify critical paths
  run: |
    uv run pytest tests/unit/test_underwriting.py --cov=modules.underwriting.services --cov-fail-under=100
```

---

**WARNING:** Test encryption keys must be stored in `.env.test` and `.env.test.example` only. Never commit production keys. All test data must be synthetic and compliant with PIPEDA data minimization principles.