# Client Portal
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Client Portal Module

**File:** `docs/design/client-portal.md`  
**Module:** `modules/client_portal/`  
**Feature Slug:** `client-portal`  
**Last Updated:** 2024

---

## 1. Endpoints

### Authentication & Session Management

#### `POST /api/v1/auth/login`
Public endpoint for client and broker authentication.

**Request Schema (`LoginRequest`)**
```python
{
    "email": EmailStr,          # Required
    "password": SecretStr,      # Required, min 12 chars
    "user_type": Literal["client", "broker"],  # Required
    "device_fingerprint": str   # Optional, for fraud detection
}
```

**Response Schema (`LoginResponse`)**
```python
{
    "access_token": str,        # JWT, expires in 15min
    "refresh_token": str,       # JWT, expires in 7 days
    "token_type": "Bearer",
    "user": {
        "user_id": UUID,
        "role": Literal["client", "broker"],
        "full_name": str,       # First + Last, PIPEDA-compliant
        "email": EmailStr,
        "requires_password_reset": bool
    }
}
```

**Error Responses**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | PORTAL_001 | "Invalid credentials" |
| 401 | PORTAL_002 | "Account locked: {attempts} failed attempts" |
| 403 | PORTAL_003 | "User type mismatch" |
| 422 | PORTAL_004 | "Email format invalid" |

---

### Dashboard Aggregation

#### `GET /api/v1/dashboard`
Returns role-specific dashboard data. Requires authentication.

**Query Parameters**
```python
{
    "include_activity_limit": int = 50,  # Max recent items
    "pipeline_summary_days": int = 30    # Date range for broker pipeline
}
```

**Response Schema (`DashboardResponse`)**
```python
{
    "user_role": Literal["client", "broker"],
    "generated_at": datetime,
    "client_view": {           # Populated if role == client
        "active_application": {
            "application_id": UUID,
            "status": ApplicationStatusEnum,
            "status_progress_pct": Decimal,  # 0-100
            "requested_mortgage_amount": Decimal,
            "property_purchase_price": Decimal,
            "outstanding_documents": int,
            "next_action_required": str,     # Human-readable
            "recent_broker_message": {
                "message_id": UUID,
                "sent_at": datetime,
                "preview": str,              # Truncated to 140 chars
                "is_unread": bool
            }
        }
    },
    "broker_view": {           # Populated if role == broker
        "pipeline_summary": {
            "draft": int,
            "submitted": int,
            "in_review": int,
            "conditionally_approved": int,
            "approved": int,
            "closed": int,
            "total_value": Decimal          # Sum of mortgage amounts
        },
        "flagged_files": [
            {
                "application_id": UUID,
                "flag_reason": Literal["missing_documents", "past_due"],
                "flagged_at": datetime,
                "days_overdue": int
            }
        ],
        "recent_activity": [
            {
                "activity_id": UUID,
                "activity_type": Literal["document_upload", "status_change", "message"],
                "application_id": UUID,
                "description": str,
                "occurred_at": datetime,
                "actor": str                    # "Client" or "Broker Name"
            }
        ],
        "quick_actions": {
            "can_start_application": bool,
            "pending_document_requests": int
        }
    }
}
```

**Error Responses**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | AUTH_001   | "Missing or invalid token" |
| 403 | PORTAL_005 | "Dashboard access denied" |

---

### Application Management

#### `GET /api/v1/applications`
List applications with pagination and filtering.

**Query Parameters**
```python
{
    "page": int = 1,
    "limit": int = 20,         # Max 100
    "status": List[ApplicationStatusEnum] = None,
    "search": str = None       # Search by ID or client name (broker only)
}
```

**Response Schema (`ApplicationListResponse`)**
```python
{
    "total_count": int,
    "page": int,
    "limit": int,
    "applications": [
        {
            "application_id": UUID,
            "status": ApplicationStatusEnum,
            "created_at": datetime,
            "updated_at": datetime,
            "property_address": str,       # Redacted for client (street name only)
            "purchase_price": Decimal,
            "mortgage_amount": Decimal,
            "ltv_ratio": Decimal,          # Calculated, 2 decimal places
            "client_name": str             # Broker only; client sees "My Application"
        }
    ]
}
```

**Error Responses**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | AUTH_001   | "Authentication required" |
| 403 | PORTAL_006 | "Insufficient permissions for search" |
| 422 | PORTAL_007 | "Invalid pagination parameters" |

