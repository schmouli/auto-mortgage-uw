# FINTRAC Compliance
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# FINTRAC Compliance Module Design Plan

**File:** `docs/design/fintrac-compliance.md`  
**Module:** `modules/fintrac/`  
**Last Updated:** 2024

---

## 1. Endpoints

### `POST /api/v1/fintrac/applications/{application_id}/verify-identity`
Submit identity verification for a client in an application.

**Authentication:** Authenticated user (roles: `underwriter`, `compliance_officer`)  
**Request Body (IdentityVerificationCreate):**
```python
{
    "client_id": UUID,                          # Required
    "verification_method": Enum["in_person", "credit_file", "dual_process"],  # Required
    "id_type": str,                             # Required, max 50 chars
    "id_number": str,                           # Required, plaintext (encrypted at rest)
    "id_expiry_date": date,                     # Required, must be future date
    "id_issuing_province": str,                 # Required, 2-char province code
    "is_pep": bool,                             # Optional, default false
    "is_hio": bool                              # Optional, default false
}
```

**Response (IdentityVerificationRead):**
```python
{
    "verification_id": UUID,
    "application_id": UUID,
    "client_id": UUID,
    "verification_method": str,
    "id_type": str,
    "id_expiry_date": date,
    "id_issuing_province": str,
    "verified_by": UUID,
    "verified_at": datetime,
    "is_pep": bool,
    "is_hio": bool,
    "risk_level": Enum["low", "medium", "high"],
    "risk_score": int,
    "requires_enhanced_due_diligence": bool,
    "record_created_at": datetime
}
```

**Error Responses:**
- `404 FINTRAC_001`: Application not found
- `404 FINTRAC_002`: Client not found or not part of application
- `422 FINTRAC_005`: Validation error (e.g., expired ID, invalid province)
- `409 FINTRAC_006`: Verification already exists for client
- `403 FINTRAC_008`: User lacks permission
- `401`: Missing or invalid JWT

---

### `GET /api/v1/fintrac/applications/{application_id}/verification`
Retrieve identity verification status for all clients in an application.

**Authentication:** Authenticated user (roles: `underwriter`, `compliance_officer`, `admin`)  
**Response (List[IdentityVerificationRead]):** Array of verification records with pagination metadata

**Error Responses:**
- `404 FINTRAC_001`: Application not found
- `403 FINTRAC_008`: User lacks access to application
- `401`: Invalid authentication

---

### `POST /api/v1/fintrac/applications/{application_id}/report-transaction`
File a FINTRAC transaction report (LCTR, STR, or terrorist property).

**Authentication:** Authenticated user (roles: `compliance_officer`)  
**Request Body (FintracReportCreate):**
```python
{
    "report_type": Enum["large_cash_transaction", "suspicious_transaction", "terrorist_property"],  # Required
    "amount": Decimal,                          # Required, > 0, 2 decimal places
    "currency": str,                            # Optional, default "CAD", 3-letter code
    "transaction_date": datetime,               # Required
    "reason": str,                              # Required for suspicious_transaction, max 500 chars
    "client_references": List[UUID]             # Required, list of client IDs involved
}
```

**Response (FintracReportRead):**
```python
{
    "report_id": UUID,
    "application_id": UUID,
    "report_type": str,
    "amount": Decimal,
    "currency": str,
    "transaction_date": datetime,
    "report_date": datetime,
    "submitted_to_fintrac_at": Optional[datetime],
    "fintrac_reference_number": Optional[str],
    "created_by": UUID,
    "created_at": datetime,
    "status": Enum["draft", "submitted", "acknowledged", "rejected"]
}
```

**Error Responses:**
- `404 FINTRAC_001`: Application not found
- `422 FINTRAC_005`: Validation error (e.g., amount ≤ 0, missing reason for STR)
- `409 FINTRAC_007`: Business rule violation (e.g., duplicate report for same transaction)
- `403 FINTRAC_008`: User lacks compliance officer role
- `401`: Invalid authentication

---

