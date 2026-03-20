# Client Portal
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Client Portal Module Design Plan

**Module Location:** `mortgage_underwriting/modules/portal/`  
**Feature Slug:** `client-portal`  
**Design Document:** `docs/design/client-portal.md`

---

## 1. Endpoints

### Authentication & Authorization
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `POST` | `/api/v1/auth/login` | Public | `LoginRequest` | `TokenResponse` | `AUTH_001` (invalid credentials), `AUTH_002` (account locked) |
| `POST` | `/api/v1/auth/logout` | Authenticated | `LogoutRequest` | `SuccessResponse` | `AUTH_003` (invalid token) |
| `POST` | `/api/v1/auth/refresh` | Authenticated | `RefreshTokenRequest` | `TokenResponse` | `AUTH_004` (expired refresh token) |

### Dashboard
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/dashboard/client` | Client | - | `ClientDashboardResponse` | `PORTAL_001` (access denied) |
| `GET` | `/api/v1/dashboard/broker` | Broker | - | `BrokerDashboardResponse` | `PORTAL_001` (access denied) |

### Applications
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/applications` | Client/Broker | `ApplicationListQuery` | `ApplicationListResponse` | `PORTAL_002` (invalid filter) |
| `POST` | `/api/v1/applications` | Broker | `CreateApplicationRequest` | `ApplicationDetailResponse` | `PORTAL_003` (validation failed) |
| `GET` | `/api/v1/applications/{application_id}` | Client/Broker | - | `ApplicationDetailResponse` | `PORTAL_004` (application not found), `PORTAL_005` (access forbidden) |

### Documents
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/applications/{id}/documents` | Client/Broker | - | `DocumentListResponse` | `PORTAL_004`, `PORTAL_005` |
| `POST` | `/api/v1/applications/{id}/documents` | Client/Broker | `DocumentUploadRequest` (multipart) | `DocumentUploadResponse` | `PORTAL_006` (file type not allowed), `PORTAL_007` (file size exceeded) |
| `GET` | `/api/v1/applications/{id}/checklist` | Client/Broker | - | `DocumentChecklistResponse` | `PORTAL_004`, `PORTAL_005` |

### Underwriting Results (Broker Only)
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/applications/{id}/results` | Broker | - | `UnderwritingResultsResponse` | `PORTAL_004`, `PORTAL_005`, `PORTAL_008` (results not ready) |
| `GET` | `/api/v1/applications/{id}/lenders` | Broker | - | `LenderComparisonResponse` | `PORTAL_004`, `PORTAL_005` |

### FINTRAC Verification (Broker Only)
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/applications/{id}/fintrac` | Broker | - | `FintracStatusResponse` | `PORTAL_004`, `PORTAL_005` |
| `POST` | `/api/v1/applications/{id}/fintrac/verify` | Broker | `FintracVerificationRequest` | `FintracVerificationResponse` | `PORTAL_009` (verification failed) |

### Notifications
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/notifications` | Client/Broker | `NotificationQuery` | `NotificationListResponse` | `PORTAL_010` (invalid pagination) |
| `PUT` | `/api/v1/notifications/{id}/read` | Client/Broker | - | `SuccessResponse` | `PORTAL_011` (notification not found) |
| `PUT` | `/api/v1/notifications/read-all` | Client/Broker | `ReadAllNotificationsRequest` | `SuccessResponse` | - |

