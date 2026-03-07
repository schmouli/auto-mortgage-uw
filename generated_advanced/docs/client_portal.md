# Client Portal
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# docs/design/client-portal.md

**Module:** `client_portal`  
**Feature slug:** `client-portal`  
**Purpose:** Provide a secure, role‑based web portal for mortgage clients and brokers to manage applications, upload documents, receive notifications, and view underwriting results while adhering to Canadian regulatory requirements (OSFI B‑20, FINTRAC, CMHC, PIPEDA).

---

## 1. Endpoints

| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| **POST** | `/api/v1/auth/login` | Public | `{username: str, password: str}` | `{access_token: str, token_type: "bearer", user: {id: int, role: "client"\|"broker"}}` | `CLIENT_PORTAL_004` (Unauthorized) |
| **GET** | `/api/v1/client-portal/client/dashboard` | Client | – | `{progress: {current_status: str, next_status: str, percent_complete: int}, outstanding_documents: [{document_type: str, required: bool, uploaded: bool}], recent_message: {from: str, message: str, timestamp: datetime}, key_numbers: {requested_mortgage: Decimal, purchase_price: Decimal, status: str}}` | `CLIENT_PORTAL_001` (Not Found), `CLIENT_PORTAL_005` (Forbidden) |
| **GET** | `/api/v1/client-portal/broker/dashboard` | Broker | – | `{pipeline_summary: {draft: int, submitted: int, in_review: int, conditionally_approved: int, approved: int, closed: int}, flagged_files: [{application_id: int, reason: str, days_overdue: int}], recent_activity: [{type: str, description: str, timestamp: datetime}], quick_actions: [{action: str, url: str}]}` | `CLIENT_PORTAL_005` (Forbidden) |
| **GET** | `/api/v1/client-portal/applications` | Client/Broker | Query: `status?: str, page: int (default=1), limit: int (default=20)` | `{total: int, page: int, limit: int, items: [{id: int, status: str, created_at: datetime, updated_at: datetime, requested_mortgage: Decimal, purchase_price: Decimal, property_address: str}]}` | `CLIENT_PORTAL_001` (Not Found), `CLIENT_PORTAL_002` (Invalid query) |
| **GET** | `/api/v1/client-portal/applications/{application_id}` | Client/Broker | – | Full application object (see schema below). | `CLIENT_PORTAL_001`, `CLIENT_PORTAL_005` |
| **POST** | `/api/v1/client-portal/applications/{application_id}/documents` | Client/Broker | multipart/form‑data: `file: UploadFile, document_type: str, description?: str` | `{document_id: int, status: "pending"\|"verified"\|"rejected", uploaded_at: datetime}` | `CLIENT_PORTAL_001`, `CLIENT_PORTAL_002` (invalid file type/size), `CLIENT_PORTAL_006` |
| **GET** | `/api/v1/client-portal/applications/{application_id}/documents` | Client/Broker | – | `[{id: int, type: str, status: str, uploaded_at: datetime, file_url: str (presigned S3 URL)}]` | `CLIENT_PORTAL_001` |
| **GET** | `/api/v1/client-portal/applications/{application_id}/checklist` | Client/Broker | – | `[{document_type: str, required: bool, status: "pending"\|"uploaded"\|"verified"\|"rejected", description: str}]` | `CLIENT_PORTAL_001` |
| **GET** | `/api/v1/client-portal/applications/{application_id}/results` | Broker only | – | `{gds: Decimal, tds: Decimal, qualifying_rate: Decimal, cmhc_required: bool, cmhc_premium: Decimal, decision: "approved"\|"rejected"\|"refer", reason: str}` | `CLIENT_PORTAL_001`, `CLIENT_PORTAL_005` |
| **GET** | `/api/v1/client-portal/applications/{application_id}/fintrac` | Broker only | – | `{verification_status: "pending"\|"verified"\|"flagged", verified_at: datetime, transaction_id: str, flagged: bool}` | `CLIENT_PORTAL_001`, `CLIENT_PORTAL_005` |
| **POST** | `/api/v1/client-portal/applications/{application_id}/fintrac/verify` | Broker only | – | `{status: "verification_triggered"}` | `CLIENT_PORTAL_001`, `CLIENT_PORTAL_005` |
| **GET** | `/api/v1/client-portal/applications/{application_id}/lenders` | Broker only | – | `[{lender_id: int, name: str, rate: Decimal, term: int, payment: Decimal, cmhc_eligible: bool}]` | `CLIENT_PORTAL_001`, `CLIENT_PORTAL_005` |
| **GET** | `/api/v1/client-portal/notifications` | Client/Broker | Query: `unread_only?: bool, page: int, limit: int` | `{total: int, items: [{id: int, type: str, message: str, read: bool, created_at: datetime, application_id: int}]}` | `CLIENT_PORTAL_002` |
| **PUT** | `/api/v1/client-portal/notifications/{notification_id}/read` | Client/Broker | – | `{success: bool}` | `CLIENT_PORTAL_007` |
| **PUT** | `/api/v1/client-portal/notifications/read-all` | Client/Broker | – | `{updated_count: int}` | – |
| **GET** | `/api/v1/client-portal/settings` | Client/Broker | – | `{user: {id: int, email: str, first_name: str, last_name: str, role: str}, preferences: {notifications_email: bool, notifications_sms: bool}}` | `CLIENT_PORTAL_001` |
| **PUT** | `/api/v1/client-portal/settings` | Client/Broker | `{first_name?: str, last_name?: str, preferences?: {notifications_email: bool, notifications_sms: bool}}` | `{success: bool}` | `CLIENT_PORTAL_002` |

