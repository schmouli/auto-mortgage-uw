# Design: Reporting & Analytics
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

docs/design/reporting_analytics.md

# Reporting & Analytics Module Design

## 1. Endpoints

### 1.1 GET /api/v1/reports/pipeline
**Authentication**: Authenticated users (broker, underwriter, admin)

**Query Parameters**:
- `start_date` (optional, date): Filter start date (YYYY-MM-DD)
- `end_date` (optional, date): Filter end date (YYYY-MM-DD)
- `lender_id` (optional, int): Filter by specific lender

**Response Schema**:
```json
{
  "period": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  },
  "metrics": {
    "total_active": 1247,
    "by_status": {
      "draft": 45,
      "submitted": 312,
      "underwriting": 189,
      "approved": 478,
      "declined": 223
    },
    "avg_days_per_stage": {
      "draft": 2.3,
      "submitted": 1.8,
      "underwriting": 5.4,
      "approved": 3.1,
      "declined": 4.2
    },
    "approval_rate": 68.2,
    "decline_reasons_frequency": {
      "gds_tds_exceeded": 89,
      "insufficient_income": 67,
      "credit_score": 41,
      "property_value": 26
    }
  },
  "generated_at": "2024-12-19T14:30:00Z"
}
```

**Error Responses**:
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 | REPORTING_001 | "Invalid date range: start_date must be before end_date" |
| 403 | REPORTING_002 | "Insufficient permissions to access pipeline metrics" |
| 422 | REPORTING_003 | "lender_id must be a positive integer" |

---

### 1.2 GET /api/v1/reports/volume
**Authentication**: Authenticated users

**Query Parameters**:
- `period` (required, enum): `monthly`, `quarterly`, `ytd`
- `property_type` (optional, enum): `single_family`, `condo`, `multi_unit`, `commercial`
- `application_type` (optional, enum): `purchase`, `refinance`, `renewal`, `switch`

**Response Schema**:
```json
{
  "period": "monthly",
  "filter": {
    "property_type": null,
    "application_type": "purchase"
  },
  "metrics": {
    "total_volume": "2874567890.50",
    "avg_deal_size": "230456.78",
    "total_applications": 1247,
    "monthly_breakdown": [
      {
        "period": "2024-01",
        "volume": "215678900.25",
        "application_count": 98,
        "avg_deal_size": "220080.51"
      }
    ]
  },
  "generated_at": "2024-12-19T14:30:00Z"
}
```

**Error Responses**:
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 | REPORTING_004 | "Invalid period value. Must be: monthly, quarterly, or ytd" |
| 403 | REPORTING_002 | "Insufficient permissions to access volume metrics" |
| 422 | REPORTING_005 | "property_type value not recognized" |

---

### 1.3 GET /api/v1/reports/lenders
**Authentication**: Authenticated users (admin, compliance)

**Query Parameters**:
- `start_date` (required, date)
- `end_date` (required, date)
- `top_n` (optional, int, default=10): Limit results to top N lenders

**Response Schema**:
```json
{
  "period": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  },
  "lender_performance": [
    {
      "lender_id": 1,
      "lender_name": "Major Bank A",
      "total_submissions": 456,
      "approved_count": 342,
      "approval_rate": 75.0,
      "avg_contract_rate": "5.24",
      "total_volume": "987654321.00"
    }
  ],
  "summary": {
    "total_lenders_active": 12,
    "overall_approval_rate": 68.2
  },
  "generated_at": "2024-12-19T14:30:00Z"
}
```

**Error Responses**:
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 | REPORTING_001 | "Invalid date range" |
| 403 | REPORTING_006 | "Admin or compliance role required" |
| 422 | REPORTING_007 | "top_n must be between 1 and 100" |

---

### 1.4 GET /api/v1/reports/applications/export
**Authentication**: Authenticated users with `reports:export` permission

**Query Parameters**:
- `start_date` (required, date)
- `end_date` (required, date)
- `status` (optional, enum): Filter by application status
- `lender_id` (optional, int)

**Response**: CSV file download with filename `applications_export_{timestamp}.csv`

**CSV Columns** (PIPEDA-compliant):
```
application_id,created_date,status,lender_name,property_type,application_type,loan_amount,property_value,ltv_ratio,gds_ratio,tds_ratio,insurance_required,decline_reason
```

**Error Responses**:
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 | REPORTING_001 | "Invalid date range" |
| 403 | REPORTING_008 | "Export permission required" |
| 409 | REPORTING_009 | "Export generation already in progress for this user" |
| 413 | REPORTING_010 | "Date range exceeds maximum 365 days" |

**FINTRAC Compliance Note**: This endpoint triggers audit log entries for each export action. Exports include transaction type flags for amounts > $10,000.

---