### Settings
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/settings/profile` | Client/Broker | - | `UserProfileResponse` | `PORTAL_012` (profile not found) |
| `PUT` | `/api/v1/settings/profile` | Client/Broker | `UpdateProfileRequest` | `UserProfileResponse` | `PORTAL_013` (validation failed) |

---

## 2. Models & Database

### User Model (`portal/models.py`)
```python
class User(Base):
    __tablename__ = "portal_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    role = Column(Enum("client", "broker", name="user_role"), nullable=False)
    
    # PIPEDA compliance: SIN encrypted at rest, hash for lookups
    sin_encrypted = Column(LargeBinary, nullable=True)  # AES-256 encrypted
    sin_hash = Column(String(64), unique=True, nullable=True, index=True)  # SHA256 hash
    
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Audit fields (FINTRAC 5-year retention)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)  # For audit trail
    
    # Relationships
    applications = relationship("Application", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    activity_logs = relationship("ActivityLog", back_populates="user")
    
    # Indexes
    __table_args__ = (
        Index('idx_user_role_active', 'role', 'is_active'),
        Index('idx_user_sin_hash', 'sin_hash', postgresql_where=sin_hash.isnot(None)),
    )
```

### Application Model (`portal/models.py`)
```python
class Application(Base):
    __tablename__ = "portal_applications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("portal_users.id"), nullable=False)
    broker_id = Column(UUID(as_uuid=True), ForeignKey("portal_users.id"), nullable=True)
    
    # Status workflow (OSFI B-20 audit requirement)
    status = Column(
        Enum(
            "draft", "submitted", "in_review", "conditionally_approved", 
            "approved", "rejected", "closed", name="application_status"
        ),
        nullable=False,
        index=True
    )
    
    # Financial data (Decimal for all monetary values)
    requested_mortgage_amount = Column(Numeric(12, 2), nullable=False)
    purchase_price = Column(Numeric(12, 2), nullable=False)
    property_value = Column(Numeric(12, 2), nullable=False)
    
    # OSFI B-20 stress test results
    contract_rate = Column(Numeric(5, 4), nullable=False)
    qualifying_rate = Column(Numeric(5, 4), nullable=False)  # max(contract_rate + 2%, 5.25%)
    gds_ratio = Column(Numeric(5, 2), nullable=True)  # PITH / gross_income
    tds_ratio = Column(Numeric(5, 2), nullable=True)  # (PITH + other debt) / gross_income
    
    # CMHC insurance
    insurance_required = Column(Boolean, default=False)
    insurance_premium = Column(Numeric(12, 2), default=Decimal("0.00"))
    ltv_ratio = Column(Numeric(5, 2), nullable=False)  # loan_amount / property_value
    
    # FINTRAC compliance
    fintrac_verified = Column(Boolean, default=False)
    fintrac_verified_at = Column(DateTime(timezone=True), nullable=True)
    fintrac_transaction_flag = Column(Boolean, default=False)  # > CAD $10,000
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="applications")
    broker = relationship("User", foreign_keys=[broker_id])
    documents = relationship("Document", back_populates="application")
    checklist_items = relationship("DocumentChecklistItem", back_populates="application")
    notifications = relationship("Notification", back_populates="application")
    activity_logs = relationship("ActivityLog", back_populates="application")
    
    # Indexes
    __table_args__ = (
        Index('idx_application_user_status', 'user_id', 'status'),
        Index('idx_application_broker_status', 'broker_id', 'status'),
        Index('idx_application_created', 'created_at'),
        CheckConstraint('gds_ratio <= 39.0', name='chk_gds_limit'),  # OSFI B-20
        CheckConstraint('tds_ratio <= 44.0', name='chk_tds_limit'),  # OSFI B-20
    )
```

### Document Model (`portal/models.py`)
```python
class Document(Base):
    __tablename__ = "portal_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("portal_applications.id"), nullable=False)
    
    # Document metadata
    document_type = Column(Enum("id_proof", "income_proof", "employment_letter", "bank_statement", "property_appraisal", name="doc_type"), nullable=False)
    filename = Column(String(255), nullable=False)
    s3_key = Column(String(500), nullable=False, unique=True)  # PII never in logs
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    
    # Verification workflow
    status = Column(Enum("pending", "verified", "rejected", name="doc_status"), nullable=False, default="pending")
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("portal_users.id"), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("portal_users.id"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())
    
    # Relationships
    application = relationship("Application", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    
    # Indexes
    __table_args__ = (
        Index('idx_document_app_type', 'application_id', 'document_type'),
        Index('idx_document_status', 'status'),
    )
```

### DocumentChecklistItem Model (`portal/models.py`)
```python
class DocumentChecklistItem(Base):
    __tablename__ = "portal_checklist_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("portal_applications.id"), nullable=False)
    item_type = Column(Enum("id_proof", "income_proof", "employment_letter", "bank_statement", "property_appraisal", name="checklist_item_type"), nullable=False)
    
    # Required by lender or regulation
    required = Column(Boolean, default=True)
    status = Column(Enum("not_provided", "provided", "verified", "rejected", name="checklist_status"), nullable=False, default="not_provided")
    due_date = Column(DateTime(timezone=True), nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())
    
    # Relationships
    application = relationship("Application", back_populates="checklist_items")
    
    # Indexes
    __table_args__ = (
        Index('idx_checklist_app_status', 'application_id', 'status'),
        Index('idx_checklist_due_date', 'due_date'),
    )
```

### Notification Model (`portal/models.py`)
```python
class Notification(Base):
    __tablename__ = "portal_notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("portal_users.id"), nullable=False)
    application_id = Column(UUID(as_uuid=True), ForeignKey("portal_applications.id"), nullable=True)
    
    # Event types for audit trail
    event_type = Column(
        Enum(
            "document_uploaded", "document_verified", "document_rejected", 
            "status_changed", "message_received", "condition_added",
            name="notification_event_type"
        ),
        nullable=False,
        index=True
    )
    
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)  # No PII in message content
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # FINTRAC 5-year retention
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    application = relationship("Application", back_populates="notifications")
    
    # Indexes
    __table_args__ = (
        Index('idx_notification_user_unread', 'user_id', 'is_read'),
    )
