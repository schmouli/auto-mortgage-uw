# Testing Suite
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Testing Suite Module Design

**Design Document**: `docs/design/testing-suite.md`  
**Module ID**: TEST_MGMT  
**Feature Slug**: testing-suite  
**Last Updated**: 2024-01-15

---

## 1. Endpoints

### Test Scenario Management (Admin-only)
| Method | Path | Request Body | Response | Error Codes | Auth |
|--------|------|--------------|----------|-------------|------|
| `POST` | `/api/v1/test/scenarios` | `TestScenarioCreate` (name, description, test_type, fixture_ids, expected_outcomes) | `TestScenarioResponse` (id, name, status) | `TEST_002`, `TEST_005` | Admin |
| `GET` | `/api/v1/test/scenarios/{id}` | - | `TestScenarioResponse` | `TEST_001` | Admin |
| `PUT` | `/api/v1/test/scenarios/{id}` | `TestScenarioUpdate` | `TestScenarioResponse` | `TEST_001`, `TEST_002` | Admin |
| `DELETE` | `/api/v1/test/scenarios/{id}` | - | `204 No Content` | `TEST_001` | Admin |

### Test Execution (Admin-only)
| Method | Path | Request Body | Response | Error Codes | Auth |
|--------|------|--------------|----------|-------------|------|
| `POST` | `/api/v1/test/scenarios/{id}/execute` | `TestExecuteRequest` (environment, coverage_threshold) | `TestExecutionResponse` (execution_id, status) | `TEST_001`, `TEST_003` | Admin |
| `GET` | `/api/v1/test/executions/{id}` | - | `TestExecutionDetail` (status, results, coverage) | `TEST_004` | Admin |

### Test Fixture Management (Admin-only)
| Method | Path | Request Body | Response | Error Codes | Auth |
|--------|------|--------------|----------|-------------|------|
| `POST` | `/api/v1/test/fixtures` | `TestFixtureCreate` (name, data_type, encrypted_payload, pii_markers) | `TestFixtureResponse` (id, name, created_at) | `TEST_002`, `TEST_006` | Admin |
| `GET` | `/api/v1/test/fixtures/{id}/data` | - | `TestFixtureData` (decrypted_data) | `TEST_001`, `TEST_007` | Admin |

### Test Coverage Reporting (Authenticated)
| Method | Path | Request Body | Response | Error Codes | Auth |
|--------|------|--------------|----------|-------------|------|
| `GET` | `/api/v1/test/coverage` | `CoverageQuery` (module, date_range) | `CoverageReport` (percentage, uncovered_lines) | - | Authenticated |

### Public Health Check (Public)
| Method | Path | Request Body | Response | Error Codes | Auth |
|--------|------|--------------|----------|-------------|------|
| `GET` | `/api/v1/test/health` | - | `{ "status": "healthy", "tests_passed": 123 }` | - | Public |

---

## 2. Models & Database

### `test_scenarios` Table
```python
class TestScenario(Base):
    __tablename__ = "test_scenarios"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: str = Column(String(255), nullable=False, index=True)
    description: str = Column(Text, nullable=False)
    test_type: TestType = Column(SQLAlchemyEnum(TestType), nullable=False)  # unit, integration, e2e
    module_target: str = Column(String(100), nullable=False, index=True)  # e.g., "underwriting", "fintrac"
    fixture_ids: List[UUID] = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    expected_outcomes: JSON = Column(JSONB, nullable=False)  # regulatory assertions
    is_regulatory_mandated: bool = Column(Boolean, default=False, nullable=False)
    osfi_compliance_tags: List[str] = Column(ARRAY(String(50)), nullable=False)  # e.g., ["B-20-GDS", "B-20-TDS"]
    
    # Audit fields
    created_at: datetime = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_by: str = Column(String(255), nullable=False)  # User ID
    updated_at: datetime = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    
    # Index for regulatory audits
    __table_args__ = (
        Index('idx_test_scenarios_compliance', 'module_target', 'osfi_compliance_tags'),
    )
```

