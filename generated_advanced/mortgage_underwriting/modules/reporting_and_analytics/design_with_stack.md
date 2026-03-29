# Design: Reporting & Analytics
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Reporting & Analytics Module

**Feature Slug:** `reporting-analytics`  
**Document:** `docs/design/reporting-analytics.md`  
**Last Updated:** 2024-01-15  
**Design Owner:** Designer Agent (Complexity: Reasoning)

---

## 1. Endpoints

### 1.1 GET /api/v1/reports/pipeline
**Purpose:** Retrieve pipeline status summary with stage duration and approval metrics.

**Authentication:** Authenticated user (role: `analyst`, `admin`, `compliance_officer`)

**Query Parameters:**
```python
class PipelineReportQuery(BaseModel):
    date_from: date | None = Field(None, description="Filter start date (YYYY-MM-DD)")
    date_to: date | None = Field(None, description="Filter end date (YYYY-MM-DD)")
    lender_id: int | None = Field(None, description="Filter by specific lender")
    include_decline_reasons: bool = Field(True, description="Include decline reason frequency")
```

**Response Schema:**
```python
class PipelineSummaryResponse(BaseModel):
    total_active_by_status: dict[str, int] = Field(..., example={"draft": 15, "underwriting": 42, "approved": 128})
    avg_days_per_stage: dict[str, Decimal] = Field(..., example={"draft": Decimal("2.5"), "underwriting": Decimal("5.8")})
    approval_rate: Decimal = Field(..., description="Percentage (0-100)", example=Decimal("78.5"))
    decline_reasons_frequency: dict[str, int] | None = Field(None, example={"gds_tds_exceeded": 12, "insufficient_income": 8})
    calculated_at: datetime = Field(..., description="Timestamp when metrics were last computed")
    correlation_id: str = Field(..., description="For audit trail tracking")
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | REPORTING_001 | `date_from` > `date_to` or invalid date format |
| 403 | REPORTING_003 | User lacks `analyst` role |
| 422 | REPORTING_002 | No pipeline data found for specified filters |

---

### 1.2 GET /api/v1/reports/volume
**Purpose:** Retrieve volume metrics across time periods with deal size analysis.

**Authentication:** Authenticated user (role: `analyst`, `admin`)

**Query Parameters:**
```python
class VolumeReportQuery(BaseModel):
    period: Literal["monthly", "quarterly", "ytd"] = Field("monthly", description="Aggregation period")
    date_from: date | None = Field(None, description="Override default period start")
    date_to: date | None = Field(None, description="Override default period end")
    property_type: str | None = Field(None, description="Filter by property_type (e.g., 'single_family')")
```

**Response Schema:**
```python
class VolumeMetricsResponse(BaseModel):
    period: str = Field(..., example="2024-Q1")
    total_volume: Decimal = Field(..., description="Sum of all approved mortgage amounts", example=Decimal("125000000.00"))
    avg_deal_size: Decimal = Field(..., description="Average mortgage amount", example=Decimal("425000.50"))
    applications_by_type: dict[str, int] = Field(..., example={"purchase": 45, "refinance": 23, "renewal": 12})
    applications_by_property_type: dict[str, int] = Field(..., example={"condo": 30, "single_family": 38, "multi_unit": 12})
    trend_data: list[VolumeTrendPoint] = Field(..., description="12-month trend for line chart")
    calculated_at: datetime = Field(...)

class VolumeTrendPoint(BaseModel):
    period_label: str = Field(..., example="2024-01")
    volume: Decimal = Field(..., example=Decimal("9800000.00"))
    application_count: int = Field(..., example=42)
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | REPORTING_001 | Invalid period value or date range |
| 403 | REPORTING_003 | User lacks `analyst` role |
| 422 | REPORTING_002 | No volume data available for period |

---

### 1.3 GET /api/v1/reports/lenders
**Purpose:** Retrieve lender performance breakdown with submission and approval metrics.

**Authentication:** Authenticated user (role: `analyst`, `admin`)

**Query Parameters:**
```python
class LenderReportQuery(BaseModel):
    date_from: date = Field(..., description="Required: analysis start date")
    date_to: date = Field(..., description="Required: analysis end date")
    lender_id: int | None = Field(None, description="Filter by specific lender")
    min_submission_threshold: int = Field(5, description="Exclude lenders with fewer submissions")
```