```

### ActivityLog Model (`portal/models.py`)
```python
class ActivityLog(Base):
    __tablename__ = "portal_activity_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("portal_applications.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("portal_users.id"), nullable=False)
    
    action_type = Column(
        Enum(
            "application_created", "status_changed", "document_uploaded", 
            "document_verified", "message_sent", "fintrac_verified",
            name="activity_type"
        ),
        nullable=False
    )
    
    description = Column(Text, nullable=False)  # No PII
    metadata_json = Column(JSON, nullable=True)  # Structured data for audit
    
    # Immutable audit trail (FINTRAC requirement)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    application = relationship("Application", back_populates="activity_logs")
    user = relationship("User", back_populates="activity_logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_activity_app_created', 'application_id', 'created_at'),
        Index('idx_activity_user_created', 'user_id', 'created_at'),
    )
```

---

## 3. Business Logic

### Status Workflow State Machine
```python
# modules/portal/services/application_workflow.py

class ApplicationStatusWorkflow:
    """
    OSFI B-20 compliant status transitions with audit logging.
    All transitions generate ActivityLog entries and notifications.
    """
    
    VALID_TRANSITIONS = {
        "draft": ["submitted"],
        "submitted": ["in_review", "rejected"],
        "in_review": ["conditionally_approved", "rejected"],
        "conditionally_approved": ["approved", "in_review"],
        "approved": ["closed"],
        "rejected": ["draft"],  # Allow re-submission
        "closed": []  # Terminal state
    }
    
    @staticmethod
    async def transition_application(
        application_id: UUID,
        new_status: str,
        user_id: UUID,
        session: AsyncSession,
        reason: Optional[str] = None
    ) -> Application:
        """
        Transition application status with validation and audit trail.
        Generates notifications for both client and broker.
        """
        # 1. Fetch application with lock
        # 2. Validate transition against VALID_TRANSITIONS
        # 3. Update status and timestamps
        # 4. Create ActivityLog entry
        # 5. Create Notification records for relevant users
        # 6. Trigger FINTRAC verification if status == "submitted" and amount > 10000
        # 7. Log calculation breakdown for GDS/TDS if entering "in_review"
```

### Document Upload & Verification Logic
```python
# modules/portal/services/document_service.py

class DocumentService:
    """
    Handles document upload, storage, and verification with PIPEDA compliance.
    """
    
    ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @staticmethod
    async def upload_document(
        application_id: UUID,
        file: UploadFile,
        document_type: str,
        user_id: UUID,
        session: AsyncSession
    ) -> Document:
        """
        1. Validate file type and size
        2. Scan for malware (integration point)
        3. Generate unique S3 key: {application_id}/{uuid}_{filename}
        4. Encrypt file in transit (HTTPS) and at rest (S3 encryption)
        5. Store metadata in DB (never log S3 key or filename)
        6. Update checklist item status to "provided"
        7. Create ActivityLog and Notification
        8. Return presigned URL for frontend confirmation
        """
    
    @staticmethod
    async def verify_document(
        document_id: UUID,
        verified_by: UUID,
        status: str,
        rejection_reason: Optional[str],
        session: AsyncSession
    ) -> Document:
        """
        1. Update document status
        2. Update checklist item status
        3. Generate notification to uploader
        4. If all required documents verified, trigger underwriting workflow
        """