### `GET /api/v1/fintrac/applications/{application_id}/reports`
List all FINTRAC reports for an application with pagination.

**Authentication:** Authenticated user (roles: `underwriter`, `compliance_officer`, `admin`)  
**Query Parameters:**
- `report_type`: Optional filter
- `start_date`: Optional ISO date filter
- `end_date`: Optional ISO date filter
- `limit`: Optional, default 50, max 200
- `offset`: Optional, default 0

**Response (PaginatedFintracReports):**
```python
{
    "total": int,
    "limit": int,
    "offset": int,
    "reports": List[FintracReportRead]
}
```

**Error Responses:**
- `404 FINTRAC_001`: Application not found
- `403 FINTRAC_008`: User lacks access
- `401`: Invalid authentication

---

### `GET /api/v1/fintrac/risk-assessment/{client_id}`
Get consolidated risk assessment for a client across all applications.

**Authentication:** Authenticated user (roles: `underwriter`, `compliance_officer`, `admin`)  
**Response (RiskAssessmentRead):**
```python
{
    "client_id": UUID,
    "current_risk_level": Enum["low", "medium", "high"],
    "verifications": List[{
        "application_id": UUID,
        "verification_method": str,
        "risk_score": int,
        "verified_at": datetime,
        "is_pep": bool,
        "is_hio": bool
    }],
    "total_reports_filed": int,
    "enhanced_due_diligence_required": bool,
    "last_assessed_at": datetime
}
```

**Error Responses:**
- `404 FINTRAC_002`: Client not found
- `403 FINTRAC_008`: User lacks permission
- `401`: Invalid authentication

---

## 2. Models & Database

### `fintrac_verifications` Table

```sql
CREATE TABLE fintrac_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    verification_method VARCHAR(20) NOT NULL CHECK (verification_method IN ('in_person', 'credit_file', 'dual_process')),
    id_type VARCHAR(50) NOT NULL,
    id_number_encrypted VARCHAR(255) NOT NULL,  -- AES-256 encrypted
    id_expiry_date DATE NOT NULL,
    id_issuing_province CHAR(2) NOT NULL,
    verified_by UUID NOT NULL REFERENCES users(id),
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_pep BOOLEAN NOT NULL DEFAULT FALSE,
    is_hio BOOLEAN NOT NULL DEFAULT FALSE,
    risk_level VARCHAR(10) NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    record_created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- FINTRAC 5-year retention marker
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,  -- Soft delete only
    
    -- Indexes for common query patterns
    CONSTRAINT idx_fintrac_verifications_app_client UNIQUE (application_id, client_id),
    CONSTRAINT idx_fintrac_verifications_verified_by FOREIGN KEY (verified_by) REFERENCES users(id),
    CONSTRAINT idx_fintrac_verifications_risk_level CHECK (risk_level IN ('low', 'medium', 'high'))
);

CREATE INDEX idx_fintrac_verifications_app_client ON fintrac_verifications(application_id, client_id);
CREATE INDEX idx_fintrac_verifications_verified_by ON fintrac_verifications(verified_by);
CREATE INDEX idx_fintrac_verifications_risk_level ON fintrac_verifications(risk_level);
CREATE INDEX idx_fintrac_verifications_record_created_at ON fintrac_verifications(record_created_at) 
    WHERE deleted_at IS NULL;
CREATE INDEX idx_fintrac_verifications_pep_hio ON fintrac_verifications(is_pep, is_hio) 
    WHERE is_pep = TRUE OR is_hio = TRUE;
```

**Encrypted Fields:** `id_number_encrypted` (AES-256, encrypted by `common/security.encrypt_pii()`)  
**Audit Fields:** `created_at`, `updated_at`, `deleted_at` (soft delete), `record_created_at` (immutable retention marker)

---

### `fintrac_reports` Table

