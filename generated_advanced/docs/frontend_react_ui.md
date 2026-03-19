# Frontend React UI
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

```markdown
# Frontend React UI Module Design

**Module Path:** `mortgage_underwriting/frontend/`  
**Feature Slug:** `frontend-react-ui`  
**Document:** `docs/design/frontend-react-ui.md`

## 1. Endpoints

The frontend consumes the following backend API endpoints. All endpoints require JWT authentication via OAuth 2.0 with PKCE flow, except health checks.

### Application Management
| Method | Path | Request Body | Response Schema | Auth | Error Codes |
|--------|------|--------------|-----------------|------|-------------|
| `POST` | `/api/v1/applications` | `ApplicationCreateDTO` | `ApplicationResponseDTO` | Authenticated | `APP_001`, `APP_002` |
| `GET` | `/api/v1/applications/{id}` | - | `ApplicationResponseDTO` | Authenticated | `APP_001` |
| `PATCH` | `/api/v1/applications/{id}` | `ApplicationUpdateDTO` | `ApplicationResponseDTO` | Authenticated | `APP_001`, `APP_002` |

### Document Upload
| Method | Path | Request Body | Response Schema | Auth | Error Codes |
|--------|------|--------------|-----------------|------|-------------|
| `POST` | `/api/v1/applications/{id}/documents` | `multipart/form-data` (pdf, jpg, png; max 10MB) | `DocumentUploadResponseDTO` | Authenticated | `DOC_001`, `DOC_002`, `DOC_003` |
| `GET` | `/api/v1/applications/{id}/documents` | - | `DocumentListDTO[]` | Authenticated | `APP_001` |

### Pipeline & Status
| Method | Path | Request Body | Response Schema | Auth | Error Codes |
|--------|------|--------------|-----------------|------|-------------|
| `GET` | `/api/v1/applications/{id}/status` | - | `PipelineStatusDTO` | Authenticated | `APP_001` |
| `GET` | `/api/v1/applications/{id}/decision` | - | `DecisionResultDTO` | Authenticated | `APP_001`, `DEC_001` |

### Exception Queue
| Method | Path | Request Body | Response Schema | Auth | Error Codes |
|--------|------|--------------|-----------------|------|-------------|
| `GET` | `/api/v1/exception-queue` | Query: `?status=flagged&sort=priority&page=1&limit=20` | `ExceptionQueueItemDTO[]` | Authenticated (Underwriter) | `QUEUE_001` |
| `POST` | `/api/v1/applications/{id}/review` | `UnderwriterReviewDTO` | `ReviewSubmittedDTO` | Authenticated (Underwriter) | `APP_001`, `REVIEW_001` |

### Audit Trail
| Method | Path | Request Body | Response Schema | Auth | Error Codes |
|--------|------|--------------|-----------------|------|-------------|
| `GET` | `/api/v1/applications/{id}/audit-trail` | - | `AuditLogDTO[]` | Authenticated | `APP_001` |

**Request/Response DTOs (TypeScript Interfaces):**
```typescript
// ApplicationCreateDTO
interface ApplicationCreateDTO {
  lender_id: string;
  property_value: string; // Decimal as string
  loan_amount: string; // Decimal as string
  borrower_profile: BorrowerProfileDTO;
}

// DocumentUploadResponseDTO
interface DocumentUploadResponseDTO {
  document_id: string;
  filename: string;
  upload_status: "pending" | "processing" | "completed" | "failed";
  extracted_data?: Record<string, any>;
}

// PipelineStatusDTO
interface PipelineStatusDTO {
  application_id: string;
  current_stage: "draft" | "extraction" | "validation" | "policy_check" | "underwriting" | "decision" | "exception_review";
  stage_status: "pending" | "in_progress" | "completed" | "failed";
  started_at: string;
  completed_at?: string;
  error_details?: string;
}

