# Reporting & Analytics Documentation

## 1. API Documentation

**File:** `docs/api/reporting_analytics.md`

```markdown
# Reporting & Analytics API

## Overview

This module provides endpoints to retrieve aggregated metrics regarding mortgage applications, pipeline status, volume trends, and lender performance. All financial values are returned as `Decimal` strings to ensure precision.

---

## GET /api/v1/reports/pipeline

Retrieves metrics related to the current application pipeline, including status distribution, stage duration, and decline analysis.

**Query Parameters:**
- `start_date` (optional, string, date-time): Filter applications created after this date (ISO 8601).
- `end_date` (optional, string, date-time): Filter applications created before this date (ISO 8601).

**Response (200):**
```json
{
  "summary": {
    "total_active": 150,
    "approval_rate": "68.5",
    "avg_days_in_stage": 12.5
  },
  "by_status": {
    "submitted": 40,
    "under_review": 60,
    "approved": 35,
    "declined": 15
  },
  "decline_reasons": {
    "high_tds": 8,
    "poor_credit": 4,
    "property_value_issue": 3
  }
}
```

**Errors:**
- 401: Not authenticated
- 403: Insufficient permissions (Admin/Analyst role required)
- 500: Internal server error during aggregation

---

## GET /api/v1/reports/volume

Retrieves volume metrics based on the specified period.

**Query Parameters:**
- `period` (required, string, enum): `monthly`, `quarterly`, or `ytd`.
- `year` (optional, integer): Required if period is `monthly` or `quarterly`. Defaults to current year.

**Response (200):**
```json
{
  "period": "monthly",
  "year": 2026,
  "month": 3,
  "metrics": {
    "total_volume": "15400000.00",
    "total_deals": 42,
    "avg_deal_size": "366666.67"
  },
  "breakdown": {
    "purchase": {
      "count": 30,
      "volume": "12000000.00"
    },
    "refinance": {
      "count": 12,
      "volume": "3400000.00"
    }
  }
}
```

**Errors:**
- 400: Invalid period specified
- 401: Not authenticated
- 403: Insufficient permissions
- 500: Internal server error

---

## GET /api/v1/reports/lenders

Retrieves performance metrics broken down by lending institution.

**Query Parameters:**
- `start_date` (optional, string, date-time): Start of reporting window.
- `end_date` (optional, string, date-time): End of reporting window.

**Response (200):**
```json
{
  "data": [
    {
      "lender_id": 1,
      "lender_name": "Big Bank Corp",
      "total_submissions": 45,
      "approved_count": 30,
      "approval_rate": "66.67",
      "avg_rate_offered": "5.15"
    },
    {
      "lender_id": 2,
      "lender_name": "Trusty Credit Union",
      "total_submissions": 20,
      "approved_count": 18,
      "approval_rate": "90.00",
      "avg_rate-offered": "4.95"
    }
  ]
}
```

**Errors:**
- 401: Not authenticated
- 403: Insufficient permissions
- 500: Internal server error

---
```

## 2. Module README

**File:** `docs/modules/reporting_analytics.md`

```markdown
# Reporting & Analytics Module

## Overview

The `reporting_analytics` module is responsible for aggregating and serving business intelligence data derived from the mortgage underwriting system. It performs complex read-only queries against the database to calculate Key Performance Indicators (KPIs) for pipeline management, financial volume, and lender performance.

## Key Functions

### Pipeline Metrics
Calculates the health of the current application pipeline:
- **Active Applications:** Counts applications not in a terminal state.
- **Approval Rate:** Calculates the ratio of approved vs. finalized applications.
- **Stage Velocity:** Computes the average number of days an application spends in specific underwriting stages.
- **Decline Analysis:** Aggregates decline reasons to identify common risk factors.

### Volume Metrics
Provides financial overviews:
- **Total Mortgage Volume:** Sums the principal loan amounts for closed or approved applications.
- **Deal Size:** Calculates average loan size.
- **Segmentation:** Breaks down volume by application type (Purchase vs. Refinance) and property type.

### Lender Performance
Analyzes external lender behavior:
- **Submission Counts:** Tracks how many applications are sent to each lender.
- **Conversion Rates:** Calculates the approval rate for each lender.
- **Rate Analysis:** Averages the offered interest rates per lender.

## Usage Example

To retrieve pipeline metrics for the current month:

```python
from httpx import AsyncClient

async def get_pipeline_stats():
    async with AsyncClient(base_url="http://localhost:8000") as ac:
        response = await ac.get(
            "/api/v1/reports/pipeline",
            headers={"Authorization": "Bearer <token>"}
        )
    return response.json()
```

## Compliance Notes

- **OSFI B-20:** All ratio calculations (approval rates) are logged for auditability.
- **FINTRAC:** Reports rely on immutable `created_at` timestamps. No historical data is ever modified; reports are generated from point-in-time snapshots or live aggregated views.
- **PIPEDA:** Reports aggregate data. No Personally Identifiable Information (PII) such as SIN or DOB is included in the API responses.
```

## 3. Configuration & Changelog

### Configuration Updates

**File:** `.env.example`

```bash
# Reporting & Analytics Configuration
# Time-to-live (TTL) in seconds for caching heavy aggregate queries
REPORTING_CACHE_TTL=300

# Default timezone for reporting dates (IANA format)
REPORTING_TIMEZONE=America/Toronto
```

### Changelog

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Reporting & Analytics: New module for business intelligence.
  - GET /api/v1/reports/pipeline: Status and velocity metrics.
  - GET /api/v1/reports/volume: Financial volume analysis.
  - GET /api/v1/reports/lenders: Lender performance tracking.
- Aggregation services for calculating KPIs.
- Configuration for reporting cache TTL.

### Changed
- N/A

### Fixed
- N/A
```