### `test_results` Table
```python
class TestResult(Base):
    __tablename__ = "test_results"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id: UUID = Column(UUID(as_uuid=True), ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False)
    execution_id: UUID = Column(UUID(as_uuid=True), nullable=False, index=True)
    status: TestStatus = Column(SQLAlchemyEnum(TestStatus), nullable=False)
    execution_time_ms: int = Column(Integer, nullable=False)
    coverage_percentage: Decimal = Column(Numeric(5, 2), nullable=False)  # 80.00 format
    
    # Regulatory verification fields (immutable)
    gds_calculation_verified: bool = Column(Boolean, nullable=False, default=False)
    tds_calculation_verified: bool = Column(Boolean, nullable=False, default=False)
    stress_test_floor_verified: bool = Column(Boolean, nullable=False, default=False)
    cmhc_premium_lookup_verified: bool = Column(Boolean, nullable=False, default=False)
    sin_encryption_verified: bool = Column(Boolean, nullable=False, default=False)
    
    # FINTRAC audit trail for test transactions
    fintrac_test_transactions_flagged: bool = Column(Boolean, nullable=False, default=False)
    
    # PIPEDA compliance verification
    pii_leakage_detected: bool = Column(Boolean, nullable=False, default=False)
    
    # Full result payload (encrypted if contains PII)
    result_payload: bytes = Column(LargeBinary, nullable=False)  # Encrypted with AES-256
    
    created_at: datetime = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_by: str = Column(String(255), nullable=False)
    
    __table_args__ = (
        Index('idx_test_results_execution', 'execution_id', 'status'),
        Index('idx_test_results_regulatory', 'created_at', 'gds_calculation_verified'),
    )
```

### `test_fixtures` Table (PII-encrypted)
```python
class TestFixture(Base):
    __tablename__ = "test_fixtures"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: str = Column(String(255), nullable=False, index=True)
    data_type: FixtureType = Column(SQLAlchemyEnum(FixtureType), nullable=False)  # applicant, property, transaction
    encrypted_payload: bytes = Column(LargeBinary, nullable=False)  # AES-256-GCM encrypted
    
    # PII markers for audit (store field names only, never values)
    pii_fields: List[str] = Column(ARRAY(String(100)), nullable=False)  # e.g., ["sin", "dob", "bank_account"]
    
    # Hash of SIN for lookup validation (never store actual SIN)
    sin_hash: Optional[str] = Column(String(64), index=True)  # SHA256 hex digest
    
    # FINTRAC: Mark if fixture represents >$10K transaction
    is_large_transaction: bool = Column(Boolean, default=False, nullable=False)
    
    created_at: datetime = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_by: str = Column(String(255), nullable=False)
    
    __table_args__ = (
        CheckConstraint(
            "length(encrypted_payload) > 0",
            name="ck_test_fixtures_payload_not_empty"
        ),
    )
```

### `test_coverage_metrics` Table
```python
class TestCoverageMetric(Base):
    __tablename__ = "test_coverage_metrics"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_name: str = Column(String(100), nullable=False, index=True)
    coverage_percentage: Decimal = Column(Numeric(5, 2), nullable=False)
    lines_covered: int = Column(Integer, nullable=False)
    lines_total: int = Column(Integer, nullable=False)
    branch_coverage: Decimal = Column(Numeric(5, 2), nullable=False)
    
    # Regulatory path coverage
    osfi_b20_paths_covered: int = Column(Integer, nullable=False)
    osfi_b20_paths_total: int = Column(Integer, nullable=False)
    fintrac_audit_paths_covered: int = Column(Integer, nullable=False)
    fintrac_audit_paths_total: int = Column(Integer, nullable=False)
    
    created_at: datetime = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        Index('idx_coverage_module_date', 'module_name', 'created_at'),
    )
```

---

## 3. Business Logic

