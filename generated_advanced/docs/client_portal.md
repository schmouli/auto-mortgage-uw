# Client Portal
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Client Portal Module Design Plan

**File:** `docs/design/client-portal.md`  
**Module ID:** CLIENT_PORTAL  
**Complexity:** reasoning  
**Regulatory Scope:** PIPEDA, FINTRAC, OSFI B-20 (indirect), CMHC (indirect)

---

## 1. Endpoints

### Authentication
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `POST` | `/api/v1/auth/login` | Public | `LoginRequest` | `LoginResponse` | `CLIENT_PORTAL_002`, `CLIENT_PORTAL_007` |
| `POST` | `/api/v1/auth/logout` | Authenticated | - | `SuccessResponse` | `CLIENT_PORTAL_001` |
| `POST` | `/api/v1/auth/refresh` | Authenticated | `RefreshTokenRequest` | `LoginResponse` | `CLIENT_PORTAL_002` |

### Dashboard
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `GET` | `/api/v1/dashboard` | Authenticated | - | `DashboardResponse` | `CLIENT_PORTAL_001` |

### Applications
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `GET` | `/api/v1/applications` | Authenticated | - | `List[ApplicationSummary]` | `CLIENT_PORTAL_001` |
| `GET` | `/api/v1/applications/{application_id}` | Authenticated | - | `ApplicationDetail` | `CLIENT_PORTAL_003`, `CLIENT_PORTAL_004` |
| `POST` | `/api/v1/applications` | Authenticated | `CreateApplicationRequest` | `ApplicationDetail` | `CLIENT_PORTAL_007`, `CLIENT_PORTAL_008` |
| `PUT` | `/api/v1/applications/{application_id}` | Authenticated | `UpdateApplicationRequest` | `ApplicationDetail` | `CLIENT_PORTAL_003`, `CLIENT_PORTAL_004`, `CLIENT_PORTAL_007` |

### Documents
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `GET` | `/api/v1/applications/{application_id}/documents` | Authenticated | - | `List[DocumentSummary]` | `CLIENT_PORTAL_003`, `CLIENT_PORTAL_004` |
| `POST` | `/api/v1/applications/{application_id}/documents` | Authenticated | `DocumentUploadRequest` (multipart) | `DocumentDetail` | `CLIENT_PORTAL_003`, `CLIENT_PORTAL_004`, `CLIENT_PORTAL_007`, `CLIENT_PORTAL_009` |
| `GET` | `/api/v1/applications/{application_id}/documents/{document_id}` | Authenticated | - | `FileResponse` | `CLIENT_PORTAL_005`, `CLIENT_PORTAL_004` |
| `DELETE` | `/api/v1/applications/{application_id}/documents/{document_id}` | Authenticated | - | `SuccessResponse` | `CLIENT_PORTAL_005`, `CLIENT_PORTAL_004` |

### Document Checklist
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `GET` | `/api/v1/applications/{application_id}/checklist` | Authenticated | - | `List[ChecklistItem]` | `CLIENT_PORTAL_003`, `CLIENT_PORTAL_004` |
| `PUT` | `/api/v1/applications/{application_id}/checklist/{item_id}` | Authenticated | `ChecklistUpdateRequest` | `ChecklistItem` | `CLIENT_PORTAL_006`, `CLIENT_PORTAL_004`, `CLIENT_PORTAL_007` |

### Underwriting Results (Broker Only)
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `GET` | `/api/v1/applications/{application_id}/results` | Broker | - | `UnderwritingResults` | `CLIENT_PORTAL_003`, `CLIENT_PORTAL_004` |

### FINTRAC Verification (Broker Only)
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `GET` | `/api/v1/applications/{application_id}/fintrac` | Broker | - | `FintracVerificationStatus` | `CLIENT_PORTAL_003`, `CLIENT_PORTAL_004` |
| `POST` | `/api/v1/applications/{application_id}/fintrac/verify` | Broker | `FintracVerifyRequest` | `FintracVerificationStatus` | `CLIENT_PORTAL_003`, `CLIENT_PORTAL_004`, `CLIENT_PORTAL_007`, `CLIENT_PORTAL_010` |