---

#### `GET /api/v1/applications/{application_id}`
Fetch single application detail. Field visibility role-based.

**Response Schema (`ApplicationDetailResponse`)**
```python
{
    "application_id": UUID,
    "status": ApplicationStatusEnum,
    "status_history": [
        {
            "status": ApplicationStatusEnum,
            "changed_at": datetime,
            "changed_by": str,
            "reason": str
        }
    ],
    "property_details": {
        "address": str,
        "purchase_price": Decimal,
        "property_type": str,
        "closing_date": date
    },
    "mortgage_details": {
        "requested_amount": Decimal,
        "down_payment": Decimal,
        "amortization_years": int,
        "interest_rate": Decimal,        # OSFI stress test rate displayed
        "ltv_ratio": Decimal,
        "insurance_required": bool,
        "insurance_premium": Decimal | None
    },
    "applicants": [                    # Broker sees full; client sees only self
        {
            "applicant_id": UUID,
            "full_name": str,
            "is_primary": bool,
            # SIN/DOB omitted entirely for client; broker sees masked
        }
    ],
    "gds_tds_ratios": {                # OSFI B-20 compliance block
        "gds_ratio": Decimal,          # ≤ 39%
        "tds_ratio": Decimal,          # ≤ 44%
        "qualifying_rate": Decimal,    # max(contract_rate + 2%, 5.25%)
        "is_gds_compliant": bool,
        "is_tds_compliant": bool,
        "calculation_breakdown": {     # For audit trail
            "pith_amount": Decimal,
            "gross_monthly_income": Decimal,
            "other_debt_payments": Decimal
        }
    },
    "audit_trail": [                   # Broker only
        {
            "event": str,
            "actor": str,
            "timestamp": datetime,
            "ip_address": IPv4Address | IPv6Address
        }
    ]
}
```

**Error Responses**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | AUTH_001   | "Authentication required" |
| 403 | PORTAL_008 | "Access denied to application" |
| 404 | PORTAL_009 | "Application not found" |

---

### Document Management

#### `GET /api/v1/applications/{application_id}/documents`
List uploaded documents for an application.

**Response Schema (`DocumentListResponse`)**
```python
{
    "application_id": UUID,
    "documents": [
        {
            "document_id": UUID,
            "document_type": DocumentTypeEnum,  # pay_stub, t4, id_verify, etc.
            "file_name": str,
            "file_size_bytes": int,
            "uploaded_at": datetime,
            "uploaded_by": str,                 # "Client" or "Broker Name"
            "verification_status": Literal["pending", "verified", "rejected"],
            "verified_at": datetime | None,
            "rejection_reason": str | None
        }
    ]
}
```

---

#### `POST /api/v1/applications/{application_id}/documents`
Upload a new document. Supports multipart/form-data and camera capture.

**Request Schema (`DocumentUploadRequest`)**
```python
{
    "document_type": DocumentTypeEnum,      # Required
    "file": UploadFile,                     # Max 10MB, PDF/JPG/PNG
    "captured_via_camera": bool = False,    # Metadata for audit
    "checksum": str                         # SHA256 for integrity verification
}
```

**Response Schema (`DocumentUploadResponse`)**
```python
{
    "document_id": UUID,
    "status": "uploaded",
    "verification_queue_position": int,
    "estimated_processing_hours": int
}
```

**Error Responses**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 | PORTAL_010 | "File type not allowed" |
| 400 | PORTAL_011 | "File size exceeds 10MB limit" |
| 409 | PORTAL_012 | "Document type already uploaded and verified" |
| 422 | PORTAL_013 | "Invalid checksum format" |

---

### Document Checklist

#### `GET /api/v1/applications/{application_id}/checklist`
Returns required document checklist based on application context.

**Response Schema (`DocumentChecklistResponse`)**
```python
{
    "application_id": UUID,
    "checklist_items": [
        {
            "document_type": DocumentTypeEnum,
            "display_name": str,
            "is_required": bool,
            "is_conditional": bool,
            "condition": str | None,            # e.g., "LTV > 80%"
            "is_uploaded": bool,
            "uploaded_document_id": UUID | None,
            "verification_status": str | None,
            "is_overdue": bool,
            "due_date": date | None
        }
    ],
    "overall_completion_pct": Decimal,      # 0-100
    "blocking_items_count": int             # Items preventing status advance
}
```

