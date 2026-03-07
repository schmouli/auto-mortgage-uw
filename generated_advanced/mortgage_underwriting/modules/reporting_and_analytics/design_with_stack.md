# Design: Reporting & Analytics
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Reporting & Analytics Module

**File:** `docs/design/reporting-analytics.md`

---

## 1. Endpoints

### `GET /api/v1/reports/pipeline`
**Description**: Retrieve pipeline status summary with stage durations and approval metrics.

**Authentication**: Authenticated (`underwriter`, `manager`, `admin` roles)

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | date | No | Filter start date (ISO 8601) |
| `end_date` | date | No | Filter end date (ISO 8601) |
| `include_declined` | boolean | No | Include declined applications in metrics (default: true) |

**Response Schema**:
```python
class PipelineSummaryResponse(BaseModel):
    period_start: date
    period_end: date
    total_applications: int
    status_breakdown: dict[str, int]  # {"submitted": 45, "underwriting": 12, ...}
    avg_days_per_stage: dict[str, Decimal]  # {"submitted": 1.5, "underwriting": 3.2}
    approval_rate: Decimal  # Percentage (e.g., 78.5)
    decline_reasons_frequency: dict[str, int]  # {"gds_tds": 8, "credit_score": 3}
    gds_tds_violations: int  # Count of applications exceeding OSFI limits
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | `REPORTING_001` | Invalid date range (start > end) |
| 403 | `REPORTING_002` | Insufficient permissions |
| 422 | `REPORTING_003` | Date format validation failed |

---

### `GET /api/v1/reports/volume`
**Description**: Retrieve mortgage volume metrics by period with deal size analytics.

**Authentication**: Authenticated (`underwriter`, `manager`, `admin` roles)

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `period` | enum | Yes | `monthly`, `quarterly`, `ytd` |
| `start_date` | date | No | Custom range start |
| `end_date` | date | No | Custom range end |

**Response Schema**:
```python
class VolumeMetricsResponse(BaseModel):
    period: str
    total_volume: Decimal  # Sum of all loan_amount in period
    average_deal_size: Decimal
    application_count: int
    mortgage_type_breakdown: dict[str, int]  # {"fixed": 120, "variable": 85}
    property_type_breakdown: dict[str, int]  # {"single_family": 150, "condo": 55}
    monthly_trend: list[MonthlyTrendPoint]  # Last 12 months

class MonthlyTrendPoint(BaseModel):
    month: str  # "2024-01"
    volume: Decimal
    application_count: int
    avg_interest_rate: Decimal
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | `REPORTING_004` | Invalid period parameter |
| 403 | `REPORTING_002` | Insufficient permissions |
| 422 | `REPORTING_003` | Date validation failed |

---

### `GET /api/v1/reports/lenders`
**Description**: Retrieve lender performance breakdown with submission and approval metrics.

**Authentication**: Authenticated (`manager`, `admin` roles only)

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lender_id` | uuid | No | Filter by specific lender |
| `min_submissions` | int | No | Minimum submissions threshold (default: 5) |
| `start_date` | date | No | Performance period start |

**Response Schema**:
```python
class LenderPerformanceResponse(BaseModel):
    period_start: date
    period_end: date
    lenders: list[LenderMetrics]

class LenderMetrics(BaseModel):
    lender_id: uuid
    lender_name: str
    total_submissions: int
    approved_count: int
    declined_count: int
    approval_rate: Decimal  # Percentage
    average_interest_rate: Decimal
    average_loan_amount: Decimal
    cmhc_insured_rate: Decimal  # Percentage requiring insurance
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 403 | `REPORTING_005` | Endpoint restricted to managers/admins |
| 404 | `REPORTING_006` | Specified lender not found |

---

### `GET /api/v1/reports/applications/export`
**Description**: Export filtered application data as CSV for external analysis.

**Authentication**: Authenticated (`manager`, `admin`, `compliance_officer` roles)

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | enum | No | Filter by application status |
| `start_date` | date | No | Export date range start |
| `end_date` | date | No | Export date range end |
| `lender_id` | uuid | No | Filter by lender |
| `format` | enum | Yes | `csv` (future: `xlsx`, `json`) |

