# Design: Reporting & Analytics
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

```markdown
# Reporting & Analytics Module Design

**Module Path:** `mortgage_underwriting/modules/reporting/`  
**Design Doc:** `docs/design/reporting-analytics.md`  
**Feature Slug:** `reporting-analytics`

---

## 1. Endpoints

### 1.1 GET /api/v1/reports/pipeline
**Description:** Retrieve pipeline status summary with stage metrics.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status_filter` | string | No | Comma-separated statuses (e.g., "submitted,underwriting") |
| `start_date` | date | No | ISO 8601 format, defaults to 30 days ago |
| `end_date` | date | No | ISO 8601 format, defaults to today |

**Request Schema:** None (query params only)

**Response Schema (200 OK):**
```python
class PipelineSummaryResponse(BaseModel):
    total_active: int
    by_status: Dict[str, int]  # {"submitted": 45, "underwriting": 32, ...}
    avg_days_per_stage: Dict[str, Decimal]  # {"submitted": Decimal("2.5"), ...}
    approval_rate: Decimal  # Percentage, e.g., Decimal("78.5")
    decline_reasons_frequency: Dict[str, int]  # {"gds_tds": 12, "credit": 8, ...}
    generated_at: datetime
    period_start: date
    period_end: date
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 422 | `REPORTING_002` | Invalid date format or start_date > end_date |
| 401 | `SECURITY_001` | Missing or invalid JWT token |

**Authentication:** Authenticated user (any role)

---

### 1.2 GET /api/v1/reports/volume
**Description:** Retrieve mortgage volume metrics by period.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `period` | enum | Yes | `monthly`, `quarterly`, `ytd` |
| `start_date` | date | No | Required if period=custom |
| `end_date` | date | No | Required if period=custom |

**Request Schema:** None

**Response Schema (200 OK):**
```python
class VolumeMetricsResponse(BaseModel):
    period: str
    total_volume: Decimal  # SUM(loan_amount)
    avg_deal_size: Decimal
    applications_by_type: Dict[str, int]  # {"purchase": 120, "refinance": 45, ...}
    applications_by_property: Dict[str, int]  # {"single_family": 98, "condo": 67, ...}
    monthly_trend: List[MonthlyVolume]  # Last 12 months for line chart
    generated_at: datetime

class MonthlyVolume(BaseModel):
    month: str  # "2024-01"
    volume: Decimal
    count: int
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 422 | `REPORTING_002` | Invalid period value or date range |
| 401 | `SECURITY_001` | Missing or invalid JWT token |

**Authentication:** Authenticated user (any role)

---

### 1.3 GET /api/v1/reports/lenders
**Description:** Retrieve lender performance breakdown.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | int | No | Top N lenders, default 10, max 50 |
| `date_range` | str | No | `30d`, `90d`, `1y`, `all` |

**Request Schema:** None

**Response Schema (200 OK):**
```python
class LenderPerformanceResponse(BaseModel):
    date_range: str
    lenders: List[LenderPerformance]
    generated_at: datetime

class LenderPerformance(BaseModel):
    lender_id: UUID
    lender_name: str
    total_submissions: int
    approved_count: int
    approval_rate: Decimal  # e.g., Decimal("82.3")
    avg_interest_rate: Decimal  # Decimal("5.25")
    total_volume: Decimal
    market_share: Decimal  # Percentage of total volume
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 422 | `REPORTING_002` | Invalid limit or date_range value |
| 401 | `SECURITY_001` | Missing or invalid JWT token |

**Authentication:** Authenticated user (any role)

---

### 1.4 GET /api/v1/reports/applications/export
**Description:** Export filtered applications as CSV (FINTRAC auditable).

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `format` | enum | Yes | `csv` (only supported initially) |
| `status` | string | No | Filter by status |
| `start_date` | date | No | Inclusive |
| `end_date` | date | No | Inclusive |
| `lender_id` | UUID | No | Filter by lender |

**Request Schema:** None

**Response Schema (200 OK):**
- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename="applications_2024-01-15.csv"`
- Body: CSV stream

