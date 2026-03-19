# Client Portal
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Client Portal Module Design Plan

**Module ID:** `client_portal`  
**Feature Slug:** `client-portal`  
**Document Path:** `docs/design/client-portal.md`

---

## 1. Endpoints

### Authentication
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| `POST` | `/api/v1/auth/login` | Public | `LoginRequest` | `TokenResponse` | `401 INVALID_CREDENTIALS`, `422 VALIDATION_ERROR` |
| `POST` | `/api/v1/auth/logout` | Authenticated | - | `204 No Content` | `401 UNAUTHORIZED` |
| `POST` | `/api/v1/auth/refresh` | Authenticated | `RefreshTokenRequest` | `TokenResponse` | `401 TOKEN_EXPIRED` |

### Dashboard
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| `GET` | `/api/v1/dashboard` | Authenticated | - | `DashboardResponse` (role-based) | `401 UNAUTHORIZED`, `403 FORBIDDEN` |

### Applications
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| `GET` | `/api/v1/applications` | Authenticated | - | `List[ApplicationSummaryResponse]` | `401 UNAUTHORIZED` |
| `GET` | `/api/v1/applications/{id}` | Authenticated | - | `ApplicationDetailResponse` | `401 UNAUTHORIZED`, `404 APPLICATION_NOT_FOUND` |
| `POST` | `/api/v1/applications` | Broker only | `CreateApplicationRequest` | `ApplicationDetailResponse` | `401 UNAUTHORIZED`, `403 FORBIDDEN`, `422 VALIDATION_ERROR` |
| `PUT` | `/api/v1/applications/{id}` | Broker only | `UpdateApplicationRequest` | `ApplicationDetailResponse` | `401 UNAUTHORIZED`, `403 FORBIDDEN`, `404 APPLICATION_NOT_FOUND`, `409 STATUS_LOCKED` |

### Documents
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| `GET` | `/api/v1/applications/{id}/documents` | Authenticated | - | `List[DocumentResponse]` | `401 UNAUTHORIZED`, `404 APPLICATION_NOT_FOUND` |
| `POST` | `/api/v1/applications/{id}/documents` | Authenticated | `DocumentUploadRequest` (multipart/form-data) | `DocumentResponse` | `401 UNAUTHORIZED`, `404 APPLICATION_NOT_FOUND`, `413 PAYLOAD_TOO_LARGE`, `422 UNSUPPORTED_FILE_TYPE` |
| `GET` | `/api/v1/applications/{id}/checklist` | Authenticated | - | `DocumentChecklistResponse` | `401 UNAUTHORIZED`, `404 APPLICATION_NOT_FOUND` |
| `PUT` | `/api/v1/applications/{id}/checklist/{item_id}` | Broker only | `ChecklistItemUpdateRequest` | `ChecklistItemResponse` | `401 UNAUTHORIZED`, `403 FORBIDDEN`, `404 NOT_FOUND` |

### Underwriting Results (Broker Only)
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| `GET` | `/api/v1/applications/{id}/results` | Broker only | - | `UnderwritingResultsResponse` | `401 UNAUTHORIZED`, `403 FORBIDDEN`, `404 APPLICATION_NOT_FOUND`, `412 RESULTS_NOT_READY` |

### FINTRAC Verification (Broker Only)
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| `GET` | `/api/v1/applications/{id}/fintrac` | Broker only | - | `FintracVerificationResponse` | `401 UNAUTHORIZED`, `403 FORBIDDEN`, `404 APPLICATION_NOT_FOUND` |
| `POST` | `/api/v1/applications/{id}/fintrac/verify` | Broker only | `FintracVerifyRequest` | `FintracVerificationResponse` | `401 UNAUTHORIZED`, `403 FORBIDDEN`, `404 APPLICATION_NOT_FOUND`, `422 VALIDATION_ERROR` |

### Lender Comparison (Broker Only)
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| `GET` | `/api/v1/applications/{id}/lenders` | Broker only | - | `List[LenderComparisonResponse]` | `401 UNAUTHORIZED`, `403 FORBIDDEN`, `404 APPLICATION_NOT_FOUND` |

### Notifications
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| `GET` | `/api/v1/notifications` | Authenticated | Query: `?unread_only=true&limit=50` | `List[NotificationResponse]` | `401 UNAUTHORIZED` |
| `PUT` | `/api/v1/notifications/{id}/read` | Authenticated | - | `NotificationResponse` | `401 UNAUTHORIZED`, `404 NOTIFICATION_NOT_FOUND` |
| `PUT` | `/api/v1/notifications/read-all` | Authenticated | - | `{count: int}` | `401 UNAUTHORIZED` |