**Response**: `200 OK` with `Content-Type: text/csv` and `Content-Disposition: attachment`

**CSV Columns** (PIPEDA-compliant, no PII):
```
application_id,status,mortgage_type,property_type,loan_amount,property_value,ltv_ratio,interest_rate,cmhc_insured,created_at,decision_date,lender_name,gds_ratio,tds_ratio
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | `REPORTING_007` | Export would exceed 50,000 records (use date range) |
| 403 | `REPORTING_008` | Export permission denied (FINTRAC audit trigger) |
| 409 | `REPORTING_009` | Export already in progress for user (rate limit) |

**Compliance Note**: Every export generates audit log entry with `created_by`, `filters`, `record_count` for FINTRAC 5-year retention.

---

### `GET /api/v1/reports/fintrac/summary`
**Description**: Generate FINTRAC compliance summary for regulatory reporting.

**Authentication**: Authenticated (`compliance_officer`, `admin` roles only)

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `reporting_period` | enum | Yes | `quarterly`, `annual` |
| `year` | int | Yes | Reporting year (e.g., 2024) |
| `quarter` | int | No | Required if period=quarterly (1-4) |

**Response Schema**:
```python
class FintracSummaryResponse(BaseModel):
    reporting_period: str  # "2024-Q1"
    large_transactions_count: int  # > CAD $10,000
    large_transactions_total: Decimal
    identity_verifications_count: int
    applications_flagged: int
    audit_completeness_score: Decimal  # Percentage of records with full audit trail
    data_retention_status: str  # "compliant" | "needs_attention"
    report_generated_at: datetime
    next_report_due: date
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | `REPORTING_010` | Invalid reporting period parameters |
| 403 | `REPORTING_011` | Compliance role required |
| 503 | `REPORTING_012` | Data warehouse temporarily unavailable |

---

## 2. Models & Database

### New Tables

#### `report_cache`
**Purpose**: Store pre-computed report results for performance optimization.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | |
| `report_type` | VARCHAR(50) | NOT NULL, CHECK IN ('pipeline', 'volume', 'lenders', 'fintrac') | idx_report_type |
| `parameters_hash` | VARCHAR(64) | NOT NULL | idx_params_hash |
| `data` | JSONB | NOT NULL | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | idx_created_at |
| `expires_at` | TIMESTAMP | NOT NULL | idx_expires_at |
| `generated_by` | UUID | NOT NULL, FK → users.id | |

**Indexes**:
- Composite: `(report_type, parameters_hash, expires_at)` for cache lookup
- Partial: `WHERE expires_at > NOW()` for active cache entries

---

#### `report_export_log`
**Purpose**: FINTRAC-mandated audit trail for all data exports.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | |
| `user_id` | UUID | NOT NULL, FK → users.id | idx_user_id |
| `report_type` | VARCHAR(50) | NOT NULL | idx_report_type |
| `filters_applied` | JSONB | NOT NULL | |
| `record_count` | INTEGER | NOT NULL, CHECK >= 0 | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | idx_created_at |
| `ip_address` | INET | NOT NULL | idx_ip_address |
| `retention_until` | DATE | NOT NULL, DEFAULT NOW() + INTERVAL '5 years' | |

**Indexes**:
- Composite: `(created_at, retention_until)` for retention policy queries
- Partial: `WHERE retention_until > CURRENT_DATE` for active records

---

### Materialized Views (Performance Optimization)

#### `mv_application_pipeline_metrics`
**Refresh Strategy**: Incremental refresh every 15 minutes via `pg_cron`

```sql
CREATE MATERIALIZED VIEW mv_application_pipeline_metrics AS
SELECT 
    a.status,
    COUNT(*) as application_count,
    AVG(EXTRACT(EPOCH FROM (COALESCE(a.decision_date, NOW()) - a.created_at))/86400) as avg_days_in_stage,
    COUNT(CASE WHEN a.status = 'approved' THEN 1 END)::DECIMAL / COUNT(*) as approval_rate,
    d.decline_reason,
    COUNT(d.id) as decline_count
FROM applications a
LEFT JOIN application_decisions d ON a.id = d.application_id
WHERE a.created_at >= NOW() - INTERVAL '2 years'
GROUP BY a.status, d.decline_reason;
```

