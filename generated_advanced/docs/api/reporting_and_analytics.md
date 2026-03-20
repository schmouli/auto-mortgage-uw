Here is the documentation for the Reporting & Analytics module.

### 1. API Documentation

**File:** `docs/api/reporting_analytics.md`

```markdown
# Reporting & Analytics API

This module provides endpoints for aggregating and reporting on mortgage application data. It covers pipeline status, financial volume metrics, and lender performance.

**Base URL:** `/api/v1/reports`

---

## GET /reports/pipeline

Retrieves a summary of the current application pipeline, including status breakdowns, average processing times, and approval/decline statistics.

**Query Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| start_date | string (date) | No | Filter applications created after this date (ISO 8601). |
| end_date | string (date) | No | Filter applications created before this date (ISO 8601). |

**Response (200):**
```json
{
  "meta": {
    "start_date": "2026-01-01",
    "end_date": "2026-03-31",
    "generated_at": "2026-03-02T10:00:00Z"
  },
  "pipeline": {
    "total_active": 142,
    "by_status": {
      "New": 45,
      "Under Review": 38,
      "Approved": 12,
      "Funded": 47
    },
    "average_days_per_stage": {
      "New": 1.2,
      "Under Review": 4.5,
      "Approved": 2.1
    },
    "approval_rate": 0.68,
    "decline_reasons": {
      "High_TDS": 15,
      "Credit_Score": 8,
      "Property_Valuation": 4
    }
  }
}
```

**Errors:**
- 400: Invalid date format provided.
- 401: Not authenticated.
- 403: Insufficient permissions to view reports.

---

## GET /reports/volume

Calculates financial volume metrics based on mortgage applications. Supports grouping by month, quarter, or year-to-date (YTD).

**Query Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| period | string | Yes | One of: `monthly`, `quarterly`, `ytd`. |
| year | integer | No | Required if period is `monthly` or `quarterly`. Defaults to current year. |

**Response (200):**
```json
{
  "meta": {
    "period": "quarterly",
    "year": 2026
  },
  "volume": {
    "total_mortgage_volume": "15420000.00",
    "average_deal_size": "345000.50",
    "application_count": 447,
    "breakdown": [
      {
        "period_label": "Q1",
        "volume": "5400000.00",
        "count": 150
      }
    ],
    "by_property_type": {
      "Detached": 250,
      "Condo": 120,
      "Semi-Detached": 77
    },
    "by_application_type": {
      "Purchase": 300,
      "Refinance": 100,
      "Renewal": 47
    }
  }
}
```

**Errors:**
- 400: Invalid period type or year.
- 401: Not authenticated.
- 403: Insufficient permissions to view financial reports.

---

## GET /reports/lenders

Aggregates performance metrics broken down by specific lending partners.

**Query Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| limit | integer | No | Maximum number of lenders to return (default: 10). |
| sort_by | string | No | Sort metric: `submissions`, `approval_rate`, `avg_rate`. |

**Response (200):**
```json
{
  "lenders": [
    {
      "lender_id": "lender_abc",
      "lender_name": "ABC Bank",
      "submissions": 120,
      "approvals": 90,
      "approval_rate": 0.75,
      "average_rate": "5.15",
      "total_funded": "31050000.00"
    },
    {
      "lender_id": "lender_xyz",
      "lender_name": "XYZ Credit Union",
      "submissions": 85,
      "approvals": 60,
      "approval_rate": 0.70,
      "average_rate": "4.95",
      "total_funded": "21250000.00"
    }
  ]
}
```

**Errors:**
- 400: Invalid sort parameter.
- 401: Not authenticated.
- 403: Insufficient permissions to view lender reports.
```

---

### 2. Module README

**File:** `docs/modules/reporting_analytics.md`

```markdown
# Reporting & Analytics Module

## Overview
The Reporting & Analytics module is responsible for aggregating data from the mortgage underwriting pipeline to provide business intelligence. It calculates key performance indicators (KPIs) regarding pipeline efficiency, financial volume, and lender performance.

This module ensures data consistency by using `Decimal` types for all financial calculations to prevent floating-point errors. It adheres to PIPEDA by aggregating data and ensuring no PII (SIN, DOB) is exposed in report outputs.

## Key Functions

### `ReportingService`

#### `get_pipeline_metrics(filters: PipelineFilters)`
Calculates the status of the active underwriting pipeline.
- **Logic:** Queries `Application` models grouped by status.
- **OSFI B-20 Compliance:** Tracks approval rates to monitor underwriting strictness.
- **Metrics:**
  - Total active applications.
  - Average days spent in each status (e.g., "Under Review").
  - Approval rate vs. Decline rate.
  - Frequency of decline reasons (e.g., High TDS, Credit Score).

#### `get_volume_metrics(period: str, year: int)`
Calculates total mortgage volume and deal sizes.
- **Logic:** Sums `loan_amount` from funded or approved applications within the specified timeframe.
- **Financial Precision:** Uses Python `Decimal` for all monetary sums.
- **Metrics:**
  - Total volume (CAD).
  - Average deal size.
  - Volume by application type (Purchase, Refinance, Renewal).
  - Volume by property type.

#### `get_lender_performance(sort_by: str)`
Evaluates lender-specific statistics.
- **Logic:** Joins `Application` with `Lender` records.
- **Metrics:**
  - Total submissions sent to lender.
  - Approval rate (Approvals / Submissions).
  - Average interest rate offered.
  - Total funded volume.

## Usage Examples

### Python Client (httpx)
```python
import httpx

async def get_pipeline_report():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.mortgage-system.com/api/v1/reports/pipeline",
            params={"start_date": "2026-01-01"},
            headers={"Authorization": "Bearer <token>"}
        )
        return response.json()
```

### cURL
```bash
curl -X GET "https://api.mortgage-system.com/api/v1/reports/volume?period=monthly&year=2026" \
  -H "Authorization: Bearer <token>"
```
```

---

### 3. CHANGELOG Entry

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Reporting & Analytics: New endpoints for pipeline, volume, and lender performance metrics.
- Reporting & Analytics: Aggregated views for mortgage volume (monthly/quarterly/YTD).
- Reporting & Analytics: Lender performance tracking including approval rates and average rates.

### Changed
- Updated common/exceptions.py to include `ReportGenerationException`.
```

---

### 4. Environment Variables

**File:** `.env.example`

```bash
# Reporting & Analytics Configuration
# Default timezone for date grouping in reports (e.g., America/Toronto)
REPORTING_TIMEZONE=America/Toronto

# Cache duration for report results in seconds (reduces DB load)
REPORTING_CACHE_TTL=300
```