### Lender Comparison (Broker Only)
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `GET` | `/api/v1/applications/{application_id}/lenders` | Broker | - | `List[LenderOffer]` | `CLIENT_PORTAL_003`, `CLIENT_PORTAL_004` |

### Notifications
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `GET` | `/api/v1/notifications` | Authenticated | - | `List[Notification]` | `CLIENT_PORTAL_001` |
| `PUT` | `/api/v1/notifications/{notification_id}/read` | Authenticated | - | `SuccessResponse` | `CLIENT_PORTAL_006`, `CLIENT_PORTAL_004` |
| `PUT` | `/api/v1/notifications/read-all` | Authenticated | - | `SuccessResponse` | `CLIENT_PORTAL_001` |

### Settings
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `GET` | `/api/v1/settings` | Authenticated | - | `UserSettings` | `CLIENT_PORTAL_001` |
| `PUT` | `/api/v1/settings` | Authenticated | `UpdateSettingsRequest` | `UserSettings` | `CLIENT_PORTAL_001`, `CLIENT_PORTAL_007` |

---

## 2. Models & Database

### `users` Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('client', 'broker')), -- PIPEDA: role-based access
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by VARCHAR(100) -- FINTRAC: audit trail
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
```

### `user_profiles` Table
```sql
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    encrypted_sin BYTEA, -- PIPEDA: AES-256 encrypted
    sin_hash VARCHAR(64), -- PIPEDA: SHA256 for lookups only
    encrypted_dob BYTEA, -- PIPEDA: AES-256 encrypted
    dob_hash VARCHAR(64), -- PIPEDA: SHA256 for lookups only
    address VARCHAR(255),
    city VARCHAR(100),
    province VARCHAR(2),
    postal_code VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by VARCHAR(100) -- FINTRAC: audit trail
);

CREATE INDEX idx_user_profiles_sin_hash ON user_profiles(sin_hash);
CREATE INDEX idx_user_profiles_dob_hash ON user_profiles(dob_hash);
```

### `applications` Table
```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    broker_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN (
        'draft', 'submitted', 'in_review', 'conditionally_approved', 'approved', 'rejected', 'closed'
    )),
    requested_mortgage_amount DECIMAL(15,2) NOT NULL, -- CMHC: LTV calculation
    property_value DECIMAL(15,2) NOT NULL, -- CMHC: LTV calculation
    property_address VARCHAR(255) NOT NULL,
    property_type VARCHAR(50) NOT NULL,
    purpose VARCHAR(50) NOT NULL,
    ltv_ratio DECIMAL(5,2) GENERATED ALWAYS AS (
        requested_mortgage_amount / property_value * 100
    ) STORED, -- CMHC: insurance requirement trigger
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by VARCHAR(100) -- FINTRAC: 5-year retention
);

CREATE INDEX idx_applications_user_id ON applications(user_id);
CREATE INDEX idx_applications_broker_id ON applications(broker_id);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_ltv ON applications(ltv_ratio);
```

### `documents` Table
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(100) NOT NULL, -- FINTRAC: transaction type flag for >$10K
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL, -- Store in secure S3-equivalent
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    verification_status VARCHAR(20) DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'rejected')),
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by VARCHAR(100) -- FINTRAC: immutable audit trail
);

CREATE INDEX idx_documents_application_id ON documents(application_id);
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX idx_documents_verification_status ON documents(verification_status);
```

### `document_checklist_items` Table
```sql
CREATE TABLE document_checklist_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(100) NOT NULL,
    required BOOLEAN DEFAULT true,
    provided BOOLEAN DEFAULT false,
    due_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by VARCHAR(100)
);

CREATE INDEX idx_checklist_application_id ON document_checklist_items(application_id);
CREATE INDEX idx_checklist_provided ON document_checklist_items(application_id, provided) WHERE required = true AND provided = false;
```

### `notifications` Table
```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
        'document_uploaded', 'document_verified', 'document_rejected', 'status_changed', 'message_received', 'condition_added'
    )),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by VARCHAR(100) -- FINTRAC: audit trail
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_application_id ON notifications(application_id);
CREATE INDEX idx_notifications_unread ON notifications(user_id, is_read) WHERE is_read = false;
```

