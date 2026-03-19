```markdown
# Reporting & Analytics API

This module provides endpoints for generating insights on mortgage pipeline performance, volume metrics, and lender efficiency. All financial values are returned as strings (Decimal) to ensure precision.

## GET /api/v1/reports/pipeline

Retrieves a summary of the current underwriting pipeline status.

**Query Parameters:**
- `start_date` (optional, string): ISO 8601 date (e.g., `2026-01-01`) to filter applications.
- `end_date` (optional, string): ISO 8601 date to filter applications.

**Response (200):**
```json
{
  "active_by_status": {
    "submitted": 12,
    "under_review": 5,
    "approval_pending": 3,
    "funded": 40
  },
  "avg_days_per_stage": {
    "submitted": "1.5",
    "under_review": "3.2",
    "approval_pending": "2.0"
  },
  "approval_rate": "0.65",
  "decline_reasons": [
    {
      "reason": "High TDS",
      "count": 4
    },
    {
      "reason": "Poor Credit",
      "count": 2
    }
  ]
}
```

**Errors:**
- 401: Not authenticated
- 422: Validation error (invalid date format)

---

## GET /api/v1/reports/volume

Calculates mortgage volume metrics based on the specified period.

**Query Parameters:**
- `period` (required, string): `monthly`, `quarterly`, or `ytd`.
- `year` (optional, integer): Required if period is `monthly` or `quarterly`. Defaults to current year.
- `quarter` (optional, integer): Required if period is `quarterly` (1-4).

**Response (200):**
```json
{
  "total_volume": "12500000.00",
  "avg_deal_size": "425000.00",
  "application_count": 29,
  "applications_by_type": {
    "purchase": 20,
    "refinance": 5,
    "renewal": 4
  },
  "applications_by_property": {
    "single_family": 22,
    "condo": 5,
    "multi_family": 2
  }
}
```

**Errors:**
- 401: Not authenticated
- 400: Invalid period or quarter specified
- 422: Validation error

---

## GET /api/v1/reports/lenders

Analyzes performance metrics broken down by lender.

**Query Parameters:**
- `start_date` (optional, string): ISO 8601 start date.
- `end_date` (optional, string): ISO 8601 end date.

**Response (200):**
```json
[
  {
    "lender_id": 1,
    "lender_name": "Maple Bank",
    "submissions_count": 15,
    "approval_rate": "0.80",
    "avg_rate": "5.15",
    "total_funded": "6000000.00"
  },
  {
    "lender_id": 2,
    "lender_name": "Northern Credit Union",
    "submissions_count": 8,
    "approval_rate": "0.50",
    "avg_rate": "4.95",
    "total_funded": "2000000.00"
  }
]
```

**Errors:**
- 401: Not authenticated
- 422: Validation error

---

# Module README: Reporting & Analytics

## Overview
The Reporting & Analytics module aggregates data from the underwriting pipeline to provide actionable insights. It supports monitoring team performance (Pipeline), tracking business growth (Volume), and evaluating partner relationships (Lenders).

## Key Functions
- **Pipeline Analysis**: Tracks application flow through statuses, calculates stage duration averages, and aggregates decline reasons to identify bottlenecks.
- **Volume Aggregation**: Summarizes total funded amounts and deal sizes over specific timeframes (Monthly, Quarterly, Year-to-Date).
- **Lender Performance**: Ranks lenders by submission volume, approval rates, and average offered rates.

## Usage Examples

### Python Client Example
```python
import httpx

async def get_pipeline_summary():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.mortgage-system.com/api/v1/reports/pipeline",
            headers={"Authorization": "Bearer YOUR_TOKEN"}
        )
        return response.json()

# Example: Get Volume for Q1 2026
async def get_q1_volume():
    async with httpx.AsyncClient() as client:
        params = {"period": "quarterly", "year": 2026, "quarter": 1}
        response = await client.get(
            "https://api.mortgage-system.com/api/v1/reports/volume",
            params=params,
            headers={"Authorization": "Bearer YOUR_TOKEN"}
        )
        return response.json()
```

## Data Privacy & Compliance
- **PIPEDA**: This endpoint only returns aggregated data. No PII (SIN, DOB, names) is included in the responses.
- **OSFI B-20**: Approval rates and volume metrics are derived from records that have passed stress testing logic.

---

# Configuration Notes

## Environment Variables

No specific module-specific environment variables are strictly required for basic functionality, as the module relies on the core database connection. However, for performance optimization in high-volume environments, the following variables may be configured in `.env`:

```bash
# Reporting & Analytics Configuration
# Time-to-live for cached report results in seconds (optional, recommended for production)
REPORTING_CACHE_TTL=300

# Database read replica connection string (optional, offloads read-heavy reporting queries)
# If not set, defaults to the primary DATABASE_URL
REPORTING_DATABASE_URL=postgresql+asyncpg://user:pass@replica-host/dbname
```

## Setup
1. Ensure the database has sufficient indexes on `applications.status`, `applications.created_at`, and `lenders.id` to ensure fast report generation.
2. If using a read replica, update `common/database.py` to utilize the `REPORTING_DATABASE_URL` when a session is created within the reporting service context.
```