// DecisionResultDTO
interface DecisionResultDTO {
  decision: "approved" | "rejected" | "manual_review";
  gds_ratio: string; // Decimal percentage
  tds_ratio: string; // Decimal percentage
  qualifying_rate: string; // OSFI stress test rate
  cmhc_insurance_required: boolean;
  insurance_premium?: string;
  flags: DecisionFlagDTO[];
  ratio_breakdown: RatioBreakdownDTO;
}

// ExceptionQueueItemDTO
interface ExceptionQueueItemDTO {
  application_id: string;
  borrower_hash: string; // SHA256 of SIN for display
  priority: "high" | "medium" | "low";
  flag_categories: string[];
  days_in_queue: number;
  assigned_underwriter?: string;
}
```

## 2. Models & Database (Frontend State Management)

### TypeScript Domain Models
```typescript
// Core Application Model
interface Application {
  id: string;
  lender_id: string;
  property_value: Decimal;
  loan_amount: Decimal;
  ltv_ratio: Decimal; // Calculated frontend-side for display
  status: ApplicationStatus;
  created_at: Date;
  updated_at: Date;
  borrower_profile: BorrowerProfile;
}

// Borrower Profile (PIPEDA: sensitive fields masked)
interface BorrowerProfile {
  id: string;
  first_name: string;
  last_name: string;
  sin_hash: string; // SHA256 for lookups, never full SIN
  date_of_birth: string; // YYYY-MM-DD format, encrypted at rest
  gross_annual_income: Decimal;
  encrypted_data?: EncryptedPII; // For secure form editing
}

// Document Model
interface Document {
  id: string;
  application_id: string;
  filename: string;
  document_type: "pay_stub" | "tax_return" | "bank_statement" | "property_appraisal" | "id_verification";
  upload_status: UploadStatus;
  file_size: number; // bytes
  uploaded_at: Date;
  extracted_data?: Record<string, any>;
}

// Decision & Ratios (OSFI B-20 Compliance Display)
interface Decision {
  application_id: string;
  decision: DecisionOutcome;
  ratios: {
    gds: Decimal; // Must be ≤ 39%
    tds: Decimal; // Must be ≤ 44%
    qualifying_rate: Decimal; // max(contract_rate + 2%, 5.25%)
    contract_rate: Decimal;
  };
  cmhc: {
    insurance_required: boolean;
    premium_rate?: Decimal; // 2.80% | 3.10% | 4.00%
    premium_amount?: Decimal;
  };
  flags: Flag[];
  calculated_at: Date;
}

// Audit Trail (FINTRAC 5-year retention display)
interface AuditLogEntry {
  id: string;
  application_id: string;
  event_type: "created" | "updated" | "document_uploaded" | "ratio_calculated" | "flag_raised" | "decision_made" | "review_submitted";
  actor: string; // user_id or "system"
  timestamp: Date;
  details: Record<string, any>; // Never contains PII
  ip_address?: string;
}
```

### State Management Architecture
**Library:** Redux Toolkit with RTK Query for API caching

**Slices:**
- `applicationsSlice`: Manages application list, current application, form state
- `documentsSlice`: Manages document upload queue, progress, and status polling
- `decisionSlice`: Stores decision data and ratio breakdowns
- `exceptionQueueSlice`: Manages queue filtering, sorting, and pagination
- `authSlice`: Handles JWT tokens, refresh logic, and session timeout

**Persistent Storage:**
- `localStorage`: Encrypted JWT tokens (using `crypto.subtle` with rotation)
- `sessionStorage`: Form drafts (auto-saved, cleared on submission)
- **NEVER store**: SIN, DOB, or banking data in browser storage

## 3. Business Logic

### Document Upload Validation
- **File Types:** PDF, JPG, PNG only (MIME type validation)
- **Size Limit:** 10MB per file, 50MB total per application
- **Virus Scan:** Frontend hash check + backend scan status polling
- **Drag & Drop:** HTML5 File API with progress tracking
- **Accessibility:** Keyboard-navigable file selection, screen reader announcements for upload progress

### Pipeline Stage State Machine
```typescript
const PIPELINE_STAGES = {
  DRAFT: { next: "EXTRACTION", allow_edit: true },
  EXTRACTION: { next: "VALIDATION", allow_edit: false, auto_advance: true },
  VALIDATION: { next: "POLICY_CHECK", allow_edit: false },
  POLICY_CHECK: { 
    next: ["UNDERWRITING", "EXCEPTION_REVIEW"], 
    allow_edit: false,
    decision_paths: {
      passed: "UNDERWRITING",
      flagged: "EXCEPTION_REVIEW"
    }
  },
  UNDERWRITING: { next: "DECISION", allow_edit: false },
  DECISION: { next: null, allow_edit: false },
  EXCEPTION_REVIEW: { next: "UNDERWRITING", allow_edit: true, requires_underwriter: true }
} as const;
```

### Ratio Calculation Display Logic (OSFI B-20)
Frontend must display the **exact** calculation breakdown:
```
GDS = (Principal + Interest + Taxes + Heat) / Gross Monthly Income
TDS = (PITH + Other Debt Payments) / Gross Monthly Income
Qualifying Rate = MAX(Contract Rate + 2%, 5.25%)