**CSV Columns (PIPEDA-compliant):**
```csv
application_id,status,mortgage_type,property_type,loan_amount,property_value,ltv_ratio,gds_ratio,tds_ratio,insurance_required,lender_name,created_at,approved_at,decline_reason
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 422 | `REPORTING_002` | Invalid filter parameters |
| 403 | `REPORTING_004` | User lacks EXPORT_REPORTS permission |
| 401 | `SECURITY_001` | Missing or invalid JWT token |

**Authentication:** Authenticated user with `EXPORT_REPORTS` role

**FINTRAC Compliance:**
- Logs `created_by`, `timestamp`, `filter_criteria` to `audit_log` table
- Includes only non-PII fields (SIN/DOB excluded)
- 5-year retention enforced via audit log

---

### 1.5 GET /api/v1/reports/fintrac/summary
**Description:** FINTRAC compliance summary for regulatory reporting.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `period` | enum | Yes | `monthly`, `quarterly`, `annual` |
| `reporting_year` | int | Yes | e.g., 2024 |
| `reporting_month` | int | No | Required for monthly/quarterly |

**Request Schema:** None

**Response Schema (200 OK):**
```python
class FintracSummaryResponse(BaseModel):
    period: str
    total_applications: int
    high_value_transactions: List[HighValueTransaction]  # > CAD $10,000
    identity_verifications: List[IdentityVerification]
    record_retention_status: str  # "compliant" | "expiring_soon" | "expired"
    summary_statistics: Dict[str, int]
    generated_at: datetime

class HighValueTransaction(BaseModel):
    application_id: UUID
    loan_amount: Decimal  # > 10000
    transaction_type: str  # "purchase", "refinance"
    created_at: datetime
    applicant_hash: str  # SHA256 of SIN for tracking

class IdentityVerification(BaseModel):
    application_id: UUID
    verified_at: datetime
    verification_method: str  # "document", "electronic"
    verified_by: str  # User ID
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 422 | `REPORTING_002` | Invalid period or date parameters |
| 403 | `REPORTING_005` | User lacks FINTRAC_VIEWER role |
| 401 | `SECURITY_001` | Missing or invalid JWT token |

**Authentication:** Authenticated user with `FINTRAC_VIEWER` role (admin/compliance)

---

## 2. Models & Database

### 2.1 Existing Models (Enhanced Indexes)

**applications Table:**
```python
# Add composite indexes for reporting queries
Index('idx_applications_status_created_at', 'status', 'created_at')
Index('idx_applications_lender_id_created_at', 'lender_id', 'created_at')
Index('idx_applications_mortgage_type', 'mortgage_type')
Index('idx_applications_property_type', 'property_type')
Index('idx_applications_created_at_loan_amount', 'created_at', 'loan_amount')
Index('idx_applications_loan_amount_high_value', 'loan_amount')  # For > $10K queries
```

**audit_log Table:**
```python
# Ensure immutable audit trail for FINTRAC
class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True)
    table_name: str = Column(String(50), nullable=False)
    record_id: UUID = Column(UUID(as_uuid=True), nullable=False)
    action: str = Column(String(20), nullable=False)  # INSERT, UPDATE, DELETE
    created_by: str = Column(String(100), nullable=False)  # User ID
    created_at: datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    # No updated_at - immutable
    # No deletion allowed
```

### 2.2 New Models

**report_cache Table (Performance Optimization):**
```python
class ReportCache(Base):
    __tablename__ = "report_cache"
    
    cache_key: str = Column(String(255), primary_key=True)  # MD5 of query params
    report_type: str = Column(String(50), nullable=False, index=True)  # pipeline, volume, lenders
    data: dict = Column(JSONB, nullable=False)
    generated_at: datetime = Column(DateTime(timezone=True), nullable=False)
    expires_at: datetime = Column(DateTime(timezone=True), nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), nullable=False)
    updated_at: datetime = Column(DateTime(timezone=True), nullable=False)
    
    Index('idx_report_cache_expires_at', 'expires_at')
```