**Indexes**:
- `idx_mv_pipeline_status` ON `(status)`
- `idx_mv_pipeline_decline_reason` ON `(decline_reason)`

---

#### `mv_volume_metrics`
**Refresh Strategy**: Hourly refresh

```sql
CREATE MATERIALIZED VIEW mv_volume_metrics AS
SELECT 
    DATE_TRUNC('month', a.created_at) as period,
    SUM(a.loan_amount) as total_volume,
    AVG(a.loan_amount) as avg_deal_size,
    COUNT(*) as application_count,
    a.mortgage_type,
    a.property_type
FROM applications a
WHERE a.created_at >= NOW() - INTERVAL '5 years'
GROUP BY period, a.mortgage_type, a.property_type;
```

**Indexes**:
- Composite: `(period, mortgage_type, property_type)`

---

#### `mv_lender_performance`
**Refresh Strategy**: Every 30 minutes

```sql
CREATE MATERIALIZED VIEW mv_lender_performance AS
SELECT 
    a.lender_id,
    l.name as lender_name,
    COUNT(*) as total_submissions,
    COUNT(CASE WHEN a.status = 'approved' THEN 1 END) as approved_count,
    COUNT(CASE WHEN a.status = 'declined' THEN 1 END) as declined_count,
    AVG(a.interest_rate) as avg_interest_rate,
    AVG(a.loan_amount) as avg_loan_amount,
    COUNT(CASE WHEN a.cmhc_insured = TRUE THEN 1 END)::DECIMAL / COUNT(*) as cmhc_insured_rate
FROM applications a
JOIN lenders l ON a.lender_id = l.id
WHERE a.created_at >= NOW() - INTERVAL '1 year'
GROUP BY a.lender_id, l.name;
```

**Indexes**:
- Unique: `(lender_id)`
- `idx_mv_lender_performance_submissions` ON `(total_submissions DESC)`

---

## 3. Business Logic

### Pipeline Metrics Calculation Algorithm

```python
async def calculate_pipeline_metrics(start_date: date, end_date: date) -> PipelineSummary:
    # 1. Query materialized view for base metrics
    base_metrics = await session.execute(
        select(mv_application_pipeline_metrics)
        .where(mv_application_pipeline_metrics.c.created_at.between(start_date, end_date))
    )
    
    # 2. Calculate GDS/TDS violations for OSFI compliance audit
    violations = await session.execute(
        select(func.count())
        .select_from(Application)
        .where(
            and_(
                Application.created_at.between(start_date, end_date),
                or_(
                    Application.gds_ratio > 39,
                    Application.tds_ratio > 44
                )
            )
        )
    )
    
    # 3. Compute approval rate with stress test audit logging
    approval_rate = approved_count / total_count if total_count > 0 else 0
    
    # 4. Log calculation breakdown for OSFI auditability
    logger.info("pipeline_metrics_calculated", 
        start_date=start_date, 
        end_date=end_date,
        approval_rate=approval_rate,
        gds_violations=violations,
        qualifying_rate_used="max(contract_rate + 2%, 5.25%)"  # OSFI B-20 audit trail
    )
    
    return PipelineSummary(...)
```

### Volume Metrics Calculation

```python
async def calculate_volume_metrics(period: str) -> VolumeMetricsResponse:
    # Use materialized view for performance
    # Ensure all financial calculations use Decimal
    # Apply FINTRAC filter for large transactions
    large_transaction_threshold = Decimal("10000.00")
    
    volume_data = await session.execute(
        select(
            mv_volume_metrics.c.period,
            func.sum(mv_volume_metrics.c.total_volume).cast(Decimal),
            func.avg(mv_volume_metrics.c.avg_deal_size).cast(Decimal),
            func.sum(mv_volume_metrics.c.application_count)
        )
        .where(
            mv_volume_metrics.c.total_volume >= large_transaction_threshold
        )
        .group_by(mv_volume_metrics.c.period)
    )
    
    # Return aggregated data, no PII
```

### Lender Performance Calculation