**Schema Notes**

- All `Decimal` values are returned as strings to avoid JSON float precision loss.
- `file_url` is a short‑lived presigned URL (e.g., 5 min expiry) to avoid exposing S3 bucket structure.
- The `results` object includes OSFI B‑20 stress‑test rate (`qualifying_rate = max(contract_rate + 2%, 5.25%)`) and CMHC premium tier (80.01‑85 % → 2.80 %, 85.01‑90 % → 3.10 %, 90.01‑95 % → 4.00 %).
- `application_id` is validated as a positive integer; any mismatch returns `CLIENT_PORTAL_001`.

---

## 2. Models & Database

### 2.1 New Tables

#### `applications` (extends existing underwriting application)
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `Integer` | PK | – |
| `user_id` | `Integer` | FK → `users.id` | `idx_applications_user_id` |
| `status` | `Enum` | `draft, submitted, in_review, conditionally_approved, approved, closed` | `idx_applications_status` |
| `requested_mortgage_amount` | `Numeric(12,2)` | Not null | – |
| `purchase_price` | `Numeric(12,2)` | Not null | – |
| `property_address` | `String(255)` | Not null | – |
| `property_value` | `Numeric(12,2)` | Not null | – |
| `loan_amount` | `Numeric(12,2)` | Not null | – |
| `contract_rate` | `Numeric(5,3)` | Not null | – |
| `qualifying_rate` | `Numeric(5,3)` | Computed `max(contract_rate + 2%, 5.25)` | – |
| `gds` | `Numeric(5,2)` | Nullable | – |
| `tds` | `Numeric(5,2)` | Nullable | – |
| `cmhc_required` | `Boolean` | Default `False` | – |
| `cmhc_premium` | `Numeric(12,2)` | Default `0.00` | – |
| `fintrac_verified` | `Boolean` | Default `False` | `idx_applications_fintrac` |
| `fintrac_flagged` | `Boolean` | Default `False` | – |
| `fintrac_transaction_id` | `String(64)` | Nullable | – |
| `created_at` | `DateTime` | Not null, default `now()` | `idx_applications_created_at` |
| `updated_at` | `DateTime` | Not null, default `now()` on update | – |

**Encrypted PII Columns** (PIPEDA compliance)
| Column | Type | Encryption |
|--------|------|------------|
| `borrower_sin_encrypted` | `LargeBinary` | AES‑256 (via `common.security.encrypt_pii`) |
| `borrower_sin_hash` | `String(64)` | SHA‑256 for lookup |
| `borrower_dob_encrypted` | `LargeBinary` | AES‑256 |
| `borrower_address_encrypted` | `LargeBinary` | AES‑256 |

---

#### `documents`
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `Integer` | PK | – |
| `application_id` | `Integer` | FK → `applications.id` | `idx_documents_app_id` |
| `document_type` | `String(50)` | Not null | `idx_documents_type` |
| `file_path` | `String(255)` | Not null (S3 key) | – |
| `status` | `Enum` | `pending, verified, rejected` | `idx_documents_status` |
| `uploaded_at` | `DateTime` | Not null, default `now()` | – |
| `created_at` | `DateTime` | Not null, default `now()` | – |
| `updated_at` | `DateTime` | Not null, default `now()` on update | – |