### `user_settings` Table
```sql
CREATE TABLE user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_notifications BOOLEAN DEFAULT true,
    sms_notifications BOOLEAN DEFAULT false,
    theme VARCHAR(20) DEFAULT 'light',
    language VARCHAR(2) DEFAULT 'en',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by VARCHAR(100)
);

CREATE INDEX idx_user_settings_user_id ON user_settings(user_id);
```

---

## 3. Business Logic

### Application Status Progression State Machine
```python
# State transitions are immutable and logged for FINTRAC compliance
TRANSITIONS = {
    'draft': ['submitted'],
    'submitted': ['in_review', 'rejected'],
    'in_review': ['conditionally_approved', 'approved', 'rejected'],
    'conditionally_approved': ['approved', 'rejected'],
    'approved': ['closed'],
    'rejected': ['draft'],  # Allow resubmission
    'closed': []  # Terminal state
}

# Trigger conditions:
# - draft → submitted: All required checklist items provided
# - submitted → in_review: Broker initiates review
# - in_review → conditionally_approved: UW module returns conditions
# - conditionally_approved → approved: All conditions met
# - Any → rejected: UW failure or compliance violation
```

### Document Checklist Completion Logic
```python
# Checklist is generated based on application type and LTV ratio (CMHC)
def generate_checklist(application_id: UUID):
    application = get_application(application_id)
    required_docs = BASE_DOCUMENTS[application.purpose]
    
    # CMHC: LTV > 80% requires insurance documents
    if application.ltv_ratio > Decimal('80.00'):
        required_docs.extend(INSURANCE_DOCUMENTS)
    
    # FINTRAC: Transactions > $10K require enhanced verification
    if application.requested_mortgage_amount > Decimal('10000.00'):
        required_docs.extend(FINTRAC_ENHANCED_DOCS)
    
    return [DocumentChecklistItem(...) for doc in required_docs]

def calculate_completion(application_id: UUID) -> Decimal:
    items = get_checklist_items(application_id)
    required = [i for i in items if i.required]
    provided = [i for i in required if i.provided]
    return Decimal(len(provided)) / Decimal(len(required)) * 100
```

### Broker Pipeline Summary Aggregation
```python
# Real-time counts per status with performance optimization
def get_pipeline_summary(broker_id: UUID) -> PipelineSummary:
    return {
        'draft': count_by_status(broker_id, 'draft'),
        'submitted': count_by_status(broker_id, 'submitted'),
        'in_review': count_by_status(broker_id, 'in_review'),
        'conditionally_approved': count_by_status(broker_id, 'conditionally_approved'),
        'approved': count_by_status(broker_id, 'approved'),
        'total_value': sum_by_status(broker_id, ['approved', 'conditionally_approved'])
    }

# Flagged files detection
def get_flagged_applications(broker_id: UUID) -> List[FlaggedApplication]:
    return {
        'missing_documents': applications_with_incomplete_checklist(broker_id),
        'past_due_date': applications_past_due(broker_id),
        'fintrac_pending': applications_pending_fintrac(broker_id)
    }
```

### Notification Generation Rules
```python
# Event-driven notification creation with PIPEDA-safe messages
EVENT_TRIGGERS = {
    'document_uploaded': lambda doc: f"Document {doc.document_type} uploaded",
    'document_verified': lambda doc: f"Document {doc.document_type} verified",
    'document_rejected': lambda doc: f"Document {doc.document_type} requires revision",
    'status_changed': lambda app: f"Application status: {app.status}",
    'message_received': lambda msg: f"New message from {msg.sender}",
    'condition_added': lambda cond: f"New condition: {cond.title}"
}

# Notification routing:
# - Clients: Only their own applications
# - Brokers: All applications assigned to them
```

### FINTRAC Verification Workflow
```python
# Mandatory for all applications (FINTRAC requirement)
def verify_identity(application_id: UUID, broker_id: UUID):
    application = get_application(application_id)
    
    # Verify application belongs to broker
    if application.broker_id != broker_id:
        raise AccessDeniedError()
    
    # Enhanced verification if > $10K
    if application.requested_mortgage_amount > Decimal('10000.00'):
        required_verification = 'enhanced'
    else:
        required_verification = 'standard'
    
    # Log verification attempt (immutable audit trail)
    log_fintrac_verification(
        application_id=application_id,
        broker_id=broker_id,
        verification_type=required_verification,
        sin_hash=application.user.profile.sin_hash  # PIPEDA: use hash only
    )
    
    return verification_status
```