```python
async def calculate_lender_performance(min_submissions: int = 5):
    # Query materialized view
    # Filter out lenders with insufficient data (data minimization)
    # Calculate approval rates with precision
    # Include CMHC insurance rates for regulatory reporting
    pass
```

### FINTRAC Summary Logic

```python
async def generate_fintrac_summary(reporting_period: str, year: int, quarter: int = None):
    # 1. Count transactions > $10,000
    large_tx_count = await session.execute(
        select(func.count())
        .where(Application.loan_amount > Decimal("10000.00"))
    )
    
    # 2. Verify identity verification logs exist for all applications
    # 3. Calculate audit completeness score
    # 4. Check 5-year retention compliance
    # 5. Return summary for regulatory filing
    pass
```

### Caching Strategy

- **TTL**: 15 minutes for pipeline, 1 hour for volume, 30 minutes for lender metrics
- **Cache key**: `SHA256(report_type + parameters_hash + user_role)`
- **Invalidation**: Triggered on application status changes via PostgreSQL `NOTIFY` + `LISTEN`

---

## 4. Migrations

### Alembic Migration: `001_create_reporting_tables.py`

```python
def upgrade():
    # Create report_cache table
    op.create_table(
        'report_cache',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('parameters_hash', sa.String(64), nullable=False),
        sa.Column('data', JSONB, nullable=False),
        sa.Column('created_at', TIMESTAMP, nullable=False, server_default=func.now()),
        sa.Column('expires_at', TIMESTAMP, nullable=False),
        sa.Column('generated_by', UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['generated_by'], ['users.id'])
    )
    
    # Create report_export_log table
    op.create_table(
        'report_export_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('filters_applied', JSONB, nullable=False),
        sa.Column('record_count', sa.Integer, nullable=False),
        sa.Column('created_at', TIMESTAMP, nullable=False, server_default=func.now()),
        sa.Column('ip_address', INET, nullable=False),
        sa.Column('retention_until', sa.Date, nullable=False, server_default=func.current_date() + text("INTERVAL '5 years'")),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'])
    )
    
    # Create materialized views
    op.execute("""
        CREATE MATERIALIZED VIEW mv_application_pipeline_metrics AS
        -- SQL from section 2
    """)
    
    # Create indexes
    op.create_index('idx_report_cache_lookup', 'report_cache', ['report_type', 'parameters_hash', 'expires_at'])
    op.create_index('idx_export_log_retention', 'report_export_log', ['created_at', 'retention_until'])
```

### Alembic Migration: `002_create_reporting_indexes.py`

```python
def upgrade():
    # Materialized view indexes
    op.create_index('idx_mv_pipeline_status', 'mv_application_pipeline_metrics', ['status'])
    op.create_index('idx_mv_volume_period', 'mv_volume_metrics', ['period'])
    op.create_index('idx_mv_lender_id', 'mv_lender_performance', ['lender_id'], unique=True)
    
    # Partial indexes for active cache
    op.execute("""
        CREATE INDEX idx_active_cache ON report_cache (report_type, parameters_hash) 
        WHERE expires_at > NOW()
    """)
```

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Audit Logging**: All ratio calculations in reports must log the qualifying rate used (`max(contract_rate + 2%, 5.25%)`) and the stress test application
- **Violation Tracking**: Pipeline report includes `gds_tds_violations` count for regulatory review
- **Immutability**: Report export logs cannot be modified or deleted (FINTRAC overlap)

### FINTRAC Compliance
- **Large Transaction Flagging**: `/reports/fintrac/summary` automatically flags all applications with `loan_amount > CAD $10,000`
- **Export Auditing**: Every call to `/applications/export` creates immutable audit entry with:
  - User ID and IP address
  - Filters applied
  - Record count
  - 5-year retention period
- **Identity Verification**: Summary includes count of identity verification checks performed
- **Data Retention**: `report_export_log.retention_until` enforces 5-year retention policy
- **Access Control**: FINTRAC endpoint restricted to `compliance_officer` role only