**report_schedule Table (Scheduled Delivery):**
```python
class ReportSchedule(Base):
    __tablename__ = "report_schedule"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True)
    name: str = Column(String(100), nullable=False)
    report_type: str = Column(String(50), nullable=False)
    schedule: str = Column(String(50), nullable=False)  # cron expression
    recipients: list = Column(ARRAY(String(255)), nullable=False)
    filters: dict = Column(JSONB, default={})
    is_active: bool = Column(Boolean, default=True)
    last_run_at: datetime = Column(DateTime(timezone=True))
    created_by: str = Column(String(100), nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), nullable=False)
    updated_at: datetime = Column(DateTime(timezone=True), nullable=False)
```

### 2.3 Materialized View (Daily Metrics)

```sql
CREATE MATERIALIZED VIEW mv_daily_metrics AS
SELECT 
    DATE(created_at) as metric_date,
    status,
    mortgage_type,
    property_type,
    lender_id,
    COUNT(*) as application_count,
    SUM(loan_amount) as total_volume,
    AVG(loan_amount) as avg_loan_amount
FROM applications
WHERE created_at >= NOW() - INTERVAL '5 years'  -- FINTRAC retention
GROUP BY DATE(created_at), status, mortgage_type, property_type, lender_id;

CREATE UNIQUE INDEX ON mv_daily_metrics (metric_date, status, mortgage_type, property_type, lender_id);
CREATE INDEX ON mv_daily_metrics (metric_date);
```

---

## 3. Business Logic

### 3.1 Metric Calculation Algorithms

**Pipeline Metrics:**
```python
# Approval Rate
approval_rate = (approved_count / total_completed) * 100
where total_completed = approved_count + declined_count + withdrawn_count

# Average Days per Stage
for status in ['submitted', 'underwriting', 'approved', 'declined']:
    avg_days = AVG(
        EXTRACT(EPOCH FROM status_exit_time - status_entry_time) / 86400
    )
    # Status transitions logged in audit_log table

# Decline Reasons Frequency
SELECT decline_reason, COUNT(*) 
FROM applications 
WHERE status = 'declined' 
GROUP BY decline_reason
```

**Volume Metrics:**
```python
# Total Volume (Period)
total_volume = SUM(loan_amount) 
WHERE created_at BETWEEN start_date AND end_date

# Average Deal Size
avg_deal_size = AVG(loan_amount)

# LTV Ratio (per application)
ltv_ratio = (loan_amount / property_value) * 100
# Use Decimal with precision=10, scale=2
```

**Lender Performance:**
```python
# Approval Rate by Lender
approval_rate = (approved_count / total_submissions) * 100

# Average Interest Rate
avg_rate = AVG(interest_rate) 
WHERE status = 'approved'
```

### 3.2 OSFI B-20 Compliance in Reports

All ratio calculations must include stress test verification:
```python
qualifying_rate = max(contract_rate + Decimal('2.0'), Decimal('5.25'))
# GDS = (Principal + Interest + Taxes + Heat) / Gross Monthly Income
# TDS = GDS + Other Debts / Gross Monthly Income
# Enforce: GDS ≤ 39%, TDS ≤ 44%
# Log calculation breakdown: `log.info("gds_calculation", application_id=app_id, gds=gds, tds=tds, qualifying_rate=qualifying_rate)`
```

### 3.3 State Machine for Application Status

Reporting queries must respect the immutable status transition flow:
```
draft → submitted → underwriting → [approved | declined]
      ↘ withdrawn
```
- `audit_log` captures every transition with `created_by`
- Reports only count terminal statuses (`approved`, `declined`, `withdrawn`) in completion metrics

---

## 4. Migrations

### 4.1 New Tables

```python
# migrations/versions/20240115_001_add_reporting_tables.py

def upgrade():
    # report_cache table
    op.create_table('report_cache',
        sa.Column('cache_key', sa.String(255), primary_key=True),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('idx_report_cache_expires_at', 'report_cache', ['expires_at'])
    
    # report_schedule table
    op.create_table('report_schedule',
        sa.Column('id', postgresql.UUID(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('schedule', sa.String(50), nullable=False),
        sa.Column('recipients', postgresql.ARRAY(sa.String(255)), nullable=False),
        sa.Column('filters', postgresql.JSONB(), default={}),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True)),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)
    )

def downgrade():
    op.drop_table('report_schedule')
    op.drop_table('report_cache')
```