### Test Execution Engine (`services.py`)
```python
class TestExecutionService:
    """
    Orchestrates test runs with regulatory compliance verification.
    """
    
    async def execute_scenario(
        self,
        scenario_id: UUID,
        coverage_threshold: Decimal = Decimal("80.0"),
        environment: str = "staging"
    ) -> TestExecutionResult:
        """
        1. Validate scenario exists and is runnable
        2. Load fixtures with PII decryption
        3. Execute tests in isolated transaction
        4. Verify regulatory calculations:
           - GDS/TDS formula: (PITH + other_debt) / gross_income
           - Stress test: qualifying_rate = max(contract_rate + 2%, 5.25%)
           - LTV: loan_amount / property_value (Decimal precision)
           - CMHC premium: tiered lookup (80.01-85%: 2.80%, etc.)
        5. Check for PII leakage in logs/results
        6. Store encrypted results
        7. Update coverage metrics
        8. FINTRAC: Flag any test transaction > $10K in results
        """
        pass
    
    async def verify_osfi_b20_compliance(
        self,
        test_results: Dict[str, Any]
    ) -> ComplianceVerification:
        """
        Hard limits enforcement validation:
        - GDS ≤ 39% (test must fail if > 39%)
        - TDS ≤ 44% (test must fail if > 44%)
        - Stress test floor 5.25% must be applied
        - All calculations logged with correlation_id for audit
        """
        pass
    
    async def verify_fintrac_audit_trail(
        self,
        test_transaction: Dict[str, Any]
    ) -> AuditVerification:
        """
        Validates immutable audit fields:
        - created_at, created_by never modified
        - Transaction > $10K flagged with transaction_type
        - 5-year retention flag set on all records
        """
        pass
    
    async def verify_piped_encryption(
        self,
        fixture_data: Dict[str, Any]
    ) -> EncryptionVerification:
        """
        Validates:
        - SIN encrypted at rest (AES-256)
        - SIN hash used for lookups (SHA256)
        - DOB encrypted, never in logs
        - No PII in error messages or responses
        """
        pass
```

### Mock Data Generation (`services.py`)
```python
class MockDataGenerator:
    """
    Generates FINTRAC/OSFI-compliant test data with encrypted PII.
    """
    
    async def generate_applicant_fixture(
        self,
        income_range: Tuple[Decimal, Decimal],
        include_sin: bool = True
    ) -> UUID:
        """
        Creates applicant with:
        - Randomized income (Decimal, no float)
        - Encrypted SIN (if requested)
        - Hashed SIN for lookup
        - PII markers for audit
        """
        pass
    
    async def generate_property_fixture(
        self,
        price_range: Tuple[Decimal, Decimal],
        loan_amount: Decimal
    ) -> UUID:
        """
        Creates property with:
        - LTV calculation: loan_amount / property_value
        - CMHC eligibility flag (LTV > 80%)
        - Property value cap verification ($1.5M+ excluded from CMHC)
        """
        pass
```

### Coverage Calculator (`services.py`)
```python
class CoverageCalculator:
    """
    Enforces 80% minimum coverage with regulatory path tracking.
    """
    
    def calculate_coverage(
        self,
        module_name: str
    ) -> CoverageReport:
        """
        Returns:
        - Overall percentage (must be ≥ 80%)
        - OSFI B-20 path coverage (must be 100%)
        - FINTRAC audit path coverage (must be 100%)
        - Branch coverage for decision trees
        """
        pass
    
    def assert_regulatory_path_coverage(self) -> None:
        """
        Raises Test_003 if any OSFI/FINTRAC path is uncovered.
        """
        pass
```

---

## 4. Migrations