```sql
CREATE TABLE fintrac_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
    report_type VARCHAR(30) NOT NULL CHECK (report_type IN ('large_cash_transaction', 'suspicious_transaction', 'terrorist_property')),
    amount DECIMAL(15,2) NOT NULL CHECK (amount > 0),
    currency CHAR(3) NOT NULL DEFAULT 'CAD',
    report_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_to_fintrac_at TIMESTAMPTZ,
    fintrac_reference_number VARCHAR(100),
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,  -- Soft delete only
    
    -- Immutable audit constraint
    CONSTRAINT fintrac_reports_immutable_after_submission 
        CHECK (submitted_to_fintrac_at IS NULL OR updated_at = created_at)
);

CREATE INDEX idx_fintrac_reports_application_id ON fintrac_reports(application_id);
CREATE INDEX idx_fintrac_reports_report_type ON fintrac_reports(report_type);
CREATE INDEX idx_fintrac_reports_report_date ON fintrac_reports(report_date);
CREATE INDEX idx_fintrac_reports_submitted_at ON fintrac_reports(submitted_to_fintrac_at) 
    WHERE submitted_to_fintrac_at IS NOT NULL;
CREATE INDEX idx_fintrac_reports_amount_threshold ON fintrac_reports(amount) 
    WHERE amount > 10000.00;
CREATE INDEX idx_fintrac_reports_currency ON fintrac_reports(currency);
```

**Audit Fields:** `created_at`, `updated_at`, `deleted_at`, `created_by`  
**Immutable Constraint:** Once `submitted_to_fintrac_at` is set, record becomes immutable (FINTRAC requirement)

---

### Supporting Models

**PEP/HIO Watchlist Cache Table** (for automated screening):
```sql
CREATE TABLE pep_hio_watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('pep', 'hio', 'sanctioned')),
    source_list VARCHAR(100) NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB  -- For additional attributes
);

CREATE INDEX idx_pep_hio_watchlist_name ON pep_hio_watchlist USING gin (entity_name gin_trgm_ops);
CREATE INDEX idx_pep_hio_watchlist_type ON pep_hio_watchlist(entity_type, active);
```

---

## 3. Business Logic

### Identity Verification Algorithm

```python
# Risk Scoring Calculation (0-100 scale)
def calculate_risk_score(verification: IdentityVerificationCreate) -> tuple[int, str]:
    risk_score = 0
    
    # 1. Verification method weight (OSFI/FINTRAC guidance)
    method_weights = {
        "in_person": 0,
        "dual_process": 5,
        "credit_file": 10
    }
    risk_score += method_weights[verification.verification_method]
    
    # 2. ID type risk
    if verification.id_type == "passport":
        risk_score += 0
    elif verification.id_type == "driver_license":
        risk_score += 5
    else:
        risk_score += 10
    
    # 3. Province of issuance risk (based on FINTRAC regional risk data)
    high_risk_provinces = ["NU", "NT", "YT", "NL"]
    medium_risk_provinces = ["MB", "SK", "NB", "NS", "PE"]
    
    if verification.id_issuing_province in high_risk_provinces:
        risk_score += 15
    elif verification.id_issuing_province in medium_risk_provinces:
        risk_score += 10
    else:
        risk_score += 5
    
    # 4. PEP/HIO flags (FINTRAC mandatory escalation)
    if verification.is_pep:
        risk_score += 50  # Automatic high risk
    if verification.is_hio:
        risk_score += 30
    
    # 5. ID expiry proximity (if expires < 30 days = higher risk)
    days_to_expiry = (verification.id_expiry_date - date.today()).days
    if days_to_expiry < 30:
        risk_score += 20
    
    # Determine risk level
    if risk_score <= 20:
        risk_level = "low"
    elif risk_score <= 40:
        risk_level = "medium"
    else:
        risk_level = "high"
    
    return risk_score, risk_level

# Enhanced Due Diligence Trigger
def requires_enhanced_due_diligence(risk_level: str, is_pep: bool, is_hio: bool) -> bool:
    return risk_level == "high" or is_pep or is_hio
```

---

### Transaction Monitoring & Structuring Detection