---

## 4. Migrations

### New Tables
```python
# Revision: 001_create_client_portal_tables.py
# Dependencies: base schema

def upgrade():
    # Create all tables defined in Models section
    create_table('users', ...)
    create_table('user_profiles', ...)
    create_table('applications', ...)
    create_table('documents', ...)
    create_table('document_checklist_items', ...)
    create_table('notifications', ...)
    create_table('user_settings', ...)
    
    # Add foreign key constraints
    op.create_foreign_key('fk_applications_users', 'applications', 'users', ['user_id'], ['id'])
    op.create_foreign_key('fk_applications_brokers', 'applications', 'users', ['broker_id'], ['id'])
    # ... additional FKs
    
    # Create indexes for performance
    op.create_index('idx_applications_status_broker', 'applications', ['status', 'broker_id'])
    op.create_index('idx_documents_verification_application', 'documents', ['verification_status', 'application_id'])
    op.create_index('idx_notifications_created_at', 'notifications', ['user_id', 'created_at DESC'])
    
def downgrade():
    # NEVER delete data in production (FINTRAC retention)
    raise NotImplementedError("Downgrades prohibited for compliance")
```

### Data Migration
```python
# Revision: 002_seed_document_types.py
# Populate document checklist templates based on regulatory requirements

def upgrade():
    op.bulk_insert('document_type_templates',
        [
            {'type': 'government_id', 'description': 'Government-issued photo ID', 'required': True},
            {'type': 'proof_of_income', 'description': 'Recent pay stubs or tax returns', 'required': True},
            {'type': 'property_appraisal', 'description': 'Certified property appraisal', 'required': True},
            {'type': 'insurance_certificate', 'description': 'CMHC insurance certificate', 'required': False},  # CMHC: conditional
            {'type': 'fintrac_form', 'description': 'FINTRAC Declaration Form', 'required': True},  # FINTRAC: mandatory
        ]
    )
```

---

## 5. Security & Compliance

### PIPEDA Requirements
- **Encryption at Rest**: `encrypted_sin`, `encrypted_dob` use AES-256-GCM via `common/security.py::encrypt_pii()`
- **Hash Lookups**: `sin_hash`, `dob_hash` are SHA256 hex digests for query operations
- **Data Minimization**: Only collect SIN/DOB when required for UW; store only hashes in application logs
- **No PII in Logs**: All logging calls must pass `sin_hash` not `encrypted_sin`; use `security.get_sin_hash()` helper
- **PII Access Audit**: Every decryption event logged with `correlation_id` and `user_id` for 5-year retention

### FINTRAC Requirements
- **Immutable Audit Trail**: All `created_by` fields populated from JWT `sub` claim; never updated
- **Transaction Flagging**: `documents.document_type` flagged as `fintrac_large_transaction` if application amount > $10,000
- **5-Year Retention**: Soft delete only via `is_active` flag; physical deletion prohibited
- **Identity Verification**: `fintrac_verification_log` table records every verification attempt with timestamp and broker ID
- **Reportable Events**: `document_uploaded` events for large transactions trigger FINTRAC reporting queue

### OSFI B-20 Indirect Compliance
- Client Portal does **not** calculate GDS/TDS but must display stress test rate from UW module
- Displayed rate must be `max(contract_rate + 2%, 5.25%)` as calculated by underwriting service
- Hard limits (GDS ≤ 39%, TDS ≤ 44%) enforced by UW module; portal displays rejection reasons only

### CMHC Insurance Requirement
- `applications.ltv_ratio` calculated as `loan_amount / property_value`
- If LTV > 80%, portal displays insurance premium tier:
  - 80.01-85%: 2.80% of loan amount
  - 85.01-90%: 3.10% of loan amount
  - 90.01-95%: 4.00% of loan amount
- Insurance certificate document automatically added to checklist when LTV > 80%

### Authentication & Authorization
- **OAuth 2.0 + JWT**: Access tokens expire after 15 minutes; refresh tokens after 7 days
- **Role-Based Access Control**:
  - `client`: Can only access own applications (`WHERE user_id = :current_user`)
  - `broker`: Can access assigned applications (`WHERE broker_id = :current_user`)
