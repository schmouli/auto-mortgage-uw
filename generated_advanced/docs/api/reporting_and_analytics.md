```markdown
# Reporting & Analytics API

## Overview
The Reporting & Analytics module provides endpoints to aggregate and visualize key performance indicators (KPIs) across the mortgage underwriting lifecycle. It supports pipeline monitoring, financial volume tracking, and lender performance analysis.

---

## GET /api/v1/reports/pipeline

Retrieves a summary of the current application pipeline, including status distribution, average processing times, and approval/decline statistics.

**Query Parameters:**
- `start_date` (optional, string): ISO 8601 date string (e.g., `2026-01-01`) to filter applications created after this date.
- `end_date` (optional, string): ISO 8601 date string to filter applications created before this date.

**Response (200):**
```json
{
  "summary": {
    "total_active": 150,
    "approval_rate": 0.65,
    "avg_days_in_stage": {
      "submission": 2.5,
      "underwriting": 4.2,
      "closing": 10.0
    }
  },
  "status_breakdown": [
    { "status": "submitted", "count": 45 },
    { "status": "under_review", "count": 30 },
    { "status": "approved", "count": 60 },
    { "status": "declined", "count": 15 }
  ],
  "decline_reasons": [
    { "reason": "high_tds", "count": 8 },
    { "reason": "poor_credit", "count": 5 },
    { "reason": "insufficient_downpayment", "count": 2 }
  ]
}
```

**Errors:**
- 400: Invalid date format provided
- 401: Not authenticated
- 403: Insufficient permissions to view reports

---

## GET /api/v1/reports/volume

Calculates mortgage volume metrics based on the specified time period. Returns total funded amounts, average deal sizes, and application breakdowns.

**Query Parameters:**
- `period` (required, string): `monthly`, `quarterly`, or `ytd`.
- `year` (optional, integer): The calendar year (defaults to current year).

**Response (200):**
```json
{
  "period": "monthly",
  "year": 2026,
  "metrics": {
    "total_volume": "15200000.00",
    "avg_deal_size": "380000.00",
    "application_count": 40
  },
  "breakdown_by_type": {
    "purchase": { "count": 30, "volume": "12000000.00" },
    "refinance": { "count": 10, "volume": "3200000.00" }
  },
  "breakdown_by_property_type": {
    "detached": { "count": 25 },
    "condo": { "count": 10 },
    "townhouse": { "count": 5 }
  }
}
```

**Errors:**
- 400: Invalid period specified
- 401: Not authenticated
- 422: Validation error on input parameters

---

## GET /api/v1/reports/lenders

Analyzes performance metrics broken down by specific lending partners. Useful for comparing approval rates and pricing competitiveness.

**Query Parameters:**
- `lender_id` (optional, integer): Filter results to a specific lender ID. If omitted, returns stats for all lenders.

**Response (200):**
```json
{
  "lenders": [
    {
      "lender_id": 1,
      "lender_name": "Maple Trust",
      "submissions": 120,
      "approvals": 90,
      "approval_rate": 0.75,
      "avg_rate": 4.85
    },
    {
      "lender_id": 2,
      "lender_name": "Oak Mortgage Corp",
      "submissions": 85,
      "approvals": 60,
      "approval_rate": 0.70,
      "avg_rate": 4.92
    }
  ]
}
```

**Errors:**
- 400: Invalid lender_id format
- 401: Not authenticated
- 404: Lender not found (if specific lender_id is provided)

---

# Module README: Reporting & Analytics

## Purpose
This module aggregates data from the `applications`, `lenders`, and `properties` modules to generate business intelligence reports. It is designed to handle read-heavy loads efficiently, utilizing optimized SQL queries to calculate ratios and sums without loading large datasets into memory.

## Key Functions

### `ReportingService`
The primary service class handling business logic for metrics calculation.

*   `get_pipeline_summary(filters: PipelineFilters) -> PipelineSummary`
    *   Calculates the distribution of applications across their current status.
    *   Computes average time spent in specific lifecycle stages (e.g., days from submission to underwriting).
    *   Aggregates decline reasons to identify common risk factors.

*   `calculate_volume_metrics(period: str, year: int) -> VolumeMetrics`
    *   Sums total mortgage amounts for funded applications within the date range.
    *   Calculates average deal size using `Decimal` for financial precision.
    *   Groups applications by `type` (purchase/refinance) and `property_type`.

*   `analyze_lender_performance(lender_id: Optional[int]) -> List[LenderStats]`
    *   Determines submission counts and approval rates per lender.
    *   Calculates the average interest rate offered by each lender for comparison.

## Usage Example

To fetch the current pipeline status using Python:

```python
import httpx

async def get_pipeline_report():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.mortgage-system.com/api/v1/reports/pipeline",
            headers={"Authorization": "Bearer <token>"}
        )
        response.raise_for_status()
        return response.json()
```

## Notes on Data Integrity
- All financial calculations use `Decimal` to prevent floating-point rounding errors.
- Metrics are calculated based on immutable audit fields (`created_at`, `updated_at`) to ensure historical accuracy.
- PII (SIN, DOB) is strictly excluded from all reports and aggregations.

---

# Configuration Notes

## Environment Variables

No specific module-specific environment variables are required for the Reporting module to function. It relies on the core database configuration.

However, ensure your `.env.example` includes the standard database and observability settings:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/mortgage_db

# Observability
LOG_LEVEL=INFO
CORRELATION_ID_HEADER=X-Correlation-ID
```

## Performance Considerations
- Ensure database indexes exist on `applications.status`, `applications.created_at`, and `applications.lender_id` to prevent full table scans during report generation.
- For high-volume deployments, consider caching the results of `GET /reports/volume` for a short duration (e.g., 5-15 minutes) as the underlying data changes relatively slowly.
```