```

### Dashboard Aggregation Queries
```python
# modules/portal/services/dashboard_service.py

class DashboardService:
    """
    Optimized queries for dashboard widgets with security boundaries.
    """
    
    @staticmethod
    async def get_client_dashboard(client_id: UUID, session: AsyncSession) -> dict:
        """
        Returns:
        - active_application: Latest application with status progress
        - outstanding_documents: Count of checklist items not verified
        - recent_notification: Most recent unread notification
        - key_numbers: requested_mortgage, purchase_price, status
        """
        # Single optimized query with joins and subqueries
    
    @staticmethod
    async def get_broker_dashboard(broker_id: UUID, session: AsyncSession) -> dict:
        """
        Returns:
        - pipeline_summary: SELECT status, COUNT(*) GROUP BY status
        - flagged_files: Applications with overdue checklist items or missing docs
        - recent_activity: Last 20 activity logs for broker's applications
        - quick_actions: Count of applications awaiting review
        """
        # Uses composite indexes for performance
```

### Notification Generation Triggers
```python
# modules/portal/services/notification_service.py

class NotificationService:
    """
    Generates notifications for all portal events.
    """
    
    EVENT_TEMPLATES = {
        "document_uploaded": {
            "title": "Document Received",
            "message": "A new {doc_type} has been uploaded for application {app_id}"
        },
        "status_changed": {
            "title": "Status Update",
            "message": "Your application status changed to {new_status}"
        },
        # ... other templates
    }
    
    @staticmethod
    async def create_notification(
        event_type: str,
        user_id: UUID,
        application_id: Optional[UUID],
        metadata: dict,
        session: AsyncSession
    ) -> Notification:
        """
        1. Render message from template (no PII in message)
        2. Insert notification record
        3. Trigger real-time delivery (WebSocket/push notification)
        """
```

---

## 4. Migrations

### New Tables
```sql
-- Create portal_users table
CREATE TABLE portal_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(128) NOT NULL,
    role user_role NOT NULL,
    sin_encrypted BYTEA,
    sin_hash VARCHAR(64) UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID
);

-- Create portal_applications table
CREATE TABLE portal_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES portal_users(id),
    broker_id UUID REFERENCES portal_users(id),
    status application_status NOT NULL,
    requested_mortgage_amount NUMERIC(12, 2) NOT NULL,
    purchase_price NUMERIC(12, 2) NOT NULL,
    property_value NUMERIC(12, 2) NOT NULL,
    contract_rate NUMERIC(5, 4) NOT NULL,
    qualifying_rate NUMERIC(5, 4) NOT NULL,
    gds_ratio NUMERIC(5, 2) CHECK (gds_ratio <= 39.0),
    tds_ratio NUMERIC(5, 2) CHECK (tds_ratio <= 44.0),
    insurance_required BOOLEAN DEFAULT FALSE,
    insurance_premium NUMERIC(12, 2) DEFAULT 0.00,
    ltv_ratio NUMERIC(5, 2) NOT NULL,
    fintrac_verified BOOLEAN DEFAULT FALSE,
    fintrac_verified_at TIMESTAMPTZ,
    fintrac_transaction_flag BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ
);