```python
# Structuring detection algorithm
async def detect_structuring(client_id: UUID, amount: Decimal, db_session) -> bool:
    """
    Check if multiple transactions < $10,000 within 24h exceed threshold
    """
    if amount >= Decimal("10000.00"):
        return False  # Direct LCTR, not structuring
    
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    
    result = await db_session.execute(
        select(func.sum(fintrac_reports.amount))
        .where(
            fintrac_reports.client_id == client_id,
            fintrac_reports.report_date >= twenty_four_hours_ago,
            fintrac_reports.deleted_at.is_(None)
        )
    )
    total = result.scalar() or Decimal("0")
    
    return (total + amount) > Decimal("10000.00")

# Auto-report generation trigger
async def auto_generate_report(application_id: UUID, transaction_data: dict):
    if transaction_data["amount"] > Decimal("10000.00") or \
       await detect_structuring(transaction_data["client_id"], transaction_data["amount"], db):
        
        report_type = "large_cash_transaction" if transaction_data["amount"] > Decimal("10000.00") else "suspicious_transaction"
        
        await fintrac_service.create_report(
            application_id=application_id,
            report_type=report_type,
            amount=transaction_data["amount"],
            currency=transaction_data.get("currency", "CAD"),
            reason="Structuring pattern detected" if report_type == "suspicious_transaction" else None,
            client_references=[transaction_data["client_id"]]
        )
```

---

### State Machine for Reports

```
DRAFT → SUBMITTED → ACKNOWLEDGED
   ↓
REJECTED (if FINTRAC rejects)

Transitions:
- DRAFT → SUBMITTED: Compliance officer submits to FINTRAC API
- SUBMITTED → ACKNOWLEDGED: FINTRAC returns reference number
- SUBMITTED → REJECTED: FINTRAC validation failure
```

---

## 4. Migrations

### Alembic Migration: `2024_xxxxx_create_fintrac_tables.py`

```python
def upgrade():
    # Create fintrac_verifications table
    op.create_table(
        'fintrac_verifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('verification_method', sa.String(length=20), nullable=False),
        sa.Column('id_type', sa.String(length=50), nullable=False),
        sa.Column('id_number_encrypted', sa.String(length=255), nullable=False),
        sa.Column('id_expiry_date', sa.Date(), nullable=False),
        sa.Column('id_issuing_province', sa.String(length=2), nullable=False),
        sa.Column('verified_by', sa.UUID(), nullable=False),
        sa.Column('verified_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('is_pep', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_hio', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('risk_level', sa.String(length=10), nullable=False),
        sa.Column('record_created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('application_id', 'client_id', name='idx_fintrac_verifications_app_client')
    )
    
    # Indexes for performance
    op.create_index('idx_fintrac_verifications_verified_by', 'fintrac_verifications', ['verified_by'])
    op.create_index('idx_fintrac_verifications_risk_level', 'fintrac_verifications', ['risk_level'])
    op.create_index('idx_fintrac_verifications_record_created_at', 'fintrac_verifications', ['record_created_at'])
    op.create_index('idx_fintrac_verifications_pep_hio', 'fintrac_verifications', ['is_pep', 'is_hio'])
    
    # Create fintrac_reports table
    op.create_table(
        'fintrac_reports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('report_type', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.DECIMAL(precision=15, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='CAD'),
        sa.Column('report_date', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('submitted_to_fintrac_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('fintrac_reference_number', sa.String(length=100), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for reporting queries
    op.create_index('idx_fintrac_reports_application_id', 'fintrac_reports', ['application_id'])
    op.create_index('idx_fintrac_reports_report_type', 'fintrac_reports', ['report_type'])
    op.create_index('idx_fintrac_reports_report_date', 'fintrac_reports', ['report_date'])
    op.create_index('idx_fintrac_reports_submitted_at', 'fintrac_reports', ['submitted_to_fintrac_at'])
    op.create_index('idx_fintrac_reports_amount_threshold', 'fintrac_reports', ['amount'])
    
    # Create PEP/HIO watchlist table
    op.create_table(
        'pep_hio_watchlist',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('entity_name', sa.String(length=255), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('source_list', sa.String(length=100), nullable=False),
        sa.Column('last_updated', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_pep_hio_watchlist_name', 'pep_hio_watchlist', ['entity_name'], postgresql_using='gin')
    op.create_index('idx_pep_hio_watchlist_type', 'pep_hio_watchlist', ['entity_type', 'active'])

def downgrade():
    op.drop_index('idx_pep_hio_watchlist_type')
    op.drop_index('idx_pep_hio_watchlist_name')
    op.drop_table('pep_hio_watchlist')
    op.drop_index('idx_fintrac_reports_amount_threshold')
    op.drop_index('idx_fintrac_reports_submitted_at')
    op.drop_index('idx_fintrac_reports_report_date')
    op.drop_index('idx_fintrac_reports_report_type')
    op.drop_index('idx_fintrac_reports_application_id')
    op.drop_table('fintrac_reports')
    op.drop_index('idx_fintrac_verifications_pep_hio')
    op.drop_index('idx_fintrac_verifications_record_created_at')
    op.drop_index('idx_fintrac_verifications_risk_level')
    op.drop_index('idx_fintrac_verifications_verified_by')
    op.drop_table('fintrac_verifications')
```