---

#### `document_checklist_items`
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `Integer` | PK | – |
| `application_id` | `Integer` | FK → `applications.id` | `idx_checklist_app_id` |
| `document_type` | `String(50)` | Not null | `idx_checklist_type` |
| `required` | `Boolean` | Not null, default `True` | – |
| `status` | `Enum` | `pending, uploaded, verified, rejected` | `idx_checklist_status` |
| `description` | `String(255)` | Nullable | – |
| `created_at` | `DateTime` | Not null, default `now()` | – |
| `updated_at` | `DateTime` | Not null, default `now()` on update | – |

**Composite Index**: `(application_id, document_type)` for fast lookup.

---

#### `notifications`
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `Integer` | PK | – |
| `user_id` | `Integer` | FK → `users.id` | `idx_notif_user_id` |
| `application_id` | `Integer` | FK → `applications.id`, nullable | `idx_notif_app_id` |
| `type` | `Enum` | `document_uploaded, document_verified, document_rejected, status_changed, message_received, condition_added` | `idx_notif_type` |
| `message` | `String(500)` | Not null | – |
| `read` | `Boolean` | Default `False` | `idx_notif_unread` |
| `created_at` | `DateTime` | Not null, default `now()` | `idx_notif_created_at` |
| `updated_at` | `DateTime` | Not null, default `now()` on update | – |

---

#### `activity_log` (optional, for broker feed)
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `Integer` | PK | – |
| `application_id` | `Integer` | FK → `applications.id` | `idx_activity_app_id` |
| `event_type` | `String(50)` | Not null | `idx_activity_type` |
| `description` | `String(255)` | Not null | – |
| `created_at` | `DateTime` | Not null, default `now()` | `idx_activity_created_at` |

---

### 2.2 Relationships

- `Application` → `Document` (one‑to‑many)
- `Application` → `DocumentChecklistItem` (one‑to‑many)
- `Application` → `Notification` (one‑to‑many)
- `User` → `Application` (one‑to‑many)
- `User` → `Notification` (one‑to‑many)

---

## 3. Business Logic

### 3.1 Status Progress & State Machine

| Status | Next Allowed | Percent Complete | Trigger Event |
|--------|--------------|------------------|---------------|
| `draft` | `submitted` | 0 % | Client submits application |
| `submitted` | `in_review` | 20 % | Broker marks as “in review” |
| `in_review` | `conditionally_approved` | 40 % | UW engine returns conditional approval |
| `conditionally_approved` | `approved` | 60 % | All conditions cleared |
| `approved` | `closed` | 80 % | Funding completed |
| `closed` | – | 100 % | Final discharge |

**Transition Rules** – Only brokers can move from `submitted` onward; clients can only view. All transitions are logged in `activity_log` for audit.

---

### 3.2 Document Checklist Generation

On application creation, the system generates `document_checklist_items` based on:

- **Loan purpose** (purchase, refinance) → requires purchase agreement or existing mortgage statement.
- **LTV** (>80 % → requires CMHC certificate).
- **Employment type** (salaried → T4; self‑employed → NOA + T1 General).
- **Property type** (condo → status certificate).

Each item starts `status = "pending"`. When a document of matching `document_type` is uploaded, the status becomes `"uploaded"`. Broker review later sets `"verified"` or `"rejected"`.

---

### 3.3 Notification Generation (Async)

| Event | Notification `type` | Recipients | Message Template |
|-------|---------------------|------------|------------------|
| Document uploaded | `document_uploaded` | Broker | “Client uploaded {document_type} for app #{id}” |
| Document verified | `document_verified` | Client | “{document_type} has been verified” |
| Document rejected | `document_rejected` | Client | “{document_type} was rejected: {reason}” |
| Status changed | `status_changed` | Client + Broker | “Application moved to {new_status}” |
| New message | `message_received` | Receiver | “You have a new message from {sender}” |
| Condition added | `condition_added` | Client | “New condition: {description}” |

**Implementation:** FastAPI background task or external Celery worker creates `Notification` rows. Broker‑only notifications are filtered by role.

---

### 3.4 FINTRAC Identity Verification

- **Trigger:** Loan amount ≥ $10,000 (practically all mortgages). On application submission, set `fintrac_flagged = True`.
- **Process:** Broker clicks “Verify” → system calls external FINTRAC API (or manual review) and stores result immutably.
- **Audit:** `fintrac_transaction_id` (external reference) and `fintrac_verified` timestamp are never updated after creation (5‑year retention).

