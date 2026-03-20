# Frontend React UI
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Frontend React UI Module Design Plan

**File:** `docs/design/frontend-react-ui.md`

---

## 1. Endpoints

The frontend consumes existing backend module APIs. Key endpoints required:

### Application Management
| Method | Path | Request | Response | Auth | Purpose |
|--------|------|---------|----------|------|---------|
| `POST` | `/api/v1/applications` | `ApplicationCreateSchema` | `ApplicationResponseSchema` | Authenticated | Create new application |
| `GET` | `/api/v1/applications/{id}` | - | `ApplicationResponseSchema` | Authenticated | Fetch application details |
| `GET` | `/api/v1/applications` | `QueryParams` | `List[ApplicationResponseSchema]` | Authenticated | List applications with filters |
| `POST` | `/api/v1/applications/{id}/submit` | - | `SubmissionResponseSchema` | Authenticated | Submit for underwriting |

### Document Upload
| Method | Path | Request | Response | Auth | Purpose |
|--------|------|---------|----------|------|---------|
| `POST` | `/api/v1/documents/upload` | `multipart/form-data` | `DocumentUploadResponse` | Authenticated | Upload borrower PDFs |
| `GET` | `/api/v1/documents/{id}/status` | - | `DocumentProcessingStatus` | Authenticated | Check extraction progress |

### Decision & Audit
| Method | Path | Request | Response | Auth | Purpose |
|--------|------|---------|----------|------|---------|
| `GET` | `/api/v1/decisions/{application_id}` | - | `DecisionSchema` | Authenticated | Get decision JSON with ratios |
| `GET` | `/api/v1/audit/{application_id}` | - | `AuditTrailResponse` | Authenticated | Fetch audit trail entries |

### Exception Queue
| Method | Path | Request | Response | Auth | Purpose |
|--------|------|---------|----------|------|---------|
| `GET` | `/api/v1/exceptions/queue` | `QueryParams` | `List[ExceptionQueueItem]` | Underwriter-Only | List flagged applications |
| `POST` | `/api/v1/exceptions/{id}/review` | `ReviewActionSchema` | `ReviewResponseSchema` | Underwriter-Only | Approve/reject flagged item |

**Error Responses:** All endpoints return `{"detail": "...", "error_code": "..."}` with appropriate HTTP status codes.

---

## 2. Models & Database (Frontend State)

### TypeScript Interfaces
```typescript
// Core Application Model
interface Application {
  id: string;
  lender_id: string;
  property_value: Decimal;
  loan_amount: Decimal;
  status: 'draft' | 'submitted' | 'extracting' | 'underwriting' | 'approved' | 'rejected' | 'exception';
  created_at: ISO8601DateTime;
  updated_at: ISO8601DateTime;
  gds_ratio?: Decimal; // Calculated by backend
  tds_ratio?: Decimal; // Calculated by backend
  cmhc_insurance_required?: boolean;
  cmhc_premium?: Decimal;
}

// Document Model
interface Document {
  id: string;
  application_id: string;
  filename: string;
  document_type: 'paystub' | 'bank_statement' | 'tax_return' | 'property_appraisal';
  status: 'pending' | 'processing' | 'extracted' | 'failed';
  extracted_data?: Record<string, any>;
  created_at: ISO8601DateTime;
}

// Decision Model
interface Decision {
  application_id: string;
  decision: 'approved' | 'rejected' | 'refer';
  qualifying_rate: Decimal; // OSFI B-20: max(rate + 2%, 5.25%)
  gds_breakdown: {
    pith: Decimal;
    gross_monthly_income: Decimal;
    ratio: Decimal; // Must be ≤ 39%
  };
  tds_breakdown: {
    total_debt: Decimal;
    ratio: Decimal; // Must be ≤ 44%
  };
  flags: Array<{
    code: string;
    severity: 'low' | 'medium' | 'high';
    description: string;
  }>;
  cmhc_tier?: '80_85' | '85_90' | '90_95';
}

// Audit Trail Model
interface AuditEntry {
  id: string;
  application_id: string;
  action: string;
  actor: string; // Hashed user ID, never PII
  timestamp: ISO8601DateTime;
  ip_address?: string; // For FINTRAC logging
  details: Record<string, any>; // Never contains SIN/DOB
}
```