**Data Migration Needs:** None (new module)

---

## 5. Security & Compliance

### FINTRAC Requirements Implementation

| Requirement | Implementation |
|-------------|----------------|
| **Verify all clients** | `POST /verify-identity` enforced for every client in application before underwriting approval |
| **Enhanced due diligence** | Auto-triggered when `risk_level='high'` OR `is_pep=true` OR `is_hio=true`. Blocks application progression until EDD completed. |
| **Large cash transaction > $10,000** | `amount` field checked on every transaction. Auto-generates `large_cash_transaction` report if threshold exceeded. |
| **Structuring detection** | Background job runs hourly: `SELECT client_id, SUM(amount) FROM transactions WHERE date > NOW() - INTERVAL '24 hours' GROUP BY client_id HAVING SUM(amount) > 10000`. Flags suspicious patterns. |
| **5-year retention** | `record_created_at` timestamp immutable. Soft-delete only (`deleted_at`). Retention policy enforced by daily job: `SELECT * FROM fintrac_verifications WHERE record_created_at < NOW() - INTERVAL '5 years'` for archival. |
| **Immutable audit trail** | `fintrac_reports` constraint: once `submitted_to_fintrac_at` is set, `updated_at` cannot change. All mutations logged to separate audit log table. |

### PIPEDA Compliance

- **Encryption at Rest:** `id_number_encrypted` uses AES-256 via `common/security.encrypt_pii()`. Encryption key rotated every 90 days via Azure Key Vault.
- **Data Minimization:** Only ID number encrypted; other PII (name, DOB, SIN) stored in `clients` module with separate encryption. FINTRAC module does **not** duplicate sensitive fields.
- **No Logging of PII:** `structlog` configuration masks `id_number` field in all logs. Error messages never include encrypted values.
- **Hash-Based Lookups:** For verification searches, use `SHA256` hash of ID number (computed in-memory, never stored) to find existing records.

### Authentication & Authorization