### Settings
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| `GET` | `/api/v1/settings` | Authenticated | - | `UserSettingsResponse` | `401 UNAUTHORIZED` |
| `PUT` | `/api/v1/settings` | Authenticated | `UserSettingsUpdateRequest` | `UserSettingsResponse` | `401 UNAUTHORIZED`, `422 VALIDATION_ERROR` |

---

## 2. Models & Database

### `portal_notification` Table
```sql
CREATE TABLE portal_notification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
    notification_type VARCHAR(50) NOT NULL, -- enum: document_uploaded, document_verified, document_rejected, status_changed, message_received, condition_added
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    metadata JSONB, -- {document_id, status_from, status_to, etc.}
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id), -- for audit trail (FINTRAC)
    INDEX idx_notification_user_created (user_id, created_at DESC),
    INDEX idx_notification_unread (user_id, is_read) WHERE is_read = FALSE
);
```

### `portal_activity_log` Table
```sql
CREATE TABLE portal_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES users(id), -- who performed the action
    actor_role VARCHAR(20) NOT NULL, -- client, broker, admin
    activity_type VARCHAR(50) NOT NULL, -- enum: document_uploaded, status_changed, message_sent, fintrac_verified
    description TEXT NOT NULL,
    ip_address INET, -- FINTRAC audit requirement
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    INDEX idx_activity_application (application_id, created_at DESC),
    INDEX idx_activity_actor (actor_id, created_at DESC)
);
```

### `portal_user_settings` Table
```sql
CREATE TABLE portal_user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    email_notifications BOOLEAN DEFAULT TRUE,
    sms_notifications BOOLEAN DEFAULT FALSE,
    push_notifications BOOLEAN DEFAULT TRUE,
    notification_frequency VARCHAR(20) DEFAULT 'immediate', -- immediate, daily_digest
    theme_preference VARCHAR(20) DEFAULT 'light', -- light, dark, auto
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `document_checklist_item` Table
```sql
CREATE TABLE document_checklist_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(100) NOT NULL, -- enum: pay_stub, t4, bank_statement, id_verification, etc.
    is_required BOOLEAN DEFAULT TRUE,
    is_provided BOOLEAN DEFAULT FALSE,
    document_id UUID REFERENCES documents(id), -- when uploaded
    due_date DATE,
    verification_status VARCHAR(20) DEFAULT 'pending', -- pending, verified, rejected
    rejection_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    INDEX idx_checklist_application (application_id),
    INDEX idx_checklist_overdue (application_id, due_date) WHERE is_provided = FALSE AND due_date < CURRENT_DATE
);
```

---

## 3. Business Logic

### Application Status State Machine
```python
# Status transitions with validation rules
ALLOWED_TRANSITIONS = {
    'draft': ['submitted'],
    'submitted': ['in_review', 'conditionally_approved', 'rejected'],
    'in_review': ['conditionally_approved', 'approved', 'rejected'],
    'conditionally_approved': ['approved', 'in_review'],  # can revert if conditions not met
    'approved': ['closed', 'funded'],
    'rejected': [],  # terminal state
    'closed': [],  # terminal state
    'funded': ['closed']  # post-funding status
}

# Status change triggers notification and audit log
async def update_application_status(
    application_id: UUID, 
    new_status: str, 
    actor_id: UUID,
    trigger: Optional[str] = None
) -> Application:
    # 1. Validate transition
    # 2. Update application
    # 3. Create audit log entry (FINTRAC compliance)
    # 4. Generate notifications for client/broker
    # 5. Log structured event with correlation_id
```

### Dashboard Aggregation Logic
```python
# Client Dashboard
async def get_client_dashboard(user_id: UUID) -> ClientDashboard:
    # 1. Fetch user's active applications (max 5)
    # 2. For each application:
    #    - Calculate progress % from checklist completion
    #    - Get latest unread notification
    #    - Extract key numbers (loan_amount, property_value, status)
    # 3. Return aggregated view
    # PIPEDA: Never include SIN/DOB in response

# Broker Dashboard
async def get_broker_dashboard(broker_id: UUID) -> BrokerDashboard:
    # 1. Pipeline summary: COUNT(*) GROUP BY status
    # 2. Flagged files: 
    #    - Missing docs: checklist items where is_provided=FALSE AND is_required=TRUE
    #    - Past due: due_date < TODAY AND is_provided=FALSE
    # 3. Recent activity: Last 20 activities from portal_activity_log
    # 4. Quick actions: Pre-filled templates for document requests