**Response Schema:**
```python
class LenderPerformanceResponse(BaseModel):
    summary_period: dict[str, date] = Field(..., example={"start": "2024-01-01", "end": "2024-03-31"})
    lenders: list[LenderPerformanceItem] = Field(...)
    aggregated_avg_rate: Decimal = Field(..., description="System-wide average contract rate", example=Decimal("5.25"))

class LenderPerformanceItem(BaseModel):
    lender_id: int
    lender_name: str
    submission_count: int
    approval_count: int
    approval_rate: Decimal = Field(..., example=Decimal("82.3"))
    avg_contract_rate: Decimal = Field(..., example=Decimal("5.15"))
    total_volume: Decimal = Field(..., example=Decimal("45000000.00"))
    rank_by_volume: int | None = Field(None, description="Rank position")
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | REPORTING_001 | Missing required date parameters or invalid range |
| 403 | REPORTING_003 | User lacks `analyst` role |
| 422 | REPORTING_002 | No lender data found for period |

---

### 1.4 GET /api/v1/reports/applications/export
**Purpose:** Export filtered application data as CSV/Excel for offline analysis.

**Authentication:** Authenticated user (role: `admin`, `compliance_officer`)

**Query Parameters:**
```python
class ExportQuery(BaseModel):
    format: Literal["csv", "xlsx"] = Field("csv", description="Export file format")
    date_from: date | None = Field(None)
    date_to: date | None = Field(None)
    status: str | None = Field(None, description="Filter by application status")
    lender_id: int | None = Field(None)
    include_pii: bool = Field(False, description="Include encrypted PII fields (requires additional auth)")
    encrypt_file: bool = Field(True, description="Apply AES-256 encryption to output")
```

**Response Schema:**
```python
class ExportResponse(BaseModel):
    download_url: str = Field(..., description="Pre-signed URL to download file (expires in 15 min)")
    expires_at: datetime = Field(..., description="URL expiration timestamp")
    record_count: int = Field(..., description="Number of records exported")
    file_size_bytes: int = Field(..., description="Encrypted file size")
    audit_log_id: int = Field(..., description="Reference ID for compliance audit")
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | REPORTING_001 | Invalid format or contradictory filters (e.g., include_pii=true without proper role) |
| 403 | REPORTING_003 | User lacks `admin` or `compliance_officer` role |
| 409 | REPORTING_004 | Export generation failed (too many records, system error) |
| 422 | REPORTING_002 | No data matches filter criteria |

**Compliance Notes:**
- **PIPEDA:** If `include_pii=true`, file MUST be AES-256 encrypted and download URL must be pre-signed with short expiry
- **FINTRAC:** All exports > $10,000 aggregate volume must be logged with explicit transaction type flag
- **Audit:** Every export creates immutable record in `report_export_audit` table

---

### 1.5 GET /api/v1/reports/fintrac/summary
**Purpose:** Generate FINTRAC compliance summary for large transactions (>$10,000).

**Authentication:** Authenticated user (role: `compliance_officer` only)

**Query Parameters:**
```python
class FintracSummaryQuery(BaseModel):
    date_from: date = Field(..., description="Required: Reporting period start")
    date_to: date = Field(..., description="Required: Reporting period end")
    transaction_type: Literal["mortgage_funding", "all"] = Field("all", description="Filter transaction type")
```

