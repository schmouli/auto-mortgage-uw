# Design: Frontend React UI
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Frontend React UI Module Design

**File:** `docs/design/frontend-ui.md`  
**Module:** `frontend-ui`  
**Technology Stack:** React 18.3+, TypeScript 5.3+, Vite 5.0+

---

## Overview

The Frontend React UI module provides a secure, accessible, and auditable interface for mortgage underwriters and brokers to submit applications, monitor pipeline progress, review automated decisions, and handle exception cases. All components enforce PIPEDA data minimization principles and never display full SIN/DOB values.

---

## 1. API Endpoints Consumed

| Method | Path | Purpose | Auth Required | Sensitive Data Handling |
|--------|------|---------|---------------|------------------------|
| `POST` | `/api/v1/applications` | Submit new application | Yes | Encrypt SIN/DOB before sending |
| `GET` | `/api/v1/applications/{id}` | Fetch application details | Yes | Mask SIN/DOB in UI |
| `GET` | `/api/v1/applications/{id}/status` | Poll pipeline status | Yes | No PII returned |
| `GET` | `/api/v1/applications/{id}/decision` | Retrieve decision JSON & ratios | Yes | Log ratio breakdowns only |
| `GET` | `/api/v1/applications/{id}/audit` | Fetch audit trail | Yes | Filter PII from logs |
| `GET` | `/api/v1/applications/queue/exceptions` | List flagged applications | Yes | Mask borrower identifiers |
| `PATCH` | `/api/v1/applications/{id}/exception-review` | Submit human review decision | Yes | Audit log required |

**Error Response Handling:**
- `401 Unauthorized` → Redirect to `/login`
- `403 Forbidden` → Show error boundary with contact admin message
- `422 Validation Error` → Display field-level errors using `error_code` mapping
- `409 Business Rule Violation` → Show modal with rule details and remediation steps

---

## 2. Data Models & TypeScript Interfaces

```typescript
// src/types/application.ts
interface Borrower {
  id: string;
  sin_hash: string; // SHA256 hash for lookups
  sin_masked: string; // Last 4 digits only: "***-***-1234"
  date_of_birth_masked: string; // "19**-01-15"
  first_name: string;
  last_name: string;
  gross_annual_income: Decimal; // String serialized
  // Banking data never loaded to frontend
}

interface ApplicationSubmission {
  property_value: Decimal;
  loan_amount: Decimal;
  contract_rate: Decimal;
  amortization_years: number;
  borrowers: Array<{
    sin: string; // Encrypted in transit
    date_of_birth: string; // Encrypted
    first_name: string;
    last_name: string;
    gross_annual_income: Decimal;
  }>;
  lender_id: string;
  documents: DocumentUpload[];
}

interface DecisionBreakdown {
  gds_ratio: Decimal; // Calculated with OSFI stress test
  tds_ratio: Decimal;
  qualifying_rate: Decimal; // max(contract_rate + 2%, 5.25%)
  insurance_required: boolean;
  insurance_premium: Decimal | null;
  ltv_ratio: Decimal;
  flags: string[]; // e.g., ["HIGH_LTV", "LOW_CREDIT_SCORE"]
  recommendation: "APPROVED" | "REJECTED" | "MANUAL_REVIEW";
  ratio_audit_log: string; // Immutable calculation trace
}

interface AuditTrailEntry {
  created_at: ISO8601DateTime;
  created_by: string; // User ID hash
  action: string;
  details: Record<string, any>; // PII stripped
}
```

---

## 3. Frontend Business Logic

### State Machine Visualization
Pipeline stages: `DRAFT` → `UPLOADING` → `EXTRACTION` → `VALIDATION` → `UNDERWRITING` → (`APPROVED` | `REJECTED` | `MANUAL_REVIEW`)

### Validation Rules (Pre-Submission)
- **File Types:** PDF only, MIME type validation before upload
- **File Size:** Max 10MB per document, 50MB total
- **Lender Selection:** Required, must be from `/api/v1/lenders` list
- **Borrower Count:** 1-4 borrowers max
- **Income Validation:** `gross_annual_income > 0` and ≤ CAD $2,000,000
- **LTV Check:** Warn if LTV > 95% before submission

### Ratio Calculation Display Logic
```typescript
// Stress test rate display
const qualifyingRate = Math.max(contractRate + 0.02, 0.0525);

// GDS/TDS display formatting
// Show 2 decimal places, red if > threshold
const gdsColor = gdsRatio > 0.39 ? "text-destructive" : "text-success";
const tdsColor = tdsRatio > 0.44 ? "text-destructive" : "text-success";
```