### 4.2 Indexes on Existing Tables

```python
# migrations/versions/20240115_002_add_reporting_indexes.py

def upgrade():
    # Application table indexes
    op.create_index('idx_applications_status_created_at', 'applications', ['status', 'created_at'])
    op.create_index('idx_applications_lender_id_created_at', 'applications', ['lender_id', 'created_at'])
    op.create_index('idx_applications_mortgage_type', 'applications', ['mortgage_type'])
    op.create_index('idx_applications_property_type', 'applications', ['property_type'])
    op.create_index('idx_applications_created_at_loan_amount', 'applications', ['created_at', 'loan_amount'])
    op.create_index('idx_applications_loan_amount_high_value', 'applications', ['loan_amount'])
    
    # Audit log index for FINTRAC queries
    op.create_index('idx_audit_log_created_at_table', 'audit_log', ['created_at', 'table_name'])

def downgrade():
    op.drop_index('idx_applications_status_created_at')
    op.drop_index('idx_applications_lender_id_created_at')
    op.drop_index('idx_applications_mortgage_type')
    op.drop_index('idx_applications_property_type')
    op.drop_index('idx_applications_created_at_loan_amount')
    op.drop_index('idx_applications_loan_amount_high_value')
    op.drop_index('idx_audit_log_created_at_table')
```

### 4.3 Materialized View

```sql
-- migrations/versions/20240115_003_create_mv_daily_metrics.sql

CREATE MATERIALIZED VIEW mv_daily_metrics AS
SELECT 
    DATE(created_at) as metric_date,
    status,
    mortgage_type,
    property_type,
    lender_id,
    COUNT(*) as application_count,
    SUM(loan_amount) as total_volume,
    AVG(loan_amount) as avg_loan_amount,
    AVG(interest_rate) as avg_interest_rate
FROM applications
WHERE created_at >= CURRENT_DATE - INTERVAL '5 years'
GROUP BY DATE(created_at), status, mortgage_type, property_type, lender_id;

CREATE UNIQUE INDEX ON mv_daily_metrics (metric_date, status, mortgage_type, property_type, lender_id);
CREATE INDEX ON mv_daily_metrics (metric_date);
CREATE INDEX ON mv_daily_metrics (lender_id);

-- Refresh strategy: Daily at 2 AM via Celery/scheduler
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test Inclusion:** All reports showing GDS/TDS must log the `qualifying_rate` used (max(contract_rate + 2%, 5.25%))
- **Hard Limit Auditing:** Reports must flag applications where GDS > 39% or TDS > 44% for compliance review
- **Audit Log:** Every ratio calculation logged with `application_id`, `timestamp`, `calculated_by`

### 5.2 FINTRAC Requirements
- **High-Value Transactions:** `/reports/fintrac/summary` must identify all applications with `loan_amount > 10000`
- **Immutable Audit Trail:** `audit_log` table is append-only, no updates/deletions
- **5-Year Retention:** All reporting data sources (`applications`, `audit_log`) retained for 5 years minimum
- **Export Auditing:** `/applications/export` logs `created_by`, `timestamp`, `record_count` to `audit_log` with `table_name='report_export'`
- **Identity Verification:** FINTRAC summary includes verification method and timestamp from `applicant_verifications` table

### 5.3 PIPEDA Requirements
- **Data Minimization:** Reports exclude SIN, DOB, income, banking data
- **Encrypted Fields:** SIN/DOB remain encrypted in `applications` table; reports use `applicant_hash` (SHA256) for correlation
- **No PII in Logs:** structlog configuration redacts `sin`, `dob`, `income`, `bank_account` fields
- **Access Controls:** FINTRAC summary restricted to `FINTRAC_VIEWER` role

### 5.4 Authentication & Authorization
| Endpoint | Required Role | Justification |
|----------|---------------|---------------|
| `/reports/pipeline` | `ANALYST` | Standard business metrics |
| `/reports/volume` | `ANALYST` | Standard business metrics |
| `/reports/lenders` | `ANALYST` | Standard business metrics |
| `/reports/applications/export` | `EXPORT_REPORTS` | Sensitive data export capability |
| `/reports/fintrac/summary` | `FINTRAC_VIEWER` | Regulatory compliance data |

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy

```python
# modules/reporting/exceptions.py