### State Management (Redux Toolkit)
```typescript
// Store structure
interface AppState {
  applications: {
    byId: Record<string, Application>;
    listIds: string[];
    filters: {
      status?: string;
      lender_id?: string;
      date_range?: [ISO8601Date, ISO8601Date];
    };
    loading: boolean;
  };
  documents: {
    uploadQueue: Array<{
      file: File;
      status: 'pending' | 'uploading' | 'complete' | 'error';
      progress: number;
    }>;
  };
  decisions: {
    current: Decision | null;
    auditTrail: AuditEntry[];
  };
  exceptions: {
    queue: ExceptionQueueItem[];
    sortBy: 'timestamp' | 'severity' | 'lender';
  };
}
```

---

## 3. Business Logic

### Document Upload Flow
1. **Drag-and-Drop Validation**: Accept only PDF, max 10MB per file, max 20 files
2. **Client-Side Virus Scan**: Integrate ClamAV WASM scanner before upload
3. **Progress Tracking**: Calculate upload percentage using `xhr.upload.onprogress`
4. **Resumable Uploads**: Implement TUS protocol for files > 5MB
5. **FINTRAC Trigger**: If `loan_amount > 10000`, attach `transaction_type` metadata

### Pipeline Status State Machine
```
draft → submitted → extracting → underwriting → [approved|rejected]
                                      ↓
                                   exception → [approved|rejected] (human review)
```

**UI Transitions:**
- **Extracting**: Poll `/documents/{id}/status` every 2s, show progress bar
- **Underwriting**: Display skeleton loader, subscribe to WebSocket `decision_ready` event
- **Exception**: Auto-refresh queue every 30s, show notification badge

### Decision Visualization Logic
- **GDS/TDS Gauge Charts**: Color-coded thresholds (Green ≤ 39%/44%, Yellow 39-42%/44-47%, Red > 42%/47%)
- **Stress Test Indicator**: Show `qualifying_rate` calculation: `max(contract_rate + 2%, 5.25%)`
- **CMHC Premium Display**: If `insurance_required`, show tiered premium:
  - 80.01-85%: 2.80% of loan amount
  - 85.01-90%: 3.10% of loan amount
  - 90.01-95%: 4.00% of loan amount
- **Audit Trail Collapsible**: Group by `action` type, default collapsed for `created_at` > 24h

### Exception Queue Filtering
- **Filters**: `lender_id`, `severity`, `flag_code`, `date_range`
- **Sorting**: `timestamp` (default), `severity` (high→low), `gds_ratio` (desc)
- **Pagination**: Cursor-based, 20 items per page
- **Auto-refresh**: Pause when user is interacting (scroll/click within last 5s)

---

## 4. Migrations (UI Versioning & Local Storage)

### Version 1.0 → 1.1 Migration
- **Purpose**: Add `cmhc_premium` field to cached applications
- **Migration Script**:
  ```typescript
  // localStorage key: mortgage_app_cache_v1
  const migrate = (oldData: any) => ({
    ...oldData,
    applications: oldData.applications.map((app: any) => ({
      ...app,
      cmhc_premium: calculateCMHCPremium(app.loan_amount, app.property_value)
    }))
  });
  ```

### IndexedDB Schema (Offline Support)
**Object Stores:**
- `applications`: `id` (primary key), `status`, `updated_at` (index)
- `documents`: `id` (primary key), `application_id` (index), `status`
- `audit_logs`: `id` (primary key), `application_id` (index), `timestamp`

**Version 1:** Initial schema  
**Version 2:** Add `sync_status` field to applications for offline queue

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Data Masking**: Display only last 4 digits of SIN (`***-**-1234`), hash in memory
- **DOB Redaction**: Show age only (e.g., "42 years old"), never full date
- **PII Logging**: Frontend logs must **never** contain SIN, DOB, income, banking data
- **Session Timeout**: Auto-logout after 15min inactivity, clear Redux state
- **Secure Storage**: Store JWT in `httpOnly` cookies, never `localStorage`