```

### Document Upload Workflow
```python
# File validation
ALLOWED_MIME_TYPES = {
    'application/pdf': '.pdf',
    'image/jpeg': '.jpg',
    'image/png': '.png'
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

async def upload_document(
    application_id: UUID,
    file: UploadFile,
    document_type: str,
    uploader_id: UUID
) -> Document:
    # 1. Validate file type and size
    # 2. Scan for malware (integrate with ClamAV or similar)
    # 3. Encrypt file at rest (AES-256) - PIPEDA compliance
    # 4. Store in secure blob storage (S3 with SSE-KMS)
    # 5. Update checklist item status
    # 6. Create audit log entry
    # 7. Trigger notifications (document_uploaded event)
    # 8. FINTRAC: Log transaction if file relates to $10K+ transaction
```

### Notification Generation Rules
```python
NOTIFICATION_TEMPLATES = {
    'document_uploaded': {
        'title': 'Document Received',
        'message': '{document_type} has been uploaded for application {app_id}',
        'recipients': ['broker']
    },
    'status_changed': {
        'title': 'Status Update',
        'message': 'Your application moved to {new_status}',
        'recipients': ['client']
    },
    # ... other types
}

async def create_notification(
    event_type: str,
    application_id: UUID,
    metadata: dict
) -> None:
    # 1. Determine recipients based on event type
    # 2. Insert notification records
    # 3. Send real-time push if enabled (WebSocket/FCM)
    # 4. Log creation without PII
```

---

## 4. Migrations

### New Tables
```python
# Alembic migration: create_portal_tables.py

def upgrade():
    # portal_notification table
    op.create_table('portal_notification',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('application_id', UUID(), nullable=True),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), default=False),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_by', UUID(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_notification_user_created', 'portal_notification', ['user_id', 'created_at'])
    op.create_index('idx_notification_unread', 'portal_notification', ['user_id', 'is_read'], 
                    postgresql_where=sa.text('is_read = false'))

    # portal_activity_log table
    op.create_table('portal_activity_log',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('application_id', UUID(), nullable=False),
        sa.Column('actor_id', UUID(), nullable=False),
        sa.Column('actor_role', sa.String(20), nullable=False),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('ip_address', INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_activity_application', 'portal_activity_log', ['application_id', 'created_at'])
    op.create_index('idx_activity_actor', 'portal_activity_log', ['actor_id', 'created_at'])

    # portal_user_settings table
    op.create_table('portal_user_settings',
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('email_notifications', sa.Boolean(), default=True),
        sa.Column('sms_notifications', sa.Boolean(), default=False),
        sa.Column('push_notifications', sa.Boolean(), default=True),
        sa.Column('notification_frequency', sa.String(20), default='immediate'),
        sa.Column('theme_preference', sa.String(20), default='light'),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )

    # document_checklist_item table
    op.create_table('document_checklist_item',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('application_id', UUID(), nullable=False),
        sa.Column('document_type', sa.String(100), nullable=False),
        sa.Column('is_required', sa.Boolean(), default=True),
        sa.Column('is_provided', sa.Boolean(), default=False),
        sa.Column('document_id', UUID(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('verification_status', sa.String(20), default='pending'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_checklist_application', 'document_checklist_item', ['application_id'])
    op.create_index('idx_checklist_overdue', 'document_checklist_item', ['application_id', 'due_date'],
                    postgresql_where=sa.text('is_provided = false AND due_date < CURRENT_DATE'))

def downgrade():
    op.drop_table('document_checklist_item')
    op.drop_table('portal_user_settings')
    op.drop_table('portal_activity_log')
    op.drop_table('portal_notification')
```

### Data Migration
- Seed `portal_user_settings` for existing users: `INSERT INTO portal_user_settings (user_id) SELECT id FROM users;`
- Populate initial checklist items based on application LTV and product type (CMHC rules)

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Stress Test Display**: Underwriting results endpoint must include both contract_rate and qualifying_rate (max(contract_rate + 2%, 5.25%)) in response
- **Ratio Limits**: GDS/TDS values returned must be calculated with stress test applied; values > 39%/44% must trigger `status: 'rejected'` automatically
- **Audit Trail**: All ratio calculations logged in `portal_activity_log` with `activity_type: 'underwriting_calculated'` and full breakdown in metadata

### FINTRAC Compliance
- **Immutable Audit**: `portal_activity_log` table enforces append-only pattern; no UPDATE/DELETE operations permitted via Row Level Security (RLS)
- **Identity Verification**: FINTRAC verification endpoint logs `actor_id`, `ip_address`, `user_agent`, and verification result; records retained for 5 years
- **Transaction Threshold**: Document upload service checks if `loan_amount >= 10000`; if true, sets `metadata.transaction_flag = 'LARGE_CASH'` and triggers additional logging
- **5-Year Retention**: All portal_notification and portal_activity_log records archived monthly to cold storage; never physically deleted

### PIPEDA Data Handling
- **Encryption at Rest**: All uploaded documents encrypted with AES-256-GCM before S3 storage; encryption keys managed via AWS KMS with key rotation
- **PII Masking**: Application responses never include `sin`, `dob`, or `banking_details`; these fields return `null` or are omitted
- **Hashed Lookups**: SIN lookups use SHA256 hash; store `sin_hash` in separate indexed column
- **Data Minimization**: Document checklist only requests docs required for specific application type (purchase/refinance/renewal)

### Authentication & Authorization
- **OAuth 2.0**: JWT tokens with 15min expiry; refresh tokens rotated on each use
- **Role-Based Access**: 
  - `@require_role('client')` for client-only endpoints
  - `@require_role('broker')` for broker-only endpoints
  - `@require_role('client', 'broker')` for shared endpoints
- **mTLS**: Internal service-to-service calls (e.g., to underwriting engine) use mutual TLS
- **CORS**: Strict origin whitelist; `Access-Control-Allow-Origin` set to configured client portal domain only

---

## 6. Error Codes & HTTP Responses

### Portal-Specific Exceptions
```python
# modules/client_portal/exceptions.py

class PortalException(AppException):
    """Base exception for client portal module"""
    pass

class ApplicationNotFoundError(PortalException):
    """Application ID does not exist or user lacks access"""
    pass

class DocumentValidationError(PortalException):
    """File type, size, or content validation failed"""
    pass

class StatusTransitionError(PortalException):
    """Invalid status transition requested"""
    pass

class NotificationNotFoundError(PortalException):
    """Notification ID does not belong to user"""
    pass

class FintracVerificationError(PortalException):
    """Identity verification failed or data incomplete"""
    pass

class UnauthorizedAccessError(PortalException):
    """User role lacks permission for resource"""
    pass
```

### Error Mapping Table
| Exception Class | HTTP Status | Error Code | Message Pattern | When Triggered |
|-----------------|-------------|------------|-----------------|----------------|
| `ApplicationNotFoundError` | 404 | `PORTAL_001` | "Application {id} not found" | Application ID not in user's accessible set |
| `DocumentValidationError` | 422 | `PORTAL_002` | "Document invalid: {reason}" | MIME type not in whitelist, size > 10MB, or malware detected |
| `StatusTransitionError` | 409 | `PORTAL_003` | "Invalid transition: {from} → {to}" | Status change violates ALLOWED_TRANSITIONS |
| `NotificationNotFoundError` | 404 | `PORTAL_004` | "Notification {id} not found" | User attempts to mark non-existent/unowned notification as read |
| `FintracVerificationError` | 422 | `PORTAL_005` | "FINTRAC verification failed: {detail}" | Identity check fails or missing required fields |
| `UnauthorizedAccessError` | 403 | `PORTAL_006` | "Access denied: {resource}" | Client attempts to access broker-only endpoint |
| `ValidationError` | 422 | `PORTAL_007` | "{field}: {error}" | Pydantic validation failure on request body |

### Global Error Handler
```python
# In routes.py or common/exceptions.py
@app.exception_handler(PortalException)
async def portal_exception_handler(request: Request, exc: PortalException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": str(exc),
            "error_code": exc.error_code,
            "correlation_id": structlog.contextvars.get_contextvars().get("correlation_id")
        }
    )
```

---

## Additional Considerations

### Real-Time Notifications
- **Implementation**: WebSocket endpoint `/api/v1/ws/notifications` with JWT authentication
- **Fallback**: Long polling for clients behind restrictive proxies
- **Message Format**: JSON with `{event: string, data: object, timestamp: ISO8601}`
- **PIPEDA**: No PII in WebSocket messages; use UUID references only

### Performance Optimization
- **Dashboard Queries**: Materialized view `dashboard_stats_mv` refreshed every 5 minutes
- **Notification Counts**: Cached in Redis with 30s TTL per user
- **Document List**: Paginated with cursor-based pagination; max 50 items per page
- **Indexes**: All FK columns indexed; composite indexes on common query patterns

### Monitoring & Observability
- **Metrics**: Counter for file uploads, notification deliveries, status transitions
- **Tracing**: OpenTelemetry spans for each document upload workflow
- **Logging**: structlog with `correlation_id`, `user_id`, `application_id`; never log file contents or PII

### Scalability Notes
- **File Storage**: S3 with CloudFront CDN for downloads; signed URLs with 5min expiry
- **Async Processing**: Document virus scanning and encryption offloaded to Celery workers
- **Rate Limiting**: 10 login attempts per 15min per IP; 100 API calls per minute per user

---

**WARNING**: This design assumes existence of `users`, `applications`, and `documents` tables in other modules. If these do not exist, additional migrations will be required.