**Response Schema:**
```python
class FintracSummaryResponse(BaseModel):
    reporting_period: dict[str, date] = Field(..., example={"start": "2024-01-01", "end": "2024-01-31"})
    transaction_count: int = Field(..., description="Count of transactions > $10,000 threshold")
    total_amount: Decimal = Field(..., example=Decimal("2500000.00"))
    threshold_violations: list[FintracViolationDetail] = Field(...)
    report_submitted: bool = Field(..., description="Whether this summary was submitted to FINTRAC")
    submitted_at: datetime | None = Field(None)
    audit_trail_id: int = Field(..., description="Immutable audit record ID")

class FintracViolationDetail(BaseModel):
    transaction_id: int
    transaction_date: date
    amount: Decimal
    applicant_hash: str = Field(..., description="SHA256 of SIN for lookup, not PII")
    mortgage_type: str
    property_value: Decimal
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | REPORTING_001 | Invalid date range or exceeds 90-day maximum |
| 403 | REPORTING_003 | User lacks `compliance_officer` role |
| 422 | REPORTING_002 | No large transactions found in period |

**Compliance Notes:**
- **FINTRAC:** Response must be logged to `fintrac_report` table with 5-year retention
- **PIPEDA:** `applicant_hash` is SHA256(SIN) — never return SIN in API response
- **Immutability:** Once `report_submitted=true`, record cannot be modified (append-only)

---

## 2. Models & Database

### 2.1 New ORM Models

#### `reporting_cache` Table
**Purpose:** Store pre-aggregated metrics to improve dashboard performance.

```python
class ReportingCache(Base):
    __tablename__ = "reporting_cache"
    
    id: int = Column(BigInteger, primary_key=True, autoincrement=True)
    metric_name: str = Column(String(100), nullable=False, index=True)  # e.g., 'pipeline_summary'
    metric_value: dict = Column(JSONB, nullable=False)  # Structured metric data
    period_start: date = Column(Date, nullable=False, index=True)
    period_end: date = Column(Date, nullable=False, index=True)
    filters: dict | None = Column(JSONB)  # Optional filter criteria used
    refresh_frequency: str = Column(String(20), default="15min")  # 'realtime', '15min', 'hourly', 'daily'
    
    # Mandatory audit fields
    created_at: datetime = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: datetime = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_reporting_cache_metric_period', 'metric_name', 'period_start', 'period_end'),
        Index('idx_reporting_cache_refresh', 'refresh_frequency', 'updated_at'),
    )
```

#### `fintrac_report` Table
**Purpose:** Immutable audit trail for FINTRAC compliance reports (5-year retention).

```python
class FintracReport(Base):
    __tablename__ = "fintrac_report"
    
    id: int = Column(BigInteger, primary_key=True, autoincrement=True)
    reporting_period_start: date = Column(Date, nullable=False, index=True)
    reporting_period_end: date = Column(Date, nullable=False, index=True)
    transaction_count: int = Column(Integer, nullable=False)
    total_amount: Decimal = Column(Numeric(15, 2), nullable=False)
    report_data: dict = Column(JSONB, nullable=False)  # Complete snapshot of violations
    submitted_at: datetime | None = Column(TIMESTAMP(timezone=True))
    submitted_by: int | None = Column(Integer, ForeignKey("users.id"))  # Who submitted to FINTRAC
    
    # Immutable audit fields (no updated_at)
    created_at: datetime = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_by: int = Column(Integer, ForeignKey("users.id"), nullable=False)  # Who generated the report
    
    __table_args__ = (
        CheckConstraint("transaction_count >= 0", name="chk_fintrac_transaction_count_non_negative"),
        Index('idx_fintrac_period', 'reporting_period_start', 'reporting_period_end', unique=True),
    )
```

#### `report_export_audit` Table
**Purpose:** Track all data exports for PIPEDA and FINTRAC compliance.

```python
class ReportExportAudit(Base):
    __tablename__ = "report_export_audit"
    
    id: int = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    report_type: str = Column(String(50), nullable=False)  # 'pipeline', 'volume', 'lenders', 'fintrac'
    filters_used: dict = Column(JSONB, nullable=False)
    record_count: int = Column(Integer, nullable=False)
    file_format: str = Column(String(10), nullable=False)  # 'csv', 'xlsx'
    file_size_bytes: int = Column(BigInteger, nullable=False)
    file_checksum: str = Column(String(64), nullable=False)  # SHA256 of encrypted file
    encrypted: bool = Column(Boolean, default=True)
    download_url_expiry: datetime = Column(TIMESTAMP(timezone=True), nullable=False)
    
    # Immutable audit fields
    created_at: datetime = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    # No updated_at - append only for 5-year retention
    
    __table_args__ = (
        Index('idx_export_audit_user_date', 'user_id', 'created_at'),
        Index('idx_export_audit_report_type', 'report_type', 'created_at'),
    )
```

### 2.2 Materialized Views (for performance)

```sql
-- View: mv_pipeline_metrics
CREATE MATERIALIZED VIEW mv_pipeline_metrics AS
SELECT 
    status,
    COUNT(*) as application_count,
    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))/86400.0)::DECIMAL(10,2) as avg_days_in_stage