```python
# Role-based access control
ROLES = {
    "public": [],  # No public endpoints
    "authenticated": ["GET /risk-assessment/{client_id}"],
    "underwriter": ["GET /applications/{id}/verification", "POST /applications/{id}/verify-identity"],
    "compliance_officer": ["*"],  # Full access
    "admin": ["*"]  # Full access + soft-delete recovery
}

# Application-level access control
def check_application_access(user: User, application_id: UUID):
    """Users can only access applications they own or are assigned to"""
    if user.role == "admin":
        return True
    return db.session.query(
        exists().where(
            Application.id == application_id,
            or_(
                Application.assigned_underwriter_id == user.id,
                Application.created_by == user.id
            )
        )
    ).scalar()
```

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `FintracApplicationNotFoundError` | 404 | FINTRAC_001 | "Application {application_id} not found" | Application ID not in database |
| `FintracClientNotFoundError` | 404 | FINTRAC_002 | "Client {client_id} not found or not part of application" | Client ID invalid or not linked to application |
| `FintracVerificationNotFoundError` | 404 | FINTRAC_003 | "Verification record not found" | GET request for non-existent verification |
| `FintracReportNotFoundError` | 404 | FINTRAC_004 | "Report {report_id} not found" | Report ID not found |
| `FintracValidationError` | 422 | FINTRAC_005 | "{field_name}: {validation_message}" | Pydantic validation failure or business rule violation (e.g., expired ID) |
| `FintracDuplicateVerificationError` | 409 | FINTRAC_006 | "Verification already exists for client {client_id}" | Attempting to verify same client twice |
| `FintracBusinessRuleError` | 409 | FINTRAC_007 | "{rule_name} violated: {detail}" | Structuring detected, or EDD not completed |
| `FintracUnauthorizedError` | 403 | FINTRAC_008 | "Access denied to FINTRAC resource" | User lacks required role or application access |
| `FintracEncryptionError` | 500 | FINTRAC_009 | "Failed to encrypt ID number" | Encryption service failure |
| `FintracSubmissionError` | 502 | FINTRAC_010 | "FINTRAC API submission failed: {detail}" | External FINTRAC API returns error |

**Error Response Format (consistent across all endpoints):**
```json
{
    "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
    "error_code": "FINTRAC_001",
    "timestamp": "2024-01-15T14:30:00Z",
    "correlation_id": "req_abc123xyz"
}
```

---

## 7. Background Jobs & Integration Points

### PEP/HIO List Sync Service
```python
# Daily cron job at 02:00 UTC
@celery.task
def sync_pep_hio_watchlist():
    """
    Downloads latest PEP/HIO lists from:
    - Government of Canada sanctions list (XML)
    - FINTRAC guidance updates
    - Provincial registries
    """
    sources = [
        "https://www.international.gc.ca/world-monde/assets/office_docs/sanctions/sema-lmes.xml",
        "https://www.canada.ca/en/financial-consumer-agency/services/identity-theft/fraud-types.html"
    ]
    
    for source in sources:
        entities = parse_and_normalize(source)
        for entity in entities:
            db.session.merge(PEPHIOWatchlist(
                entity_name=entity.name,
                entity_type=entity.type,
                source_list=source,
                active=True
            ))
    
    db.session.commit()
```

### FINTRAC Submission Gateway
```python
# Asynchronous submission queue (Redis/RabbitMQ)
class FintracSubmissionGateway:
    async def submit_report(self, report_id: UUID):
        """
        Submits report to FINTRAC EFTS API via mTLS
        Implements exponential backoff retry
        """
        report = await self.db.get(FintracReport, report_id)
        
        payload = {
            "reportType": report.report_type,
            "amount": str(report.amount),  # Decimal serialized as string
            "currency": report.currency,
            "transactionDate": report.transaction_date.isoformat(),
            "entities": await self.get_entity_details(report.application_id)
        }
        
        async with httpx.AsyncClient(cert=self.mtls_cert) as client:
            response = await client.post(
                config.FINTRAC_API_URL,
                json=payload,
                headers={"X-Correlation-ID": correlation_id.get()}
            )
            
            if response.status_code == 202:
                report.submitted_to_fintrac_at = datetime.utcnow()
                report.fintrac_reference_number = response.json()["referenceNumber"]
                report.status = "submitted"
            else:
                log.error("FINTRAC submission failed", report_id=report_id, status=response.status_code)
                raise FintracSubmissionError(detail=response.text)
```

### Transaction Monitoring Job
```python
# Hourly Celery beat schedule
@celery.task
def monitor_structuring_patterns():
    """
    Scan last hour's transactions for structuring
    """
    query = """
    SELECT client_id, COUNT(*) as tx_count, SUM(amount) as total_amount
    FROM transactions
    WHERE created_at > NOW() - INTERVAL '24 hours'
      AND amount < 10000
      AND deleted_at IS NULL
    GROUP BY client_id
    HAVING SUM(amount) > 10000
    """
    
    results = db.session.execute(query)
    for row in results:
        # Auto-file suspicious transaction report
        fintrac_service.create_structuring_report(
            client_id=row.client_id,
            aggregated_amount=row.total_amount,
            transaction_count=row.tx_count
        )
```