### PIPEDA Data Handling
- **PII Exclusion**: No SIN, DOB, full name, or banking details in any report response
- **Aggregation**: All metrics aggregated to prevent individual identification
- **Hash Lookups**: If application-level data needed, use `SHA256(application_id)` for references
- **Data Minimization**: Export CSV includes only underwriting-relevant fields
- **Encryption**: Materialized views stored in encrypted PostgreSQL tablespace

### Authentication & Authorization
| Endpoint | Required Role | MFA Required | Rate Limit |
|----------|---------------|--------------|------------|
| `/pipeline` | underwriter+ | No | 60/min |
| `/volume` | underwriter+ | No | 30/min |
| `/lenders` | manager+ | Yes | 20/min |
| `/export` | manager+ | Yes | 5/min |
| `/fintrac/summary` | compliance_officer+ | Yes | 10/min |

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy

```python
# In modules/reporting/exceptions.py
class ReportingException(AppException):
    """Base exception for reporting module"""
    pass

class ReportNotFoundError(ReportingException):
    """Requested report data not available"""
    pass

class ReportValidationError(ReportingException):
    """Invalid report parameters"""
    pass

class ReportPermissionError(ReportingException):
    """User lacks required role for report"""
    pass

class ReportGenerationError(ReportingException):
    """Backend error during report generation"""
    pass
```

### Error Mapping Table

| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `ReportValidationError` | 400 | `REPORTING_001` | "Invalid parameters: {detail}" | WARNING |
| `ReportPermissionError` | 403 | `REPORTING_002` | "Access denied to {report_type}" | ERROR |
| `ReportNotFoundError` | 404 | `REPORTING_003` | "Report data not found for period" | INFO |
| `ReportGenerationError` | 409 | `REPORTING_004` | "Report generation failed: {reason}" | ERROR |
| `RateLimitExceeded` | 429 | `REPORTING_005` | "Rate limit exceeded: {limit} per minute" | WARNING |

### Structured Error Response Example
```json
{
  "detail": "Invalid parameters: start_date must be before end_date",
  "error_code": "REPORTING_001",
  "module": "reporting",
  "timestamp": "2024-01-15T14:30:00Z",
  "request_id": "corr-1234567890",
  "documentation": "https://api.docs.mortgage.ca/errors/REPORTING_001"
}
```

### Special Compliance Error Cases
- **FINTRAC Data Unavailable**: Returns `503 Service Unavailable` with error code `REPORTING_012` and triggers PagerDuty alert
- **PIPEDA Violation Attempt**: If export request attempts to include SIN/DOB fields, returns `403 Forbidden` with code `REPORTING_013` and logs security event
- **Audit Trail Gap**: If FINTRAC summary detects incomplete audit data, returns `409 Conflict` with code `REPORTING_014` and includes `data_completeness_score`

---

## Performance & Scalability Considerations

1. **Materialized View Refresh**: Use `pg_cron` extension for scheduled refreshes
2. **Cache Warming**: Pre-warm cache for common periods (YTD, last quarter) on startup
3. **Query Timeout**: Set `statement_timeout = 30s` for reporting queries
4. **Read Replica**: Configure dedicated read replica for reporting queries
5. **Pagination**: Export endpoint streams CSV in chunks of 5,000 rows to avoid memory issues
6. **Compression**: Cache JSONB data compressed with `pg_compress` extension

---

## Testing Strategy

### Unit Tests (`tests/unit/test_reporting.py`)
- Mock materialized view queries
- Validate Decimal precision in calculations
- Test error code mappings
- Verify PII exclusion in all response schemas

### Integration Tests (`tests/integration/test_reporting_integration.py`)
- Test against real PostgreSQL materialized views
- Verify FINTRAC audit log creation on export
- Test cache hit/miss behavior
- Validate 5-year retention policy calculation

### Compliance Tests (`tests/integration/test_fintrac_compliance.py`)
- Verify large transaction flagging accuracy
- Confirm export logs are immutable
- Test role-based access control for all endpoints
- Validate OSFI stress test audit logging

---

## Future Enhancements (Out of Scope)

- Custom report builder with drag-and-drop fields
- Real-time WebSocket updates for dashboard
- Scheduled email report delivery
- Machine learning anomaly detection on metrics
- Grafana/Prometheus metrics integration