FROM applications
WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY status;

CREATE UNIQUE INDEX ON mv_pipeline_metrics (status);
CREATE INDEX ON mv_pipeline_metrics (application_count);

-- View: mv_volume_metrics
CREATE MATERIALIZED VIEW mv_volume_metrics AS
SELECT 
    DATE_TRUNC('month', funding_date) as period,
    COUNT(*) as application_count,
    SUM(loan_amount) as total_volume,
    AVG(loan_amount) as avg_deal_size
FROM applications
WHERE status = 'funded' AND funding_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY period
ORDER BY period;

CREATE UNIQUE INDEX ON mv_volume_metrics (period);

-- View: mv_lender_performance
CREATE MATERIALIZED VIEW mv_lender_performance AS
SELECT 
    lender_id,
    COUNT(*) as submission_count,
    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approval_count,
    (SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))::DECIMAL(5,2) as approval_rate,
    AVG(contract_rate) as avg_contract_rate,
    SUM(loan_amount) as total_volume
FROM applications
WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY lender_id;

CREATE UNIQUE INDEX ON mv_lender_performance (lender_id);
CREATE INDEX ON mv_lender_performance (total_volume DESC);
```

### 2.3 Indexes on Existing Tables

```sql
-- applications table (existing)
CREATE INDEX IF NOT EXISTS idx_applications_status_created ON applications(status, created_at);
CREATE INDEX IF NOT EXISTS idx_applications_lender_status ON applications(lender_id, status);
CREATE INDEX IF NOT EXISTS idx_applications_funding_date ON applications(funding_date) WHERE status = 'funded';

-- transactions table (for FINTRAC queries)
CREATE INDEX IF NOT EXISTS idx_transactions_amount_date ON transactions(amount, transaction_date) 
WHERE amount > 10000.00;

-- audit_logs table
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_action ON audit_logs(created_at, action_type);
```

---

## 3. Business Logic

### 3.1 Metric Calculation Algorithms

#### Pipeline Metrics
```python
# Pseudo-algorithm for pipeline summary
def calculate_pipeline_metrics(date_from: date, date_to: date, lender_id: int | None):
    """
    OSFI B-20 Compliance: Log all ratio calculations for rejected applications
    """
    base_query = """
        SELECT 
            status,
            COUNT(*) as count,
            AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))/86400.0) as avg_days
        FROM applications
        WHERE created_at BETWEEN :date_from AND :date_to
        {lender_filter}
        GROUP BY status
    """
    
    # For decline reasons, join with underwriting_decisions table
    decline_query = """
        SELECT 
            decline_reason,
            COUNT(*) as frequency
        FROM underwriting_decisions
        WHERE decision = 'declined' 
          AND created_at BETWEEN :date_from AND :date_to
        GROUP BY decline_reason
    """
    
    approval_rate = """
        SELECT 
            (SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))::DECIMAL(5,2)
        FROM applications
        WHERE created_at BETWEEN :date_from AND :date_to
        {lender_filter}
    """
    
    # Log calculation breakdown for audit (OSFI B-20 requirement)
    log.info("pipeline_metrics_calculated", 
             date_from=date_from, date_to=date_to, lender_id=lender_id,
             correlation_id=get_correlation_id())
```

#### Volume Metrics
```python
# Use materialized view for performance, fallback to dynamic query
def get_volume_metrics(period: str, date_from: date | None, date_to: date | None):
    """
    Calculate total mortgage volume with CMHC premium adjustments
    All financial values use Decimal to prevent precision loss
    """
    if period == "ytd":
        start_date = date(date.today().year, 1, 1)
    elif period == "quarterly":
        # Calculate current quarter start
        ...
    
    query = """
        SELECT 
            mortgage_type,
            property_type,
            COUNT(*) as app_count,
            SUM(loan_amount + cmhc_premium_amount) as total_volume
        FROM applications
        WHERE funding_date BETWEEN :start AND :end
          AND status = 'funded'
        GROUP BY ROLLUP(mortgage_type, property_type)
    """
    
    # CMHC premium calculation must use LTV tiers
    # LTV = loan_amount / property_value (Decimal division)
    # Premium tiers: 80.01-85% = 2.80%, 85.01-90% = 3.10%, 90.01-95% = 4.00%