---

### Broker-Only Underwriting Views

#### `GET /api/v1/applications/{application_id}/results`
Underwriting decision details. Broker role only.

**Response Schema (`UnderwritingResultsResponse`)**
```python
{
    "application_id": UUID,
    "decision": Literal["approved", "conditionally_approved", "rejected", "pending"],
    "decision_date": datetime | None,
    "decisioned_by": str | None,
    "gds_tds_summary": {
        "gds_ratio": Decimal,
        "tds_ratio": Decimal,
        "is_osfi_compliant": bool,
        "qualifying_rate_used": Decimal
    },
    "risk_flags": [str],                    # e.g., ["high_ltv", "self_employed"]
    "conditions": [
        {
            "condition_id": UUID,
            "description": str,
            "is_satisfied": bool,
            "satisfied_at": datetime | None
        }
    ],
    "recommended_lenders": [                # From lenders module
        {
            "lender_id": UUID,
            "lender_name": str,
            "product_name": str,
            "interest_rate": Decimal,
            "probability_of_funding": Decimal
        }
    ]
}
```

**Error Responses**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 403 | PORTAL_014 | "Broker access only" |

---

#### `GET /api/v1/applications/{application_id}/fintrac`
FINTRAC verification status and audit trail. Broker only.

**Response Schema (`FintracVerificationResponse`)**
```python
{
    "application_id": UUID,
    "verification_status": Literal["not_started", "in_progress", "verified", "flagged"],
    "identity_verification": {
        "method": Literal["document", "electronic", "in_person"],
        "verified_at": datetime,
        "verified_by": str,
        "documents": [UUID]                 # Document IDs used
    },
    "transaction_flags": [
        {
            "flag_id": UUID,
            "flag_type": Literal["large_cash", "suspicious_activity"],
            "transaction_amount": Decimal,   # > $10,000 CAD
            "flagged_at": datetime,
            "report_submitted": bool
        }
    ],
    "audit_trail": [                        # 5-year retention
        {
            "action": str,
            "actor": str,
            "timestamp": datetime,
            "ip_address": str
        }
    ]
}
```

---

### Notification System

#### `GET /api/v1/notifications`
Fetch paginated notifications for authenticated user.

**Query Parameters**
```python
{
    "page": int = 1,
    "limit": int = 20,         # Max 50
    "unread_only": bool = False,
    "event_type": List[NotificationEventEnum] = None
}
```

**Response Schema (`NotificationListResponse`)**
```python
{
    "total_unread": int,
    "notifications": [
        {
            "notification_id": UUID,
            "event_type": NotificationEventEnum,
            "title": str,
            "message": str,                # PII-free message
            "is_read": bool,
            "created_at": datetime,
            "metadata": {                  # Structured data for UI routing
                "application_id": UUID | None,
                "document_id": UUID | None
            }
        }
    ]
}
```

---

#### `PUT /api/v1/notifications/{notification_id}/read`
Mark single notification as read.

**Response Schema**
```python
{
    "notification_id": UUID,
    "is_read": True,
    "read_at": datetime
}
```

---

#### `PUT /api/v1/notifications/read-all`
Mark all unread notifications as read.

**Response Schema**
```python
{
    "marked_as_read": int,     # Count of notifications updated
    "read_at": datetime
}
```

---

### User Settings

#### `GET /api/v1/settings`
Fetch user profile and notification preferences.

**Response Schema (`UserSettingsResponse`)**
```python
{
    "profile": {
        "user_id": UUID,
        "full_name": str,
        "email": EmailStr,
        "phone": PhoneNumber | None,       # E.164 format, encrypted at rest
        "notification_preferences": {
            "email_enabled": bool,
            "push_enabled": bool,
            "sms_enabled": bool,           # PIPEDA consent required
            "subscribed_events": List[NotificationEventEnum]
        }
    }
}
```

---

#### `PUT /api/v1/settings`
Update settings. PII fields encrypted.

**Request Schema (`UpdateSettingsRequest`)**
```python
{
    "phone": PhoneNumber | None,
    "notification_preferences": {
        "email_enabled": bool,
        "push_enabled": bool,
        "sms_enabled": bool,
        "subscribed_events": List[NotificationEventEnum]
    }
}
```