-- Create portal_documents table
CREATE TABLE portal_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES portal_applications(id),
    document_type doc_type NOT NULL,
    filename VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500) UNIQUE NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    status doc_status NOT NULL DEFAULT 'pending',
    uploaded_by UUID NOT NULL REFERENCES portal_users(id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at TIMESTAMPTZ,
    verified_by UUID REFERENCES portal_users(id),
    rejection_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create portal_checklist_items table
CREATE TABLE portal_checklist_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES portal_applications(id),
    item_type checklist_item_type NOT NULL,
    required BOOLEAN DEFAULT TRUE,
    status checklist_status NOT NULL DEFAULT 'not_provided',
    due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create portal_notifications table
CREATE TABLE portal_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES portal_users(id),
    application_id UUID REFERENCES portal_applications(id),
    event_type notification_event_type NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create portal_activity_logs table
CREATE TABLE portal_activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES portal_applications(id),
    user_id UUID NOT NULL REFERENCES portal_users(id),
    action_type activity_type NOT NULL,
    description TEXT NOT NULL,
    metadata_json JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Indexes
```sql
-- Composite indexes for dashboard queries
CREATE INDEX idx_user_role_active ON portal_users(role, is_active);
CREATE INDEX idx_application_user_status ON portal_applications(user_id, status);
CREATE INDEX idx_application_broker_status ON portal_applications(broker_id, status);
CREATE INDEX idx_checklist_app_status ON portal_checklist_items(application_id, status);
CREATE INDEX idx_notification_user_unread ON portal_notifications(user_id, is_read) WHERE is_read = FALSE;
CREATE INDEX idx_activity_app_created ON portal_activity_logs(application_id, created_at DESC);
```

### Data Migration
```python
# migrations/versions/xxx_seed_default_document_types.py
"""
Seed default document checklist templates for new applications.
Required for CMHC and lender compliance.
"""
def upgrade():
    op.execute("""
        INSERT INTO portal_document_templates (item_type, required, description)
        VALUES 
            ('id_proof', TRUE, 'Government-issued photo ID'),
            ('income_proof', TRUE, 'Recent pay stubs or tax returns'),
            ('employment_letter', TRUE, 'Letter of employment'),
            ('bank_statement', TRUE, '90-day bank statements'),
            ('property_appraisal', FALSE, 'Property appraisal report')
        ON CONFLICT DO NOTHING;
    """)
```

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Stress Test Display**: `/applications/{id}/results` endpoint must return `qualifying_rate`, `gds_ratio`, and `tds_ratio` with calculation breakdown in `ActivityLog.metadata_json`
- **Hard Limits**: Database constraints enforce GDS ≤ 39% and TDS ≤ 44%. API returns `PORTAL_014` error if limits exceeded
- **Audit Trail**: Every ratio calculation logged with inputs (income, debts, property tax, heating costs) in immutable `ActivityLog`

### FINTRAC Requirements
- **Identity Verification**: `POST /fintrac/verify` creates `ActivityLog` with `action_type='fintrac_verified'` and immutable metadata
- **Transaction Flagging**: `Application.fintrac_transaction_flag` automatically set TRUE if `requested_mortgage_amount > 10000`
- **5-Year Retention**: All portal tables have `created_at` timestamp; soft-deletes only via `is_active=FALSE`. No hard deletes implemented
- **Immutable Records**: `ActivityLog` and `Document` tables have no UPDATE/DELETE operations after creation

### CMHC Requirements
- **Insurance Calculation**: `insurance_required` and `insurance_premium` calculated when LTV > 80% using tier lookup:
  - 80.01-85%: 2.80% of loan amount
  - 85.01-90%: 3.10% of loan amount  
  - 90.01-95%: 4.00% of loan amount
- **LTV Precision**: `ltv_ratio` calculated as `loan_amount / property_value` using Decimal division, stored with 2 decimal places

### PIPEDA Requirements
- **SIN Encryption**: `User.sin_encrypted` uses AES-256-GCM via `common/security.encrypt_pii()`. Hash stored separately for lookups
- **Data Minimization**: API responses filter out PII fields. `UserProfileResponse` excludes `sin_encrypted` and `sin_hash`
- **No PII in Logs**: `structlog` configuration masks `sin`, `dob`, `income`, `banking` fields. `Document.s3_key` never logged
- **Secure File Handling**: Documents stored in S3 with KMS encryption. Presigned URLs expire after 5 minutes. No direct file content in API responses

### Authentication & Authorization
- **JWT Tokens**: Access token TTL 15min, refresh token TTL 7 days. Token contains `user_id` and `role`
- **Role-Based Access**: 
  - Client: Can only access own applications (enforced by `user_id` filter in all queries)
  - Broker: Can access applications where `broker_id` matches, plus pipeline summary
- **mTLS**: Internal service-to-service calls use mutual TLS. Public endpoints terminate TLS at load balancer

---

## 6. Error Codes & HTTP Responses

### Portal Module Exception Hierarchy
```python
# modules/portal/exceptions.py

class PortalException(AppException):
    """Base exception for portal module"""
    pass

class PortalNotFoundError(PortalException):
    http_status = 404
    error_code = "PORTAL_001"
    message_template = "{resource_type} not found: {resource_id}"

class PortalValidationError(PortalException):
    http_status = 422
    error_code = "PORTAL_002"
    message_template = "{field}: {reason}"

class PortalBusinessRuleError(PortalException):
    http_status = 409
    error_code = "PORTAL_003"
    message_template = "Business rule violated: {rule_name}"

class PortalAccessDeniedError(PortalException):
    http_status = 403
    error_code = "PORTAL_004"
    message_template = "Access denied to {resource_type} {resource_id}"

class PortalFileError(PortalException):
    http_status = 413
    error_code = "PORTAL_005"
    message_template = "File error: {reason}"

class PortalFintracError(PortalException):
    http_status = 422
    error_code = "PORTAL_006"
    message_template = "FINTRAC verification failed: {detail}"

class PortalStatusTransitionError(PortalException):
    http_status = 409
    error_code = "PORTAL_007"
    message_template = "Invalid status transition from {from_status} to {to_status}"
```

### Error Response Mapping
| Exception Class | HTTP Status | Error Code | When Triggered |
|-----------------|-------------|------------|----------------|
| `PortalNotFoundError` | 404 | PORTAL_001 | Application, document, or notification ID not found |
| `PortalValidationError` | 422 | PORTAL_002 | Pydantic validation failure or business logic validation |
| `PortalBusinessRuleError` | 409 | PORTAL_003 | Duplicate email, file already uploaded, etc. |
| `PortalAccessDeniedError` | 403 | PORTAL_004 | User attempts to access another user's application |
| `PortalFileError` | 413 | PORTAL_005 | File size > 10MB or invalid MIME type |
| `PortalFintracError` | 422 | PORTAL_006 | Identity verification failed or missing data |
| `PortalStatusTransitionError` | 409 | PORTAL_007 | Invalid workflow state transition |
| `PortalGdsTdsLimitError` | 422 | PORTAL_008 | GDS/TDS exceeds OSFI B-20 limits (39%/44%) |
| `PortalResultsNotReadyError` | 404 | PORTAL_009 | Underwriting results requested before completion |

### Structured Error Response Format
```json
{
  "detail": "Application not found: 123e4567-e89b-12d3-a456-426614174000",
  "error_code": "PORTAL_001",
  "correlation_id": "req_8f9d3a2b1c4e5f6a",
  "timestamp": "2024-01-15T14:30:00Z",
  "path": "/api/v1/applications/123e4567-e89b-12d3-a456-426614174000",
  "method": "GET"
}
```

---

## 7. Additional Considerations

### Real-Time Notifications
- **Recommendation**: Implement WebSocket endpoint at `/api/v1/ws/notifications` using `fastapi.websockets`
- **Fallback**: Long polling with ETag-based caching for mobile clients
- **Delivery**: Use Redis Pub/Sub to broadcast notifications to connected clients

### File Upload Strategy
- **Direct-to-S3**: Frontend gets presigned POST URL from `GET /api/v1/upload/signature` to bypass backend for large files
- **Virus Scanning**: S3 event triggers Lambda to scan before marking document as "available"
- **Chunked Upload**: Support resumable uploads for files > 5MB

### Mobile Responsiveness
- API returns `mobile_optimized: bool` flag for document types that support camera capture
- `/api/v1/applications/{id}/documents/upload-url` returns multipart upload URL with content-type restrictions

### Performance Optimization
- Dashboard endpoints use `SELECT ... FOR UPDATE SKIP LOCKED` for pipeline counts to avoid contention
- Notification list cached per user for 30 seconds with `Cache-Control: private, max-age=30`
- Document list paginated with cursor-based pagination (not OFFSET) for large applications

---

**Next Steps**: Implementation should proceed with:
1. Create module directory structure
2. Implement models and migrations
3. Build authentication layer
4. Develop core endpoints (applications, documents)
5. Add dashboard aggregation queries
6. Implement notification system
7. Add WebSocket support
8. Security audit and penetration testing