### 1.5 GET /api/v1/reports/fintrac/summary
**Authentication**: Admin/compliance officers only (role: `compliance_officer`)

**Query Parameters**:
- `reporting_period` (required, enum): `q1`, `q2`, `q3`, `q4`, `annual`
- `year` (required, int): Reporting year

**Response Schema**:
```json
{
  "reporting_period": "q4",
  "year": 2024,
  "summary": {
    "total_transactions": 1247,
    "large_transactions_10k_plus": 89,
    "total_large_transaction_volume": "12345678.90",
    "identity_verifications": 1247,
    "suspicious_activity_reports": 0
  },
  "compliance_status": {
    "records_retained_5_years": true,
    "audit_trail_complete": true,
    "last_audit_date": "2024-11-15T10:00:00Z"
  },
  "generated_at": "2024-12-19T14:30:00Z",
  "generated_by": "compliance_user_123"
}
```

**Error Responses**:
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 | REPORTING_011 | "Invalid reporting period. Must be: q1, q2, q3, q4, or annual" |
| 403 | REPORTING_012 | "Compliance officer role required" |
| 422 | REPORTING_013 | "Year must be between 2020 and current year" |

---

## 2. Models & Database

### 2.1 Materialized Views (Performance Layer)

**`reporting.pipeline_metrics_mv`**
```sql
CREATE MATERIALIZED VIEW reporting.pipeline_metrics_mv AS
SELECT 
    status,
    COUNT(*) as application_count,
    AVG(EXTRACT(EPOCH FROM (COALESCE(closed_at, CURRENT_TIMESTAMP) - created_at))/86400) as avg_days,
    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END)::DECIMAL / NULLIF(COUNT(*), 0) as approval_rate
FROM applications.application
WHERE created_at >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY status;
```

**`reporting.volume_metrics_mv`**
```sql
CREATE MATERIALIZED VIEW reporting.volume_metrics_mv AS
SELECT 
    DATE_TRUNC('month', created_at) as period,
    property_type,
    application_type,
    COUNT(*) as application_count,
    SUM(loan_amount) as total_volume,
    AVG(loan_amount) as avg_deal_size
FROM applications.application
GROUP BY DATE_TRUNC('month', created_at), property_type, application_type;
```

**`reporting.lender_metrics_mv`**
```sql
CREATE MATERIALIZED VIEW reporting.lender_metrics_mv AS
SELECT 
    l.lender_id,
    l.name as lender_name,
    COUNT(a.application_id) as total_submissions,
    SUM(CASE WHEN a.status = 'approved' THEN 1 ELSE 0 END) as approved_count,
    AVG(CASE WHEN a.status = 'approved' THEN a.contract_rate END) as avg_contract_rate,
    SUM(a.loan_amount) as total_volume
FROM applications.application a
JOIN lenders.lender l ON a.lender_id = l.lender_id
WHERE a.created_at >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY l.lender_id, l.name;
```

### 2.2 ORM Models (for querying materialized views)

**File**: `modules/reporting/models.py`

```python
from sqlalchemy import Column, Integer, Numeric, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base
from decimal import Decimal
from datetime import datetime

Base = declarative_base()

class PipelineMetricsMV(Base):
    __tablename__ = "pipeline_metrics_mv"
    __table_args__ = {"schema": "reporting"}
    
    status: str = Column(String(50), primary_key=True)
    application_count: int = Column(Integer, nullable=False)
    avg_days: float = Column(Numeric(10, 2), nullable=False)
    approval_rate: Decimal = Column(Numeric(5, 2), nullable=True)

class VolumeMetricsMV(Base):
    __tablename__ = "volume_metrics_mv"
    __table_args__ = {"schema": "reporting"}
    
    period: datetime = Column(DateTime, primary_key=True)
    property_type: str = Column(String(50), primary_key=True)
    application_type: str = Column(String(50), primary_key=True)
    application_count: int = Column(Integer, nullable=False)
    total_volume: Decimal = Column(Numeric(15, 2), nullable=False)
    avg_deal_size: Decimal = Column(Numeric(12, 2), nullable=False)

class LenderMetricsMV(Base):
    __tablename__ = "lender_metrics_mv"
    __table_args__ = {"schema": "reporting"}
    
    lender_id: int = Column(Integer, primary_key=True)
    lender_name: str = Column(String(255), nullable=False)
    total_submissions: int = Column(Integer, nullable=False)
    approved_count: int = Column(Integer, nullable=False)
    avg_contract_rate: Decimal = Column(Numeric(5, 2), nullable=True)
    total_volume: Decimal = Column(Numeric(15, 2), nullable=False)
```

### 2.3 Indexes for Source Tables

To support reporting queries, add indexes to existing tables:

```sql
-- On applications.application table
CREATE INDEX idx_app_created_at_status ON applications.application (created_at, status);
CREATE INDEX idx_app_lender_id ON applications.application (lender_id);
CREATE INDEX idx_app_loan_amount ON applications.application (loan_amount);
CREATE INDEX idx_app_property_type ON applications.application (property_type);

-- On underwriting.underwriting_result table
CREATE INDEX idx_uwr_application_id ON underwriting.underwriting_result (application_id);

-- On fintrac.transaction_log table
CREATE INDEX idx_fintrac_amount_date ON fintrac.transaction_log (transaction_amount, transaction_date);
CREATE INDEX idx_fintrac_large_txn ON fintrac.transaction_log (transaction_amount) WHERE transaction_amount >= 10000;
```

---

## 3. Business Logic

### 3.1 Pipeline Metrics Calculation

**Algorithm**:
```python
# Pseudo-algorithm for pipeline metrics
def calculate_pipeline_metrics(start_date: date, end_date: date, lender_id: int = None):
    # Query from materialized view for performance
    base_query = select(PipelineMetricsMV)
    
    if lender_id:
        # Join with application table for lender filter
        base_query = (
            select(
                Application.status,
                func.count().label('application_count'),
                func.avg(func.extract('epoch', func.coalesce(Application.closed_at, func.now()) - Application.created_at) / 86400).label('avg_days')
            )
            .where(Application.created_at.between(start_date, end_date))
            .where(Application.lender_id == lender_id)
            .group_by(Application.status)
        )
    
    results = await session.execute(base_query)
    # Calculate approval rate from counts
    # Calculate decline reasons from underwriting_result table
```

**State Machine Consideration**: Applications follow `draft → submitted → underwriting → [approved|declined]`. Average days per stage calculated using `created_at` timestamps at each transition.

### 3.2 Volume Metrics Calculation

**Formula**:
- Total Volume = Σ(loan_amount) for period
- Avg Deal Size = Total Volume / application_count
- Monthly breakdown uses `DATE_TRUNC('month', created_at)`

**CMHC LTV Compliance**: When filtering by LTV ranges, use exact Decimal calculation: `loan_amount / property_value * 100`

### 3.3 Lender Performance Calculation

**Formula**:
- Approval Rate = (approved_count / total_submissions) * 100
- Avg Rate = Σ(contract_rate) / approved_count (only approved applications)
- Total Volume = Σ(loan_amount) for lender

### 3.4 FINTRAC Summary Compliance

**Mandatory Checks**:
1. **Large Transactions**: Count all applications where loan_amount ≥ 10000
2. **Identity Verification**: Count from `identity_verification_log` table
3. **Audit Trail Completeness**: Verify `created_at` exists for all records in period
4. **5-Year Retention**: Check that no records older than 5 years are missing

**Logic**:
```python
# FINTRAC summary generation
async def generate_fintrac_summary(period: str, year: int):
    # Calculate date range for period
    start_date, end_date = get_period_dates(period, year)
    
    # Count large transactions
    large_txn_count = await session.scalar(
        select(func.count())
        .where(FintracTransaction.transaction_amount >= 10000)
        .where(FintracTransaction.transaction_date.between(start_date, end_date))
    )
    
    # Verify 5-year retention
    oldest_record = await session.scalar(select(func.min(FintracTransaction.created_at)))
    retention_compliant = (datetime.now() - oldest_record).days <= 1825
    
    return {
        "large_transactions_10k_plus": large_txn_count,
        "records_retained_5_years": retention_compliant,
        # ... other metrics
    }
```

---

## 4. Migrations

### 4.1 New Schema
```sql
CREATE SCHEMA IF NOT EXISTS reporting;
```

### 4.2 Materialized Views
Create the three materialized views defined in Section 2.1.

### 4.3 Refresh Schedule
```sql
-- Create function to refresh all reporting views
CREATE OR REPLACE FUNCTION reporting.refresh_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY reporting.pipeline_metrics_mv;
    REFRESH MATERIALIZED VIEW CONCURRENTLY reporting.volume_metrics_mv;
    REFRESH MATERIALIZED VIEW CONCURRENTLY reporting.lender_metrics_mv;
END;
$$ LANGUAGE plpgsql;
```

### 4.4 Indexes on Materialized Views
```sql
CREATE UNIQUE INDEX idx_pipeline_mv_status ON reporting.pipeline_metrics_mv (status);
CREATE UNIQUE INDEX idx_volume_mv_period_type ON reporting.volume_metrics_mv (period, property_type, application_type);
CREATE UNIQUE INDEX idx_lender_mv_lender_id ON reporting.lender_metrics_mv (lender_id);
```