---

## 2. Models & Database

### `portal_notifications` Table
Stores all notification events for 5-year FINTRAC retention.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PK, default gen_random_uuid() | |
| `user_id` | UUID | FK → users.id, NOT NULL | IX |
| `event_type` | VARCHAR(32) | NOT NULL, check in list | IX |
| `title` | VARCHAR(255) | NOT NULL | |
| `message` | TEXT | NOT NULL, PII-free | |
| `metadata` | JSONB | Default '{}' | GIN |
| `is_read` | BOOLEAN | Default false, NOT NULL | IX |
| `read_at` | TIMESTAMPTZ | Nullable | |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() | IX |
| `created_by` | UUID | FK → users.id, NOT NULL | IX |
| `ip_address` | INET | Nullable, for audit | |

**Indexes:**
- `IX_portal_notifications_user_created`: `(user_id, created_at DESC)`
- `IX_portal_notifications_unread`: `(user_id, is_read, created_at DESC)`
- `GIN_idx_metadata`: GIN index on `metadata` for JSON queries

**Relationships:**
- Many-to-one with `users` (recipient)
- Many-to-one with `users` (actor who triggered)

---

### `portal_user_preferences` Table
Stores per-user portal configuration.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `user_id` | UUID | FK → users.id, UNIQUE, NOT NULL | IX |
| `phone_encrypted` | BYTEA | Nullable, AES-256-GCM encrypted | |
| `phone_iv` | BYTEA | Nullable, IV for decryption | |
| `notification_email` | BOOLEAN | Default true, NOT NULL | |
| `notification_push` | BOOLEAN | Default true, NOT NULL | |
| `notification_sms` | BOOLEAN | Default false, NOT NULL | |
| `subscribed_events` | JSONB | Default '[]', array of event types | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, auto-update | IX |

**Indexes:**
- `IX_portal_prefs_user`: `(user_id)`

---

### `portal_sessions` Table (Optional, for enhanced security)
If using server-side session revocation capability.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PK | |
| `user_id` | UUID | FK → users.id, NOT NULL | IX |
| `session_token_hash` | VARCHAR(64) | UNIQUE, NOT NULL | IX |
| `device_fingerprint` | VARCHAR(128) | Nullable | IX |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() | IX |
| `expires_at` | TIMESTAMPTZ | NOT NULL | IX |
| `revoked_at` | TIMESTAMPTZ | Nullable | |

**Indexes:**
- `IX_portal_sessions_user`: `(user_id, created_at DESC)`
- `IX_portal_sessions_active`: `(user_id, expires_at) WHERE revoked_at IS NULL`

---

## 3. Business Logic

### Application Status State Machine
```python
class ApplicationStatus(Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    CONDITIONALLY_APPROVED = "conditionally_approved"
    APPROVED = "approved"
    CLOSED = "closed"

# Valid transitions
TRANSITIONS = {
    DRAFT: [SUBMITTED],
    SUBMITTED: [IN_REVIEW],
    IN_REVIEW: [CONDITIONALLY_APPROVED, APPROVED, CLOSED],
    CONDITIONALLY_APPROVED: [APPROVED, CLOSED],
    APPROVED: [CLOSED],
    CLOSED: []  # Terminal state
}
```

**Transition Rules:**
- `DRAFT → SUBMITTED`: Requires `checklist_completion_pct == 100` and all required documents uploaded
- `SUBMITTED → IN_REVIEW`: Auto-transition when broker begins underwriting
- `IN_REVIEW → CONDITIONALLY_APPROVED`: GDS/TDS compliant but conditions exist
- `IN_REVIEW → APPROVED`: GDS/TDS compliant, no conditions, OSFI B-20 validated
- `IN_REVIEW → CLOSED`: Rejected or withdrawn
- `CONDITIONALLY_APPROVED → APPROVED`: All conditions satisfied
- `APPROVED → CLOSED`: Funding completed or expired (90 days)

**Audit Logging:** Every transition creates immutable `portal_notifications` record with `event_type = status_changed`.

---

### Document Checklist Engine
Dynamic checklist generation based on:

```python
def generate_checklist(application: Application) -> List[ChecklistItem]:
    required = []
    
    # Always required
    required.append(DocumentType.ID_VERIFICATION)
    required.append(DocumentType.PROOF_OF_INCOME)
    required.append(DocumentType.PROPERTY_PURCHASE_AGREEMENT)
    
    # Conditional logic
    if application.ltv_ratio > Decimal('0.80'):
        required.append(DocumentType.MORTGAGE_INSurance_APPLICATION)
    
    if application.self_employed:
        required.append(DocumentType.NOTICE_OF_ASSESSMENT)
        required.append(DocumentType.BUSINESS_FINANCIAL_STATEMENTS)
    
    if application.down_payment_source == "gift":
        required.append(DocumentType.GIFT_LETTER)
    
    if application.property_type in ["condo", "condo_townhouse"]:
        required.append(DocumentType.CONDO_STATUS_CERTIFICATE)
    
    # FINTRAC large transaction flag
    if application.mortgage_amount > Decimal('10000'):
        required.append(DocumentType.SOURCE_OF_FUNDS_DECLARATION)
    
    return required
```

**Due Date Calculation:** `due_date = application.created_at + timedelta(days=7)` for initial submission; `application.status_changed_at + timedelta(days=3)` for conditional approvals.

---

### Notification Generation Service
Triggered by events across modules via async message queue (Redis Streams).

```python
class NotificationService:
    async def create_notification(
        self,
        user_id: UUID,
        event_type: NotificationEventEnum,
        application_id: UUID | None,
        metadata: dict
    ) -> Notification:
        # PIPEDA: Never include PII in message field
        templates = {
            NotificationEventEnum.DOCUMENT_UPLOADED: {
                "title": "Document Received",
                "message": "A new document has been uploaded for application {app_id}",
                "metadata": {"application_id": application_id}
            },
            NotificationEventEnum.STATUS_CHANGED: {
                "title": "Application Status Update",
                "message": "Your application status changed to {new_status}",
                "metadata": {
                    "application_id": application_id,
                    "old_status": metadata["old_status"],
                    "new_status": metadata["new_status"]
                }
            }
        }
        
        # FINTRAC: Log to immutable audit storage
        await self.audit_logger.info(
            "notification_created",
            user_id=user_id,
            event_type=event_type,
            application_id=application_id,
            ip_address=metadata.get("ip_address")
        )
        
        return await self.repository.save(notification)
```

**Real-Time Delivery:** WebSocket with fallback to polling. WebSocket endpoint: `wss://api/v1/notifications/stream` with JWT sub-protocol.

---

### Dashboard Aggregation Algorithm
```python
class DashboardService:
    async def get_client_dashboard(self, user_id: UUID) -> ClientDashboard:
        # Fetch most recent active application
        app = await self.app_repo.get_latest_by_user(user_id)
        
        # Count outstanding documents
        outstanding = await self.doc_repo.count_by_status(
            app.id, 
            verification_status="pending"
        )
        
        # Get latest unread broker message
        message = await self.message_repo.get_latest_broker_message(
            app.id, 
            unread_only=True
        )
        
        # Calculate progress percentage based on status
        progress_map = {
            ApplicationStatus.DRAFT: Decimal("20"),
            ApplicationStatus.SUBMITTED: Decimal("40"),
            ApplicationStatus.IN_REVIEW: Decimal("60"),
            ApplicationStatus.CONDITIONALLY_APPROVED: Decimal("80"),
            ApplicationStatus.APPROVED: Decimal("100"),
            ApplicationStatus.CLOSED: Decimal("100")
        }
        
        return ClientDashboard(
            application_id=app.id,
            status=app.status,
            status_progress_pct=progress_map[app.status],
            requested_mortgage_amount=app.mortgage_amount,
            property_purchase_price=app.property_value,
            outstanding_documents=outstanding,
            recent_broker_message=message
        )
```

---

## 4. Migrations

### Alembic Revision: `create_portal_tables`