### New Tables
```python
# migration: 2024_01_15_create_test_management_tables

def upgrade():
    # test_scenarios table
    op.create_table(
        'test_scenarios',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('test_type', sa.Enum('UNIT', 'INTEGRATION', 'E2E', name='testtype'), nullable=False),
        sa.Column('module_target', sa.String(100), nullable=False),
        sa.Column('fixture_ids', ARRAY(UUID(as_uuid=True)), nullable=False),
        sa.Column('expected_outcomes', JSONB, nullable=False),
        sa.Column('is_regulatory_mandated', sa.Boolean, default=False, nullable=False),
        sa.Column('osfi_compliance_tags', ARRAY(sa.String(50)), nullable=False),
        sa.Column('created_at', TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('updated_at', TIMESTAMP(timezone=True), onupdate=sa.func.now()),
        sa.Index('idx_test_scenarios_compliance', 'module_target', 'osfi_compliance_tags')
    )
    
    # test_results table with immutable audit
    op.create_table(
        'test_results',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('scenario_id', UUID(as_uuid=True), sa.ForeignKey('test_scenarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('execution_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('status', sa.Enum('PASSED', 'FAILED', 'ERROR', name='teststatus'), nullable=False),
        sa.Column('execution_time_ms', sa.Integer, nullable=False),
        sa.Column('coverage_percentage', Numeric(5, 2), nullable=False),
        sa.Column('lines_covered', sa.Integer, nullable=False),
        sa.Column('lines_total', sa.Integer, nullable=False),
        sa.Column('branch_coverage', Numeric(5, 2), nullable=False),
        sa.Column('osfi_b20_paths_covered', sa.Integer, nullable=False),
        sa.Column('osfi_b20_paths_total', sa.Integer, nullable=False),
        sa.Column('fintrac_audit_paths_covered', sa.Integer, nullable=False),
        sa.Column('fintrac_audit_paths_total', sa.Integer, nullable=False),
        sa.Column('gds_calculation_verified', sa.Boolean, default=False, nullable=False),
        sa.Column('tds_calculation_verified', sa.Boolean, default=False, nullable=False),
        sa.Column('stress_test_floor_verified', sa.Boolean, default=False, nullable=False),
        sa.Column('cmhc_premium_lookup_verified', sa.Boolean, default=False, nullable=False),
        sa.Column('sin_encryption_verified', sa.Boolean, default=False, nullable=False),
        sa.Column('fintrac_test_transactions_flagged', sa.Boolean, default=False, nullable=False),
        sa.Column('pii_leakage_detected', sa.Boolean, default=False, nullable=False),
        sa.Column('result_payload', LargeBinary, nullable=False),  # Encrypted
        sa.Column('created_at', TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Index('idx_test_results_execution', 'execution_id', 'status'),
        sa.Index('idx_test_results_regulatory', 'created_at', 'gds_calculation_verified')
    )
    
    # test_fixtures table with PII encryption
    op.create_table(
        'test_fixtures',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('data_type', sa.Enum('APPLICANT', 'PROPERTY', 'TRANSACTION', name='fixturetype'), nullable=False),
        sa.Column('encrypted_payload', LargeBinary, nullable=False),
        sa.Column('pii_fields', ARRAY(sa.String(100)), nullable=False),
        sa.Column('sin_hash', sa.String(64), index=True),
        sa.Column('is_large_transaction', sa.Boolean, default=False, nullable=False),
        sa.Column('created_at', TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.CheckConstraint("length(encrypted_payload) > 0", name="ck_test_fixtures_payload_not_empty")
    )
    
    # test_coverage_metrics table
    op.create_table(
        'test_coverage_metrics',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('module_name', sa.String(100), nullable=False, index=True),
        sa.Column('coverage_percentage', Numeric(5, 2), nullable=False),
        sa.Column('lines_covered', sa.Integer, nullable=False),
        sa.Column('lines_total', sa.Integer, nullable=False),
        sa.Column('branch_coverage', Numeric(5, 2), nullable=False),
        sa.Column('osfi_b20_paths_covered', sa.Integer, nullable=False),
        sa.Column('osfi_b20_paths_total', sa.Integer, nullable=False),
        sa.Column('fintrac_audit_paths_covered', sa.Integer, nullable=False),
        sa.Column('fintrac_audit_paths_total', sa.Integer, nullable=False),
        sa.Column('created_at', TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Index('idx_coverage_module_date', 'module_name', 'created_at')
    )

def downgrade():
    op.drop_table('test_coverage_metrics')
    op.drop_table('test_fixtures')
    op.drop_table('test_results')
    op.drop_table('test_scenarios')
    op.execute('DROP TYPE testtype, teststatus, fixturetype')
```

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Stress Test Validation**: All test scenarios must verify `qualifying_rate = max(contract_rate + 2%, 5.25%)`. Minimum 5.25% floor enforced.
- **Ratio Enforcement**: Unit tests for GDS/TDS must validate hard limits (GDS ≤ 39%, TDS ≤ 44%). Test cases must include boundary values (38.9%, 39.1%, 43.9%, 44.1%).
- **Audit Logging**: Every GDS/TDS calculation in tests must log breakdown with `correlation_id` for regulatory audit.
- **Coverage Mandate**: 100% coverage of all GDS/TDS calculation code paths required (fails build if < 100%).