---

## 4. State Management & Storage

**Library:** Zustand with Immer middleware  
**Persistence:** None (no PII stored in localStorage)

### Store Slices

```typescript
// src/store/applicationStore.ts
interface ApplicationStore {
  currentApplication: Application | null;
  isSubmitting: boolean;
  uploadProgress: Record<string, number>; // Document ID → progress %
  setUploadProgress: (docId: string, progress: number) => void;
  clearApplication: () => void; // Secure cleanup
}

// src/store/exceptionQueueStore.ts
interface ExceptionQueueStore {
  applications: Array<{
    id: string;
    borrower_name_masked: string;
    flag_count: number;
    days_in_queue: number;
    ltv_ratio: Decimal;
  }>;
  filters: {
    flag_type: string[];
    min_ltv: number;
  };
  sorting: { field: string; direction: "asc" | "desc" };
}
```

**Security Measures:**
- `clearApplication()` called on logout or tab close
- No PII cached in memory beyond current session
- Redux DevTools disabled in production

---

## 5. Security & Compliance

### PIPEDA Implementation
- **SIN/DOB Handling:** Encrypted using AES-256-GCM in `encryptPII()` service before API call
- **Display Masking:** Only show last 4 SIN digits; birth year partially masked
- **Network:** All API calls use mTLS via Vite proxy configuration
- **Logging:** Frontend logs NEVER include SIN, DOB, income, or banking data
- **Session Timeout:** 30-minute inactivity auto-logout

### Authentication
- OAuth 2.0 Authorization Code Flow with PKCE
- JWT stored in `httpOnly` cookies only (no localStorage)
- Role-based access: `UNDERWRITER`, `BROKER`, `ADMIN`
- MFA required for all users (TOTP)

### FINTRAC Audit Trail
- Every action logged via `/api/v1/audit/events`
- Frontend generates `correlation_id` for each user session
- Transaction amount > $10,000 flagged automatically in UI with warning banner

---

## 6. Error Handling & User Feedback

### Exception Classes & UI Mapping

| API Error Code | Frontend Status | User Message | UI Action |
|----------------|-----------------|--------------|-----------|
| `APP_001` | 404 | "Application not found" | Redirect to dashboard |
| `APP_002` | 422 | "Invalid field: {field}" | Highlight field, show tooltip |
| `APP_003` | 409 | "OSFI B-20 threshold exceeded" | Show ratio breakdown modal |
| `APP_004` | 403 | "Access denied" | Logout + contact admin |
| `UNDERWRITING_005` | 422 | "Document extraction failed" | Retry upload button |

### Global Error Boundary
```tsx
// src/components/ErrorBoundary.tsx
class ErrorBoundary extends React.Component {
  componentDidCatch(error) {
    logError({ message: error.message, stack: error.stack }); // No PII
  }
  render() {
    return this.props.fallback || <GenericErrorPage />;
  }
}
```

---

## 7. Component Architecture

### DocumentUploader
- **Props:** `onUploadComplete`, `maxFiles`, `acceptedTypes`
- **Features:** Drag-and-drop, progress bars, virus scan status
- **Security:** Client-side MIME validation, file size check before upload
- **Accessibility:** Keyboard navigation, screen reader announcements

### PipelineProgress
- **Props:** `currentStage`, `stageHistory`
- **Visual:** Vertical timeline with icons, timestamps, error states
- **Compliance:** Shows audit trail for stage transitions

### DecisionVisualization
- **Charts:** Recharts pie chart for ratio breakdown, bar chart for stress test comparison
- **Tables:** Sortable flags table with severity indicators
- **Export:** PDF generation of decision summary (PII excluded)

### AuditTrailViewer
- **Props:** `applicationId`
- **Features:** Collapsible sections, filter by action type, date range picker
- **Security:** PII fields rendered as `[REDACTED]` if present

### ExceptionQueue
- **Props:** `filters`, `onFilterChange`
- **Columns:** App ID, Borrower (masked), Flags, LTV, Days in Queue, Actions
- **Sorting:** Server-side via query params `?sort_by=ltv&order=desc`
- **Batch Actions:** Approve/Reject selected (ADMIN only)

---

## 8. Page Specifications