```python
def upgrade():
    # portal_notifications table
    op.create_table(
        'portal_notifications',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.VARCHAR(length=32), nullable=False),
        sa.Column('title', sa.VARCHAR(length=255), nullable=False),
        sa.Column('message', sa.TEXT(), nullable=False),
        sa.Column('metadata', sa.JSONB(), server_default='{}', nullable=False),
        sa.Column('is_read', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('read_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('ip_address', sa.INET(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_portal_notifications_user_created', 'portal_notifications', ['user_id', sa.text('created_at DESC')])
    op.create_index('ix_portal_notifications_unread', 'portal_notifications', ['user_id', 'is_read', 'created_at DESC'])
    op.create_index('ix_portal_notifications_event_type', 'portal_notifications', ['event_type'])
    op.create_index('ix_portal_notifications_created_by', 'portal_notifications', ['created_by'])
    op.create_index('gin_idx_metadata', 'portal_notifications', ['metadata'], postgresql_using='gin')
    
    # portal_user_preferences table
    op.create_table(
        'portal_user_preferences',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('phone_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('phone_iv', sa.LargeBinary(), nullable=True),
        sa.Column('notification_email', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notification_push', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notification_sms', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('subscribed_events', sa.JSONB(), server_default='[]', nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    op.create_index('ix_portal_prefs_user', 'portal_user_preferences', ['user_id'])
    
    # portal_sessions table (optional)
    op.create_table(
        'portal_sessions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('session_token_hash', sa.VARCHAR(length=64), nullable=False),
        sa.Column('device_fingerprint', sa.VARCHAR(length=128), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token_hash')
    )
    
    op.create_index('ix_portal_sessions_user', 'portal_sessions', ['user_id', sa.text('created_at DESC')])
    op.create_index('ix_portal_sessions_active', 'portal_sessions', ['user_id', 'expires_at'], postgresql_where=sa.text('revoked_at IS NULL'))
```

---

### Data Migration Requirements
**None** for initial portal setup. If migrating from legacy system:
- Import existing user preferences into `portal_user_preferences`
- Map legacy notification logs to `portal_notifications` with `created_at` preserved
- Generate `portal_sessions` from active JWTs if using server-side revocation

---

## 5. Security & Compliance

### OSFI B-20 Compliance (Guideline B-20)
- **Stress Test Display**: All GDS/TDS ratios must display `qualifying_rate = max(contract_rate + 2%, 5.25%)` in results view
- **Ratio Enforcement**: Portal must reject broker attempts to override GDS > 39% or TDS > 44% (enforced in underwriting module, displayed here)
- **Audit Trail**: Every ratio calculation displayed must be logged to `portal_notifications` with full breakdown for OSFI examination
- **Immutable Records**: Approved application ratios cannot be modified; any recalculation creates new audit entry

### FINTRAC Compliance (PCMLTFA)
- **Identity Verification Logging**: `fintrac` endpoint must log `identity_verification.method`, `verified_at`, `document_ids` to immutable store
- **Large Transaction Flagging**: Document checklist engine automatically adds `SOURCE_OF_FUNDS_DECLARATION` when `mortgage_amount > CAD 10,000`
- **5-Year Retention**: All `portal_notifications` and `portal_sessions` rows must be retained for 5 years post-application closure. Implement soft-delete only (`revoked_at` for sessions, never hard delete)
- **Reportable Transaction API**: Portal must expose `GET /api/v1/applications/{id}/fintrac/report` for generating FINTRAC STR submissions (admin only)

### CMHC Insurance Requirement
- **LTV Calculation**: `ltv_ratio = loan_amount / property_value` using Decimal with 5+ precision
- **Premium Tier Display**: In application detail view, show insurance premium tier:
  - 80.01-85%: 2.80%
  - 85.01-90%: 3.10%
  - 90.01-95%: 4.00%
- **Insurance Flag**: `insurance_required = True` when LTV > 80%, displayed to both client and broker

### PIPEDA Compliance
- **Encryption at Rest**: 
  - `portal_user_preferences.phone_encrypted` uses AES-256-GCM with key from `common/security.py`
  - IV stored separately; key rotated every 90 days
- **Data Minimization**: Profile settings only collect `phone` (optional); SIN/DOB never exposed to portal APIs
- **No PII in Logs**: `structlog` configuration must mask `phone`, `email`, `address` in all portal logs
- **Lookup Hashes**: SIN used only as SHA256 hash for application linking; never returned in API responses
- **Consent Management**: `notification_sms` enabled only if explicit consent recorded in `users` table

### Authentication & Authorization
- **JWT Strategy**: Access token (15min) + Refresh token (7 days) with rotation
- **Role-Based Access Control (RBAC)**:
  - `client`: Can view own applications, upload documents, view own results
  - `broker`: Can view all assigned applications, access underwriting results, FINTRAC data
  - `admin`: Can access all endpoints, generate FINTRAC reports