### FINTRAC Requirements
- **Audit Trail Display**: Show `created_by` as hashed user ID, never email/name
- **Transaction Flagging**: Display `transaction_type` badge for amounts > CAD $10,000
- **5-Year Retention Warning**: Show indicator if record is approaching retention limit

### OSFI B-20 Auditability
- **GDS/TDS Breakdown**: Always show full calculation: `PITH / Income`, `Total Debt / Income`
- **Stress Test Disclosure**: Display `qualifying_rate` formula and result prominently
- **Ratio Logging**: Frontend telemetry logs `ratio_calculated` event with `application_id` and `timestamp` (no PII)

### Authentication & Authorization
- **Public Pages**: None (all routes require auth)
- **Authenticated**: Application Submission, Application Status, Decision Review
- **Underwriter-Only**: Exception Queue (`role: 'underwriter'`)

---

## 6. Error Codes & HTTP Responses

### Frontend Error Mapping
| Backend Error Code | Frontend Display Message | UI Action |
|-------------------|--------------------------|-----------|
| `APPLICATION_001` | "Application not found. It may have been deleted." | Redirect to dashboard |
| `DOCUMENT_002` | "Invalid file type. Please upload PDF only." | Highlight file input |
| `UNDERWRITING_003` | "GDS ratio exceeds 39% limit." | Show red badge on GDS gauge |
| `UNDERWRITING_004` | "TDS ratio exceeds 44% limit." | Show red badge on TDS gauge |
| `FINTRAC_005` | "Transaction requires additional review." | Display warning banner |
| `CMHC_006` | "LTV > 80% requires mortgage insurance." | Show insurance premium calculator |
| `PIPEDA_007` | "Access denied. Sensitive data restriction." | Mask fields, show lock icon |

### Frontend-Specific Errors
| Error Code | HTTP Status | Message Pattern | Trigger |
|------------|-------------|-----------------|---------|
| `UI_VALIDATION_001` | 400 | "File size exceeds 10MB limit" | Client-side file check |
| `UI_NETWORK_002` | 503 | "Unable to connect to server" | API timeout/failure |
| `UI_AUTH_003` | 401 | "Session expired. Please log in." | JWT validation fail |
| `UI_PERMISSION_004` | 403 | "Insufficient permissions" | Role-based guard |

### Error Boundary Implementation
- **Global Boundary**: Catch-all component showing "Something went wrong" with `error_id` (UUID)
- **Route Boundaries**: Per-page error handling, e.g., `/exceptions` shows "Queue unavailable" on failure
- **Component Boundaries**: Document uploader shows retry button on upload failure

---

## 7. Accessibility & Performance (Additional)

### WCAG 2.1 AA Compliance
- **Keyboard Navigation**: All interactive elements reachable via Tab, logical order
- **Screen Readers**: ARIA labels on all charts, `alt` text on icons, `role="status"` on progress
- **Color Contrast**: Minimum 4.5:1 ratio, ratios shown with patterns (not just color)
- **Focus Management**: Trap focus in modal dialogs, return to trigger on close

### Performance Optimization
- **Code Splitting**: Route-based splitting, vendor chunk separation
- **Lazy Loading**: Load decision charts only when visible (IntersectionObserver)
- **Caching**: React Query with 5m staleTime for decisions, 1m for status
- **Bundle Size**: Keep < 200kb gzipped, tree-shake unused MUI/lodash
- **CDN**: Serve static assets from CDN with SRI hashes

### Responsive Design
- **Breakpoints**: Mobile-first (320px), tablet (768px), desktop (1024px)
- **Touch Targets**: Minimum 44x44px, increased spacing on mobile
- **Collapsible Panels**: Audit trail auto-collapses to accordion on <768px

---

**Note:** This design assumes backend endpoints exist per module specifications. Frontend implementation will use generated API clients from OpenAPI spec. All financial values displayed as `Decimal` using `big.js` library to prevent precision loss.