Display requirements:
- Show monthly breakdown in expandable section
- Highlight values > 39% (GDS) or > 44% (TDS) in red
- Show stress test rate used with tooltip explanation
- Log calculation ID to console for audit (no PII)
```

### Exception Queue Filtering & Sorting
- **Filters:** priority, flag category, days_in_queue, assigned_underwriter
- **Sorting:** priority (desc), days_in_queue (desc), created_at (asc)
- **Pagination:** Server-side with cursor-based pagination (page size: 20)
- **Real-time:** WebSocket connection for queue updates (Socket.IO)

## 4. Migrations

**Not Applicable** for frontend module. State management schema changes are handled via:
- Redux store versioning with migration functions on app load
- Local storage schema checks with automatic clearing on version mismatch
- Feature flags for gradual UI rollouts

## 5. Security & Compliance

### PIPEDA (Data Protection)
- **Masking:** Display only last 4 digits of SIN (via hash): `••••••••••1234`
- **Encryption:** All PII fields encrypted in transit (TLS 1.3) and at rest (backend)
- **Data Minimization:** Forms only collect fields required for underwriting
- **No Logging:** Frontend logs NEVER contain SIN, DOB, income, or banking data
- **Secure Redaction:** Automated redaction of PII from browser console errors using `window.onerror` interceptor

### FINTRAC (Transaction Monitoring)
- **Flag Display:** Transactions > CAD $10,000 highlighted with amber border and "LCT" badge
- **Audit Trail Viewer:** Collapsible sections with immutable event logs, 5-year retention warning
- **Identity Verification:** Separate secure iframe for ID verification to isolate PII
- **Reporting UI:** Dedicated page for FINTRAC report generation (admin only)

### OSFI B-20 (Stress Test & Ratios)
- **Hard Limit Warnings:** Show modal when GDS > 39% or TDS > 44%: "Application violates OSFI B-20 thresholds"
- **Rate Display:** Qualifying rate shown in prominent banner with formula tooltip
- **Audit Badge:** Every ratio display includes "Calculation ID: {uuid}" for backend audit lookup

### Authentication & Authorization
- **Flow:** OAuth 2.0 Authorization Code with PKCE, JWT access token (15min), refresh token (7 days)
- **Token Storage:** `httpOnly: false` (for API calls) but encrypted in localStorage with rotating key
- **Role-Based Access:**
  - `applicant`: Create/read own applications only
  - `underwriter`: Full access + exception queue
  - `admin`: FINTRAC reporting, system config
- **Session Timeout:** 30-minute inactivity timer with warning modal at 25 minutes
- **mTLS:** Optional for underwriter/admin roles (configurable via `VITE_ENABLE_MTLS`)

## 6. Error Codes & HTTP Responses

### Backend-to-Frontend Error Mapping
| Backend Error Code | HTTP Status | Frontend Action | User Message |
|--------------------|-------------|-----------------|--------------|
| `APP_001` | 404 | Redirect to 404 page | "Application not found or you don't have access" |
| `APP_002` | 422 | Show field-level errors | "Please correct the highlighted fields" |
| `DOC_001` | 413 | Clear file input, show toast | "File too large. Maximum size is 10MB." |
| `DOC_002` | 422 | Reject file, show alert | "Invalid file type. Please upload PDF, JPG, or PNG." |
| `DEC_001` | 404 | Show placeholder | "Decision not yet available. Check back shortly." |
| `QUEUE_001` | 403 | Redirect to login | "Underwriter access required" |
| `REVIEW_001` | 409 | Disable submit button | "Review already submitted for this application" |

### Frontend-Specific Error Boundaries
```typescript
class UINotFoundError extends Error { code = "UI_001"; }
class UIValidationError extends Error { code = "UI_002"; }
class UISecurityError extends Error { code = "UI_003"; } // PII leak attempt

