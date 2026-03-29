Here is the documentation for the Reporting & Analytics module, structured according to the project conventions.

### 1. API Documentation
**File:** `docs/api/reporting_analytics.md`

```markdown
# Reporting & Analytics API

This module provides endpoints for aggregating and reporting on mortgage underwriting data, focusing on pipeline efficiency, volume metrics, and lender performance.

**Note:** All financial values are returned as strings (Decimal format) to ensure precision. PII (SIN, DOB) is excluded from all reports per PIPEDA regulations.

---

## GET /api/v1/reports/pipeline

Retrieves the current status of the mortgage application pipeline, including active counts, processing times, and approval statistics.

**Query Parameters:**
- `start_date` (optional, string): ISO 8601 date (e.g., `2026-01-01`) to filter applications created after this date.
- `end_date` (optional, string): ISO 8601 date to filter applications created before this date.

**Response (200):**
```json
{
  "summary": {
    "total_active": 150,
    "approval_rate": "68.5",
    "avg_days_in_stage": "12.5"
  },
  "by_status": [
    {
      "status": "submitted",
      "count": 45,
      "avg_days": "2.1"
    },
    {
      "status": "under_review",
      "count": 30,
      "avg_days": "5.4"
    }
  ],
  "decline_reasons": [
    {
      "reason": "high_tds",
      "count": 12,
      "frequency": "24.0"
    }
  ]
}
```

**Errors:**
- 400: Invalid date format provided
- 401: Not authenticated
- 500: Internal server error during aggregation

---

## GET /api/v1/reports/volume

Calculates mortgage volume metrics based on the specified time period. Useful for tracking YTD targets and monthly performance.

**Query Parameters:**
- `period` (required, string): `monthly`, `quarterly`, or `ytd`.
- `year` (optional, integer): Required if period is `ytd` or `quarterly`. Defaults to current year.
- `month` (optional, integer): Required if period is `monthly` (1-12).

**Response (200):**
```json
{
  "period": "monthly",
  "metrics": {
    "total_volume": "2500000.00",
    "total_deals": 12,
    "avg_deal_size": "208333.33",
    "currency": "CAD"
  },
  "breakdown": {
    "by_property_type": [
      {
        "type": "detached",
        "count": 8,
        "volume": "1800000.00"
      },
      {
        "type": "condo",
        "count": 4,
        "volume": "700000.00"
      }
    ],
    "by_application_type": [
      {
        "type": "purchase",
        "count": 10,
        "volume": "2200000.00"
      },
      {
        "type": "refinance",
        "count": 2,
        "volume": "300000.00"
      }
    ]
  }
}
```

**Errors:**
- 400: Invalid period type or missing required date parameters
- 401: Not authenticated
- 404: No data found for the specified period

---

## GET /api/v1/reports/lenders

Analyzes performance metrics across different lending institutions, including submission volumes and success rates.

**Query Parameters:**
- `limit` (optional, integer): Number of top lenders to return. Defaults to 10.

**Response (200):**
```json
{
  "lenders": [
    {
      "lender_id": "lender_abc",
      "lender_name": "ABC Bank",
      "total_submissions": 45,
      "approved_count": 30,
      "approval_rate": "66.67",
      "avg_rate": "5.25"
    },
    {
      "lender_id": "lender_xyz",
      "lender_name": "XYZ Mortgage Corp",
      "total_submissions": 20,
      "approved_count": 18,
      "approval_rate": "90.00",
      "avg_rate": "4.95"
    }
  ]
}
```

**Errors:**
- 401: Not authenticated
- 500: Database query failed
```

### 2. Module README
**File:** `modules/reporting_analytics/README.md`

```markdown
# Reporting & Analytics Module

## Overview
The Reporting & Analytics module aggregates data from the Applications, Lenders, and Properties modules to provide business intelligence insights. It supports the calculation of key performance indicators (KPIs) required for operational monitoring and regulatory reporting (OSFI/FINTRAC).

## Key Functions

### Pipeline Metrics
- **Active Status Tracking:** Counts applications currently in specific workflow stages (e.g., `submitted`, `under_review`, `approved`).
- **Efficiency Calculation:** Calculates average days an application spends in a specific stage.
- **Approval/Decline Ratios:** Computes the percentage of approved vs. declined applications and categorizes decline reasons (e.g., High TDS, Low Credit Score).

### Volume Metrics
- **Financial Aggregation:** Sums total mortgage amounts using `Decimal` arithmetic to prevent floating-point errors.
- **Time-based Grouping:** Supports filtering by Monthly, Quarterly, or Year-to-Date (YTD) periods.
- **Categorization:** Breaks down volume by Property Type (Detached, Condo) and Application Type (Purchase, Refinance).

### Lender Performance
- **Submission Analysis:** Tracks how many applications are sent to each lender.
- **Rate Comparison:** Calculates the average approved interest rate per lender.
- **Success Rates:** Determines the approval percentage for each lender to identify optimal partners.

## Usage Examples

### Using the Service Layer
```python
from modules.reporting_analytics.services import ReportingService
from decimal import Decimal

service = ReportingService(db_session)

# Get volume for March 2026
volume_data = await service.get_volume_metrics(
    period="monthly", 
    year=2026, 
    month=3
)

print(f"Total Volume: ${volume_data.total_volume}")
```

## Regulatory Compliance Notes
1.  **PIPEDA:** This module strictly excludes PII (SIN, DOB, Names) from all aggregates. Reports contain only counts, rates, and financial sums.
2.  **OSFI B-20:** While this module reports on ratios, the actual GDS/TDS calculations are performed in the Underwriting module. This module merely aggregates the results.
3.  **Auditability:** All report generation requests are logged via `structlog` with `correlation_id` to track who accessed specific financial summaries.
```

### 3. Configuration Notes
**File:** `.env.example` (Append or Update)

```ini
# Reporting & Analytics Configuration
# Timezone used for date grouping in volume reports (e.g., 'America/Toronto')
DEFAULT_REPORTING_TIMEZONE=America/Toronto

# Cache TTL for report results in seconds (Redis)
# Reduces DB load for frequently accessed dashboard data
REPORTING_CACHE_TTL=300
```