```

#### Lender Performance
```python
def calculate_lender_performance(date_from: date, date_to: date, min_threshold: int):
    """
    Aggregates lender metrics with statistical significance filtering
    """
    query = """
        SELECT 
            l.id as lender_id,
            l.name as lender_name,
            COUNT(a.id) as submissions,
            SUM(CASE WHEN a.status = 'approved' THEN 1 ELSE 0 END) as approvals,
            AVG(a.contract_rate)::DECIMAL(5,3) as avg_rate,
            SUM(a.loan_amount) as total_volume
        FROM lenders l
        LEFT JOIN applications a ON l.id = a.lender_id
        WHERE a.created_at BETWEEN :date_from AND :date_to
        GROUP BY l.id, l.name
        HAVING COUNT(a.id) >= :min_threshold
        ORDER BY total_volume DESC
    """
    
    # Calculate approval rate as Decimal
    # approval_rate = (approvals / submissions) * 100
```

#### FINTRAC Summary
```python
def generate_fintrac_summary(date_from: date, date_to: date):
    """
    FINTRAC Compliance: Identify all transactions > CAD $10,000
    Creates immutable audit record in fintrac_report table
    """
    query = """
        SELECT 
            t.id,
            t.transaction_date,
            t.amount,
            a.sin_hash,  -- SHA256 hash, not PII
            a.mortgage_type,
            a.property_value
        FROM transactions t
        JOIN applications a ON t.application_id = a.id
        WHERE t.amount > 10000.00
          AND t.transaction_date BETWEEN :date_from AND :date_to
          AND t.transaction_type IN ('mortgage_funding', 'down_payment')
        ORDER BY t.amount DESC
    """
    
    # Calculate aggregates
    total_count = len(results)
    total_amount = sum(r.amount for r in results)
    
    # Create immutable audit record BEFORE returning response
    audit_record = FintracReport(
        reporting_period_start=date_from,
        reporting_period_end=date_to,
        transaction_count=total_count,
        total_amount=total_amount,
        report_data={"violations": [r._asdict() for r in results]},
        created_by=current_user.id
    )
    # Insert with no updated_at field