### FINTRAC Requirements
- **Test Data Flagging**: All test fixtures representing transactions > CAD $10,000 must have `is_large_transaction = True` and include `transaction_type` in metadata.
- **Immutable Audit**: `test_results` table rows are append-only. `created_at` and `created_by` cannot be modified after creation.
- **5-Year Retention**: Test results must be retained for 5 years. Soft delete only (no `DELETE` statements; use `is_archived` flag if needed).
- **Structuring Detection Tests**: Integration tests must simulate transaction structuring scenarios (e.g., multiple $9,999 transactions) and verify detection logic.

### CMHC Requirements
- **LTV Precision**: Tests must use `Decimal` for `loan_amount / property_value` calculation. No float precision loss allowed.
- **Premium Tier Tests**: Coverage for all LTV ranges:
  - 80.01-85% → 2.80% premium
  - 85.01-90% → 3.10% premium
  - 90.01-95% → 4.00% premium
- **Property Cap Tests**: Integration tests must verify properties ≥ $1.5M are correctly excluded from CMHC eligibility.

### PIPEDA Requirements
- **Encryption at Rest**: All PII in `test_fixtures.encrypted_payload` must use AES-256-GCM. Encryption key rotation every 90 days.
- **SIN Handling**: Store only SHA256 hash of SIN in `sin_hash` column for lookup. Never log or return decrypted SIN.
- **Data Minimization**: Test fixtures must only include fields required for the specific test case. Use `pii_fields` array to track what PII exists.
- **Leakage Detection**: Automated scanning in `verify_piped_encryption` to detect SIN/DOB/income in test logs or result payloads.

### Authentication & Authorization
- **Test Endpoints**: All `/api/v1/test/**` endpoints require `admin` role. No broker/client access.
- **Fixture Data Access**: Decryption of `test_fixtures.encrypted_payload` requires `test_data_access` permission with audit log.
- **CI/CD Service Account**: Dedicated service account `test-runner-svc` with `test_execution` role. Token TTL: 1 hour.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `TestScenarioNotFoundError` | 404 | `TEST_001` | "Test scenario {id} not found" | Scenario ID does not exist |
| `TestScenarioValidationError` | 422 | `TEST_002` | "{field}: {reason}" | Invalid fixture IDs or missing required fields |
| `TestExecutionFailedError` | 409 | `TEST_003` | "Test execution failed: {detail}" | Runtime error during test execution |
| `TestExecutionNotFoundError` | 404 | `TEST_004` | "Execution {id} not found" | Execution ID not found |
| `TestCoverageThresholdError` | 409 | `TEST_005` | "Coverage {actual}% below threshold {threshold}%" | Coverage < 80% or regulatory < 100% |
| `TestFixtureValidationError` | 422 | `TEST_006` | "Fixture {id}: {reason}" | Invalid encrypted payload or PII markers |
| `TestFixtureAccessError` | 403 | `TEST_007` | "Access denied to fixture {id}" | Missing decryption permission |
| `PIILeakageDetectedError` | 500 | `TEST_008` | "PII leakage detected in test output" | SIN/DOB found in logs/results |
| `RegulatoryPathUncoveredError` | 409 | `TEST_009` | "OSFI/FINTRAC path uncovered: {path}" | Critical regulatory code not tested |

---

## 7. Test Suite Implementation Details (Supplementary)

### Unit Test Files (Required)

**`tests/unit/test_underwriting.py`**
- **Focus**: GDS/TDS/LTV/stress test calculations
- **Mocking**: `get_async_session()`, `encrypt_pii()`, `verify_token()`
- **Test Cases**:
  - `test_gds_calculation_standard`: Validates GDS = (principal + interest + taxes + heat) / gross_income
  - `test_gds_ceiling_enforcement`: Asserts rejection when GDS > 39%
  - `test_stress_test_floor_5_25`: Verifies qualifying_rate never below 5.25%
  - `test_tds_includes_other_debt`: TDS = GDS + other_debt_payments
  - `test_ltv_decimal_precision`: LTV = loan_amount / property_value (Decimal to 4 places)