- **mTLS**: Optional for broker API endpoints handling FINTRAC verification
- **Rate Limiting**: 60 requests/minute per IP for login; 1000 requests/minute per user for authenticated endpoints

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `ClientPortalAuthError` | 401 | `CLIENT_PORTAL_001` | "Authentication required" | Missing JWT token |
| `ClientPortalInvalidCredentialsError` | 401 | `CLIENT_PORTAL_002` | "Invalid email or password" | Login failure |
| `ClientPortalApplicationNotFoundError` | 404 | `CLIENT_PORTAL_003` | "Application {id} not found" | Access non-existent application |
| `ClientPortalAccessDeniedError` | 403 | `CLIENT_PORTAL_004` | "Access denied to resource" | Client accessing broker-only endpoint |
| `ClientPortalDocumentNotFoundError` | 404 | `CLIENT_PORTAL_005` | "Document {id} not found" | Download missing document |
| `ClientPortalChecklistItemNotFoundError` | 404 | `CLIENT_PORTAL_006` | "Checklist item {id} not found" | Update non-existent checklist item |
| `ClientPortalValidationError` | 422 | `CLIENT_PORTAL_007` | "{field}: {reason}" | Invalid email format |
| `ClientPortalBusinessRuleError` | 409 | `CLIENT_PORTAL_008` | "Business rule violated: {detail}" | Submit application with incomplete checklist |
| `ClientPortalFileUploadError` | 413 | `CLIENT_PORTAL_009` | "File too large: {size}" | Upload > 50MB file |
| `ClientPortalFintracVerificationError` | 422 | `CLIENT_PORTAL_010` | "FINTRAC verification failed: {reason}" | Missing enhanced verification docs |

### Structured Error Response Format
```json
{
  "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "CLIENT_PORTAL_003",
  "correlation_id": "corr_01HQX...",
  "timestamp": "2024-01-15T14:30:00Z",
  "path": "/api/v1/applications/123e4567-e89b-12d3-a456-426614174000"
}
```

### Exception Hierarchy
```python
class ClientPortalError(AppException):
    """Base exception for client portal module"""
    module_code = "CLIENT_PORTAL"

class ClientPortalAuthError(ClientPortalError):
    http_status = 401
    error_code = "CLIENT_PORTAL_001"

# ... all other exceptions inherit from ClientPortalError
```

---

## 7. Performance & Scalability Considerations

### Database Optimization
- Use `SELECT ... FOR UPDATE SKIP LOCKED` for notification processing to avoid contention
- Partition `documents` table by `application_id` hash for large brokers
- Materialized view `broker_pipeline_summary` refreshed every 5 minutes
- Query `notifications` with `LIMIT 50` + cursor pagination; never full table scan

### Caching Strategy
- Cache `DashboardResponse` for 30 seconds per user (Redis TTL)
- Cache `ApplicationDetail` only if status is 'approved' or 'closed' (immutable states)
- Never cache PII fields; decrypt on-demand only

### Real-Time Notifications
- **WebSocket** for brokers (`/ws/notifications`) to receive instant updates on document uploads
- **Polling** for clients (`GET /notifications?since={timestamp}`) to reduce connection overhead
- Event bus (Kafka) publishes `notification.created` events from document, application, and UW modules

---

## 8. Observability & Audit

### Logging
```python
# structlog JSON format with correlation_id
logger.info(
    "application_status_changed",
    application_id=str(application_id),
    old_status=old_status,
    new_status=new_status,
    user_id=str(current_user.id),  # PIPEDA: log user_id not PII
    correlation_id=correlation_id.get()
)

# NEVER log: sin, dob, income, banking data
```

### Metrics
- `client_portal_login_attempts_total` (counter with `status=success|failure`)
- `client_portal_application_submitted_total` (counter)
- `client_portal_document_upload_size_bytes` (histogram)
- `client_portal_notification_delivery_latency_seconds` (histogram)

### Tracing
- OpenTelemetry spans for every database query and external API call
- Trace propagation through Kafka events for async notification processing

---

**WARNING**: This design assumes the existence of `common/security.py` with `encrypt_pii()`, `decrypt_pii()`, and `get_sin_hash()` functions compliant with PIPEDA AES-256 requirements. If these are not available, they must be implemented before module development begins.