---

### 3.5 Lender Comparison Engine

- **Input:** `loan_amount`, `property_value`, `credit_score`, `amortization`, `insurance_required`.
- **Logic:** Query lender rate sheets (cached daily). Filter by `cmhc_eligible` if insurance required. Compute monthly payment using `Decimal` precise formula:  
  `payment = (rate/12) * loan_amount / (1 - (1 + rate/12)^(-term*12))`.
- **Output:** Sorted list by rate, then payment.

---

### 3.6 Pipeline Summary & Flagged Files

- **Pipeline:** `SELECT status, COUNT(*) FROM applications GROUP BY status`.
- **Flagged:** Applications where:
  - Any `document_checklist_items` with `status = "pending"` and `created_at < NOW() - INTERVAL '7 days'`.
  - `fintrac_verified = False` and `created_at < NOW() - INTERVAL '3 days'`.

---

## 4. Migrations

### 4.1 New Tables

```sql
-- Table: applications (extends existing)
ALTER TABLE applications
  ADD COLUMN IF NOT EXISTS qualifying_rate        NUMERIC(5,3) GENERATED ALWAYS AS (MAX(contract_rate + 2, 5.25)) STORED,
  ADD COLUMN IF NOT EXISTS gds                   NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS tds                   NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS cmhc_required         BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS cmhc_premium          NUMERIC(12,2) DEFAULT 0.00,
  ADD COLUMN IF NOT EXISTS fintrac_verified      BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS fintrac_flagged       BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS fintrac_transaction_id VARCHAR(64),
  ADD COLUMN IF NOT EXISTS borrower_sin_encrypted BYTEA,
  ADD COLUMN IF NOT EXISTS borrower_sin_hash     VARCHAR(64),
  ADD COLUMN IF NOT EXISTS borrower_dob_encrypted BYTEA,
  ADD COLUMN IF NOT EXISTS borrower_address_encrypted BYTEA;

CREATE INDEX idx_applications_user_id ON applications(user_id);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_fintrac ON applications(fintrac_verified, fintrac_flagged);
CREATE INDEX idx_applications_created_at ON applications(created_at);

-- Table: documents
CREATE TABLE documents (
    id               SERIAL PRIMARY KEY,
    application_id   INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type    VARCHAR(50) NOT NULL,
    file_path        VARCHAR(255) NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',
    uploaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_documents_app_id ON documents(application_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_status ON documents(status);

-- Table: document_checklist_items
CREATE TABLE document_checklist_items (
    id               SERIAL PRIMARY KEY,
    application_id   INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type    VARCHAR(50) NOT NULL,
    required         BOOLEAN NOT NULL DEFAULT TRUE,
    status           VARCHAR(20) NOT NULL DEFAULT 'pending',
    description      VARCHAR(255),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_checklist_app_id ON document_checklist_items(application_id);
CREATE INDEX idx_checklist_type ON document_checklist_items(document_type);
CREATE INDEX idx_checklist_status ON document_checklist_items(status);
CREATE UNIQUE INDEX uq_checklist_app_type ON document_checklist_items(application_id, document_type);

-- Table: notifications
CREATE TABLE notifications (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    application_id   INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    type             VARCHAR(50) NOT NULL,
    message          VARCHAR(500) NOT NULL,
    read             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_notif_user_id ON notifications(user_id);
CREATE INDEX idx_notif_app_id ON notifications(application_id);
CREATE INDEX idx_notif_type ON notifications(type);
CREATE INDEX idx_notif_unread ON notifications(read) WHERE read = FALSE;
CREATE INDEX idx_notif_created_at ON notifications(created_at DESC);

-- Table: activity_log (optional)
CREATE TABLE activity_log (
    id               SERIAL PRIMARY KEY,
    application_id   INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    event_type       VARCHAR(50) NOT NULL,
    description      VARCHAR(255) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_activity_app_id ON activity_log(application_id);
CREATE INDEX idx_activity_type ON activity_log(event_type);
CREATE INDEX idx_activity_created_at ON activity_log(created_at DESC);
```

### 4.2 Data Migration

- **Seed checklist templates** (one‑time script): Insert default `document_checklist_items` for each existing application based on LTV, purpose, etc.
- **Back‑populate `fintrac_flagged`**: Set `fintrac_flagged = TRUE` where `loan_amount >= 10000`.