**`tests/unit/test_fintrac.py`**
- **Focus**: Cash thresholds, structuring detection, retention
- **Mocking**: Database inserts, `created_at` timestamps
- **Test Cases**:
  - `test_transaction_10k_threshold_flagging`: amount > 10000 → `is_large_transaction = True`
  - `test_structuring_detection_3x9999`: Detects 3 transactions of $9,999 in 24h
  - `test_audit_fields_immutable`: Attempts to modify `created_at` → raises exception
  - `test_5_year_retention_flag`: All records have `retention_until = created_at + 5 years`

**`tests/unit/test_auth.py`**
- **Focus**: Token generation, expiry, refresh, logout
- **Mocking**: `verify_token()`, `encrypt_pii()` for SIN
- **Test Cases**:
  - `test_jwt_token_lifecycle`: Generate → Verify → Refresh → Expire
  - `test_token_expiry_15min`: Token expires after 15 minutes
  - `test_sin_hash_lookup`: SIN → SHA256 hash for database queries
  - `test_logout_token_blacklist`: Revoked tokens cannot be reused

**`tests/unit/test_documents.py`**
- **Focus**: File validation, MIME types, size limits
- **Test Cases**:
  - `test_upload_size_limit_10mb`: Files > 10MB rejected with `DOCUMENT_002`
  - `test_mime_type_whitelist`: Only PDF, JPG, PNG allowed
  - `test_virus_scan_integration`: ClamAV scan called on all uploads
  - `test_document_encryption_at_rest`: File bytes encrypted in storage

### Integration Test Files (Required)

**`tests/integration/test_application_flow.py`**
- **Workflow**: Full pipeline: Application → Document Upload → Underwriting → Approval
- **Test Data**: Uses `MockDataGenerator` with encrypted fixtures
- **Assertions**:
  - GDS/TDS calculated with stress test
  - CMHC premium applied when LTV > 80%
  - SIN encrypted in database, hash used for queries
  - Audit trail created for every state transition

**`tests/integration/test_auth_flow.py`**
- **Workflow**: Register → Login → Refresh → Logout → Access Protected Resource
- **Test Data**: Service account tokens, mock user fixtures
- **Assertions**:
  - Token refresh maintains session
  - Blacklisted tokens rejected
  - PII never in response bodies

**`tests/integration/test_broker_access.py`**
- **Workflow**: Broker A creates application → Broker B attempts access
- **Test Data**: Two broker fixtures with separate client portfolios
- **Assertions**:
  - Broker B cannot access Broker A's applications (403)
  - Broker A can only see own clients in list views
  - Cross-broker ID enumeration returns 404 (not 403) to prevent data leakage

**`tests/integration/test_client_access.py`**
- **Workflow**: Client A views application → Client B attempts access
- **Test Data**: Two client fixtures with separate applications
- **Assertions**:
  - Client isolation enforced at API level
  - Clients cannot access other clients' SIN hashes
  - 404 returned for cross-client access attempts

### End-to-End Test Scripts (curl-based)

**`tests/e2e/test_underwriting_workflow.sh`**
```bash
#!/bin/bash
# E2E test for complete mortgage application with OSFI compliance verification

# Step 1: Create applicant with encrypted SIN
APPLICANT_RESPONSE=$(curl -X POST $API_URL/api/v1/applications \
  -H "Authorization: Bearer $BROKER_TOKEN" \
  -H "Content-Type: application/json" \
  -d @fixtures/applicant_encrypted_sin.json)

# Step 2: Upload documents (size/MIME validation)
DOC_UPLOAD=$(curl -X POST $API_URL/api/v1/documents \
  -H "Authorization: Bearer $BROKER_TOKEN" \
  -F "file=@fixtures/sample_mortgage_document.pdf")

# Step 3: Submit for underwriting (triggers GDS/TDS calculation)
UNDERWRITING_RESULT=$(curl -X POST $API_URL/api/v1/underwriting/calculate \
  -H "Authorization: Bearer $UNDERWRITER_TOKEN" \
  -d '{"application_id": "'$APP_ID'", "contract_rate": "5.5"}')

# Verify stress test floor 5.25% applied
if echo $UNDERWRITING_RESULT | jq '.qualifying_rate' | grep -q "5.25"; then
  echo "✓ Stress test floor validated"
else
  echo "✗ Stress test floor violation"
  exit 1
fi

# Step 4: Verify audit trail created
AUDIT_LOG=$(curl -X GET $API_URL/api/v1/audit/applications/$APP_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN")
```