### `/submit-application`
- **Layout:** Two-column (form left, document upload right)
- **Form Fields:** Property value, loan amount, rate, amortization, lender dropdown, borrower repeater
- **Validation:** Real-time LTV calculation with CMHC premium preview
- **Submission:** Disable button while submitting, show progress overlay

### `/applications/{id}/status`
- **Polling:** 5-second interval for `EXTRACTION`/`UNDERWRITING` stages
- **Auto-refresh:** Stop polling when terminal state reached
- **Links:** Decision review button appears when available

### `/applications/{id}/decision`
- **Tabs:** Overview, Ratios, Flags, Audit Trail
- **Ratio Display:** Large numeric display with color coding, tooltip showing formula
- **OSFI Compliance:** Stress test rate always visible with calculation footnote

### `/queue/exceptions`
- **Filters:** Flag type multiselect, LTV range slider, days in queue
- **Pagination:** Server-side, 50 items per page
- **Detail Panel:** Slide-out panel showing summary without page navigation

---

## 9. UI/UX Considerations

### Responsive Design (Mobile First)
- **Breakpoints:** `sm: 640px`, `lg: 1024px`
- **Mobile:** Single-column layout, collapsible navigation, touch-optimized file upload
- **Tablet:** Two-column on landscape, maintain document preview

### Accessibility (WCAG 2.1 AA)
- **Color Contrast:** Minimum 4.5:1 ratio (using Tailwind's `contrast-more` variant)
- **Keyboard:** Full keyboard navigation, `Tab` order logical
- **Screen Readers:** ARIA labels on all interactive elements, live regions for async updates
- **Forms:** Explicit `label` associations, error messages linked via `aria-describedby`

### Internationalization (i18n)
- **Library:** `react-i18next`
- **Namespaces:** `common`, `applications`, `decisions`, `errors`
- **Date/Number:** `Intl.DateTimeFormat` and `Intl.NumberFormat` for CAD currency
- **RTL:** Not required (English/French only)

### Performance Optimization
- **Code Splitting:** Route-level code splitting via React.lazy
- **Bundle:** Vite Rollup options, target modern browsers (ES2020)
- **Images:** PDF previews generated server-side as thumbnails
- **Caching:** API responses cached with SWR/React Query (5-minute TTL, no PII cached)
- **Virtualization:** Exception queue uses `react-window` for large lists

---

## 10. Testing Strategy

### Unit Tests (Vitest)
- **Coverage Target:** 80% for business logic, 100% for validation functions
- **Mocking:** MSW for API calls, never mock PII encryption
- **Snapshot Tests:** Only for presentational components

### Integration Tests (Playwright)
- **Auth Flow:** Complete login → submit → logout cycle
- **PII Handling:** Verify SIN/DOB never appear in page source or network logs
- **Accessibility:** Automated axe-core scans on every page
- **Compliance:** Simulate OSFI threshold breach and verify warning display

### Performance Budget
- **Bundle Size:** Entry point < 200KB gzipped
- **Lighthouse Score:** > 90 on Performance, Accessibility, Best Practices
- **First Contentful Paint:** < 1.5s on 3G

---

## 11. Deployment & Environment

### Build Configuration
- `.env.production`: `VITE_API_BASE_URL`, `VITE_OTEL_ENDPOINT`
- **Source Maps:** Generated but not uploaded to public CDN
- **CSP Headers:** Strict CSP blocking inline scripts, allowing only self and API domain

### Observability
- **Logs:** `structlog` via `console.log` JSON format with `correlation_id`
- **Tracing:** OpenTelemetry browser SDK, sampled at 10%
- **Metrics:** Prometheus client for page load times, error rates
- **RUM:** Capture user interactions (excluding form fields with PII)

---

## 12. Appendix: Frontend Error Code Registry

| Error Code | Trigger | User-Facing Message | Audit Log Level |
|------------|---------|---------------------|-----------------|
| `FE_AUTH_001` | Token expiry | "Session expired" | INFO |
| `FE_PII_001` | PII detected in log | [Internal only] | CRITICAL |
| `FE_API_001` | Network failure | "Service unavailable" | WARN |
| `FE_VALID_001` | Client validation fail | "Please correct errors" | DEBUG |
| `FE_COMPLIANCE_001` | FINTRAC threshold | "Large transaction flag applied" | INFO |

---

**WARNING:** This design assumes backend API implements all regulatory requirements. Frontend must never duplicate OSFI calculations or FINTRAC logic—only display backend-provided results.