class ReportingException(AppException):
    """Base exception for reporting module"""
    pass

class ReportNotFoundError(ReportingException):
    """Requested report data not found"""
    http_status = 404
    error_code = "REPORTING_001"
    message_pattern = "Report {report_type} not found for period {period}"

class ReportValidationError(ReportingException):
    """Invalid query parameters"""
    http_status = 422
    error_code = "REPORTING_002"
    message_pattern = "Invalid parameter {field}: {reason}"

class ReportGenerationError(ReportingException):
    """Failed to generate report due to system error"""
    http_status = 500
    error_code = "REPORTING_003"
    message_pattern = "Report generation failed: {detail}"

class ReportPermissionError(ReportingException):
    """User lacks required permissions"""
    http_status = 403
    error_code = "REPORTING_004"
    message_pattern = "Permission denied: {permission} required"

class FintracAccessError(ReportingException):
    """FINTRAC summary access denied"""
    http_status = 403
    error_code = "REPORTING_005"
    message_pattern = "FINTRAC viewer role required"
```

### 6.2 Error Response Format

All errors return structured JSON:
```json
{
  "detail": "Invalid parameter period: must be monthly, quarterly, or ytd",
  "error_code": "REPORTING_002",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "req-1234567890"
}
```

### 6.3 Edge Cases & Error Handling

| Scenario | Exception | HTTP Status | Log Level |
|----------|-----------|-------------|-----------|
| Invalid date format | `ReportValidationError` | 422 | WARNING |
| Date range exceeds 5 years | `ReportValidationError` | 422 | INFO |
| User requests FINTRAC without role | `FintracAccessError` | 403 | WARNING |
| Database timeout on large export | `ReportGenerationError` | 500 | ERROR |
| Cache miss with fallback success | (none) | 200 | INFO |
| No data for period | `ReportNotFoundError` | 404 | INFO |

---

## 7. Performance Optimization Strategy

### 7.1 Caching Layer
- **TTL:** Pipeline/volume reports cached for 1 hour; lender reports for 4 hours
- **Cache Key:** MD5 hash of query parameters + user role
- **Invalidation:** Cache cleared on `application.status` updates via event listener

### 7.2 Materialized View Refresh
- **Frequency:** Daily at 2 AM (off-peak)
- **Command:** `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_metrics`
- **Fallback:** Direct query if view stale

### 7.3 Query Optimization
- Use `EXISTS` instead of `COUNT(*)` for existence checks
- Partition `applications` table by `created_at` (monthly partitions)
- Set `statement_timeout = 30s` for reporting queries

### 7.4 Asynchronous Export
- Large CSV exports streamed via `StreamingResponse`
- Background task logs completion to `audit_log`
- Email notification sent to requester upon completion

---

## 8. Observability & Monitoring

### 8.1 Metrics (Prometheus)
```
report_generation_duration_seconds{report_type="pipeline"}
report_cache_hit_rate
report_export_records_total
fintrac_summary_requests_total
```

### 8.2 Logging (structlog)
```python
log.info("report_generated", 
         report_type="pipeline", 
         record_count=150, 
         query_time_ms=245,
         correlation_id=correlation_id)

log.warning("report_cache_miss", 
            cache_key="abc123", 
            reason="expired")
```

### 8.3 Tracing (OpenTelemetry)
- Span for each database query
- Span for cache get/set operations
- Span for CSV generation

---

## 9. Future Enhancements (Not in Scope)

- Custom report builder UI with drag-and-drop fields
- Real-time WebSocket updates for dashboard
- gRPC endpoint for internal microservices
- Parquet export format for data lake integration
- Machine learning forecasting for pipeline volume
```