- **mTLS**: Broker API access requires mutual TLS authentication; client access uses standard TLS
- **Rate Limiting**: Login endpoint: 5 attempts per 15min per IP; document upload: 10 per minute per user

---

## 6. Error Codes & HTTP Responses

### Portal-Specific Exceptions

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `PortalAuthError` | 401 | PORTAL_001 | "Invalid credentials" | Wrong password on login |
| `PortalAccountLockedError` | 401 | PORTAL_002 | "Account locked: {attempts} failed attempts" | 5+ failed logins |
| `PortalUserTypeMismatchError` | 403 | PORTAL_003 | "User type mismatch" | Client tries broker endpoint |
| `PortalAccessDeniedError` | 403 | PORTAL_005 | "Dashboard access denied" | Inactive user session |
| `PortalResourceNotFoundError` | 404 | PORTAL_009 | "Application {id} not found" | Invalid application_id |
| `PortalValidationError` | 422 | PORTAL_004 | "Email format invalid" | Malformed email in login |
| `PortalFileTypeError` | 400 | PORTAL_010 | "File type not allowed: {mime}" | Upload .exe file |
| `PortalFileSizeError` | 400 | PORTAL_011 | "File size exceeds {limit}MB" | 15MB PDF upload |
| `PortalDuplicateDocumentError` | 409 | PORTAL_012 | "Document {type} already verified" | Re-upload verified doc |
| `PortalChecksumError` | 422 | PORTAL_013 | "Invalid checksum format" | Non-hex checksum provided |
| `PortalBrokerOnlyError` | 403 | PORTAL_014 | "Broker access only" | Client accesses /results |

### Global Exception Mapping
```python
# In modules/client_portal/exceptions.py
class PortalException(AppException):
    """Base for all portal module exceptions."""
    module_code = "PORTAL"

class PortalAuthError(PortalException):
    http_status = 401
    error_code = "PORTAL_001"

class PortalAccountLockedError(PortalException):
    http_status = 401
    error_code = "PORTAL_002"

# ... etc
```

### Structured Error Response Format
```json
{
  "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "PORTAL_009",
  "module": "client_portal",
  "timestamp": "2024-01-15T14:30:00Z",
  "request_id": "req_abc123",
  "support_url": "https://support.mortgage.ca/errors/PORTAL_009"
}
```

---

## Technical Considerations (Non-Functional Requirements)

### Real-Time Notifications
- **Primary**: WebSocket endpoint `wss://api/v1/notifications/stream` with JWT authentication via `sec-websocket-protocol`
- **Fallback**: HTTP polling with `ETag`/`Last-Modified` caching headers; max interval 30 seconds
- **Scalability**: Use Redis Pub/Sub to broadcast events across FastAPI worker processes

### Document Upload Security
- **Virus Scanning**: All uploads streamed to ClamAV via `common/security.py:scan_file()`
- **Checksum Validation**: SHA256 provided by client verified against calculated hash
- **Storage**: Encrypted at rest in S3-compatible storage; keys managed by Vault
- **Mobile Camera**: API supports `multipart/form-data` with `capture="camera"` attribute; no special handling required

### Performance & Caching
- **Dashboard**: Cached for 5 seconds per user via Redis; invalidated on status change
- **Application List**: Cached for 30 seconds; invalidated on new application or status change
- **Document Checklist**: Cached for 60 seconds; invalidated on upload/verification

### Observability
- **Metrics**: Prometheus counters for `portal_login_attempts_total`, `portal_documents_uploaded_bytes`, `portal_notifications_delivered_total`
- **Tracing**: OpenTelemetry spans for each dashboard aggregation query
- **Logging**: `structlog` with correlation_id; never log `user_id`, `application_id` in plaintext for client requests

---

**Design Approval Checklist:**
- [ ] All endpoints include Pydantic v2 schemas with validation
- [ ] Decimal types used for all financial values
- [ ] created_at/updated_at on all models
- [ ] No SIN/DOB/income in API responses or logs
- [ ] FINTRAC 5-year retention requirement met
- [ ] OSFI B-20 stress test rate displayed in results
- [ ] Error codes follow PORTAL_XXX format
- [ ] mTLS configured for broker endpoints
- [ ] WebSocket + fallback polling for notifications
- [ ] Alembic migration scripts included
- [ ] Indexes support common query patterns