---

## 5. Security & Compliance

| Requirement | Implementation |
|-------------|----------------|
| **OSFI B‑20** | The `/results` endpoint calculates `qualifying_rate = max(contract_rate + 2%, 5.25%)`. GDS/TDS ratios are computed with `Decimal` precision and logged (without PII) for audit. Hard limits (GDS ≤ 39 %, TDS ≤ 44 %) are enforced in the underwriting engine; the portal only displays the results. |
| **FINTRAC** | `fintrac_verified` and `fintrac_transaction_id` are immutable after creation. All verification events are written to `activity_log`. Records are retained for 5 years (PostgreSQL `VACUUM` policy + backup). Transactions ≥ $10,000 are automatically flagged (`fintrac_flagged = TRUE`). |
| **CMHC** | `cmhc_required` and `cmhc_premium` are set during underwriting based on LTV tiers (80.01‑85 % → 2.80 %, 85.01‑90 % → 3.10 %, 90.01‑95 % → 4.00 %). The `/results` endpoint returns these values. |
| **PIPEDA** | SIN and DOB are encrypted at rest (`borrower_sin_encrypted`, `borrower_dob_encrypted`) using AES‑256 via `common.security.encrypt_pii`. Only the SHA‑256 hash (`borrower_sin_hash`) is used for lookups. These fields never appear in logs or API responses. Data minimization: the portal only exposes fields necessary for status tracking and document upload. |
| **Authentication** | JWT (OAuth 2.0) required for all endpoints except login. Role‑based access: `broker` role required for `/results`, `/fintrac`, `/lenders`. |
| **Authorization** | Clients can only access their own applications (`application.user_id == current_user.id`). Brokers can access all. Enforced in service layer. |
| **Input Validation** | All IDs are positive integers; file uploads limited to 10 MB; allowed MIME types: `pdf`, `jpg`, `png`. Validation errors return `CLIENT_PORTAL_002`. |
| **Audit Logging** | Every status change, document upload, and FINTRAC verification is logged to `activity_log` with `correlation_id` (via structlog) for traceability. |

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | When Raised |
|-----------------|-------------|------------|-----------------|-------------|
| `ClientPortalNotFoundError` | 404 | `CLIENT_PORTAL_001` | "{resource} not found" | Application, document, or notification ID does not exist. |
| `ClientPortalValidationError` | 422 | `CLIENT_PORTAL_002` | "{field}: {reason}" | Invalid query parameter, missing required field, or file type/size violation. |
| `ClientPortalBusinessRuleError` | 409 | `CLIENT_PORTAL_003` | "Business rule violated: {detail}" | Status transition not allowed, duplicate document type, etc. |
| `ClientPortalUnauthorizedError` | 401 | `CLIENT_PORTAL_004` | "Unauthorized" | Missing or invalid JWT. |
| `ClientPortalForbiddenError` | 403 | `CLIENT_PORTAL_005` | "Forbidden" | Client attempts to access broker‑only endpoint. |
| `ClientPortalDocumentNotFoundError` | 404 | `CLIENT_PORTAL_006` | "Document not found" | Document ID not found for the given application. |
| `ClientPortalNotificationNotFoundError` | 404 | `CLIENT_PORTAL_007` | "Notification not found" | Notification ID not found for the user. |

**Error Response Format**
```json
{
  "detail": "Application not found",
  "error_code": "CLIENT_PORTAL_001"
}
```

---

## 7. Integration Points

- **Underwriting Engine** – Called internally to compute GDS/TDS, CMHC premium, and decision. Results cached in `applications` table.
- **Document Storage** – S3 (or compatible) for file blobs; `file_path` stores the object key.
- **Notification Delivery** – Background worker creates `Notification` rows; WebSocket or polling via a separate `realtime` module can push updates.
- **FINTRAC API** – External verification service; responses stored immutably.
- **Lender Rate Sheet API** – Cached daily; used by `/lenders` endpoint.

---

## 8. Future Considerations

- **Real‑time notifications** – WebSocket vs. polling decision to be made in a separate `realtime` module.
- **Mobile camera capture** – Frontend feature; backend already supports multipart upload.
- **Drag‑and‑drop UI** – Frontend component; backend file size/type limits already defined.
- **Progress indicator UX** – Frontend maps status to percent; backend provides `status` only.

---