// Global error handler
window.addEventListener('error', (event) => {
  if (event.message.includes('SIN') || event.message.includes('DOB')) {
    event.stopImmediatePropagation();
    logger.error('PIPIPEDA violation blocked', { code: 'UI_003' });
  }
});
```

### Structured Error Responses
All API errors must return:
```typescript
interface ErrorResponse {
  detail: string; // User-friendly message
  error_code: string; // Backend error code
  correlation_id: string; // For support
  field_errors?: Record<string, string[]>; // For 422 validation errors
}
```

Frontend displays these in:
- **Toast notifications** for async errors (document upload failure)
- **Inline field errors** for form validation
- **Modal dialogs** for business rule violations
- **Error boundary fallback UI** for critical failures

---

## Additional Design Considerations

### UI/UX Mockups (Key Screens)
1. **Application Submission:** Left sidebar with document checklist, right panel with drag-drop zone and lender dropdown
2. **Status Tracker:** Vertical timeline with icons for each pipeline stage, expandable for details
3. **Decision Review:** Top summary cards (GDS/TDS), middle section with collapsible ratio breakdown, bottom flags list
4. **Exception Queue:** Data table with sortable columns, priority color coding, and quick action buttons

### Responsive Design (Mobile First)
- **Breakpoints:** `sm: 640px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`
- **Mobile Optimizations:**
  - Document upload: Native camera capture for ID documents
  - Status tracker: Horizontal swipeable cards instead of vertical timeline
  - Decision charts: Simplified bar charts instead of complex radar charts
- **Touch Targets:** Minimum 44x44px per WCAG 2.5.5

### Accessibility (WCAG 2.1 AA)
- **Keyboard Navigation:** Full tab order, skip links, focus indicators
- **Screen Readers:** ARIA labels on all interactive elements, live regions for dynamic content
- **Color Contrast:** Minimum 4.5:1 ratio, color-blind friendly palette
- **Forms:** Explicit labels, error messages associated with inputs via `aria-describedby`

### Internationalization (i18n)
- **Library:** i18next with ICU message format
- **Supported Locales:** `en-CA`, `fr-CA` (initial)
- **Content:** All user-facing strings externalized to JSON files
- **Formatting:** `Intl.NumberFormat` for currency (CAD), dates in `YYYY-MM-DD` format

### Performance Optimization
- **Code Splitting:** Route-based splitting with React.lazy, component-level splitting for heavy charts
- **Bundle Size:** Import only used icons from libraries, tree-shaking enabled
- **Caching:** RTK Query for API response caching, service worker for static assets
- **Images:** Automatic WebP conversion with JPEG fallback, lazy loading
- **Virtualization:** react-window for long audit trail lists
- **Metrics:** Core Web Vitals monitoring via OpenTelemetry browser instrumentation
```