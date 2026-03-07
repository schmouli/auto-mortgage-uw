# Frontend React UI
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Frontend React UI Module Design Plan

**Design Document Location:** `docs/design/frontend-ui-module.md`  
**Module Identifier:** `FRONTEND`  
**Last Updated:** 2024

---

## 1. Endpoints

The frontend consumes the following backend API endpoints. All endpoints require JWT authentication via `Authorization: Bearer <token>` header unless marked as public.

### Application Submission
| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| `POST` | `/api/v1/applications` | `ApplicationCreateSchema` (JSON) | `201 { application_id: uuid, status: "draft" }` | `401`, `422` |
| `POST` | `/api/v1/documents/{application_id}/upload` | `multipart/form-data` (file, doc_type) | `201 { document_id: uuid, status: "uploaded" }` | `400`, `413`, `422` |
| `GET` | `/api/v1/lenders` | - | `200 { lenders: [{id, name, code}] }` | `401` |

### Application Status
| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| `GET` | `/api/v1/applications/{id}/status` | - | `200 ApplicationStatusSchema` | `401`, `404` |
| `GET` | `/api/v1/applications/{id}/pipeline-events` | - | `200 { events: PipelineEventSchema[] }` | `401`, `404` |

### Decision Review
| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| `GET` | `/api/v1/applications/{id}/decision` | - | `200 DecisionSchema` | `401`, `404`, `409` |
| `GET` | `/api/v1/applications/{id}/audit-trail` | - | `200 { trail: AuditEntrySchema[] }` | `401`, `404` |

### Exception Queue
| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| `GET` | `/api/v1/exceptions` | `?status=flagged&sort=priority` | `200 { exceptions: ExceptionItemSchema[], total: int }` | `401`, `403` |
| `PATCH` | `/api/v1/exceptions/{id}/review` | `ReviewActionSchema` | `200 { status: "reviewed" }` | `401`, `403`, `409` |

**Authentication:** All endpoints require `underwriter` role; `admin` role for exception queue management.

---

## 2. Models & Database (Frontend State)

### TypeScript Interfaces

```typescript
// src/modules/application/types/application.types.ts
interface ApplicationCreate {
  lender_id: string;
  property_value: Decimal;
  loan_amount: Decimal;
  borrower: BorrowerDetails;
  documents: DocumentUpload[];
}

interface BorrowerDetails {
  first_name: string;
  last_name: string;
  sin_hash?: string; // PIPEDA: Never display full SIN
  dob_encrypted?: string; // PIPEDA: Encrypted, masked display
  gross_annual_income: Decimal;
}

interface Decision {
  application_id: string;
  decision: "approved" | "rejected" | "refer";
  gds_ratio: Decimal;
  tds_ratio: Decimal;
  qualifying_rate: Decimal;
  cmhc_insurance: {
    required: boolean;
    premium_rate: Decimal | null;
  };
  flags: Flag[];
  calculated_at: ISO8601;
}

interface AuditEntry {
  id: string;
  action: string;
  actor: string;
  timestamp: ISO8601;
  metadata: Record<string, any>; // FINTRAC: Immutable trail
}
```

### State Management (Zustand Store)

```typescript
// src/store/applicationStore.ts
interface ApplicationState {
  currentApplication: Application | null;
  uploadProgress: Record<string, number>; // doc_id -> percent
  pipelineStatus: {
    stage: "extraction" | "validation" | "policy" | "decision";
    progress: number; // 0-100
    errors: string[];
  };
}
```

### Local Storage Schema (for draft applications)
```typescript
// Key: `draft_application_${userId}`
interface DraftApplication {
  id: string;
  data: ApplicationCreate;
  last_saved: ISO8601;
  version: 1; // For future migrations
}
```

---

## 3. Business Logic

### Document Upload Validation
- **File Types:** PDF, JPEG, PNG only (MIME validation)
- **Max Size:** 10MB per file (configurable via `config.ts`)
- **Virus Scan:** Frontend checksum generation, upload only after backend scan token received
- **Drag & Drop:** HTML5 File API with progress tracking via Axios `onUploadProgress`

### Application State Machine
```typescript
// src/modules/application/hooks/useApplicationWorkflow.ts
const states = {
  DRAFT: { next: ["SUBMITTED"], actions: ["save_draft", "upload_docs"] },
  SUBMITTED: { next: ["EXTRACTION"], actions: [] },
  EXTRACTION: { next: ["VALIDATION", "FLAGGED"], actions: ["retry"] },
  VALIDATION: { next: ["POLICY_CHECK", "FLAGGED"], actions: [] },
  POLICY_CHECK: { next: ["DECISION_MADE", "FLAGGED"], actions: [] },
  DECISION_MADE: { next: ["APPROVED", "REJECTED", "REFERRED"], actions: [] },
  FLAGGED: { next: ["UNDER_REVIEW", "ESCALATED"], actions: ["assign_underwriter"] },
};
```

### Decision Visualization Logic
- **GDS/TDS Gauge:** Recharts radial bar with color coding:
  - Green: ≤ 35% (GDS) / ≤ 42% (TDS)
  - Yellow: 35-39% / 42-44%
  - Red: > 39% / > 44% (OSFI B-20 violation)
- **Stress Test Indicator:** Show `qualifying_rate` vs `contract_rate` + 2% with warning if < 5.25%

### Exception Queue Filtering
- **Filters:** status, priority, lender, submission_date_range
- **Sorting:** priority (high→low), submission_date (new→old)
- **Search:** Application ID, borrower last name (debounced 300ms)

---

## 4. Migrations