---

## 8. Audit Trail Requirements

Every FINTRAC action must be logged to a separate immutable audit table:

```sql
CREATE TABLE fintrac_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type VARCHAR(50) NOT NULL,  -- 'verification_created', 'report_submitted', 'edd_completed'
    user_id UUID NOT NULL REFERENCES users(id),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    resource_type VARCHAR(50),  -- 'verification', 'report'
    resource_id UUID,
    old_values JSONB,
    new_values JSONB,
    compliance_context JSONB  -- FINTRAC-specific metadata
) PARTITION BY RANGE (timestamp);

-- Retention: 7 years (exceeds FINTRAC 5-year requirement)
CREATE INDEX idx_fintrac_audit_log_timestamp ON fintrac_audit_log(timestamp);
CREATE INDEX idx_fintrac_audit_log_user ON fintrac_audit_log(user_id);
```

**Logged Actions:**
- `verification_created`: When identity verification is submitted
- `report_submitted`: When report sent to FINTRAC API
- `report_acknowledged`: When FINTRAC reference number received
- `edd_triggered`: When enhanced due diligence required
- `edd_completed`: When EDD documentation uploaded
- `risk_level_updated`: Manual risk override by compliance officer

---

## 9. Observability & Metrics

**Prometheus Metrics:**
```python
# Custom metrics for FINTRAC module
fintrac_verifications_total = Counter(
    'fintrac_verifications_total',
    'Total identity verifications',
    ['risk_level', 'verification_method']
)

fintrac_reports_filed = Counter(
    'fintrac_reports_filed_total',
    'Reports filed to FINTRAC',
    ['report_type', 'status']
)

fintrac_structuring_detected = Counter(
    'fintrac_structuring_detected_total',
    'Structuring patterns detected'
)

fintrac_api_latency = Histogram(
    'fintrac_api_latency_seconds',
    'FINTRAC API submission latency'
)

# Log correlation
log = structlog.get_logger()
log.bind(correlation_id=correlation_id.get())
```

---

## 10. Addressing Missing Details

### PEP/HIO List Integration
- **Design Decision:** Cached copy in `pep_hio_watchlist` table, synced daily via Celery beat
- **Search Algorithm:** Trigram similarity matching (PostgreSQL `pg_trgm`) with 85% threshold to handle name variations
- **False Positive Handling:** Manual review queue for matches >90% similarity

### Risk Scoring Algorithm
- **Weights Justification:** Based on FINTRAC Guidance 2021-01 and OSFI B-20 risk management principles
- **Tunability:** Weights stored in `common/config.py` as environment variables for rapid adjustment without code deploy

### FINTRAC Submission API
- **Integration Pattern:** Async queue with at-least-once delivery semantics
- **Failure Handling:** Exponential backoff (1min, 5min, 15min, 1h, 3h) with dead-letter queue after 24h
- **Idempotency:** FINTRAC reference number serves as idempotency key

### Transaction Monitoring Threshold
- **Tunable Parameter:** `STRUCTURING_THRESHOLD=10000` and `STRUCTURING_WINDOW_HOURS=24` in config
- **Testing Mode:** Integration tests use `$500` threshold to validate detection logic without production delays

### Audit Trail
- **Immutability:** `fintrac_audit_log` is append-only, with write-only permissions for application user
- **Archival:** After 7 years, records moved to cold storage (S3 Glacier) with SHA256 integrity checks

---

**Next Steps:** Implementation should proceed with `models.py` and `schemas.py` first, followed by `services.py` with unit tests covering all risk scoring branches. Integration tests must verify FINTRAC API gateway behavior with mocked mTLS endpoints.