### 4.5 Background Job Table (Optional)
```sql
CREATE TABLE reporting.refresh_log (
    refresh_id SERIAL PRIMARY KEY,
    view_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL, -- 'running', 'completed', 'failed'
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 5. Security & Compliance

### 5.1 PIPEDA Data Handling
- **Encryption**: All export queries must exclude `encrypted_sin` and `encrypted_dob` columns. Use `hashed_sin` only for internal correlation.
- **Data Minimization**: Export CSV includes only fields required for business/regulatory purposes. SIN and DOB are **never** exported.
- **Logging**: Report access is logged with `correlation_id` and `user_id`, but **never** log financial data or personal identifiers.

### 5.2 FINTRAC Compliance
- **Export Audit**: Every CSV export triggers `FintracExportAudit` log entry with:
  - `exported_by_user_id`
  - `record_count`
  - `date_range`
  - `timestamp`
- **Large Transactions**: Export automatically flags records with `loan_amount ≥ 10000` with `transaction_type_flag = 'large_transaction'`
- **Retention**: All report generation metadata retained for 5 years in `reporting.audit_log`

### 5.3 OSFI B-20 Requirements
- While reporting doesn't calculate ratios, it **must** include GDS/TDS values from underwriting results that were calculated **with** stress test applied.
- Audit field `underwriting_log.qualifying_rate_used` must be included in data exports for regulator review.

### 5.4 Authorization Matrix
| Endpoint | Broker | Underwriter | Lender Admin | Compliance | System Admin |
|----------|--------|-------------|--------------|------------|--------------|
| /pipeline | ✅ | ✅ | ✅ | ✅ | ✅ |
| /volume | ✅ | ✅ | ✅ | ✅ | ✅ |
| /lenders | ❌ | ❌ | ✅ | ✅ | ✅ |
| /export | ✅ (own) | ✅ | ✅ | ✅ | ✅ |
| /fintrac/summary | ❌ | ❌ | ❌ | ✅ | ✅ |

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
# modules/reporting/exceptions.py
class ReportingException(AppException):
    """Base exception for reporting module"""
    module_code = "REPORTING"

class ReportNotFoundError(ReportingException):
    """Requested report or data not found"""
    http_status = 404
    error_code = "REPORTING_001"

class ReportPermissionError(ReportingException):
    """User lacks permission for report"""
    http_status = 403
    error_code = "REPORTING_002"

class InvalidReportParametersError(ReportingException):
    """Validation error for report parameters"""
    http_status = 422
    error_code = "REPORTING_003"

class ReportGenerationError(ReportingException):
    """Background report generation failed"""
    http_status = 500
    error_code = "REPORTING_004"

class ExportTooLargeError(ReportingException):
    """Requested export exceeds size limits"""
    http_status = 413
    error_code = "REPORTING_005"
```

### 6.2 Error Response Format
All errors return structured JSON:
```json
{
  "detail": "Export date range exceeds maximum 365 days",
  "error_code": "REPORTING_005",
  "module": "reporting",
  "timestamp": "2024-12-19T14:30:00Z",
  "correlation_id": "req_1234567890"
}
```

### 6.3 Edge Cases & Handling
| Scenario | Error Code | Handling Strategy |
|----------|------------|-------------------|
| Date range > 365 days | REPORTING_005 | Reject with 413, suggest pagination |
| Non-existent lender_id | REPORTING_001 | Return empty result set with warning |
| Concurrent export request | REPORTING_009 | Return 409, provide existing task ID |
| Materialized view stale | REPORTING_004 | Trigger refresh, return 202 accepted |
| Database timeout | REPORTING_004 | Retry with exponential backoff, log error |

---

## 7. Performance & Scalability

### 7.1 Materialized View Refresh Strategy
- **Refresh Frequency**: Every 15 minutes via Celery beat task
- **Concurrent Refresh**: Use `CONCURRENTLY` option to avoid table locks
- **Fallback**: If MV is unavailable, query source tables with 30s timeout

### 7.2 Query Optimization
- All reporting queries use `READ ONLY` transaction mode
- Set `statement_timeout = '30s'` for reporting connections
- Use `pg_stat_statements` to monitor slow queries

### 7.3 Caching Layer
- Redis cache for `/pipeline` and `/lenders` endpoints: TTL 5 minutes
- Cache key includes user role and filter parameters (hashed)

### 7.4 Export Streaming
- CSV exports use PostgreSQL `COPY TO STDOUT` with async streaming
- Maximum 100,000 records per export to prevent memory exhaustion
- Large exports (>10MB) uploaded to S3 with presigned URL returned

---

## 8. Future Enhancements (Out of Scope)

- Custom report builder with drag-and-drop fields
- Scheduled email delivery of reports
- Real-time WebSocket updates for dashboard
- Support for Parquet/Excel export formats
- Machine learning predictions for approval likelihood