**Not Applicable** for frontend module. Frontend is stateless; no database migrations required. Versioning handled via:
- **API Versioning:** `/api/v1` prefix ensures backward compatibility
- **Local Storage:** If `draft_application` schema changes, implement migration logic in `src/utils/storageMigrator.ts`
- **Feature Flags:** Use LaunchDarkly SDK for gradual rollout of UI changes

---

## 5. Security & Compliance

### PIPEDA (Data Minimization & Encryption)
- **SIN Display:** Never show full SIN. Display last 3 digits only: `***-**-1234`
- **DOB Display:** Mask as `**/**/1990` in all UI components
- **Logs:** Configure `structlog` in frontend to never log PII. Use `pino` with redaction paths:
  ```typescript
  const logger = pino({
    redact: ["*.sin", "*.dob", "*.banking"]
  });
  ```
- **Cache:** Disable browser caching for pages showing PII via `Cache-Control: no-store`

### FINTRAC Audit Trail
- **Frontend Actions:** Log all underwriter actions to backend audit endpoint
- **Immutability:** Frontend never modifies audit trail entries; display only with read-only indicators
- **Large Transactions:** Highlight applications with loan_amount > CAD $10,000 with amber border

### OSFI B-20 Compliance Display
- **Ratio Warnings:** Show inline warnings when GDS/TDS exceeds thresholds during form input
- **Stress Test:** Always display qualifying rate calculation breakdown in collapsible panel
- **Read-Only:** Decision ratios are immutable once calculated; frontend disables editing

### Authentication & Authorization
- **JWT Handling:** Stored in `httpOnly` cookies only; frontend accesses via `X-CSRF-Token` header
- **Role-Based Access:** `usePermission` hook checks `underwriter` role for all routes
- **Session Timeout:** Auto-logout after 15 minutes inactivity (FINTRAC requirement)

---

## 6. Error Codes & HTTP Responses

### Frontend Exception Mapping

| Exception Class | HTTP Status | Error Code | User Message Pattern | Action |
|-----------------|-------------|------------|----------------------|--------|
| `AuthenticationError` | 401 | `FRONTEND_001` | "Session expired. Please log in." | Redirect to `/login` |
| `AuthorizationError` | 403 | `FRONTEND_002` | "You don't have permission to view this." | Show 403 page |
| `ApplicationNotFoundError` | 404 | `FRONTEND_003` | "Application {id} not found." | Redirect to dashboard |
| `ValidationError` | 422 | `FRONTEND_004` | "Please fix the errors in the form." | Highlight fields |
| `UploadSizeExceededError` | 413 | `FRONTEND_005` | "File exceeds 10MB limit." | Clear file input |
| `RateLimitError` | 429 | `FRONTEND_006` | "Too many requests. Try again later." | Disable button 30s |
| `ServerError` | 500+ | `FRONTEND_007` | "System error. Contact support." | Log to Sentry |
| `NetworkError` | 0/timeout | `FRONTEND_008` | "Network connection lost." | Retry button |

### Toast Notification System
```typescript
// src/components/common/ToastProvider.tsx
interface Toast {
  id: string;
  type: "error" | "warning" | "success";
  title: string;
  message: string;
  error_code?: string;
  dismissible: boolean;
  duration: number; // 0 for persistent errors
}
```

### Error Boundary Implementation
- **Component-Level:** Wrap document uploader and decision viewer in `React.ErrorBoundary`
- **Fallback UI:** Show "Something went wrong" with `error_code` and "Retry" button
- **Reporting:** Auto-send to Sentry with sanitized context (no PII)

---

## Appendix: Missing Details Implementation Strategy

### WCAG 2.1 AA Compliance
- **Keyboard Navigation:** All interactive elements reachable via Tab; focus indicators visible
- **Screen Readers:** Use `aria-live` for async updates; `aria-describedby` for form errors
- **Color Contrast:** Minimum 4.5:1 ratio; use `axe-core` in CI pipeline
- **Testing:** `@axe-core/react` in development; manual testing with NVDA/JAWS

### Responsive Design (Mobile-First)
- **Breakpoints:** `sm: 640px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`
- **Layouts:** CSS Grid for dashboards; Flexbox for forms; `react-responsive` for component variants
- **Touch Targets:** Minimum 44x44px; increase padding on mobile upload zones

### Internationalization (i18n)
- **Framework:** `react-i18next` with namespaces per module
- **Locales:** `en-CA`, `fr-CA` (OSFI bilingual requirement)
- **Currency:** Use `Intl.NumberFormat` with `CAD` currency; `Decimal.js` for calculations
- **Date Format:** `YYYY-MM-DD` display with `fr-CA` as `AAAA-MM-JJ`

### Performance Optimization
- **Code Splitting:** Route-based splitting via `React.lazy()`; vendor chunk separation
- **Bundle Size:** `esbuild` with tree-shaking; analyze via `webpack-bundle-analyzer`
- **Images:** Lazy load with `loading="lazy"`; WebP format with JPEG fallback
- **API:** React Query with aggressive caching (5min for decisions, 30s for status)
- **Virtualization:** `react-window` for exception queue > 100 items

### Observability
- **RUM:** Datadog Real User Monitoring with `trackUserActions`
- **Performance:** Web Vitals (LCP < 2.5s, FID < 100ms, CLS < 0.1)
- **Error Tracking:** Sentry with PII scrubbing rules

---

**Next Steps:**  
1. Create `frontend/` directory parallel to `mortgage_underwriting/`  
2. Initialize with Vite + React + TypeScript template  
3. Implement module structure matching backend module names for 1:1 mapping  
4. Add `Makefile` target: `make frontend-dev` (runs `vite dev --port 3000`)