```

### 3.2 State Machine for Reports
Reports do not have a traditional state machine, but exports follow this lifecycle:
```
requested → generating → ready → downloaded → expired
```
- `requested`: User initiates export, audit log created
- `generating`: Async worker processes query and encrypts file
- `ready`: Pre-signed URL available for download
- `downloaded`: User successfully downloaded (event logged)
- `expired`: URL expired after 15 minutes, file deleted from temp storage

### 3.3 Validation Rules
- **Date Range Limits:** Maximum 90 days for FINTRAC, 12 months for volume trends
- **Rate Precision:** All rates returned as Decimal with 3 decimal places
- **Volume Threshold:** Exclude lenders with < 5 submissions to protect privacy
- **Export Size Limit:** Maximum 50,000 records per export to prevent timeouts
- **PII Access:** `include_pii=true` requires `compliance_officer` role AND MFA verification

---

## 4. Migrations

### 4.1 New Tables

**Migration ID:** `202401150001_create_reporting_tables.py`

```python
def upgrade():
    # reporting_cache table
    op.create_table(
        'reporting_cache',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('metric_name', sa.String(100), nullable=False, index=True),
        sa.Column('metric_value', postgresql.JSONB, nullable=False),
        sa.Column('period_start', sa.Date, nullable=False, index=True),
        sa.Column('period_end', sa.Date, nullable=False, index=True),
        sa.Column('filters', postgresql.JSONB, nullable=True),
        sa.Column('refresh_frequency', sa.String(20), server_default='15min'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('idx_reporting_cache_metric_period', 'reporting_cache', ['metric_name', 'period_start', 'period_end'])
    op.create_index('idx_reporting_cache_refresh', 'reporting_cache', ['refresh_frequency', 'updated_at'])

    # fintrac_report table (immutable)
    op.create_table(
        'fintrac_report',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('reporting_period_start', sa.Date, nullable=False, index=True),
        sa.Column('reporting_period_end', sa.Date, nullable=False, index=True),
        sa.Column('transaction_count', sa.Integer, nullable=False),
        sa.Column('total_amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('report_data', postgresql.JSONB, nullable=False),
        sa.Column('submitted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('submitted_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
    )
    op.create_unique_constraint('uq_fintrac_period', 'fintrac_report', ['reporting_period_start', 'reporting_period_end'])
    op.create_check_constraint('chk_fintrac_transaction_count_non_negative', 'fintrac_report', 'transaction_count >= 0')

    # report_export_audit table (immutable)
    op.create_table(
        'report_export_audit',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('filters_used', postgresql.JSONB, nullable=False),
        sa.Column('record_count', sa.Integer, nullable=False),
        sa.Column('file_format', sa.String(10), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger, nullable=False),
        sa.Column('file_checksum', sa.String(64), nullable=False),
        sa.Column('encrypted', sa.Boolean, server_default='true'),
        sa.Column('download_url_expiry', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_export_audit_user_date', 'report_export_audit', ['user_id', 'created_at'])
    op.create_index('idx_export_audit_report_type', 'report_export_audit', ['report_type', 'created_at'])
```

### 4.2 Materialized Views

**Migration ID:** `202401150002_create_reporting_matviews.py`

```python
def upgrade():
    op.execute("""
        CREATE MATERIALIZED VIEW mv_pipeline_metrics AS
        SELECT 
            status,
            COUNT(*) as application_count,
            AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))/86400.0)::DECIMAL(10,2) as avg_days_in_stage
        FROM applications
        WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY status;
        
        CREATE UNIQUE INDEX ON mv_pipeline_metrics (status);
        CREATE INDEX ON mv_pipeline_metrics (application_count);
    """)
    
    op.execute("""
        CREATE MATERIALIZED VIEW mv_volume_metrics AS
        SELECT 
            DATE_TRUNC('month', funding_date) as period,
            COUNT(*) as application_count,
            SUM(loan_amount + COALESCE(cmhc_premium_amount, 0)) as total_volume,
            AVG(loan_amount + COALESCE(cmhc_premium_amount, 0)) as avg_deal_size
        FROM applications
        WHERE status = 'funded' AND funding_date >= CURRENT_DATE - INTERVAL '12 months'
        GROUP BY period
        ORDER BY period;
        
        CREATE UNIQUE INDEX ON mv_volume_metrics (period);
    """)
    
    op.execute("""
        CREATE MATERIALIZED VIEW mv_lender_performance AS
        SELECT 
            lender_id,
            COUNT(*) as submission_count,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approval_count,
            (SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))::DECIMAL(5,2) as approval_rate,
            AVG(contract_rate)::DECIMAL(5,3) as avg_contract_rate,
            SUM(loan_amount) as total_volume
        FROM applications
        WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY lender_id;
        
        CREATE UNIQUE INDEX ON mv_lender_performance (lender_id);
        CREATE INDEX ON mv_lender_performance (total_volume DESC);
    """)
```

### 4.3 Indexes on Existing Tables

**Migration ID:** `202401150003_add_reporting_indexes.py`

```python
def upgrade():
    # applications table indexes
    op.create_index('idx_applications_status_created', 'applications', ['status', 'created_at'])
    op.create_index('idx_applications_lender_status', 'applications', ['lender_id', 'status'])
    op.create_index('idx_applications_funding_date', 'applications', ['funding_date'], 
                    postgresql_where='status = \'funded\'')
    
    # transactions table for FINTRAC queries
    op.create_index('idx_transactions_amount_date', 'transactions', ['amount', 'transaction_date'], 
                    postgresql_where='amount > 10000.00')
    
    # audit_logs table
    op.create_index('idx_audit_logs_created_action', 'audit_logs', ['created_at', 'action_type'])
```

### 4.4 Refresh Strategy for Materialized Views

```python
# Scheduled job (via Celery Beat) - every 15 minutes
@celery.task
def refresh_reporting_views():
    """
    Refresh materialized views for dashboard performance
    """
    async with async_engine.begin() as conn:
        await conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pipeline_metrics"))
        await conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_volume_metrics"))
        await conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_lender_performance"))
    
    log.info("reporting_views_refreshed", correlation_id=get_correlation_id())
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test Logging:** When calculating approval rates, any application rejected due to GDS/TDS must log:
  ```python
  log.info("osfi_b20_ratio_rejection", 
           application_id=app.id,
           gds_ratio=Decimal("42.5"),
           tds_ratio=Decimal("48.2"),
           qualifying_rate=Decimal("7.25"),  # max(contract_rate + 2%, 5.25%)
           correlation_id=get_correlation_id())
  ```
- **Hard Limits Enforcement:** GDS ≤ 39%, TDS ≤ 44% must be validated in underwriting module, but reporting must flag any violations
- **Audit Trail:** All ratio calculations stored in `underwriting_decisions` table with `created_by` and immutable timestamp

### 5.2 FINTRAC Requirements
- **Transaction Threshold:** All transactions > CAD $10,000 automatically flagged in `transactions` table with `is_fintrac_reportable = True`
- **Immutable Records:** `fintrac_report` table has **no `updated_at` column** — append-only for 5-year retention
- **Reporting Flag:** Endpoint `/reports/fintrac/summary` must be called by `compliance_officer` role only
- **Audit Logging:** Every FINTRAC summary generation creates record in `fintrac_report` table with complete data snapshot

### 5.3 PIPEDA Requirements
- **PII Encryption:** Export files containing SIN/DOB must be AES-256 encrypted (zip format)
- **Data Minimization:** Default export excludes PII fields; `include_pii=true` requires explicit opt-in
- **Hash Lookups:** Use `sin_hash` (SHA256) for applicant identification in reports, never raw SIN
- **Access Logging:** Every export logged to `report_export_audit` with user, timestamp, and record count
- **No PII in Logs:** structlog configuration must filter SIN, DOB, income, banking data from all reporting module logs

### 5.4 Authentication & Authorization
```python
# FastAPI dependency for role-based access
async def require_analyst(user: User = Depends(get_current_user)):
    if user.role not in ["analyst", "admin", "compliance_officer"]:
        raise ReportingPermissionError("User must have analyst role or higher")
    return user

async def require_compliance_officer(user: User = Depends(get_current_user)):
    if user.role != "compliance_officer":
        raise ReportingPermissionError("FINTRAC reports require compliance officer role")
    return user
```

### 5.5 Data Retention
- **Reporting Cache:** 90 days (automatic cleanup via scheduled job)
- **FINTRAC Reports:** 5 years (hard retention, no deletion)
- **Export Audit Logs:** 5 years (FINTRAC requirement)
- **Temporary Export Files:** 15 minutes (auto-deleted after download URL expiry)

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
# modules/reporting/exceptions.py
class ReportingException(AppException):
    """Base exception for reporting module"""
    pass

class ReportingValidationError(ReportingException):
    """Invalid query parameters"""
    http_status = 422
    error_code = "REPORTING_001"

class ReportingNotFoundError(ReportingException):
    """No data found for requested criteria"""
    http_status = 404
    error_code = "REPORTING_002"

class ReportingPermissionError(ReportingException):
    """Insufficient permissions for operation"""
    http_status = 403
    error_code = "REPORTING_003"

class ReportingExportError(ReportingException):
    """Export generation or encryption failure"""
    http_status = 409
    error_code = "REPORTING_004"
```

### 6.2 Error Response Mapping

| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `ReportingValidationError` | 422 | REPORTING_001 | "Invalid parameter: {detail}" | WARNING |
| `ReportingNotFoundError` | 404 | REPORTING_002 | "No data found for {resource}" | INFO |
| `ReportingPermissionError` | 403 | REPORTING_003 | "Access denied: {reason}" | WARNING |
| `ReportingExportError` | 409 | REPORTING_004 | "Export generation failed: {detail}" | ERROR |
| `AppException` (base) | 500 | REPORTING_500 | "Internal reporting error" | CRITICAL |

### 6.3 Structured Error Response Example
```json
{
  "detail": "Invalid parameter: date_from cannot be after date_to",
  "error_code": "REPORTING_001",
  "correlation_id": "c4a7f2e9-8b3d-4e1a-9c6f-7d5e8a3b2c1d",
  "timestamp": "2024-01-15T14:30:22Z"
}
```

---

## 7. Performance & Scalability Considerations

### 7.1 Caching Strategy
- **Materialized Views:** Refresh every 15 minutes via Celery Beat (CONCURRENTLY to avoid locks)
- **Redis Cache:** Store serialized JSON responses for 5 minutes with cache key: `report:{metric_name}:{period}:{filters_hash}`
- **Cache Invalidation:** Clear cache on application status changes via PostgreSQL NOTIFY/LISTEN

### 7.2 Query Optimization
- Use `EXISTS` instead of `COUNT(*)` when checking for data presence
- Partition `applications` table by `created_at` (monthly partitions) for historical queries
- Use read replica for all reporting endpoints (configure in `common/database.py`)

### 7.3 Export Streaming
For large exports, use PostgreSQL `COPY TO` command with server-side cursor:
```python
async def stream_export(query: str, format: str):
    async with async_engine.connect() as conn:
        async with conn.stream(query) as stream:
            for chunk in stream.chunks():
                yield encrypt_chunk(chunk)  # Encrypt on-the-fly
```

### 7.4 Rate Limiting
- `/reports/*` endpoints: 60 requests/minute per user
- `/reports/applications/export`: 5 requests/hour per user (due to data sensitivity)
- `/reports/fintrac/summary`: 20 requests/day per compliance officer

---

## 8. Frontend Integration (Recharts)

### 8.1 Chart Data Contracts
```typescript
// Bar chart: Applications by status
interface PipelineBarData {
  status: string;
  count: number;
}

// Line chart: Monthly volume trend
interface VolumeTrendData {
  period_label: string; // "2024-01"
  volume: string; // Decimal as string
  application_count: number;
}

// Pie chart: Mortgage type breakdown
interface MortgageTypePieData {
  type: string;
  value: number;
  percentage: number;
}

// Table: Top lenders
interface LenderTableRow {
  lender_id: number;
  lender_name: string;
  submission_count: number;
  approval_rate: string; // Decimal as string
  total_volume: string; // Decimal as string
  rank_by_volume: number;
}
```

### 8.2 API Client Configuration
```typescript
// Use React Query with 5-min stale time
const usePipelineReport = (params: PipelineReportQuery) => {
  return useQuery({
    queryKey: ['reports', 'pipeline', params],
    queryFn: () => api.get('/reports/pipeline', { params }),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false, // Fail fast for reporting errors
  });
};
```

---

## 9. Scheduled Report Delivery (Future Enhancement)

**Design Note:** Not in initial implementation, but tables prepared for extension.

```python
# Future model for scheduled reports
class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"
    
    id: int = Column(BigInteger, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    report_type: str = Column(String(50), nullable=False)  # 'pipeline', 'volume', etc.
    schedule: str = Column(String(20), nullable=False)  # 'daily', 'weekly', 'monthly'
    filters: dict = Column(JSONB, nullable=False)
    delivery_method: str = Column(String(10), nullable=False)  # 'email', 's3'
    last_run_at: datetime | None = Column(TIMESTAMP(timezone=True))
    next_run_at: datetime = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at: datetime = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    # No updated_at - schedule changes create new records (audit trail)
```

---

## 10. Compliance Checklist

- [ ] **OSFI B-20:** All ratio-based rejections logged with stress test rate and calculation breakdown
- [ ] **FINTRAC:** Transactions > $10,000 flagged, `fintrac_report` table append-only with 5-year retention
- [ ] **CMHC:** LTV calculations use Decimal, premium tiers applied correctly in volume metrics
- [ ] **PIPEDA:** SIN/DOB encrypted at rest, hashed for lookups, never in logs or responses
- [ ] **Data Minimization:** Export endpoints exclude PII by default, require explicit opt-in
- [ ] **Audit Trail:** Every report generation and export logged with user, timestamp, and filters
- [ ] **Immutability:** `fintrac_report` and `report_export_audit` have no `updated_at` columns
- [ ] **Encryption:** Export files with PII use AES-256 zip encryption
- [ ] **Access Control:** Role-based permissions enforced on all endpoints
- [ ] **Retention:** Automated cleanup of reporting cache after 90 days, FINTRAC data retained 5 years

---

**WARNING:** This design assumes existing tables `applications`, `lenders`, `transactions`, `underwriting_decisions`, and `users`. If these tables have different schemas, adjust foreign keys and column names accordingly.