---

## 8. Missing Details Implementation Strategy

### Test Fixture & Mocking Strategy
- **pytest fixtures**: `conftest.py` defines `mock_encrypted_sin()`, `mock_applicant_fixture()`, `mock_property_fixture()`
- **Factory Pattern**: `TestFixtureFactory` generates valid/invalid test data for boundary testing
- **Encryption Mock**: `mock_encrypt_pii()` returns deterministic ciphertext for reproducible tests
- **Database Isolation**: Each test runs in nested transaction (rollback after test). No test data persists.

### Load Testing Requirements
- **Tool**: Locust (Python) or k6 (TypeScript)
- **Target**: 100 concurrent mortgage applications/minute
- **Endpoints**: 
  - `POST /api/v1/applications` (50% of load)
  - `POST /api/v1/underwriting/calculate` (30% of load)
  - `GET /api/v1/applications/{id}` (20% of load)
- **PII Handling**: Load tests use pre-generated encrypted fixtures; no real PII
- **Metrics**: p95 latency < 500ms, error rate < 0.1%

### Test Data Cleanup & Isolation
- **Database**: `pytest-postgresql` spins up fresh PostgreSQL instance per test session
- **File System**: `tmp_path` fixture for document uploads, auto-cleanup
- **Encryption Keys**: Test key generated per session, destroyed after
- **FINTRAC Compliance**: Test transactions marked with `is_test = True`, excluded from production reports

### CI/CD Pipeline Integration
```yaml
# .github/workflows/test.yml
jobs:
  test:
    steps:
      - run: uv sync --dev
      - run: uv run pytest -m unit --cov=modules --cov-min=80
      - run: uv run pytest -m integration --cov-append
      - run: uv run pytest tests/e2e/  # curl-based
      - run: uv run pip-audit  # Security scan
      - run: |
          # Upload coverage to test_mgmt module
          curl -X POST $API_URL/api/v1/test/coverage \
            -H "Authorization: Bearer $TEST_MGMT_TOKEN" \
            -d @coverage.json
```

### Performance Benchmark Baselines
- **GDS/TDS Calculation**: < 50ms per application
- **SIN Encryption**: < 10ms per operation
- **Document Upload**: < 200ms (≤ 10MB file)
- **Underwriting Decision**: < 300ms end-to-end
- **Test Suite Runtime**: Unit < 2min, Integration < 10min, E2E < 15min

### Accessibility (a11y) Testing
- **Tool**: axe-core (Python) or pa11y (Node)
- **Scope**: All user-facing endpoints (client portal, broker dashboard)
- **Requirements**: WCAG 2.1 AA compliance
- **Integration**: Separate test suite `tests/a11y/` run on staging environment only
- **Exclusions**: Internal test management endpoints (`/api/v1/test/**`) not required for a11y

---

## 9. Test Execution Checklist

**Pre-Commit Hook**:
- [ ] `uv run ruff check .`
- [ ] `uv run mypy modules/`
- [ ] `uv run pytest -m unit --cov-fail-under=80`
- [ ] No `print()` statements in test code (use `structlog`)

**Pre-Merge CI**:
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] E2E curl tests pass against staging
- [ ] `pip-audit` shows 0 vulnerabilities
- [ ] Coverage report uploaded to test_mgmt module
- [ ] OSFI B-20 path coverage = 100%
- [ ] FINTRAC audit path coverage = 100%

**Pre-Deploy to Prod**:
- [ ] Load tests pass (100 req/s for 10 min)
- [ ] PII leakage scan passes (no SIN/DOB in logs)
- [ ] Accessibility scan passes (WCAG 2.1 AA)
- [ ] Performance benchmarks met (p95 latency < 500ms)
- [ ] Test results retained in `test_results` table (5-year retention)

---

**WARNING**: This module is for testing infrastructure only. In production deployments, consider disabling `/api/v1/test/**` endpoints or restricting to VPN-only access.